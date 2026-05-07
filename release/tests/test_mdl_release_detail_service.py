"""
MdlReleaseDetailService 关键修复回归测试
覆盖：
  1. _do_upgrade 异常处理：MySQL gone away 时 set_log 失败，set_status('发布失败')
     仍应被尝试调用，避免状态卡在"发布中"（commit ed289ab）
  2. _get_current_version：SSH 卡住时 ThreadPoolExecutor.shutdown(wait=False)，
     主线程不应被 with 块阻塞 15 分钟（commit 62ba297）
  3. _get_upgrade_log：同上
  4. SshClient：connect 后给 transport socket 设硬超时，避免 paramiko transport
     线程卡死在 TCP 读
"""

import concurrent.futures
from unittest.mock import patch, MagicMock

from django.contrib.auth import get_user_model
from django.test import TestCase

from api.models import ReleasePlan, MdlReleaseContent
from api.services.mdl_release_detail_service import MdlReleaseDetailService

User = get_user_model()


class _MdlServiceTestBase(TestCase):
    """公共 setUp：创建用户 + MDL 发布计划，便于直接构造 MdlReleaseDetailService"""

    def setUp(self):
        self.user = User.objects.create_user(username='svc_test_user', password='pw')
        self.plan = ReleasePlan.objects.create(
            name='svc-test-plan-001', project='MDL', owner='svc_test_user',
        )
        self.module = MdlReleaseContent.objects.create(
            release_plan=self.plan,
            index=1,
            issue_key='MDL-1',
            release_version='v1.0.0',
            release_object='host1__1.2.3.4__svc',
            type='version',
            is_release=True,
            status='wait',
        )
        self.service = MdlReleaseDetailService(name=self.plan.name, user=self.user)


# =============================================================
# 1. _do_upgrade except 块：MySQL gone away 不应让状态卡在"发布中"
# =============================================================

class TestDoUpgradeExceptionResilience(_MdlServiceTestBase):

    def test_set_status_called_even_when_set_log_raises(self):
        """
        模拟：升级中抛错 → 进入 except → set_log 也抛 MySQL gone away → 仍应继续
        调用 set_status('发布失败')，否则状态会永远卡在"发布中"
        """
        status_calls = []

        def fake_set_status(status):
            status_calls.append(status)

        # set_log 抛 MySQL gone away（模拟连接断开）
        # set_status 不抛（模拟 close_old_connections 已重建连接）
        with patch.object(self.service, 'deploy_config'), \
             patch.object(self.service, '_upgrade', side_effect=Exception("simulated upgrade failure")), \
             patch.object(self.service.release_detail, 'set_log',
                          side_effect=Exception("(2006, 'MySQL server has gone away')")), \
             patch.object(self.service.release_detail, 'set_status', side_effect=fake_set_status), \
             patch.object(MdlReleaseContent, 'objects') as mock_objs:
            mock_objs.filter.return_value.exists.return_value = True

            with self.assertRaises(Exception):
                self.service._do_upgrade([self.module])

        self.assertIn("发布失败", status_calls,
                      "set_status('发布失败') 必须被调用，否则状态会卡在'发布中'")

    def test_close_old_connections_called_in_except_block(self):
        """except 块开头应调 close_old_connections，让 Django 重建失效的 MySQL 连接"""
        with patch('api.services.mdl_release_detail_service.close_old_connections') as mock_close, \
             patch.object(self.service, 'deploy_config'), \
             patch.object(self.service, '_upgrade', side_effect=Exception("boom")), \
             patch.object(self.service.release_detail, 'set_status'), \
             patch.object(MdlReleaseContent, 'objects') as mock_objs:
            mock_objs.filter.return_value.exists.return_value = True

            with self.assertRaises(Exception):
                self.service._do_upgrade([self.module])

        # 至少在 except 块中被调用一次（_run_ansible 也会调，但本测不会触发）
        self.assertTrue(mock_close.called,
                        "close_old_connections 必须被调用，否则后续 DB 操作会继续抛 gone away")

    def test_module_set_status_called_even_if_release_detail_set_status_fails(self):
        """release_detail.set_status 失败时，module.set_status('error') 仍应被调用"""
        with patch.object(self.service, 'deploy_config'), \
             patch.object(self.service, '_upgrade', side_effect=Exception("boom")), \
             patch.object(self.service.release_detail, 'set_log'), \
             patch.object(self.service.release_detail, 'set_status',
                          side_effect=Exception("MySQL gone away again")), \
             patch.object(self.module, 'set_status') as mock_module_set_status, \
             patch.object(MdlReleaseContent, 'objects') as mock_objs:
            mock_objs.filter.return_value.exists.return_value = True

            with self.assertRaises(Exception):
                self.service._do_upgrade([self.module])

        mock_module_set_status.assert_any_call("error")


# =============================================================
# 2. _get_current_version：SSH 卡住时 executor.shutdown(wait=False)
# =============================================================

class TestGetCurrentVersionShutdownWaitFalse(_MdlServiceTestBase):
    """
    回归 commit 62ba297：以前用 `with ThreadPoolExecutor(...) as ex:` 会在
    future.result(timeout=30) 抛 TimeoutError 后调 shutdown(wait=True)，
    若 paramiko 卡在 TCP 层，整个部署主线程被阻塞 10~30 分钟。
    """

    def _patch_dependencies(self):
        """通用：mock MdlServer / Constance，仅保留 ThreadPoolExecutor 真实行为待断言"""
        fake_host = MagicMock()
        fake_host.ip = '1.2.3.4'
        fake_server = MagicMock()
        fake_server.host = fake_host
        fake_server.install_dir = '/tmp/x'
        mdl_server_patch = patch(
            'api.services.mdl_release_detail_service.MdlServer.objects.select_related'
        )
        mdl_server_mock = mdl_server_patch.start()
        mdl_server_mock.return_value.get.return_value = fake_server
        self.addCleanup(mdl_server_patch.stop)

        const_patch = patch(
            'api.services.mdl_release_detail_service.Constance.get_value',
            side_effect=lambda key: {'ansible_ssh_user': 'u', 'ansible_ssh_pass': 'p'}[key],
        )
        const_patch.start()
        self.addCleanup(const_patch.stop)

    def test_shutdown_called_with_wait_false_on_timeout(self):
        """SSH 超时时 executor.shutdown 必须以 wait=False 调用，不等待卡住的线程"""
        self._patch_dependencies()

        recorded = {'shutdown_wait': None}
        real_executor_cls = concurrent.futures.ThreadPoolExecutor

        class _TrackingExecutor(real_executor_cls):
            def shutdown(self_inner, wait=True, **kw):
                recorded['shutdown_wait'] = wait
                return super().shutdown(wait=False, **kw)  # 实际不等，避免测试卡住

        with patch.object(concurrent.futures, 'ThreadPoolExecutor', _TrackingExecutor):
            # 让 SshClient 构造时直接抛异常，模拟 SSH 失败（走 except Exception 分支）
            with patch('api.services.mdl_release_detail_service.SshClient',
                       side_effect=OSError("connection refused")):
                ret = self.service._get_current_version('host1', 'svc')

        self.assertEqual(ret, '', "SSH 失败应返回空串（视为首次部署）")
        self.assertEqual(recorded['shutdown_wait'], False,
                         "executor.shutdown 必须以 wait=False 调用")

    def test_shutdown_called_with_wait_false_on_success(self):
        """正常成功路径也应该用 wait=False shutdown，避免重构时退回 with 写法"""
        self._patch_dependencies()

        recorded = {'shutdown_wait': None}
        real_executor_cls = concurrent.futures.ThreadPoolExecutor

        class _TrackingExecutor(real_executor_cls):
            def shutdown(self_inner, wait=True, **kw):
                recorded['shutdown_wait'] = wait
                return super().shutdown(wait=False, **kw)

        with patch.object(concurrent.futures, 'ThreadPoolExecutor', _TrackingExecutor):
            fake_ssh = MagicMock()
            fake_ssh.send_cmd.return_value = ['v1.2.3\n']
            with patch('api.services.mdl_release_detail_service.SshClient',
                       return_value=fake_ssh):
                ret = self.service._get_current_version('host1', 'svc')

        self.assertEqual(ret, 'v1.2.3')
        self.assertEqual(recorded['shutdown_wait'], False)

    def test_returns_empty_on_real_timeout_quickly(self):
        """
        端到端：SSH 真的"卡住"（_ssh_get 调用 sleep），_get_current_version
        应在 future timeout 后立即返回，不等线程结束。
        为避免测试本身耗时太久，这里用 monkey-patch 把 timeout 改小。
        """
        import time as _time
        self._patch_dependencies()

        sleeping_done = []

        def _slow_ssh_init(*args, **kwargs):
            _time.sleep(2)  # 模拟 SSH 卡 2 秒
            sleeping_done.append(True)
            m = MagicMock()
            m.send_cmd.return_value = ['lateversion\n']
            return m

        # 把 future.result 的 timeout 改成 0.2s（远小于 sleep）
        original_result = concurrent.futures.Future.result

        def patched_result(self_future, timeout=None):
            return original_result(self_future, timeout=0.2)

        with patch('api.services.mdl_release_detail_service.SshClient',
                   side_effect=_slow_ssh_init), \
             patch.object(concurrent.futures.Future, 'result', patched_result):
            t0 = _time.time()
            ret = self.service._get_current_version('host1', 'svc')
            elapsed = _time.time() - t0

        self.assertEqual(ret, '')
        # 旧实现 with 块会等到 _slow_ssh_init 的 sleep(2) 结束才返回 → > 2s
        # 新实现 finally + shutdown(wait=False) 应在 ~0.2s 内返回
        self.assertLess(elapsed, 1.5,
                        "shutdown(wait=False) 应该立即返回，不等待 SSH 线程结束")


# =============================================================
# 3. SshClient：connect 后设硬 socket timeout
# =============================================================

class TestSshClientSocketTimeout(TestCase):

    @patch('external.ssh_client.paramiko.SSHClient')
    def test_socket_timeout_set_with_default_value(self, mock_ssh_class):
        from external.ssh_client import SshClient

        mock_client = MagicMock()
        mock_ssh_class.return_value = mock_client
        mock_sock = MagicMock()
        mock_transport = MagicMock()
        mock_transport.sock = mock_sock
        mock_client.get_transport.return_value = mock_transport

        SshClient(ip='1.2.3.4', username='u', password='p')

        mock_sock.settimeout.assert_called_once_with(SshClient.DEFAULT_SOCK_TIMEOUT)

    @patch('external.ssh_client.paramiko.SSHClient')
    def test_socket_timeout_custom_value(self, mock_ssh_class):
        from external.ssh_client import SshClient

        mock_client = MagicMock()
        mock_ssh_class.return_value = mock_client
        mock_sock = MagicMock()
        mock_transport = MagicMock()
        mock_transport.sock = mock_sock
        mock_client.get_transport.return_value = mock_transport

        SshClient(ip='1.2.3.4', username='u', password='p', sock_timeout=60)

        mock_sock.settimeout.assert_called_once_with(60)

    @patch('external.ssh_client.paramiko.SSHClient')
    def test_settimeout_failure_swallowed(self, mock_ssh_class):
        """transport socket 不支持 settimeout 时应静默忽略，不影响主流程"""
        from external.ssh_client import SshClient

        mock_client = MagicMock()
        mock_ssh_class.return_value = mock_client
        mock_sock = MagicMock()
        mock_sock.settimeout.side_effect = AttributeError("no settimeout")
        mock_transport = MagicMock()
        mock_transport.sock = mock_sock
        mock_client.get_transport.return_value = mock_transport

        # 不应抛异常
        SshClient(ip='1.2.3.4', username='u', password='p')

    @patch('external.ssh_client.paramiko.SSHClient')
    def test_no_transport_no_crash(self, mock_ssh_class):
        """get_transport() 返回 None 时不应崩"""
        from external.ssh_client import SshClient

        mock_client = MagicMock()
        mock_ssh_class.return_value = mock_client
        mock_client.get_transport.return_value = None

        SshClient(ip='1.2.3.4', username='u', password='p')
