"""
服务器初始化模块自动化测试
覆盖以下核心功能：
  1. POST /api/mdl-servers/{id}/init/ 返回 task_id
  2. GET  /api/mdl-servers/{id}/init_status/?task_id=X 查询状态
  3. 初始化后台线程正常执行（Mock subprocess Ansible）
  4. Ansible 执行失败时任务状态变为 failed
  5. 缺少 task_id 参数时返回 400
  6. 任务不存在时返回 404
"""

import time
import threading
from unittest.mock import patch, MagicMock, call

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase

from rest_framework.test import APIClient
from mdl.models import MdlServer, ConfigDeployTask

User = get_user_model()


class ServerInitTestBase(TestCase):
    """公共 setUp：创建用户和 MdlServer"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testadmin',
            password='testpass123',
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        self.server = MdlServer.objects.create(
            fqdn='mdl-test01.example.com',
            ip='10.10.10.100',
            service_name='forward',
            install_dir='/datayes/app/bin',
            backups_dir='/datayes/app/backups',
            user='root',
            remote_python='/usr/bin/python3',
            consul_space='http://consul.test/v1/kv/configs/mdl/forward/10.10.10.100/',
            consul_token='test-token',
        )


# =============================================================
# 1. 启动初始化接口
# =============================================================

class TestInitServerStart(ServerInitTestBase):

    @patch('threading.Thread')
    def test_init_returns_task_id(self, mock_thread):
        """POST /init/ 应立即返回 task_id，不等 Ansible 完成"""
        mock_thread.return_value = MagicMock()
        resp = self.client.post(
            f'/api/mdl-servers/{self.server.id}/init/',
            data={'ssh_pass': 'testpass'},
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['code'], 200)
        self.assertIn('task_id', data['data'])
        self.assertIsNotNone(data['data']['task_id'])

    @patch('threading.Thread')
    def test_init_creates_deploy_task_in_db(self, mock_thread):
        """POST /init/ 应在 DB 中创建 ConfigDeployTask，初始 status=running"""
        mock_thread.return_value = MagicMock()
        before_count = ConfigDeployTask.objects.count()
        self.client.post(
            f'/api/mdl-servers/{self.server.id}/init/',
            data={'ssh_pass': 'testpass'},
            format='json',
        )
        after_count = ConfigDeployTask.objects.count()
        self.assertEqual(after_count, before_count + 1)

        task = ConfigDeployTask.objects.order_by('-id').first()
        self.assertEqual(task.status, 'running')

    @patch('threading.Thread')
    def test_init_starts_background_thread(self, mock_thread):
        """POST /init/ 应启动后台线程执行 Ansible"""
        mock_instance = MagicMock()
        mock_thread.return_value = mock_instance
        self.client.post(
            f'/api/mdl-servers/{self.server.id}/init/',
            data={'ssh_pass': 'testpass'},
            format='json',
        )
        mock_thread.assert_called_once()
        mock_instance.start.assert_called_once()

    @patch('threading.Thread')
    def test_init_nonexistent_server_returns_404(self, mock_thread):
        """对不存在的服务器发起初始化应返回 404"""
        resp = self.client.post('/api/mdl-servers/99999/init/', format='json')
        self.assertEqual(resp.status_code, 404)

    @patch('threading.Thread')
    def test_init_egress_false_by_default(self, mock_thread):
        """默认不传 is_egress，应正常启动不报错"""
        mock_thread.return_value = MagicMock()
        resp = self.client.post(
            f'/api/mdl-servers/{self.server.id}/init/',
            data={},
            format='json',
        )
        self.assertEqual(resp.status_code, 200)


# =============================================================
# 2. 查询初始化状态
# =============================================================

class TestInitServerStatus(ServerInitTestBase):

    def setUp(self):
        super().setUp()
        # 预创建任务
        self.task = ConfigDeployTask.objects.create(
            operator='testadmin',
            status='running',
            log='[2026-01-01 00:00:00] 开始初始化...\n',
        )

    def test_init_status_returns_running(self):
        """任务运行中时，status 应为 running"""
        resp = self.client.get(
            f'/api/mdl-servers/{self.server.id}/init_status/',
            {'task_id': self.task.id},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()['data']
        self.assertEqual(data['status'], 'running')

    def test_init_status_returns_log(self):
        """响应中应包含 log 字段"""
        resp = self.client.get(
            f'/api/mdl-servers/{self.server.id}/init_status/',
            {'task_id': self.task.id},
        )
        data = resp.json()['data']
        self.assertIn('log', data)
        self.assertIn('开始初始化', data['log'])

    def test_init_status_missing_task_id_returns_400(self):
        """不传 task_id 应返回 400"""
        resp = self.client.get(
            f'/api/mdl-servers/{self.server.id}/init_status/',
        )
        self.assertEqual(resp.status_code, 400)

    def test_init_status_nonexistent_task_returns_404(self):
        """task_id 不存在时应返回 404"""
        resp = self.client.get(
            f'/api/mdl-servers/{self.server.id}/init_status/',
            {'task_id': 99999},
        )
        self.assertEqual(resp.status_code, 404)

    def test_init_status_success_after_completion(self):
        """任务完成后 status 应为 success"""
        self.task.status = 'success'
        self.task.log += 'PLAY RECAP ... ok=10 changed=8 unreachable=0 failed=0\n'
        self.task.save()

        resp = self.client.get(
            f'/api/mdl-servers/{self.server.id}/init_status/',
            {'task_id': self.task.id},
        )
        data = resp.json()['data']
        self.assertEqual(data['status'], 'success')


# =============================================================
# 3. 后台线程实际执行（同步化测试 Ansible 调用）
# =============================================================

class TestInitServerThread(ServerInitTestBase):
    """测试 run() 线程函数的实际行为（同步执行，不启动真线程）"""

    def _run_init_synchronously(self, ssh_pass='testpass', is_egress=False):
        """
        通过 patch threading.Thread 让 run() 同步执行。
        捕获传给 Thread(target=...) 的 run 函数并直接调用它。
        """
        captured = {}

        def fake_thread(target=None, daemon=None, **kwargs):
            captured['target'] = target
            m = MagicMock()
            m.start = lambda: target()  # 立即同步执行
            return m

        with patch('threading.Thread', side_effect=fake_thread):
            with patch('subprocess.run') as mock_subproc:
                mock_subproc.return_value = MagicMock(returncode=0, stdout='TASK [创建目录结构]\nPLAY RECAP ok=5\n')
                with patch('shutil.copytree'), patch('shutil.copy2'), \
                     patch('os.listdir', return_value=[]), \
                     patch('os.makedirs'), \
                     patch('builtins.open', MagicMock()):
                    resp = self.client.post(
                        f'/api/mdl-servers/{self.server.id}/init/',
                        data={'ssh_pass': ssh_pass, 'is_egress': '1' if is_egress else '0'},
                        format='json',
                    )
        return resp, mock_subproc if 'mock_subproc' in dir() else None

    @patch('subprocess.run')
    @patch('shutil.copytree')
    @patch('shutil.copy2')
    @patch('os.listdir', return_value=[])
    @patch('os.makedirs')
    def test_ansible_subprocess_called_on_init(
        self, mock_makedirs, mock_listdir, mock_copy2, mock_copytree, mock_subproc
    ):
        """初始化线程应调用 ansible-playbook subprocess"""
        mock_subproc.return_value = MagicMock(returncode=0, stdout='PLAY RECAP ok=10\n')

        # 同步执行线程：patch Thread 使其立即调用 target
        captured_target = {}

        def fake_thread(target=None, daemon=None, **kwargs):
            captured_target['fn'] = target
            m = MagicMock()
            m.start = lambda: None  # 不自动执行，手动调用
            return m

        with patch('threading.Thread', side_effect=fake_thread):
            with patch('builtins.open', MagicMock()):
                self.client.post(
                    f'/api/mdl-servers/{self.server.id}/init/',
                    data={'ssh_pass': 'testpass'},
                    format='json',
                )

        # 手动同步执行 run()
        if 'fn' in captured_target:
            captured_target['fn']()

        # 验证 subprocess.run 被调用，且参数包含 ansible-playbook
        self.assertTrue(mock_subproc.called)
        call_args = mock_subproc.call_args
        cmd = call_args[0][0] if call_args[0] else call_args[1].get('args', [])
        self.assertIn('ansible-playbook', cmd)

    @patch('subprocess.run')
    @patch('shutil.copytree')
    @patch('shutil.copy2')
    @patch('os.listdir', return_value=[])
    @patch('os.makedirs')
    def test_task_status_becomes_success_on_returncode_0(
        self, mock_makedirs, mock_listdir, mock_copy2, mock_copytree, mock_subproc
    ):
        """Ansible 返回码 0 时，任务 status 应更新为 success"""
        mock_subproc.return_value = MagicMock(returncode=0, stdout='PLAY RECAP ok=10\n')
        captured_target = {}

        def fake_thread(target=None, daemon=None, **kwargs):
            captured_target['fn'] = target
            return MagicMock(start=lambda: None)

        with patch('threading.Thread', side_effect=fake_thread):
            with patch('builtins.open', MagicMock()):
                resp = self.client.post(
                    f'/api/mdl-servers/{self.server.id}/init/',
                    data={'ssh_pass': 'testpass'},
                    format='json',
                )

        task_id = resp.json()['data']['task_id']
        if 'fn' in captured_target:
            captured_target['fn']()

        task = ConfigDeployTask.objects.get(id=task_id)
        self.assertEqual(task.status, 'success')
        self.assertIsNotNone(task.finished_at)

    @patch('subprocess.run')
    @patch('shutil.copytree')
    @patch('shutil.copy2')
    @patch('os.listdir', return_value=[])
    @patch('os.makedirs')
    def test_task_status_becomes_failed_on_nonzero_returncode(
        self, mock_makedirs, mock_listdir, mock_copy2, mock_copytree, mock_subproc
    ):
        """Ansible 返回码非 0 时，任务 status 应更新为 failed"""
        mock_subproc.return_value = MagicMock(returncode=1, stdout='FAILED! => ...\n')
        captured_target = {}

        def fake_thread(target=None, daemon=None, **kwargs):
            captured_target['fn'] = target
            return MagicMock(start=lambda: None)

        with patch('threading.Thread', side_effect=fake_thread):
            with patch('builtins.open', MagicMock()):
                resp = self.client.post(
                    f'/api/mdl-servers/{self.server.id}/init/',
                    data={'ssh_pass': 'testpass'},
                    format='json',
                )

        task_id = resp.json()['data']['task_id']
        if 'fn' in captured_target:
            captured_target['fn']()

        task = ConfigDeployTask.objects.get(id=task_id)
        self.assertEqual(task.status, 'failed')

    @patch('subprocess.run')
    @patch('shutil.copytree')
    @patch('shutil.copy2')
    @patch('os.listdir', return_value=[])
    @patch('os.makedirs')
    def test_ansible_env_has_host_key_checking_disabled(
        self, mock_makedirs, mock_listdir, mock_copy2, mock_copytree, mock_subproc
    ):
        """subprocess.run 调用时环境变量中应包含 ANSIBLE_HOST_KEY_CHECKING=False"""
        mock_subproc.return_value = MagicMock(returncode=0, stdout='')
        captured_target = {}

        def fake_thread(target=None, daemon=None, **kwargs):
            captured_target['fn'] = target
            return MagicMock(start=lambda: None)

        with patch('threading.Thread', side_effect=fake_thread):
            with patch('builtins.open', MagicMock()):
                self.client.post(
                    f'/api/mdl-servers/{self.server.id}/init/',
                    data={'ssh_pass': 'testpass'},
                    format='json',
                )

        if 'fn' in captured_target:
            captured_target['fn']()

        if mock_subproc.called:
            call_kwargs = mock_subproc.call_args[1]
            env = call_kwargs.get('env', {})
            self.assertEqual(env.get('ANSIBLE_HOST_KEY_CHECKING'), 'False')


# =============================================================
# 4. 服务器 CRUD 基础测试
# =============================================================

class TestMdlServerCRUD(ServerInitTestBase):

    def test_list_servers(self):
        """GET /api/mdl-servers/ 应返回服务器列表"""
        resp = self.client.get('/api/mdl-servers/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn('data', data)

    def test_get_server_detail(self):
        """GET /api/mdl-servers/{id}/ 应返回服务器详情"""
        resp = self.client.get(f'/api/mdl-servers/{self.server.id}/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()['data']
        self.assertEqual(data['fqdn'], 'mdl-test01.example.com')
        self.assertEqual(data['ip'], '10.10.10.100')

    def test_create_server(self):
        """POST /api/mdl-servers/ 应创建新服务器"""
        resp = self.client.post(
            '/api/mdl-servers/',
            data={
                'fqdn': 'mdl-new01.example.com',
                'ip': '10.10.10.200',
                'service_name': 'forwarder',
                'install_dir': '/datayes/app/bin',
                'backups_dir': '/datayes/app/backups',
                'user': 'root',
                'remote_python': '/usr/bin/python3',
                'consul_space': 'http://consul.test/v1/kv/configs/mdl/forwarder/10.10.10.200/',
                'consul_token': 'token',
                'create_config_instance': False,
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(MdlServer.objects.filter(fqdn='mdl-new01.example.com').exists())

    def test_update_server(self):
        """PUT /api/mdl-servers/{id}/ 应更新服务器信息"""
        resp = self.client.put(
            f'/api/mdl-servers/{self.server.id}/',
            data={
                'fqdn': self.server.fqdn,
                'ip': '10.10.10.101',
                'service_name': self.server.service_name,
                'install_dir': self.server.install_dir,
                'backups_dir': self.server.backups_dir,
                'user': self.server.user,
                'remote_python': self.server.remote_python,
                'consul_space': self.server.consul_space,
                'consul_token': self.server.consul_token,
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        self.server.refresh_from_db()
        self.assertEqual(self.server.ip, '10.10.10.101')

    def test_delete_server(self):
        """DELETE /api/mdl-servers/{id}/ 应删除服务器"""
        server_id = self.server.id
        resp = self.client.delete(f'/api/mdl-servers/{server_id}/')
        self.assertIn(resp.status_code, [200, 204])
        self.assertFalse(MdlServer.objects.filter(id=server_id).exists())
