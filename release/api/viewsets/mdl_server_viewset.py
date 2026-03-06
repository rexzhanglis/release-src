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

from mdl.models import MdlServer, Host, ConfigDeployTask, ServiceType, ConfigInstance, ConfigFile, Label, ConfigAuditLog
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


# ========== Host（物理机）==========

class HostSerializer(serializers.ModelSerializer):
    service_count = serializers.SerializerMethodField()

    class Meta:
        model = Host
        fields = ['id', 'fqdn', 'ip', 'user', 'remote_python', 'init_status',
                  'created_time', 'last_updated_time', 'service_count']
        read_only_fields = ['id', 'init_status', 'created_time', 'last_updated_time', 'service_count']
        extra_kwargs = {
            'fqdn': {'error_messages': {'unique': '该 FQDN 已存在，请勿重复添加'}},
        }

    def get_service_count(self, obj):
        return obj.services.count()


class HostViewSet(viewsets.ModelViewSet):
    queryset = Host.objects.all().order_by('fqdn')
    serializer_class = HostSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        q = self.request.query_params.get('q', '').strip()
        if q:
            from django.db.models import Q
            qs = qs.filter(Q(fqdn__icontains=q) | Q(ip__icontains=q))
        label_id = self.request.query_params.get('label_id', '').strip()
        if label_id:
            qs = qs.filter(services__label__id=label_id).distinct()
        return qs

    def destroy(self, request, *args, **kwargs):
        host = self.get_object()
        if host.services.exists():
            return Response(
                {'code': 400, 'message': '该机器下还有服务实例，请先删除所有服务实例再删除机器'},
                status=drf_status.HTTP_400_BAD_REQUEST
            )
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=['post'], url_path='init')
    def init_host(self, request, pk=None):
        """
        服务器级初始化（每台机器只需执行一次）：
        安装系统工具包 + 创建运维用户 + 配置 limits + 配置 DNS
        """
        host = self.get_object()
        try:
            ssh_user = (request.data.get('ssh_user') or '').strip() or host.user or 'root'
            ssh_pass = (request.data.get('ssh_pass') or '').strip()
            if not ssh_pass:
                try:
                    ssh_pass = Constance.get_value('ansible_ssh_pass') or ''
                except Exception:
                    ssh_pass = ''
            if not ssh_pass:
                ssh_pass = os.environ.get('ANSIBLE_SSH_PASS', '')

            operator = request.user.username if request.user.is_authenticated else 'unknown'
            ansi_dir = os.path.abspath(
                os.path.join(os.path.dirname(__file__), '..', '..', 'ansi', 'mdl')
            )

            _host_ip = host.ip
            _host_fqdn = host.fqdn
            _host_id = host.id

            task = ConfigDeployTask.objects.create(
                operator=operator,
                status='running',
                log=f'[{datetime.now():%Y-%m-%d %H:%M:%S}] 开始服务器初始化：{_host_fqdn} ({_host_ip})\n',
            )

            host.init_status = 'initializing'
            host.save(update_fields=['init_status'])

            def run():
                from django.db import connection as _db_conn
                import subprocess as _sp
                import traceback as _tb
                _db_conn.close()
                try:
                    tmpdir = tempfile.mkdtemp(prefix='mdl_host_init_')
                    for item in os.listdir(ansi_dir):
                        src = os.path.join(ansi_dir, item)
                        dst = os.path.join(tmpdir, item)
                        if os.path.isdir(src):
                            shutil.copytree(src, dst)
                        else:
                            shutil.copy2(src, dst)

                    playbook_path = os.path.join(tmpdir, 'deploy_host_init.yml')
                    hosts_path = os.path.join(tmpdir, 'hosts')
                    host_vars_dir = os.path.join(tmpdir, 'host_vars')
                    os.makedirs(host_vars_dir, exist_ok=True)

                    with open(hosts_path, 'w') as f:
                        f.write(f"release ansible_ssh_host={_host_ip} "
                                f"ansible_ssh_user={ssh_user} "
                                f"ansible_ssh_pass={ssh_pass}\n")

                    # host_init 不需要服务实例变量，只传机器级基础信息
                    host_vars = {
                        'user': host.user or 'root',
                        'remote_python': host.remote_python or '/usr/bin/python3',
                    }
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
                    try:
                        _h = Host.objects.get(id=_host_id)
                        _h.init_status = 'ready' if task.status == 'success' else 'failed'
                        _h.save(update_fields=['init_status'])
                    except Exception:
                        pass
                    try:
                        ConfigAuditLog.objects.create(
                            action='server_init',
                            operator=operator,
                            status='success' if task.status == 'success' else 'failed',
                            instance_names=f'{_host_fqdn} ({_host_ip})',
                            summary=f'服务器初始化：{_host_fqdn} ({_host_ip})',
                            deploy_task=task,
                        )
                    except Exception:
                        pass

            threading.Thread(target=run, daemon=True).start()
            return ApiResponse(data={'task_id': task.id})

        except Exception as e:
            return Response(
                {'code': 500, 'message': str(e), 'data': None},
                status=drf_status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['get'], url_path='init_status')
    def init_host_status(self, request, pk=None):
        """轮询服务器初始化任务状态"""
        task_id = request.query_params.get('task_id')
        if not task_id:
            return Response({'code': 400, 'message': '缺少 task_id'},
                            status=drf_status.HTTP_400_BAD_REQUEST)
        try:
            task = ConfigDeployTask.objects.get(id=task_id)
            return ApiResponse(data={'status': task.status, 'log': task.log or ''})
        except ConfigDeployTask.DoesNotExist:
            return Response({'code': 404, 'message': '任务不存在'},
                            status=drf_status.HTTP_404_NOT_FOUND)


# ========== MdlServer（服务实例）==========

class MdlServerSerializer(serializers.ModelSerializer):
    labels = LabelSerializer(source='label_set', many=True, read_only=True)
    label_ids = serializers.ListField(
        child=serializers.IntegerField(), write_only=True, required=False, default=list
    )
    # 展开 host 字段，方便前端直接使用
    fqdn = serializers.CharField(source='host.fqdn', read_only=True)
    ip = serializers.CharField(source='host.ip', read_only=True)
    user = serializers.CharField(source='host.user', read_only=True)
    remote_python = serializers.CharField(source='host.remote_python', read_only=True)
    host_id = serializers.PrimaryKeyRelatedField(
        queryset=Host.objects.all(), source='host', write_only=False, required=True
    )

    class Meta:
        model = MdlServer
        fields = [
            'id', 'host_id', 'fqdn', 'ip', 'user', 'remote_python',
            'role_name', 'service_name', 'install_dir', 'backups_dir',
            'consul_space', 'consul_token', 'consul_files',
            'config_git_url', 'is_consistent', 'check_detail',
            'init_status',
            'created_time', 'last_updated_time',
            'labels', 'label_ids',
        ]
        read_only_fields = ['id', 'fqdn', 'ip', 'user', 'remote_python',
                            'init_status', 'created_time', 'last_updated_time']

    def _sync_labels(self, instance, label_ids):
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
    queryset = MdlServer.objects.select_related('host').all().order_by('service_name', 'host__fqdn')
    serializer_class = MdlServerSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        q = self.request.query_params.get('q', '').strip()
        label_id = self.request.query_params.get('label_id', '').strip()
        host_id = self.request.query_params.get('host_id', '').strip()
        if q:
            from django.db.models import Q
            qs = qs.filter(
                Q(host__fqdn__icontains=q) | Q(host__ip__icontains=q) | Q(service_name__icontains=q)
            )
        if label_id:
            qs = qs.filter(label__id=label_id)
        if host_id:
            qs = qs.filter(host_id=host_id)
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
                        'host_ip': server.host.ip,
                        'consul_space': server.consul_space or default_consul_space,
                        'install_dir': server.install_dir,
                        'backups_dir': server.backups_dir,
                        'service_name': server.service_name,
                        'consul_files': server.consul_files or 'feeder_handler.cfg',
                        'remote_python': server.host.remote_python or '/usr/bin/python3',
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
        服务实例初始化（每个服务实例执行一次）：
        创建目录结构 + 配置 coredump + 部署 systemd service + 出口机器配置
        部署版本请通过 Jira 发布流程进行。
        """
        server = self.get_object()
        try:
            ssh_user = (request.data.get('ssh_user') or '').strip() or os.environ.get('ANSIBLE_SSH_USER', '') or server.host.user or 'root'
            ssh_pass = request.data.get('ssh_pass', '').strip()
            if not ssh_pass:
                try:
                    ssh_pass = Constance.get_value('ansible_ssh_pass') or ''
                except Exception:
                    ssh_pass = ''
            if not ssh_pass:
                ssh_pass = os.environ.get('ANSIBLE_SSH_PASS', '')

            operator = request.user.username if request.user.is_authenticated else 'unknown'

            ansi_dir = os.path.abspath(
                os.path.join(os.path.dirname(__file__), '..', '..', 'ansi', 'mdl')
            )

            # 上传的出口机器文件需在主线程读取（request 对象不能跨线程）
            egress_file_data = []   # [(filename, bytes), ...]
            is_egress = request.data.get('is_egress', '0') in ('1', 'true', True)
            if is_egress:
                for f in request.FILES.getlist('egress_files'):
                    egress_file_data.append((f.name, f.read()))

            _server_ip = server.host.ip
            _server_fqdn = server.host.fqdn
            task = ConfigDeployTask.objects.create(
                operator=operator,
                status='running',
                log=f'[{datetime.now():%Y-%m-%d %H:%M:%S}] 开始服务实例初始化：{_server_fqdn} ({_server_ip}) [{server.service_name}]\n',
            )

            # 立即将服务器状态置为初始化中
            server.init_status = 'initializing'
            server.save(update_fields=['init_status'])

            # 捕获所有需要的变量，避免闭包引用 request
            _server_id = server.id
            _host_vars_base = {
                'user': server.host.user or 'root',
                'remote_python': server.host.remote_python or '/usr/bin/python3',
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

                    playbook_path = os.path.join(tmpdir, 'deploy_service_init.yml')
                    hosts_path = os.path.join(tmpdir, 'hosts')
                    host_vars_dir = os.path.join(tmpdir, 'host_vars')
                    os.makedirs(host_vars_dir, exist_ok=True)

                    with open(hosts_path, 'w') as f:
                        f.write(f"release ansible_ssh_host={_server_ip} "
                                f"ansible_ssh_user={ssh_user} "
                                f"ansible_ssh_pass={ssh_pass}\n")

                    host_vars = dict(_host_vars_base)
                    egress_files_dir = os.path.join(tmpdir, 'egress_files')
                    if is_egress:
                        os.makedirs(egress_files_dir, exist_ok=True)
                        for fname, fdata in egress_file_data:
                            with open(os.path.join(egress_files_dir, fname), 'wb') as fp:
                                fp.write(fdata)

                    host_vars['egress_files_dir'] = egress_files_dir if is_egress else ''
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
                    # 回写服务器 init_status
                    try:
                        _srv = MdlServer.objects.get(id=_server_id)
                        _srv.init_status = 'ready' if task.status == 'success' else 'failed'
                        _srv.save(update_fields=['init_status'])
                    except Exception:
                        pass
                    # 写审计日志
                    try:
                        ConfigAuditLog.objects.create(
                            action='server_init',
                            operator=operator,
                            status='success' if task.status == 'success' else 'failed',
                            instance_names=f'{_server_fqdn} ({_server_ip})',
                            summary=f'服务实例初始化：{_server_fqdn} ({_server_ip}) [{server.service_name}]',
                            deploy_task=task,
                        )
                    except Exception:
                        pass

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

    @action(detail=True, methods=['get'], url_path='systemd_services')
    def systemd_services(self, request, pk=None):
        """
        获取服务器上的 systemd service 列表及其状态。
        默认从 DB 缓存读取（由定时任务每5分钟刷新），加 ?refresh=1 触发实时查询并更新缓存。
        返回：{services, ip, refreshed_at, from_cache}
        """
        from mdl.models import SystemdServiceCache
        from mdl.tasks import _fetch_systemd_for_host
        from datetime import timezone as _tz

        server = self.get_object()
        if server.init_status not in ('ready',):
            return Response(
                {'code': 400, 'message': '服务器尚未初始化完成，无法查询 systemd 服务'},
                status=drf_status.HTTP_400_BAD_REQUEST
            )

        do_refresh = request.query_params.get('refresh', '') == '1'

        if do_refresh:
            try:
                ssh_pass = Constance.get_value('ansible_ssh_pass') or os.environ.get('ANSIBLE_SSH_PASS', '')
                ssh_user = Constance.get_value('ansible_ssh_user') or os.environ.get('ANSIBLE_SSH_USER', '') or server.host.user or 'root'
                ansible_env = os.environ.copy()
                ansible_env['ANSIBLE_HOST_KEY_CHECKING'] = 'False'
                _, services, error = _fetch_systemd_for_host(server.host, ssh_user, ssh_pass, ansible_env)
                from datetime import datetime
                now = datetime.now(_tz.utc)
                cache, _ = SystemdServiceCache.objects.update_or_create(
                    host=server.host,
                    defaults={'services': services, 'refreshed_at': now, 'error': error}
                )
            except Exception as e:
                return Response({'code': 500, 'message': str(e)}, status=drf_status.HTTP_500_INTERNAL_SERVER_ERROR)
        else:
            cache = SystemdServiceCache.objects.filter(host=server.host).first()

        if cache:
            refreshed_at = cache.refreshed_at.astimezone(_tz.utc).strftime('%Y-%m-%d %H:%M:%S UTC') if cache.refreshed_at else None
            return ApiResponse(data={
                'services': cache.services,
                'ip': server.host.ip,
                'refreshed_at': refreshed_at,
                'from_cache': not do_refresh,
                'error': cache.error or '',
            })

        # 缓存不存在且未要求实时刷新，返回空并提示
        return ApiResponse(data={
            'services': [],
            'ip': server.host.ip,
            'refreshed_at': None,
            'from_cache': False,
            'error': '暂无缓存数据，请点击刷新',
        })

    @action(detail=True, methods=['post'], url_path='systemd_control')
    def systemd_control(self, request, pk=None):
        """
        控制 systemd 服务：enable/disable/start/stop/restart
        请求体：
          单个：{ "service": "mdl-forward.service", "action": "restart" }
          批量：{ "services": ["mdl-a.service", "mdl-b.service"], "action": "restart",
                  "consul_pull": true }
          支持 consul_pull=true 在 restart/start 前先执行 consul_pull.py 拉取最新配置
        """
        server = self.get_object()
        ctrl_action = (request.data.get('action') or '').strip()
        ALLOWED = ('start', 'stop', 'restart', 'enable', 'disable', 'reload')
        if ctrl_action not in ALLOWED:
            return Response(
                {'code': 400, 'message': f'action 必填，可选值：{", ".join(ALLOWED)}'},
                status=drf_status.HTTP_400_BAD_REQUEST
            )

        # 支持 service（单个）或 services（批量）
        single = (request.data.get('service') or '').strip()
        multi = request.data.get('services') or []
        if isinstance(multi, str):
            multi = [s.strip() for s in multi.split(',') if s.strip()]
        services = [single] if single else list(multi)
        if not services:
            return Response(
                {'code': 400, 'message': 'service 或 services 必填'},
                status=drf_status.HTTP_400_BAD_REQUEST
            )

        do_consul_pull = request.data.get('consul_pull', False) in (True, 'true', '1', 1)

        try:
            ssh_pass = ''
            try:
                ssh_pass = Constance.get_value('ansible_ssh_pass') or ''
            except Exception:
                pass
            if not ssh_pass:
                ssh_pass = os.environ.get('ANSIBLE_SSH_PASS', '')
            ssh_user = os.environ.get('ANSIBLE_SSH_USER', '') or server.host.user or 'root'

            import subprocess as _sp
            import tempfile as _tf
            tmpdir = _tf.mkdtemp(prefix='mdl_systemd_ctrl_')
            hosts_path = os.path.join(tmpdir, 'hosts')
            with open(hosts_path, 'w') as f:
                f.write(f"release ansible_ssh_host={server.host.ip} "
                        f"ansible_ssh_user={ssh_user} "
                        f"ansible_ssh_pass={ssh_pass}\n")

            env = os.environ.copy()
            env['ANSIBLE_HOST_KEY_CHECKING'] = 'False'

            output_parts = []

            # 先执行 consul_pull（仅 restart/start 时有意义）
            if do_consul_pull and ctrl_action in ('restart', 'start'):
                install_dir = server.install_dir or ''
                pull_script = install_dir.rstrip('/') + '/consul_pull.py'
                remote_python = server.host.remote_python or '/usr/bin/python3'
                consul_token = server.consul_token or ''
                pull_env = f'CONSUL_TOKEN={consul_token} {remote_python} {pull_script}'
                proc_pull = _sp.run(
                    ['ansible', 'release', '-i', hosts_path, '-m', 'shell',
                     '-a', pull_env],
                    stdout=_sp.PIPE, stderr=_sp.PIPE, text=True, env=env, timeout=30
                )
                output_parts.append(f'[consul_pull]\n{proc_pull.stdout or proc_pull.stderr}')

            # 执行 systemctl 命令（批量合并成一条）
            svc_list = ' '.join(services)
            cmd = f'systemctl {ctrl_action} {svc_list}'
            proc = _sp.run(
                ['ansible', 'release', '-i', hosts_path, '-m', 'shell',
                 '-a', cmd, '--become'],
                stdout=_sp.PIPE, stderr=_sp.PIPE, text=True, env=env, timeout=60
            )
            output_parts.append(f'[systemctl {ctrl_action}]\n{proc.stdout or proc.stderr}')
            shutil.rmtree(tmpdir, ignore_errors=True)

            ok = proc.returncode == 0
            return ApiResponse(data={
                'ok': ok,
                'output': '\n'.join(output_parts),
                'action': ctrl_action,
                'services': services,
            })
        except Exception as e:
            return Response(
                {'code': 500, 'message': str(e)},
                status=drf_status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['get'], url_path='systemd_service_file')
    def systemd_service_file(self, request, pk=None):
        """
        读取远端 systemd service 文件内容。
        GET /mdl-servers/{id}/systemd_service_file/?name=mdl-forward.service
        """
        server = self.get_object()
        name = (request.query_params.get('name') or '').strip()
        if not name or not name.endswith('.service'):
            return Response(
                {'code': 400, 'message': 'name 必填且必须以 .service 结尾'},
                status=drf_status.HTTP_400_BAD_REQUEST
            )
        try:
            ssh_pass = ''
            try:
                ssh_pass = Constance.get_value('ansible_ssh_pass') or ''
            except Exception:
                pass
            if not ssh_pass:
                ssh_pass = os.environ.get('ANSIBLE_SSH_PASS', '')
            ssh_user = os.environ.get('ANSIBLE_SSH_USER', '') or server.host.user or 'root'

            import subprocess as _sp
            import tempfile as _tf
            tmpdir = _tf.mkdtemp(prefix='mdl_svc_file_')
            hosts_path = os.path.join(tmpdir, 'hosts')
            with open(hosts_path, 'w') as f:
                f.write(f"release ansible_ssh_host={server.host.ip} "
                        f"ansible_ssh_user={ssh_user} "
                        f"ansible_ssh_pass={ssh_pass}\n")

            env = os.environ.copy()
            env['ANSIBLE_HOST_KEY_CHECKING'] = 'False'

            service_path = f'/lib/systemd/system/{name}'
            proc = _sp.run(
                ['ansible', 'release', '-i', hosts_path, '-m', 'shell',
                 '-a', f'cat {service_path}'],
                stdout=_sp.PIPE, stderr=_sp.PIPE, text=True, env=env, timeout=15
            )
            shutil.rmtree(tmpdir, ignore_errors=True)

            if proc.returncode != 0:
                return Response(
                    {'code': 404, 'message': f'文件不存在或读取失败：{proc.stderr}'},
                    status=drf_status.HTTP_404_NOT_FOUND
                )

            # 提取 >> 后的实际内容
            raw = proc.stdout
            idx = raw.find('>>')
            content = raw[idx + 2:].lstrip('\r\n ') if idx != -1 else raw
            return ApiResponse(data={'name': name, 'content': content, 'path': service_path})

        except Exception as e:
            return Response(
                {'code': 500, 'message': str(e)},
                status=drf_status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['post'], url_path='systemd_manage_service')
    def systemd_manage_service(self, request, pk=None):
        """
        管理 systemd service 文件：新增 / 修改 / 删除 / 重命名
        请求体：
          新增：{ "op": "create", "name": "mdl-new.service", "content": "[Unit]..." }
          修改：{ "op": "update", "name": "mdl-existing.service", "content": "[Unit]..." }
          删除：{ "op": "delete", "name": "mdl-old.service" }
          重命名：{ "op": "rename", "name": "mdl-old.service", "new_name": "mdl-new.service" }
        所有操作后执行 systemctl daemon-reload。
        """
        server = self.get_object()
        op = (request.data.get('op') or '').strip()
        name = (request.data.get('name') or '').strip()
        ALLOWED_OPS = ('create', 'update', 'delete', 'rename')

        if op not in ALLOWED_OPS:
            return Response(
                {'code': 400, 'message': f'op 必填，可选值：{", ".join(ALLOWED_OPS)}'},
                status=drf_status.HTTP_400_BAD_REQUEST
            )
        if not name or not name.endswith('.service'):
            return Response(
                {'code': 400, 'message': 'name 必填且必须以 .service 结尾'},
                status=drf_status.HTTP_400_BAD_REQUEST
            )

        content = request.data.get('content', '')
        new_name = (request.data.get('new_name') or '').strip()
        if op == 'rename' and (not new_name or not new_name.endswith('.service')):
            return Response(
                {'code': 400, 'message': 'rename 操作需要 new_name 且以 .service 结尾'},
                status=drf_status.HTTP_400_BAD_REQUEST
            )

        try:
            ssh_pass = ''
            try:
                ssh_pass = Constance.get_value('ansible_ssh_pass') or ''
            except Exception:
                pass
            if not ssh_pass:
                ssh_pass = os.environ.get('ANSIBLE_SSH_PASS', '')
            ssh_user = os.environ.get('ANSIBLE_SSH_USER', '') or server.host.user or 'root'

            import subprocess as _sp
            import tempfile as _tf
            tmpdir = _tf.mkdtemp(prefix='mdl_svc_manage_')
            hosts_path = os.path.join(tmpdir, 'hosts')
            with open(hosts_path, 'w') as f:
                f.write(f"release ansible_ssh_host={server.host.ip} "
                        f"ansible_ssh_user={ssh_user} "
                        f"ansible_ssh_pass={ssh_pass}\n")

            env = os.environ.copy()
            env['ANSIBLE_HOST_KEY_CHECKING'] = 'False'

            service_dir = '/lib/systemd/system'
            service_path = f'{service_dir}/{name}'

            def _run_shell(cmd, timeout=15):
                return _sp.run(
                    ['ansible', 'release', '-i', hosts_path, '-m', 'shell',
                     '-a', cmd, '--become'],
                    stdout=_sp.PIPE, stderr=_sp.PIPE, text=True, env=env, timeout=timeout
                )

            if op in ('create', 'update'):
                # 将 content 写入本地临时文件，再用 copy 模块上传
                local_file = os.path.join(tmpdir, name)
                with open(local_file, 'w', encoding='utf-8') as fp:
                    fp.write(content)
                proc = _sp.run(
                    ['ansible', 'release', '-i', hosts_path, '-m', 'copy',
                     '-a', f'src={local_file} dest={service_path} owner=root group=root mode=0644',
                     '--become'],
                    stdout=_sp.PIPE, stderr=_sp.PIPE, text=True, env=env, timeout=15
                )
            elif op == 'delete':
                proc = _run_shell(f'rm -f {service_path} && systemctl disable {name} 2>/dev/null || true')
            elif op == 'rename':
                new_path = f'{service_dir}/{new_name}'
                proc = _run_shell(
                    f'cp {service_path} {new_path} && '
                    f'systemctl disable {name} 2>/dev/null || true; '
                    f'rm -f {service_path}'
                )

            # daemon-reload
            _run_shell('systemctl daemon-reload')
            shutil.rmtree(tmpdir, ignore_errors=True)

            ok = proc.returncode == 0
            return ApiResponse(data={
                'ok': ok,
                'op': op,
                'name': name,
                'new_name': new_name if op == 'rename' else None,
                'output': proc.stdout or proc.stderr,
            })

        except Exception as e:
            return Response(
                {'code': 500, 'message': str(e)},
                status=drf_status.HTTP_500_INTERNAL_SERVER_ERROR
            )
