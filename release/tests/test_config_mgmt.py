"""
配置管理模块自动化测试
覆盖以下核心功能：
  1. 更新配置文件内容（含 raw_content 保留）
  2. 更新后自动创建历史快照
  3. 批量修改多实例同一 key
  4. 文本查找替换（预览模式 / 保存模式）
  5. Git 提交（Mock GitLab API）
  6. 部署任务创建与状态查询（Mock subprocess Ansible）
  7. 部署回滚恢复配置
"""

import json
import time
import threading
from unittest.mock import patch, MagicMock

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase, RequestFactory
from rest_framework.test import APIClient

from mdl.models import (
    ServiceType, ConfigInstance, ConfigFile,
    ConfigDeployTask, ConfigHistory, ConfigAuditLog,
)

User = get_user_model()


# =============================================================
# 测试基类：提供公共数据和认证客户端
# =============================================================

class ConfigMgmtTestBase(TestCase):
    """公共 setUp：创建用户、服务类型、实例、配置文件"""

    def setUp(self):
        # 创建测试用户（admin 权限）
        self.user = User.objects.create_user(
            username='testadmin',
            password='testpass123',
            email='admin@test.com',
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        # 创建测试数据
        self.service_type = ServiceType.objects.create(name='forward')
        self.instance = ConfigInstance.objects.create(
            service_type=self.service_type,
            name='10.10.10.1_19013',
            host_ip='10.10.10.1',
            port=19013,
            consul_space='http://consul.test/v1/kv/configs/mdl/forward/10.10.10.1_19013/',
            install_dir='/datayes/app/bin',
            backups_dir='/datayes/app/backups',
            service_name='forward',
        )
        self.config_file = ConfigFile.objects.create(
            instance=self.instance,
            filename='feeder_handler.cfg',
            content={'host': '10.10.10.1', 'port': 19013, 'log_level': 'INFO'},
            raw_content='{\n  "host": "10.10.10.1",\n  "port": 19013,\n  "log_level": "INFO"\n}',
        )

    def _url(self, path):
        return f'/api/config-mgmt/{path}'


# =============================================================
# 1. 配置文件更新
# =============================================================

class TestConfigFileUpdate(ConfigMgmtTestBase):

    def test_update_config_content(self):
        """PUT 更新配置内容，响应 code=200，DB 中内容已更新"""
        new_content = {'host': '10.10.10.1', 'port': 19013, 'log_level': 'DEBUG'}
        resp = self.client.put(
            self._url(f'configs/{self.config_file.id}/'),
            data={'content': new_content},
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['code'], 200)

        self.config_file.refresh_from_db()
        self.assertEqual(self.config_file.content['log_level'], 'DEBUG')

    def test_update_config_preserves_raw_content(self):
        """PUT 时传入 raw_content，数据库中 raw_content 应被更新保留"""
        raw = '{\n  "host": "10.10.10.1",\n  "port": 19013,\n  "log_level": "DEBUG"\n}'
        resp = self.client.put(
            self._url(f'configs/{self.config_file.id}/'),
            data={
                'content': {'host': '10.10.10.1', 'port': 19013, 'log_level': 'DEBUG'},
                'raw_content': raw,
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        self.config_file.refresh_from_db()
        self.assertEqual(self.config_file.raw_content, raw)

    def test_update_without_raw_content_does_not_clear_existing(self):
        """PUT 不传 raw_content 时，不应清空已有 raw_content"""
        original_raw = self.config_file.raw_content
        resp = self.client.put(
            self._url(f'configs/{self.config_file.id}/'),
            data={'content': {'host': '10.10.10.1', 'port': 9999}},
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        self.config_file.refresh_from_db()
        # raw_content 应保持不变（update_fields 只更新 content）
        self.assertEqual(self.config_file.raw_content, original_raw)

    def test_update_creates_history_snapshot(self):
        """PUT 更新配置前，应自动创建 ConfigHistory 快照"""
        before_count = ConfigHistory.objects.filter(config_file=self.config_file).count()
        self.client.put(
            self._url(f'configs/{self.config_file.id}/'),
            data={'content': {'host': '10.10.10.1', 'port': 12345}},
            format='json',
        )
        after_count = ConfigHistory.objects.filter(config_file=self.config_file).count()
        self.assertEqual(after_count, before_count + 1)

    def test_update_snapshot_stores_old_content(self):
        """快照中保存的是更新前的旧内容"""
        old_content = self.config_file.content.copy()
        self.client.put(
            self._url(f'configs/{self.config_file.id}/'),
            data={'content': {'host': 'new-host', 'port': 1}},
            format='json',
        )
        snapshot = ConfigHistory.objects.filter(
            config_file=self.config_file, action='save'
        ).order_by('-id').first()
        self.assertIsNotNone(snapshot)
        self.assertEqual(snapshot.content, old_content)


# =============================================================
# 2. 批量修改
# =============================================================

class TestBatchUpdate(ConfigMgmtTestBase):

    def setUp(self):
        super().setUp()
        # 创建第二个实例和配置文件
        self.instance2 = ConfigInstance.objects.create(
            service_type=self.service_type,
            name='10.10.10.2_19013',
            host_ip='10.10.10.2',
            port=19013,
            install_dir='/datayes/app/bin',
            backups_dir='/datayes/app/backups',
            service_name='forward',
        )
        self.config_file2 = ConfigFile.objects.create(
            instance=self.instance2,
            filename='feeder_handler.cfg',
            content={'host': '10.10.10.2', 'port': 19013, 'log_level': 'INFO'},
        )

    def test_batch_update_same_key_across_instances(self):
        """batch_update 应同时修改多个实例的同一 key"""
        resp = self.client.post(
            self._url('configs/batch_update/'),
            data={
                'instance_ids': [self.instance.id, self.instance2.id],
                'filename': 'feeder_handler.cfg',
                'updates': {'log_level': 'WARNING'},
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['data']['updated_count'], 2)

        self.config_file.refresh_from_db()
        self.config_file2.refresh_from_db()
        self.assertEqual(self.config_file.content['log_level'], 'WARNING')
        self.assertEqual(self.config_file2.content['log_level'], 'WARNING')

    def test_batch_update_delete_key(self):
        """batch_update 中 value='__DELETE__' 应删除该 key"""
        resp = self.client.post(
            self._url('configs/batch_update/'),
            data={
                'instance_ids': [self.instance.id],
                'filename': 'feeder_handler.cfg',
                'updates': {'log_level': '__DELETE__'},
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        self.config_file.refresh_from_db()
        self.assertNotIn('log_level', self.config_file.content)

    def test_batch_update_creates_history_snapshots(self):
        """batch_update 应为每个实例创建历史快照"""
        before = ConfigHistory.objects.count()
        self.client.post(
            self._url('configs/batch_update/'),
            data={
                'instance_ids': [self.instance.id, self.instance2.id],
                'filename': 'feeder_handler.cfg',
                'updates': {'log_level': 'ERROR'},
            },
            format='json',
        )
        after = ConfigHistory.objects.count()
        self.assertEqual(after - before, 2)

    def test_batch_update_missing_params_returns_400(self):
        """缺少 instance_ids 或 filename 应返回 400"""
        resp = self.client.post(
            self._url('configs/batch_update/'),
            data={'filename': 'feeder_handler.cfg'},
            format='json',
        )
        self.assertEqual(resp.status_code, 400)


# =============================================================
# 3. 文本查找替换
# =============================================================

class TestTextReplace(ConfigMgmtTestBase):

    def test_text_replace_preview_does_not_save(self):
        """preview=true 时，替换结果不保存到数据库"""
        original_content = self.config_file.content.copy()
        resp = self.client.post(
            self._url('configs/text_replace/'),
            data={
                'instance_ids': [self.instance.id],
                'filename': 'feeder_handler.cfg',
                'search_text': 'INFO',
                'replace_text': 'DEBUG',
                'preview': True,
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()['data']
        self.assertTrue(data['preview'])
        # 数据库内容不变
        self.config_file.refresh_from_db()
        self.assertEqual(self.config_file.content, original_content)

    def test_text_replace_preview_returns_diff(self):
        """preview=true 时，响应应包含 diff_preview"""
        resp = self.client.post(
            self._url('configs/text_replace/'),
            data={
                'instance_ids': [self.instance.id],
                'filename': 'feeder_handler.cfg',
                'search_text': 'INFO',
                'replace_text': 'DEBUG',
                'preview': True,
            },
            format='json',
        )
        results = resp.json()['data']['results']
        self.assertTrue(len(results) > 0)
        changed = [r for r in results if r.get('changed')]
        self.assertTrue(len(changed) > 0)
        self.assertIn('diff_preview', changed[0])

    def test_text_replace_save_updates_db(self):
        """preview=false 时，替换应保存到数据库"""
        resp = self.client.post(
            self._url('configs/text_replace/'),
            data={
                'instance_ids': [self.instance.id],
                'filename': 'feeder_handler.cfg',
                'search_text': 'INFO',
                'replace_text': 'DEBUG',
                'preview': False,
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        self.config_file.refresh_from_db()
        self.assertEqual(self.config_file.content['log_level'], 'DEBUG')

    def test_text_replace_no_match_returns_unchanged(self):
        """没有匹配文本时，changed=False，数据不变"""
        resp = self.client.post(
            self._url('configs/text_replace/'),
            data={
                'instance_ids': [self.instance.id],
                'filename': 'feeder_handler.cfg',
                'search_text': 'NOT_EXIST_TEXT_XYZ',
                'replace_text': 'something',
                'preview': False,
            },
            format='json',
        )
        data = resp.json()['data']
        self.assertEqual(data['changed_count'], 0)

    def test_text_replace_missing_search_text_returns_400(self):
        """search_text 为空时应返回 400"""
        resp = self.client.post(
            self._url('configs/text_replace/'),
            data={
                'instance_ids': [self.instance.id],
                'filename': 'feeder_handler.cfg',
                'search_text': '',
                'replace_text': 'DEBUG',
                'preview': True,
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 400)


# =============================================================
# 4. Git 提交（Mock GitLab API）
# =============================================================

class TestGitCommit(ConfigMgmtTestBase):

    @patch('api.viewsets.config_mgmt_viewset._commit_to_gitlab')
    def test_git_commit_success(self, mock_commit):
        """git_commit 调用 _commit_to_gitlab，响应包含成功信息"""
        mock_commit.return_value = [
            {'file': 'forward/10.10.10.1_19013/feeder_handler.cfg', 'status': 'ok'}
        ]
        resp = self.client.post(
            self._url('configs/git_commit/'),
            data={
                'config_ids': [self.config_file.id],
                'message': 'test commit',
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()['data']
        self.assertIn('1/1', data['message'])
        mock_commit.assert_called_once()

    @patch('api.viewsets.config_mgmt_viewset._commit_to_gitlab')
    def test_git_commit_partial_failure(self, mock_commit):
        """部分文件提交失败时，message 应反映实际成功数量"""
        mock_commit.return_value = [
            {'file': 'f1.cfg', 'status': 'ok'},
            {'file': 'f2.cfg', 'status': 'error', 'detail': 'GitLab error'},
        ]
        resp = self.client.post(
            self._url('configs/git_commit/'),
            data={'config_ids': [self.config_file.id], 'message': 'test'},
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()['data']
        self.assertIn('1/2', data['message'])

    def test_git_commit_without_config_ids_returns_400(self):
        """不传 config_ids 应返回 400"""
        resp = self.client.post(
            self._url('configs/git_commit/'),
            data={'message': 'empty commit'},
            format='json',
        )
        self.assertEqual(resp.status_code, 400)


# =============================================================
# 5. 配置部署（Mock Ansible subprocess）
# =============================================================

class TestConfigDeploy(ConfigMgmtTestBase):

    def _mock_run_deploy_task(self, task_id):
        """同步执行部署任务（替换异步线程）"""
        from api.viewsets.config_mgmt_viewset import _run_deploy_task
        _run_deploy_task(task_id)

    @patch('subprocess.run')
    @patch('threading.Thread')
    def test_create_deploy_task_returns_task_id(self, mock_thread, mock_subproc):
        """POST /deploy/ 应返回 task_id，任务状态初始为 pending"""
        mock_thread.return_value = MagicMock()
        resp = self.client.post(
            self._url('deploy/'),
            data={'instance_ids': [self.instance.id]},
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()['data']
        self.assertIn('task_id', data)
        self.assertEqual(data['status'], 'pending')

    @patch('subprocess.run')
    @patch('threading.Thread')
    def test_deploy_task_creates_snapshot_before_deploy(self, mock_thread, mock_subproc):
        """部署前应为所有涉及配置文件创建 deploy_snapshot 快照"""
        before = ConfigHistory.objects.filter(action='deploy_snapshot').count()
        mock_thread.return_value = MagicMock()
        self.client.post(
            self._url('deploy/'),
            data={'instance_ids': [self.instance.id]},
            format='json',
        )
        after = ConfigHistory.objects.filter(action='deploy_snapshot').count()
        self.assertGreater(after, before)

    @patch('threading.Thread')
    def test_get_deploy_task_detail(self, mock_thread):
        """GET /deploy/{id}/ 应返回任务详情"""
        mock_thread.return_value = MagicMock()
        post_resp = self.client.post(
            self._url('deploy/'),
            data={'instance_ids': [self.instance.id]},
            format='json',
        )
        task_id = post_resp.json()['data']['task_id']
        resp = self.client.get(self._url(f'deploy/{task_id}/'))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()['data']
        self.assertEqual(data['id'], task_id)

    @patch('threading.Thread')
    def test_get_nonexistent_deploy_task_returns_404(self, mock_thread):
        """查询不存在的部署任务应返回 404"""
        resp = self.client.get(self._url('deploy/99999/'))
        self.assertEqual(resp.status_code, 404)

    def test_deploy_missing_instance_ids_returns_400(self):
        """不传 instance_ids 应返回 400"""
        resp = self.client.post(
            self._url('deploy/'),
            data={},
            format='json',
        )
        self.assertEqual(resp.status_code, 400)


# =============================================================
# 6. 部署回滚
# =============================================================

class TestDeployRollback(ConfigMgmtTestBase):

    def setUp(self):
        super().setUp()
        # 手动创建部署任务和快照
        self.task = ConfigDeployTask.objects.create(
            operator='testadmin',
            status='success',
        )
        self.task.instances.set([self.instance])
        # 创建快照（模拟部署前内容）
        self.snapshot = ConfigHistory.objects.create(
            config_file=self.config_file,
            content={'host': '10.10.10.1', 'port': 19013, 'log_level': 'INFO'},
            action='deploy_snapshot',
            operator='testadmin',
        )
        self.task.snapshots.set([self.snapshot])
        # 修改当前内容（模拟部署后变化）
        self.config_file.content = {'host': '10.10.10.1', 'port': 19013, 'log_level': 'ERROR'}
        self.config_file.save()

    def test_rollback_restores_config_content(self):
        """回滚后，配置文件内容应恢复到快照中保存的值"""
        resp = self.client.post(self._url(f'deploy/{self.task.id}/rollback/'))
        self.assertEqual(resp.status_code, 200)
        self.config_file.refresh_from_db()
        self.assertEqual(self.config_file.content['log_level'], 'INFO')

    def test_rollback_returns_rolled_back_files(self):
        """回滚响应应包含回滚的文件列表"""
        resp = self.client.post(self._url(f'deploy/{self.task.id}/rollback/'))
        data = resp.json()['data']
        self.assertIn('files', data)
        self.assertIn('feeder_handler.cfg', data['files'])

    def test_rollback_nonexistent_task_returns_404(self):
        """回滚不存在的任务应返回 404"""
        resp = self.client.post(self._url('deploy/99999/rollback/'))
        self.assertEqual(resp.status_code, 404)

    def test_rollback_task_without_snapshot_returns_400(self):
        """无快照的任务回滚应返回 400"""
        empty_task = ConfigDeployTask.objects.create(
            operator='testadmin', status='success'
        )
        resp = self.client.post(self._url(f'deploy/{empty_task.id}/rollback/'))
        self.assertEqual(resp.status_code, 400)


# =============================================================
# 7. 配置历史
# =============================================================

class TestConfigHistory(ConfigMgmtTestBase):

    def setUp(self):
        super().setUp()
        # 创建几条历史记录
        for i in range(3):
            ConfigHistory.objects.create(
                config_file=self.config_file,
                content={'host': '10.10.10.1', 'version': i},
                action='save',
                operator='testadmin',
            )

    def test_list_history_returns_records(self):
        """GET /history/?config_id=X 应返回历史列表"""
        resp = self.client.get(
            self._url('history/'),
            {'config_id': self.config_file.id},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()['data']
        self.assertGreaterEqual(data['total'], 3)

    def test_get_history_detail(self):
        """GET /history/{id}/ 应返回历史详情含 content"""
        history = ConfigHistory.objects.filter(config_file=self.config_file).first()
        resp = self.client.get(self._url(f'history/{history.id}/'))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()['data']
        self.assertIn('content', data)

    def test_rollback_to_history_version(self):
        """POST /history/{id}/rollback/ 应将配置内容回滚到该历史版本"""
        history = ConfigHistory.objects.filter(config_file=self.config_file).first()
        target_content = history.content.copy()
        resp = self.client.post(self._url(f'history/{history.id}/rollback/'))
        self.assertEqual(resp.status_code, 200)
        self.config_file.refresh_from_db()
        self.assertEqual(self.config_file.content, target_content)


# =============================================================
# 8. 辅助函数单元测试
# =============================================================

class TestHelperFunctions(TestCase):
    """测试 set_nested_value / _delete_nested_value 等纯函数"""

    def test_set_nested_value_simple_key(self):
        from api.viewsets.config_mgmt_viewset import set_nested_value
        data = {'a': 1, 'b': 2}
        set_nested_value(data, 'b', 99)
        self.assertEqual(data['b'], 99)

    def test_set_nested_value_dotted_key(self):
        from api.viewsets.config_mgmt_viewset import set_nested_value
        data = {'db': {'host': 'localhost', 'port': 5432}}
        set_nested_value(data, 'db.port', 3306)
        self.assertEqual(data['db']['port'], 3306)

    def test_set_nested_value_creates_missing_intermediate(self):
        from api.viewsets.config_mgmt_viewset import set_nested_value
        data = {}
        set_nested_value(data, 'a.b.c', 'value')
        self.assertEqual(data['a']['b']['c'], 'value')

    def test_delete_nested_value(self):
        from api.viewsets.config_mgmt_viewset import _delete_nested_value
        data = {'host': '10.10.10.1', 'port': 8080, 'debug': True}
        _delete_nested_value(data, 'debug')
        self.assertNotIn('debug', data)

    def test_delete_nested_dotted_key(self):
        from api.viewsets.config_mgmt_viewset import _delete_nested_value
        data = {'db': {'host': 'localhost', 'password': 'secret'}}
        _delete_nested_value(data, 'db.password')
        self.assertNotIn('password', data['db'])
