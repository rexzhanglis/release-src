import os
import shutil
import tempfile
import threading
import yaml
from datetime import datetime

from rest_framework import viewsets, serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status as drf_status

try:
    import ansible_runner
except Exception:
    import subprocess

    class AnsibleRunnerMock:
        @staticmethod
        def run_command(executable_cmd, cmdline_args, **kwargs):
            import platform
            if platform.system() == 'Windows':
                print(f"[MOCK] Executing: {executable_cmd} {' '.join(cmdline_args)}")
                return "Mock Ansible Success\nSkipping actual execution on Windows.", "", 0
            try:
                env = kwargs.get('envvars', kwargs.get('env', os.environ.copy()))
                cwd = kwargs.get('cwd', None)
                res = subprocess.run([executable_cmd] + cmdline_args,
                                     capture_output=True, text=True, env=env, cwd=cwd)
                return res.stdout, res.stderr, res.returncode
            except Exception as e:
                return "", str(e), 1

    ansible_runner = AnsibleRunnerMock()

from mdl.models import MdlServer, ConfigDeployTask, ServiceType, ConfigInstance, ConfigFile, Label
from const.models import Constance
from common.utils.apiutil import ApiResponse


class LabelSerializer(serializers.ModelSerializer):
    class Meta:
        model = Label
        fields = ['id', 'name']


class LabelViewSet(viewsets.ModelViewSet):
    queryset = Label.objects.all().order_by('name')
    serializer_class = LabelSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        q = self.request.query_params.get('q', '').strip()
        if q:
            qs = qs.filter(name__icontains=q)
        return qs


class MdlServerSerializer(serializers.ModelSerializer):
    labels = LabelSerializer(source='label_set', many=True, read_only=True)
    label_ids = serializers.ListField(
        child=serializers.IntegerField(), write_only=True, required=False, default=list
    )

    class Meta:
        model = MdlServer
        fields = [
            'id', 'fqdn', 'ip', 'role_name', 'user', 'remote_python',
            'service_name', 'install_dir', 'backups_dir',
            'consul_space', 'consul_token', 'consul_files',
            'config_git_url', 'is_consistent', 'check_detail',
            'created_time', 'last_updated_time',
            'labels', 'label_ids',
        ]
        read_only_fields = ['id', 'created_time', 'last_updated_time']

    def _sync_labels(self, instance, label_ids):
        # 移除旧关联，添加新关联（从 Label 端操作 M2M）
        for label in Label.objects.filter(mdl_server=instance).exclude(id__in=label_ids):
            label.mdl_server.remove(instance)
        for label in Label.objects.filter(id__in=label_ids):
            label.mdl_server.add(instance)

    def create(self, validated_data):
        label_ids = validated_data.pop('label_ids', [])
        instance = super().create(validated_data)
        self._sync_labels(instance, label_ids)
        return instance

    def update(self, instance, validated_data):
        label_ids = validated_data.pop('label_ids', None)
        instance = super().update(instance, validated_data)
        if label_ids is not None:
            self._sync_labels(instance, label_ids)
        return instance


class MdlServerViewSet(viewsets.ModelViewSet):
    queryset = MdlServer.objects.all().order_by('service_name', 'fqdn')
    serializer_class = MdlServerSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        q = self.request.query_params.get('q', '').strip()
        label_id = self.request.query_params.get('label_id', '').strip()
        if q:
            from django.db.models import Q
            qs = qs.filter(Q(fqdn__icontains=q) | Q(ip__icontains=q) | Q(service_name__icontains=q))
        if label_id:
            qs = qs.filter(label__id=label_id)
        return qs

    def create(self, request, *args, **kwargs):
        """
        新增服务器。
        额外支持参数：
          create_config_instance: bool  (默认 true) — 同时创建配置实例
          service_type_name: str        — Git 仓库一级目录（如 aliforward/forward）
          instance_name: str            — Git 仓库二级目录（如 10.121.21.240_19015）
          git_commit: bool              (默认 true) — 创建后立即提交空配置文件到 GitLab
          commit_message: str           — Git commit message
        """
        create_config = request.data.get('create_config_instance', True)
        service_type_name = (request.data.get('service_type_name') or '').strip()
        instance_name = (request.data.get('instance_name') or '').strip()
        do_git_commit = request.data.get('git_commit', True)
        commit_message = (request.data.get('commit_message') or '').strip()

        # 先保存 MdlServer（走标准序列化流程）
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        server = serializer.save()

        result = {'server': serializer.data, 'config_instance': None, 'git': None}

        if create_config and service_type_name and instance_name:
            try:
                from django.conf import settings

                service_type, _ = ServiceType.objects.get_or_create(name=service_type_name)

                consul_url = getattr(settings, 'CONFIG_CONSUL_URL', '').rstrip('/')
                kv_prefix = getattr(settings, 'CONFIG_CONSUL_KV_PREFIX', 'configs/mdl')
                default_consul_space = '{}/v1/kv/{}/{}/{}/'.format(
                    consul_url, kv_prefix, service_type_name, instance_name)

                instance, inst_created = ConfigInstance.objects.get_or_create(
                    service_type=service_type,
                    name=instance_name,
                    defaults={
                        'host_ip': server.ip,
                        'consul_space': server.consul_space or default_consul_space,
                        'install_dir': server.install_dir,
                        'backups_dir': server.backups_dir,
                        'service_name': server.service_name,
                        'consul_files': server.consul_files or 'feeder_handler.cfg',
                        'remote_python': server.remote_python or '/usr/bin/python3',
                    }
                )

                # 为每个配置文件名创建空白 ConfigFile
                filenames = [f.strip() for f in (server.consul_files or 'feeder_handler.cfg').split(',') if f.strip()]
                config_files = []
                for fn in filenames:
                    cf, _ = ConfigFile.objects.get_or_create(
                        instance=instance,
                        filename=fn,
                        defaults={'content': {}, 'raw_content': '{}'}
                    )
                    config_files.append(cf)

                result['config_instance'] = {
                    'id': instance.id,
                    'name': instance.name,
                    'service_type': service_type_name,
                    'created': inst_created,
                    'files': [cf.filename for cf in config_files],
                }

                # Git Commit 空配置文件（让 GitLab 有占位文件）
                if do_git_commit and config_files:
                    msg = commit_message or f'Add config for {service_type_name}/{instance_name}'
                    try:
                        from api.viewsets.config_mgmt_viewset import _commit_to_gitlab
                        git_results = _commit_to_gitlab(config_files, msg)
                        ok = sum(1 for r in git_results if r['status'] == 'ok')
                        result['git'] = {
                            'message': f'Git Commit {ok}/{len(git_results)} 个文件成功',
                            'results': git_results,
                        }
                    except Exception as e:
                        result['git'] = {'message': f'Git Commit 失败: {e}', 'results': []}

            except Exception as e:
                result['config_instance'] = {'error': str(e)}

        return ApiResponse(data=result)

    @action(detail=True, methods=['post'], url_path='init')
    def init_server(self, request, pk=None):
        """
        系统环境初始化（不部署二进制包）：
        创建目录结构 + 配置 systemd service + 配置 coredump
        出口机器额外支持上传文件：egress_files（配置文件）、anaconda_file（Anaconda 包）
        部署版本请通过 Jira 发布流程进行。
        """
        server = self.get_object()
        try:
            ssh_user = (request.data.get('ssh_user') or '').strip() or server.user or 'root'
            ssh_pass = request.data.get('ssh_pass', '').strip()
            if not ssh_pass:
                try:
                    ssh_pass = Constance.get_value('ansible_ssh_pass') or ''
                except Exception:
                    ssh_pass = ''

            operator = request.user.username if request.user.is_authenticated else 'unknown'

            ansi_dir = os.path.abspath(
                os.path.join(os.path.dirname(__file__), '..', '..', 'ansi', 'mdl')
            )

            # 上传的出口机器文件需在主线程读取（request 对象不能跨线程）
            egress_file_data = []   # [(filename, bytes), ...]
            anaconda_file_data = None  # (filename, bytes)
            is_egress = request.data.get('is_egress', '0') in ('1', 'true', True)
            if is_egress:
                for f in request.FILES.getlist('egress_files'):
                    egress_file_data.append((f.name, f.read()))
                anaconda_file = request.FILES.get('anaconda_file')
                if anaconda_file:
                    anaconda_file_data = (anaconda_file.name, anaconda_file.read())

            task = ConfigDeployTask.objects.create(
                operator=operator,
                status='running',
                log=f'[{datetime.now():%Y-%m-%d %H:%M:%S}] 开始初始化系统环境：{server.fqdn} ({server.ip})\n',
            )

            # 捕获所有需要的变量，避免闭包引用 request
            _server_ip = server.ip
            _server_fqdn = server.fqdn
            _host_vars_base = {
                'user': server.user or 'root',
                'remote_python': server.remote_python or '/opt/anaconda/bin/python',
                'consul_space': server.consul_space or '',
                'consul_token': server.consul_token or '',
                'install_dir': server.install_dir,
                'backups_dir': server.backups_dir,
                'service_name': server.service_name,
                'consul_files': server.consul_files or 'feeder_handler.cfg',
                'is_egress': is_egress,
            }

            def run():
                # 子线程不能复用主线程的数据库连接，关闭后 Django 会自动建新连接
                from django.db import connection as _db_conn
                import subprocess as _sp
                import traceback as _tb
                _db_conn.close()
                try:
                    # 临时目录、文件复制等耗时操作全在线程内完成，避免阻塞请求
                    tmpdir = tempfile.mkdtemp(prefix='mdl_init_')
                    for item in os.listdir(ansi_dir):
                        src = os.path.join(ansi_dir, item)
                        dst = os.path.join(tmpdir, item)
                        if os.path.isdir(src):
                            shutil.copytree(src, dst)
                        else:
                            shutil.copy2(src, dst)

                    playbook_path = os.path.join(tmpdir, 'deploy_feeder_init.yml')
                    hosts_path = os.path.join(tmpdir, 'hosts')
                    host_vars_dir = os.path.join(tmpdir, 'host_vars')
                    os.makedirs(host_vars_dir, exist_ok=True)

                    with open(hosts_path, 'w') as f:
                        f.write(f"release ansible_ssh_host={_server_ip} "
                                f"ansible_ssh_user={ssh_user} "
                                f"ansible_ssh_pass={ssh_pass}\n")

                    host_vars = dict(_host_vars_base)
                    egress_files_dir = os.path.join(tmpdir, 'egress_files')
                    anaconda_file_path = ''
                    if is_egress:
                        os.makedirs(egress_files_dir, exist_ok=True)
                        for fname, fdata in egress_file_data:
                            with open(os.path.join(egress_files_dir, fname), 'wb') as fp:
                                fp.write(fdata)
                        if anaconda_file_data:
                            anaconda_file_path = os.path.join(tmpdir, anaconda_file_data[0])
                            with open(anaconda_file_path, 'wb') as fp:
                                fp.write(anaconda_file_data[1])

                    host_vars['egress_files_dir'] = egress_files_dir if is_egress else ''
                    host_vars['anaconda_file_path'] = anaconda_file_path
                    with open(os.path.join(host_vars_dir, 'release.yml'), 'w') as f:
                        yaml.dump(host_vars, f, allow_unicode=True)

                    env = os.environ.copy()
                    env['ANSIBLE_HOST_KEY_CHECKING'] = 'False'
                    proc = _sp.run(
                        ['ansible-playbook', playbook_path, '-i', hosts_path, '-vv'],
                        stdout=_sp.PIPE, stderr=_sp.STDOUT,
                        text=True, env=env,
                    )
                    task.refresh_from_db()
                    task.log = (task.log or '') + (proc.stdout or '')
                    task.status = 'success' if proc.returncode == 0 else 'failed'
                except Exception as ex:
                    task.log = (task.log or '') + f'\n[错误] {ex}\n{_tb.format_exc()}'
                    task.status = 'failed'
                finally:
                    task.finished_at = datetime.now()
                    task.save()

            threading.Thread(target=run, daemon=True).start()

            return ApiResponse(data={'task_id': task.id})

        except Exception as e:
            return Response(
                {'code': 500, 'message': str(e), 'data': None},
                status=drf_status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['get'], url_path='init_status')
    def init_status(self, request, pk=None):
        """轮询初始化任务状态"""
        task_id = request.query_params.get('task_id')
        if not task_id:
            return Response(
                {'code': 400, 'message': '缺少 task_id'},
                status=drf_status.HTTP_400_BAD_REQUEST
            )
        try:
            task = ConfigDeployTask.objects.get(id=task_id)
            return ApiResponse(data={
                'status': task.status,
                'log': task.log or '',
            })
        except ConfigDeployTask.DoesNotExist:
            return Response(
                {'code': 404, 'message': '任务不存在'},
                status=drf_status.HTTP_404_NOT_FOUND
            )
