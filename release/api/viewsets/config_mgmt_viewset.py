"""
MDL 配置管理 ViewSet
集成自 demo 工程，适配 release-src 的 Django 3.2 + MySQL 环境。

提供以下 API 端点（均通过 router 注册到 /api/config-mgmt/）：
  GET  /api/config-mgmt/tree/           - 配置树（ServiceType→Instance→ConfigFile）
  GET  /api/config-mgmt/configs/        - 配置文件列表
  GET  /api/config-mgmt/configs/{id}/   - 配置文件详情
  PUT  /api/config-mgmt/configs/{id}/   - 更新配置内容
  POST /api/config-mgmt/configs/batch_update/ - 批量修改同一 key
  GET  /api/config-mgmt/configs/schema/ - 多实例合并 schema
  POST /api/config-mgmt/configs/git_commit/   - 提交到 GitLab
  POST /api/config-mgmt/configs/push_consul/  - 推送 Consul KV
  POST /api/config-mgmt/sync/           - 从 GitLab 同步配置树
  GET  /api/config-mgmt/deploy/         - 查询部署任务
  POST /api/config-mgmt/deploy/         - 创建并执行部署任务
"""

import json
import re
import io
import os
import tarfile
import base64
import threading
from datetime import datetime
from urllib.parse import quote

import requests as http_requests

from rest_framework import viewsets, serializers, status
from rest_framework.decorators import action
from rest_framework.response import Response

from django.conf import settings
from django.db import models

from mdl.models import ServiceType, ConfigInstance, ConfigFile, ConfigDeployTask, ConfigAuditLog, MdlServer
from common.utils.apiutil import ApiResponse


# ===================================================================
# 审计日志辅助函数
# ===================================================================

def _audit(request, action, status='success', instance_names=None, filename='',
           summary='', detail=None, deploy_task=None):
    """写入审计日志，失败不影响主流程"""
    try:
        operator = str(request.user) if request.user and request.user.is_authenticated else 'anonymous'
        ConfigAuditLog.objects.create(
            action=action,
            operator=operator,
            status=status,
            instance_names=', '.join(instance_names) if instance_names else '',
            filename=filename or '',
            summary=summary or '',
            detail=json.dumps(detail, ensure_ascii=False) if detail is not None else '',
            deploy_task=deploy_task,
        )
    except Exception:
        pass


# ===================================================================
# 辅助函数（从 demo/backend/apps/configs/views.py 迁移）
# ===================================================================

def _parse_path_segments(key_path):
    """解析路径为段列表，支持 'a.b[0].c' 格式"""
    segments = []
    for part in key_path.split('.'):
        match = re.match(r'^([^\[]*)((?:\[\d+\])*)$', part)
        if match:
            key_name, indices = match.group(1), match.group(2)
            if key_name:
                segments.append(key_name)
            if indices:
                for idx in re.findall(r'\[(\d+)\]', indices):
                    segments.append(int(idx))
        else:
            segments.append(part)
    return segments


def set_nested_value(data, key_path, value):
    """设置嵌套结构的值"""
    segments = _parse_path_segments(key_path)
    d = data
    for seg in segments[:-1]:
        if isinstance(seg, int):
            d = d[seg]
        else:
            if seg not in d or not isinstance(d[seg], (dict, list)):
                d[seg] = {}
            d = d[seg]
    last = segments[-1]
    d[last] = value


def _delete_nested_value(data, key_path):
    """删除嵌套结构中的某个 key"""
    segments = _parse_path_segments(key_path)
    d = data
    try:
        for seg in segments[:-1]:
            if isinstance(seg, int):
                d = d[seg]
            else:
                d = d[seg]
        last = segments[-1]
        if isinstance(d, dict) and last in d:
            del d[last]
        elif isinstance(d, list) and isinstance(last, int) and 0 <= last < len(d):
            d.pop(last)
    except (KeyError, IndexError, TypeError):
        pass


def _get_nested_value(data, key_path):
    """根据路径获取嵌套值"""
    segments = _parse_path_segments(key_path)
    d = data
    try:
        for seg in segments:
            if isinstance(seg, int):
                d = d[seg]
            else:
                d = d[seg]
        return d
    except (KeyError, IndexError, TypeError):
        return '_MISSING_'


def _collect_all_keys(obj, prefix=''):
    """递归收集 JSON 中所有叶子路径"""
    keys = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            path = f'{prefix}.{k}' if prefix else k
            keys |= _collect_all_keys(v, path)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            path = f'{prefix}[{i}]'
            keys |= _collect_all_keys(v, path)
    else:
        keys.add(prefix)
    return keys


def _merge_schemas(configs_list):
    """合并多个实例的配置内容，构建结构 + 各实例值对比"""
    all_keys = set()
    for cfg in configs_list:
        content = cfg.get('content') or {}
        all_keys |= _collect_all_keys(content)

    merged = {}
    for key_path in sorted(all_keys):
        values = {}
        for cfg in configs_list:
            content = cfg.get('content') or {}
            val = _get_nested_value(content, key_path)
            if val != '_MISSING_':
                values[cfg['instance_name']] = val
        merged[key_path] = values
    return merged


def _parse_instance_name(inst_name):
    """从实例目录名解析 host_ip 和 port"""
    host_ip = ''
    port = None
    inst_parts = inst_name.rsplit('_', 1)
    if len(inst_parts) == 2:
        right = inst_parts[1]
        try:
            port = int(right)
            host_ip = inst_parts[0].replace('_', '.')
        except ValueError:
            host_ip = right
    else:
        host_ip = inst_name
    return host_ip, port


def _parse_json_safe(raw_str):
    """安全解析 JSON 字符串"""
    try:
        return json.loads(raw_str)
    except (json.JSONDecodeError, ValueError):
        return {'_raw': raw_str}


def _deep_merge_schema(target, source):
    """深度合并两个 JSON 结构（保留 target 的结构，补全 source 的字段）"""
    if isinstance(target, dict) and isinstance(source, dict):
        for k, v in source.items():
            if k not in target:
                target[k] = v
            else:
                _deep_merge_schema(target[k], v)
    elif isinstance(target, list) and isinstance(source, list):
        # List merge: 取最大长度，对应索引 deep merge
        for i in range(min(len(target), len(source))):
            _deep_merge_schema(target[i], source[i])
        if len(source) > len(target):
            target.extend(source[len(target):])
    return target


def _get_commit_content(config):
    """获取提交用的文件内容"""
    raw = config.raw_content
    if raw:
        try:
            raw_normalized = json.dumps(json.loads(raw), sort_keys=True, ensure_ascii=False)
            cur_normalized = json.dumps(config.content, sort_keys=True, ensure_ascii=False)
            if raw_normalized == cur_normalized:
                return raw
        except (json.JSONDecodeError, ValueError, TypeError):
            pass
    return json.dumps(config.content, ensure_ascii=False)


# ===================================================================
# GitLab 同步（使用 Archive API 下载 tar.gz）
# ===================================================================

def _get_gitlab_settings():
    """获取 GitLab 配置（从 settings 读取）"""
    return {
        'url': getattr(settings, 'CONFIG_GITLAB_URL', getattr(settings, 'GITLAB_URL', '')),
        'token': getattr(settings, 'CONFIG_GITLAB_TOKEN', getattr(settings, 'GITLAB_TOKEN', '')),
        'project_id': getattr(settings, 'CONFIG_GITLAB_PROJECT_ID', getattr(settings, 'GITLAB_PROJECT_ID', '')),
        'branch': getattr(settings, 'CONFIG_GITLAB_BRANCH', getattr(settings, 'GITLAB_BRANCH', 'master')),
        'root_path': getattr(settings, 'CONFIG_GITLAB_ROOT_PATH', ''),
    }


def _sync_from_gitlab():
    """从 GitLab 下载 archive 并同步到数据库"""
    cfg = _get_gitlab_settings()
    if not cfg['token'] or not cfg['project_id']:
        raise ValueError('GitLab 未配置 (TOKEN 或 PROJECT_ID 缺失)')

    gitlab_url = cfg['url'].rstrip('/')
    headers = {'PRIVATE-TOKEN': cfg['token']}
    root_path = cfg['root_path']
    results = {'service_types': 0, 'instances': 0, 'configs': 0}

    url = f"{gitlab_url}/api/v4/projects/{cfg['project_id']}/repository/archive.tar.gz"
    params = {'sha': cfg['branch']}
    if root_path:
        params['path'] = root_path

    resp = http_requests.get(url, headers=headers, params=params, timeout=120, stream=True)
    resp.raise_for_status()

    tar_bytes = io.BytesIO(resp.content)
    with tarfile.open(fileobj=tar_bytes, mode='r:gz') as tar:
        for member in tar.getmembers():
            if not member.isfile():
                continue
            parts_full = member.name.split('/', 1)
            if len(parts_full) < 2:
                continue
            rel_path = parts_full[1]
            parts = rel_path.split('/')
            if len(parts) != 3:
                continue

            st_name, inst_name, cfg_filename = parts

            service_type, created = ServiceType.objects.get_or_create(name=st_name)
            if created:
                results['service_types'] += 1

            host_ip, port = _parse_instance_name(inst_name)
            consul_url = getattr(settings, 'CONFIG_CONSUL_URL', '').rstrip('/')
            kv_prefix = getattr(settings, 'CONFIG_CONSUL_KV_PREFIX', 'configs/mdl')
            default_consul_space = '{}/v1/kv/{}/{}/{}/'.format(
                consul_url, kv_prefix, st_name, inst_name)

            # 从 MdlServer 表匹配同 IP 的记录，复用已有部署信息
            mdl_server = MdlServer.objects.filter(ip=host_ip).first() if host_ip else None
            defaults = {
                'host_ip': host_ip,
                'port': port,
                'consul_space': mdl_server.consul_space if mdl_server and mdl_server.consul_space else default_consul_space,
                'consul_token': mdl_server.consul_token if mdl_server else None,
                'install_dir': mdl_server.install_dir if mdl_server else '',
                'backups_dir': mdl_server.backups_dir if mdl_server else '',
                'service_name': mdl_server.service_name if mdl_server else '',
                'consul_files': mdl_server.consul_files if mdl_server else 'feeder_handler.cfg',
                'remote_python': mdl_server.remote_python if mdl_server else '/usr/bin/python3',
            }
            instance, created = ConfigInstance.objects.update_or_create(
                service_type=service_type,
                name=inst_name,
                defaults=defaults,
            )
            if created:
                results['instances'] += 1

            f = tar.extractfile(member)
            if f is None:
                continue
            raw = f.read().decode('utf-8', errors='replace')
            content = _parse_json_safe(raw)

            ConfigFile.objects.update_or_create(
                instance=instance,
                filename=cfg_filename,
                defaults={'content': content, 'raw_content': raw, 'git_path': rel_path}
            )
            results['configs'] += 1

    return results


def _commit_to_gitlab(configs, message):
    """提交配置到 GitLab（使用 Commits API 批量提交）"""
    cfg = _get_gitlab_settings()
    if not cfg['token'] or not cfg['project_id']:
        raise ValueError('GitLab 未配置')

    gitlab_url = cfg['url'].rstrip('/')
    headers = {'PRIVATE-TOKEN': cfg['token'], 'Content-Type': 'application/json'}
    branch = cfg['branch']

    actions = []
    results = []

    for config in configs:
        file_path = f'{config.instance.service_type.name}/{config.instance.name}/{config.filename}'
        content_str = _get_commit_content(config)

        encoded_path = quote(file_path, safe='')
        check_url = f"{gitlab_url}/api/v4/projects/{cfg['project_id']}/repository/files/{encoded_path}"
        check_resp = http_requests.head(check_url, headers={'PRIVATE-TOKEN': cfg['token']},
                                        params={'ref': branch}, timeout=10)
        action = 'update' if check_resp.status_code == 200 else 'create'

        actions.append({'action': action, 'file_path': file_path, 'content': content_str})
        results.append({'file': file_path, 'status': 'pending'})

    if not actions:
        return results

    url = f"{gitlab_url}/api/v4/projects/{cfg['project_id']}/repository/commits"
    payload = {'branch': branch, 'commit_message': message, 'actions': actions}
    resp = http_requests.post(url, headers=headers, json=payload, timeout=60)

    if resp.status_code in (200, 201):
        for r in results:
            r['status'] = 'ok'
    else:
        for r in results:
            r['status'] = 'error'
            r['detail'] = resp.text

    return results


# ===================================================================
# Consul KV 推送
# ===================================================================

def _push_config_to_consul(config):
    """推送单个配置到 Consul KV"""
    consul_url = getattr(settings, 'CONFIG_CONSUL_URL', getattr(settings, 'CONSUL_URL', ''))
    consul_token = getattr(settings, 'CONFIG_CONSUL_TOKEN', getattr(settings, 'CONSUL_TOKEN', ''))
    kv_prefix = getattr(settings, 'CONFIG_CONSUL_KV_PREFIX', getattr(settings, 'CONSUL_KV_PREFIX', 'configs/mdl'))

    # 优先使用实例自己配置的 consul_space，否则构造默认路径
    if config.instance.consul_space:
        consul_path = config.instance.consul_space
        # consul_space 可能是完整路径如 /v1/kv/configs/mdl/forward/xxx，取 kv/ 后的部分
        if '/kv/' in consul_path:
            key_path = consul_path.split('/kv/')[1].rstrip('/') + '/' + config.filename
        else:
            key_path = consul_path.lstrip('/').rstrip('/') + '/' + config.filename
    else:
        key_path = f'{kv_prefix}/{config.instance.service_type.name}/{config.instance.name}/{config.filename}'

    content = json.dumps(config.content, indent=2, ensure_ascii=False)
    url = f'{consul_url}/v1/kv/{key_path}'
    headers = {}
    if consul_token:
        headers['X-Consul-Token'] = consul_token

    resp = http_requests.put(url, data=content.encode('utf-8'), headers=headers, timeout=10)
    return key_path, resp.status_code == 200


# ===================================================================
# Ansible 部署（适配 release-src 的 ansi/mdl/ playbook 目录）
# ===================================================================

def _get_ansible_dir():
    """获取 Ansible playbook 目录（适配 release-src 目录结构）"""
    return getattr(settings, 'CONFIG_ANSIBLE_DIR',
                   os.path.join(settings.BASE_DIR, 'ansi', 'mdl'))


def _deploy_single_instance(instance, ansible_dir):
    """部署单个实例，返回 (logs, success)，使用独立临时目录避免并发冲突"""
    import yaml
    import subprocess
    import platform
    import tempfile
    import shutil
    from mdl.models import ConfigFile

    logs = []
    success = True

    service_name = instance.service_name or f'mdl-{instance.service_type.name}'
    install_dir = instance.install_dir or getattr(settings, 'DEPLOY_DEFAULT_INSTALL_DIR', '/datayes/app/bin')
    backups_dir = instance.backups_dir or getattr(settings, 'DEPLOY_DEFAULT_BACKUPS_DIR', '/datayes/app/backups')
    ssh_user = getattr(settings, 'ANSIBLE_SSH_USER', 'root')
    ssh_pass = getattr(settings, 'ANSIBLE_SSH_PASS', '')

    logs.append(f'[{datetime.now():%H:%M:%S}] === 部署 {instance.service_type.name}/{instance.name} ===')

    configs = ConfigFile.objects.filter(instance=instance)
    if not configs.exists():
        logs.append(f'  [SKIP] 无配置文件')
        return logs, True

    # Step 1: 推送 Consul
    logs.append(f'  [STEP 1] 推送 Consul...')
    for config in configs:
        try:
            key_path, ok = _push_config_to_consul(config)
            logs.append(f'    {"OK" if ok else "FAIL"}: {key_path}')
            if not ok:
                success = False
        except Exception as e:
            logs.append(f'    ERROR: {config.filename} - {e}')
            success = False

    # Step 2: Ansible
    if not instance.host_ip:
        logs.append(f'  [SKIP] Ansible: 无主机 IP')
        return logs, success

    logs.append(f'  [STEP 2] Ansible → {instance.host_ip}...')

    # 每个实例使用独立临时目录，避免并发时互相覆盖
    tmp_dir = tempfile.mkdtemp(prefix=f'ansible_{instance.id}_')
    try:
        # 复制 playbook 和 roles 到临时目录
        for item in os.listdir(ansible_dir):
            src = os.path.join(ansible_dir, item)
            dst = os.path.join(tmp_dir, item)
            if os.path.isdir(src):
                shutil.copytree(src, dst)
            else:
                shutil.copy2(src, dst)

        # 生成 hosts 文件
        hosts_path = os.path.join(tmp_dir, 'hosts')
        with open(hosts_path, 'w') as fp:
            fp.write(f'release ansible_ssh_host={instance.host_ip} '
                     f'ansible_ssh_user={ssh_user} ansible_ssh_pass={ssh_pass}\n')

        # 生成 host_vars/release.yml
        host_vars_dir = os.path.join(tmp_dir, 'host_vars')
        os.makedirs(host_vars_dir, exist_ok=True)
        host_vars = {
            'user': ssh_user,
            'remote_python': instance.remote_python or '/usr/bin/python3',
            'consul_space': instance.consul_space or '{}/v1/kv/{}/{}/{}/'.format(
                getattr(settings, 'CONFIG_CONSUL_URL', '').rstrip('/'),
                getattr(settings, 'CONFIG_CONSUL_KV_PREFIX', 'configs/mdl'),
                instance.service_type.name,
                instance.name,
            ),
            'consul_token': getattr(settings, 'CONFIG_CONSUL_TOKEN',
                                    getattr(settings, 'CONSUL_TOKEN', '')),
            'install_dir': install_dir,
            'backups_dir': backups_dir,
            'service_name': service_name,
            'consul_files': instance.consul_files or 'feeder_handler.cfg',
        }
        with open(os.path.join(host_vars_dir, 'release.yml'), 'w') as fp:
            yaml.dump(host_vars, fp, default_flow_style=False)

        playbook_path = os.path.join(tmp_dir, 'deploy_config.yml')
        is_windows = platform.system() == 'Windows'
        force_mock = os.environ.get('ANSIBLE_FORCE_MOCK', 'False').lower() == 'true'

        if is_windows or force_mock:
            logs.append(f'  [MOCK] Windows/Mock环境跳过Ansible执行')
            result_rc, result_stdout = 0, 'Mock execution success'
        else:
            env = os.environ.copy()
            env['ANSIBLE_HOST_KEY_CHECKING'] = 'False'
            try:
                proc = subprocess.run(
                    ['ansible-playbook', playbook_path, '-i', hosts_path, '-vv'],
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, env=env,
                )
                result_rc, result_stdout = proc.returncode, proc.stdout
            except FileNotFoundError:
                logs.append(f'  [ERROR] ansible-playbook 命令未找到')
                return logs, False

        if result_rc == 0:
            logs.append(f'  Ansible OK')
        else:
            logs.append(f'  Ansible FAIL (rc={result_rc})')
            for line in (result_stdout or '').strip().split('\n')[-20:]:
                logs.append(f'    > {line}')
            success = False
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    return logs, success


def _run_deploy_task(deploy_task_id):
    """后台线程执行部署，并发部署所有实例"""
    import concurrent.futures
    from mdl.models import ConfigDeployTask

    deploy_task = ConfigDeployTask.objects.get(id=deploy_task_id)
    deploy_task.status = 'running'
    deploy_task.save(update_fields=['status'])

    ansible_dir = _get_ansible_dir()
    instances = list(deploy_task.instances.select_related('service_type').all())

    all_logs = []
    all_success = True

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(instances), 10)) as executor:
            futures = {
                executor.submit(_deploy_single_instance, inst, ansible_dir): inst
                for inst in instances
            }
            for future in concurrent.futures.as_completed(futures):
                try:
                    inst_logs, inst_success = future.result()
                    all_logs.extend(inst_logs)
                    if not inst_success:
                        all_success = False
                except Exception as e:
                    import traceback
                    inst = futures[future]
                    all_logs.append(f'[ERROR] {inst.name}: {e}')
                    all_logs.append(traceback.format_exc())
                    all_success = False
    except Exception as e:
        import traceback
        all_logs.append(f'异常: {e}')
        all_logs.append(traceback.format_exc())
        all_success = False

    deploy_task.status = 'success' if all_success else 'failed'
    deploy_task.log = '\n'.join(all_logs)
    deploy_task.finished_at = datetime.now()
    deploy_task.save()

    # 写审计日志（部署结束后，operator 来自任务记录）
    try:
        inst_names = [inst.name for inst in instances]
        ConfigAuditLog.objects.create(
            action='deploy',
            operator=deploy_task.operator,
            status='success' if all_success else 'failed',
            instance_names=', '.join(inst_names),
            summary=f'Ansible 部署 {len(instances)} 个实例，{"全部成功" if all_success else "部分/全部失败"}',
            detail=json.dumps({'instance_names': inst_names}, ensure_ascii=False),
            deploy_task=deploy_task,
        )
    except Exception:
        pass


# ===================================================================
# Serializers
# ===================================================================

class ServiceTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceType
        fields = ['id', 'name', 'description']


class ConfigInstanceSerializer(serializers.ModelSerializer):
    service_type_name = serializers.CharField(source='service_type.name', read_only=True)

    class Meta:
        model = ConfigInstance
        fields = ['id', 'name', 'service_type', 'service_type_name',
                  'host_ip', 'port', 'service_name', 'consul_space',
                  'consul_files', 'remote_python', 'install_dir', 'backups_dir']


class ConfigFileSerializer(serializers.ModelSerializer):
    instance_name = serializers.CharField(source='instance.name', read_only=True)
    service_type_name = serializers.CharField(source='instance.service_type.name', read_only=True)

    class Meta:
        model = ConfigFile
        fields = ['id', 'instance', 'instance_name', 'service_type_name',
                  'filename', 'content', 'raw_content', 'git_path',
                  'created_time', 'last_updated_time']


class ConfigDeployTaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConfigDeployTask
        fields = ['id', 'status', 'operator', 'log', 'created_time', 'finished_at']


# ===================================================================
# ViewSets
# ===================================================================

class ConfigTreeViewSet(viewsets.ViewSet):
    """配置树：返回 ServiceType→Instance→ConfigFile 的层次结构"""

    def list(self, request):
        search = request.query_params.get('search', '').strip()

        service_types = ServiceType.objects.all().order_by('name')
        tree = []

        for st in service_types:
            instances_qs = st.configinstance_set.all().order_by('name')
            if search:
                instances_qs = instances_qs.filter(name__icontains=search)

            instances = []
            for inst in instances_qs:
                files = inst.configfile_set.all().order_by('filename')
                instances.append({
                    'id': f'inst_{inst.id}',
                    'type': 'instance',
                    'label': inst.name,
                    'data': {
                        'id': inst.id,
                        'host_ip': inst.host_ip,
                        'service_name': inst.service_name,
                    },
                    'children': [
                        {
                            'id': f'cfg_{cfg.id}',
                            'type': 'config',
                            'label': cfg.filename,
                            'data': {'id': cfg.id, 'config_id': cfg.id},
                            'children': [],
                        }
                        for cfg in files
                    ],
                })

            tree.append({
                'id': f'st_{st.id}',
                'type': 'service_type',
                'label': st.name,
                'data': {'id': st.id},
                'children': instances,
            })

        return ApiResponse(data=tree)


class ConfigFileViewSet(viewsets.ModelViewSet):
    """配置文件 CRUD + 批量操作 + Git + Consul"""

    queryset = ConfigFile.objects.select_related('instance', 'instance__service_type').all()
    serializer_class = ConfigFileSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        instance_id = self.request.query_params.get('instance_id')
        if instance_id:
            qs = qs.filter(instance_id=instance_id)
        return qs

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        content = request.data.get('content')
        if content is not None:
            instance.content = content
            instance.save(update_fields=['content'])
        _audit(request, 'save',
               instance_names=[instance.instance.name],
               filename=instance.filename,
               summary=f'保存配置文件 {instance.instance.service_type.name}/{instance.instance.name}/{instance.filename}')
        return ApiResponse(data=ConfigFileSerializer(instance).data)

    @action(detail=False, methods=['get'], url_path='schema')
    def schema(self, request):
        """获取选中实例的配置结构（含各实例值对比）"""
        instance_ids = (request.query_params.getlist('instance_ids[]') or
                        request.query_params.getlist('instance_ids'))
        if not instance_ids:
            return ApiResponse(data={'filenames': [], 'schema': {}, 'values_map': {}})

        configs = ConfigFile.objects.select_related('instance').filter(instance_id__in=instance_ids)
        filenames = list(configs.values_list('filename', flat=True).distinct())

        filename = request.query_params.get('filename')
        schema_data = {}
        values_map = {}

        if filename:
            file_configs = configs.filter(filename=filename)
            configs_list = [
                {'instance_name': c.instance.name, 'content': c.content}
                for c in file_configs
            ]
            if configs_list:
                values_map = _merge_schemas(configs_list)
                # 构建完整的 schema 结构（包含所有实例出现的 key）
                schema_data = {}
                for cfg in configs_list:
                    # 使用 deep copy 避免污染
                    content = json.loads(json.dumps(cfg.get('content') or {}))
                    _deep_merge_schema(schema_data, content)

        return ApiResponse(data={'filenames': filenames, 'schema': schema_data, 'values_map': values_map})

    @action(detail=False, methods=['post'], url_path='batch_update')
    def batch_update(self, request):
        """批量更新同一 key 到多个实例的同一配置文件"""
        instance_ids = request.data.get('instance_ids', [])
        filename = request.data.get('filename', '')
        updates = request.data.get('updates', {})

        if not instance_ids or not filename:
            return Response({'code': 400, 'message': '缺少 instance_ids 或 filename', 'data': None},
                            status=status.HTTP_400_BAD_REQUEST)

        updated = []
        for instance_id in instance_ids:
            try:
                config = ConfigFile.objects.get(instance_id=instance_id, filename=filename)
                content = json.loads(json.dumps(config.content)) if config.content else {}
                for key_path, value in updates.items():
                    if value == '__DELETE__':
                        _delete_nested_value(content, key_path)
                    else:
                        set_nested_value(content, key_path, value)
                config.content = content
                config.save()
                updated.append({'id': config.id, 'instance_id': instance_id})
            except ConfigFile.DoesNotExist:
                continue

        updated_names = [
            ConfigInstance.objects.get(id=u['instance_id']).name
            for u in updated
        ] if updated else []
        _audit(request, 'batch_update',
               instance_names=updated_names,
               filename=filename,
               summary=f'批量修改 {len(updates)} 项，影响 {len(updated)} 个实例',
               detail={'updates': {k: ('__DELETE__' if v == '__DELETE__' else v)
                                   for k, v in updates.items()}})
        return ApiResponse(data={'updated_count': len(updated), 'updated': updated})

    @action(detail=False, methods=['post'], url_path='git_commit')
    def git_commit(self, request):
        """提交选中配置到 GitLab"""
        config_ids = request.data.get('config_ids', [])
        message = request.data.get('message', 'Update config files')

        if not config_ids:
            return Response({'code': 400, 'message': '未指定配置文件', 'data': None},
                            status=status.HTTP_400_BAD_REQUEST)

        configs = ConfigFile.objects.select_related('instance', 'instance__service_type').filter(
            id__in=config_ids)

        try:
            results = _commit_to_gitlab(configs, message)
        except Exception as e:
            import traceback
            return Response({'code': 500, 'message': str(e), 'data': {'traceback': traceback.format_exc()}},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        success_count = sum(1 for r in results if r['status'] == 'ok')
        audit_status = 'success' if success_count == len(results) else ('failed' if success_count == 0 else 'partial')
        _audit(request, 'git_commit',
               instance_names=[c.instance.name for c in configs],
               summary=f'提交到 GitLab: {message}，{success_count}/{len(results)} 成功',
               detail={'message': message, 'results': results},
               status=audit_status)
        return ApiResponse(data={
            'message': f'已提交 {success_count}/{len(results)} 个文件到 GitLab',
            'results': results,
        })

    @action(detail=False, methods=['post'], url_path='text_replace')
    def text_replace(self, request):
        """文本查找替换：在选中实例的配置文件 JSON 文本中做字符串替换

        请求体:
          instance_ids: [...]
          filename: 'feeder_handler.cfg'
          search_text: '要查找的字符串'
          replace_text: '替换为的字符串'
          preview: true/false  (true 时只返回预览，不保存)
        """
        instance_ids = request.data.get('instance_ids', [])
        filename = request.data.get('filename', '')
        search_text = request.data.get('search_text', '')
        replace_text = request.data.get('replace_text', '')
        preview = request.data.get('preview', True)

        if not instance_ids or not filename:
            return Response({'code': 400, 'message': '缺少 instance_ids 或 filename', 'data': None},
                            status=status.HTTP_400_BAD_REQUEST)
        if not search_text:
            return Response({'code': 400, 'message': '查找内容不能为空', 'data': None},
                            status=status.HTTP_400_BAD_REQUEST)

        results = []
        for instance_id in instance_ids:
            try:
                config = ConfigFile.objects.select_related('instance').get(
                    instance_id=instance_id, filename=filename)
            except ConfigFile.DoesNotExist:
                continue

            # 使用格式化后的 JSON 文本做替换（保证一致性）
            raw_json = json.dumps(config.content, ensure_ascii=False, indent=2)
            count = raw_json.count(search_text)
            if count == 0:
                results.append({
                    'instance_id': instance_id,
                    'instance_name': config.instance.name,
                    'match_count': 0,
                    'changed': False,
                })
                continue

            new_json = raw_json.replace(search_text, replace_text)
            # 验证替换后仍是有效 JSON
            try:
                new_content = json.loads(new_json)
            except json.JSONDecodeError as e:
                results.append({
                    'instance_id': instance_id,
                    'instance_name': config.instance.name,
                    'match_count': count,
                    'changed': False,
                    'error': f'替换后 JSON 无效: {e}',
                })
                continue

            entry = {
                'instance_id': instance_id,
                'instance_name': config.instance.name,
                'match_count': count,
                'changed': True,
            }
            if preview:
                # 预览：返回 diff 片段（最多 5 处上下文）
                lines_old = raw_json.splitlines()
                lines_new = new_json.splitlines()
                diff_lines = []
                for i, (lo, ln) in enumerate(zip(lines_old, lines_new)):
                    if lo != ln:
                        diff_lines.append({'line': i + 1, 'old': lo.strip(), 'new': ln.strip()})
                        if len(diff_lines) >= 5:
                            break
                entry['diff_preview'] = diff_lines
            else:
                config.content = new_content
                config.save(update_fields=['content'])

            results.append(entry)

        changed_count = sum(1 for r in results if r.get('changed'))
        if not preview:
            _audit(request, 'text_replace',
                   instance_names=[r['instance_name'] for r in results if r.get('changed')],
                   filename=filename,
                   summary=f'文本替换: 查找 "{search_text}" → "{replace_text}"，修改 {changed_count} 个实例',
                   detail={'search_text': search_text, 'replace_text': replace_text,
                           'changed_count': changed_count, 'results': results},
                   status='success' if changed_count > 0 else 'failed')
        return ApiResponse(data={
            'preview': preview,
            'changed_count': changed_count,
            'total': len(results),
            'results': results,
        })

    @action(detail=False, methods=['post'], url_path='push_consul')
    def push_consul(self, request):
        """推送选中配置到 Consul KV"""
        config_ids = request.data.get('config_ids', [])
        if not config_ids:
            return Response({'code': 400, 'message': '未指定配置文件', 'data': None},
                            status=status.HTTP_400_BAD_REQUEST)

        configs = ConfigFile.objects.select_related('instance', 'instance__service_type').filter(
            id__in=config_ids)
        results = []
        for config in configs:
            try:
                key_path, ok = _push_config_to_consul(config)
                results.append({'key': key_path, 'status': 'ok' if ok else 'error'})
            except Exception as e:
                results.append({'key': config.filename, 'status': 'error', 'detail': str(e)})

        success_count = sum(1 for r in results if r['status'] == 'ok')
        audit_status = 'success' if success_count == len(results) else ('failed' if success_count == 0 else 'partial')
        _audit(request, 'push_consul',
               instance_names=list({c.instance.name for c in configs}),
               summary=f'推送 Consul: {success_count}/{len(results)} 成功',
               detail={'results': results},
               status=audit_status)
        return ApiResponse(data={
            'message': f'已推送 {success_count}/{len(results)} 个配置到 Consul',
            'results': results,
        })


class ConfigSyncViewSet(viewsets.ViewSet):
    """从 GitLab 同步配置树到数据库"""

    def create(self, request):
        try:
            results = _sync_from_gitlab()
            msg = (f"同步完成: {results['service_types']} 服务类型, "
                   f"{results['instances']} 实例, {results['configs']} 配置文件")
            _audit(request, 'sync', summary=msg, detail=results)
            return ApiResponse(data={'message': msg, 'results': results})
        except Exception as e:
            import traceback
            _audit(request, 'sync', status='failed', summary=str(e))
            return Response({'code': 500, 'message': str(e), 'data': {'traceback': traceback.format_exc()}},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ConfigDeployViewSet(viewsets.ViewSet):
    """配置部署任务"""

    def list(self, request):
        tasks = ConfigDeployTask.objects.order_by('-created_time')[:20]
        return ApiResponse(data=ConfigDeployTaskSerializer(tasks, many=True).data)

    @action(detail=False, methods=['post'], url_path='preview')
    def preview(self, request):
        """返回即将部署的实例详情（配置文件、目标路径、主机等），供弹窗展示"""
        instance_ids = request.data.get('instance_ids', [])
        if not instance_ids:
            return Response({'code': 400, 'message': '未指定实例', 'data': None},
                            status=status.HTTP_400_BAD_REQUEST)

        consul_url = getattr(settings, 'CONFIG_CONSUL_URL', '').rstrip('/')
        kv_prefix = getattr(settings, 'CONFIG_CONSUL_KV_PREFIX', 'configs/mdl')

        instances = (ConfigInstance.objects
                     .select_related('service_type')
                     .prefetch_related('configfile_set')
                     .filter(id__in=instance_ids))

        result = []
        for inst in instances:
            # consul_space 展示：优先用实例字段，否则构造默认
            consul_space = inst.consul_space or '{}/v1/kv/{}/{}/{}/'.format(
                consul_url, kv_prefix, inst.service_type.name, inst.name)

            configs = [
                {
                    'filename': cfg.filename,
                    'consul_key': consul_space.rstrip('/') + '/' + cfg.filename,
                    'size': len(json.dumps(cfg.content)) if cfg.content else 0,
                }
                for cfg in inst.configfile_set.all().order_by('filename')
            ]

            result.append({
                'instance_id': inst.id,
                'instance_name': inst.name,
                'service_type': inst.service_type.name,
                'host_ip': inst.host_ip or '(未配置)',
                'install_dir': inst.install_dir or '(未配置)',
                'service_name': inst.service_name or '(未配置)',
                'consul_space': consul_space,
                'configs': configs,
            })

        return ApiResponse(data=result)

    def create(self, request):
        instance_ids = request.data.get('instance_ids', [])
        operator = str(request.user) if request.user else 'anonymous'

        if not instance_ids:
            return Response({'code': 400, 'message': '未指定实例', 'data': None},
                            status=status.HTTP_400_BAD_REQUEST)

        instances = ConfigInstance.objects.filter(id__in=instance_ids)
        if not instances.exists():
            return Response({'code': 400, 'message': '实例不存在', 'data': None},
                            status=status.HTTP_400_BAD_REQUEST)

        task = ConfigDeployTask.objects.create(operator=operator, status='pending')
        task.instances.set(instances)
        task.save()

        # 后台线程执行
        thread = threading.Thread(target=_run_deploy_task, args=(task.id,))
        thread.daemon = True
        thread.start()

        return ApiResponse(data={
            'task_id': task.id,
            'message': '部署任务已提交',
            'status': task.status,
        })

    def retrieve(self, request, pk=None):
        try:
            task = ConfigDeployTask.objects.get(id=pk)
            return ApiResponse(data=ConfigDeployTaskSerializer(task).data)
        except ConfigDeployTask.DoesNotExist:
            return Response({'code': 404, 'message': '任务不存在', 'data': None},
                            status=status.HTTP_404_NOT_FOUND)


class ConfigAuditLogSerializer(serializers.ModelSerializer):
    action_display = serializers.CharField(source='get_action_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = ConfigAuditLog
        fields = ['id', 'action', 'action_display', 'operator', 'status', 'status_display',
                  'instance_names', 'filename', 'summary', 'detail',
                  'deploy_task_id', 'created_time']


class ConfigAuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """审计日志（只读）"""
    queryset = ConfigAuditLog.objects.all()
    serializer_class = ConfigAuditLogSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        action = self.request.query_params.get('action')
        operator = self.request.query_params.get('operator')
        date_from = self.request.query_params.get('date_from')
        date_to = self.request.query_params.get('date_to')
        keyword = self.request.query_params.get('keyword')
        if action:
            qs = qs.filter(action=action)
        if operator:
            qs = qs.filter(operator__icontains=operator)
        if date_from:
            qs = qs.filter(created_time__date__gte=date_from)
        if date_to:
            qs = qs.filter(created_time__date__lte=date_to)
        if keyword:
            qs = qs.filter(
                models.Q(instance_names__icontains=keyword) |
                models.Q(summary__icontains=keyword) |
                models.Q(filename__icontains=keyword)
            )
        return qs

    def list(self, request):
        qs = self.get_queryset()
        # 分页：默认每页 50 条
        page = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('page_size', 50))
        total = qs.count()
        items = qs[(page - 1) * page_size: page * page_size]
        return ApiResponse(data={
            'total': total,
            'page': page,
            'page_size': page_size,
            'items': ConfigAuditLogSerializer(items, many=True).data,
        })


class ConfigInstanceViewSet(viewsets.ModelViewSet):
    """配置实例 CRUD"""
    queryset = ConfigInstance.objects.select_related('service_type').all()
    serializer_class = ConfigInstanceSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        service_type_id = self.request.query_params.get('service_type_id')
        if service_type_id:
            qs = qs.filter(service_type_id=service_type_id)
        return qs


class ServiceTypeViewSet(viewsets.ModelViewSet):
    """服务类型 CRUD"""
    queryset = ServiceType.objects.all().order_by('name')
    serializer_class = ServiceTypeSerializer
