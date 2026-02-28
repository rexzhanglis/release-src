import os
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
except ImportError:
    import subprocess

    class AnsibleRunnerMock:
        @staticmethod
        def run_command(executable_cmd, cmdline_args, **kwargs):
            import platform
            if platform.system() == 'Windows':
                print(f"[MOCK] Executing: {executable_cmd} {' '.join(cmdline_args)}")
                return "Mock Ansible Success\nSkipping actual execution on Windows.", "", 0
            try:
                env = kwargs.get('env', os.environ.copy())
                cwd = kwargs.get('cwd', None)
                res = subprocess.run([executable_cmd] + cmdline_args,
                                     capture_output=True, text=True, env=env, cwd=cwd)
                return res.stdout, res.stderr, res.returncode
            except Exception as e:
                return "", str(e), 1

    ansible_runner = AnsibleRunnerMock()

from mdl.models import MdlServer, ConfigDeployTask, ServiceType, ConfigInstance, ConfigFile
from const.models import Constance
from common.utils.apiutil import ApiResponse


class MdlServerSerializer(serializers.ModelSerializer):
    class Meta:
        model = MdlServer
        fields = [
            'id', 'fqdn', 'ip', 'role_name', 'user', 'remote_python',
            'service_name', 'install_dir', 'backups_dir',
            'consul_space', 'consul_token', 'consul_files',
            'config_git_url', 'is_consistent', 'check_detail',
            'created_time', 'last_updated_time',
        ]
        read_only_fields = ['id', 'created_time', 'last_updated_time']


class MdlServerViewSet(viewsets.ModelViewSet):
    queryset = MdlServer.objects.all().order_by('service_name', 'fqdn')
    serializer_class = MdlServerSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        q = self.request.query_params.get('q', '').strip()
        if q:
            from django.db.models import Q
            qs = qs.filter(Q(fqdn__icontains=q) | Q(ip__icontains=q) | Q(service_name__icontains=q))
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
        部署版本请通过 Jira 发布流程进行。
        """
        server = self.get_object()

        ssh_user = server.user or 'root'
        ssh_pass = request.data.get('ssh_pass', '').strip()
        if not ssh_pass:
            try:
                ssh_pass = Constance.get_value('ansible_ssh_pass') or ''
            except Exception:
                ssh_pass = ''

        operator = request.user.username if request.user.is_authenticated else 'unknown'

        # 写临时目录（避免与现有 ansi/mdl/hosts 并发冲突）
        tmpdir = tempfile.mkdtemp(prefix='mdl_init_')
        hosts_path = os.path.join(tmpdir, 'hosts')
        host_vars_dir = os.path.join(tmpdir, 'host_vars')
        os.makedirs(host_vars_dir)

        with open(hosts_path, 'w') as f:
            f.write(f"release ansible_ssh_host={server.ip} "
                    f"ansible_ssh_user={ssh_user} "
                    f"ansible_ssh_pass={ssh_pass}\n")

        host_vars = {
            'user': server.user or 'root',
            'remote_python': server.remote_python or '/opt/anaconda/bin/python',
            'consul_space': server.consul_space or '',
            'consul_token': server.consul_token or '',
            'install_dir': server.install_dir,
            'backups_dir': server.backups_dir,
            'service_name': server.service_name,
            'consul_files': server.consul_files or 'feeder_handler.cfg',
        }
        with open(os.path.join(host_vars_dir, 'release.yml'), 'w') as f:
            yaml.dump(host_vars, f, allow_unicode=True)

        task = ConfigDeployTask.objects.create(
            operator=operator,
            status='running',
            log=f'[{datetime.now():%Y-%m-%d %H:%M:%S}] 开始初始化系统环境：{server.fqdn} ({server.ip})\n',
        )

        ansi_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), '..', '..', 'ansi', 'mdl')
        )
        playbook_path = os.path.join(ansi_dir, 'deploy_feeder_init.yml')

        def run():
            out, err, rc = ansible_runner.run_command(
                executable_cmd='ansible-playbook',
                cmdline_args=[
                    playbook_path,
                    '-i', hosts_path,
                ],
                cwd=ansi_dir,
            )
            task.log = (task.log or '') + (out or '') + (err or '')
            task.status = 'success' if rc == 0 else 'failed'
            task.finished_at = datetime.now()
            task.save()

        threading.Thread(target=run, daemon=True).start()

        return ApiResponse(data={'task_id': task.id})

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
