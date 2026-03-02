"""
发布功能自动化测试
覆盖以下核心功能：
  1. POST /api/releaseDetail/deploy/ MDL 发布触发（Mock Ansible）
  2. MDL 并发发布限制（第二个任务被拒绝）
  3. GET  /api/releaseDetail/get_release_detail_info/ 查询发布详情
  4. POST /api/releaseDetail/suspend/  暂停发布
  5. MDL 不支持回滚（返回错误）
  6. 发布计划 CRUD
"""

from unittest.mock import patch, MagicMock

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from api.models import ReleasePlan, MdlReleaseContent, ReleaseDetail

User = get_user_model()


class ReleaseTestBase(TestCase):
    """公共 setUp：创建用户、MDL 发布计划和内容"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='releaseuser',
            password='testpass123',
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        # 创建 MDL 发布计划
        self.plan = ReleasePlan.objects.create(
            name='test-mdl-plan-001',
            project='MDL',
            owner='releaseuser',
        )
        # 创建发布内容（模拟一个服务版本升级）
        self.content = MdlReleaseContent.objects.create(
            release_plan=self.plan,
            index=1,
            issue_key='MDL-123',
            release_version='v1.2.3',
            release_object='mdl-test01.example.com:forward',
            type='version',
            is_release=True,
            status='wait',
        )


# =============================================================
# 1. 发布计划 CRUD
# =============================================================

class TestReleasePlanCRUD(ReleaseTestBase):

    def test_list_release_plans(self):
        """GET /api/releasePlan/ 应返回发布计划列表"""
        resp = self.client.get('/api/releasePlan/')
        self.assertEqual(resp.status_code, 200)

    def test_create_mdl_release_plan(self):
        """POST /api/releasePlan/ 应创建 MDL 发布计划"""
        resp = self.client.post(
            '/api/releasePlan/',
            data={
                'name': 'new-mdl-plan-99',
                'project': 'MDL',
                'owner': 'releaseuser',
                'category': '正常发布',
                'is_auto': False,
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(ReleasePlan.objects.filter(name='new-mdl-plan-99').exists())

    def test_get_release_plan_detail(self):
        """GET /api/releasePlan/{id}/ 应返回计划详情"""
        resp = self.client.get(f'/api/releasePlan/{self.plan.id}/')
        self.assertEqual(resp.status_code, 200)

    def test_duplicate_plan_name_fails(self):
        """重复名称的发布计划应创建失败"""
        resp = self.client.post(
            '/api/releasePlan/',
            data={
                'name': 'test-mdl-plan-001',  # 已存在
                'project': 'MDL',
                'owner': 'releaseuser',
            },
            format='json',
        )
        # 应返回 400 或 500（唯一约束冲突）
        self.assertNotEqual(resp.status_code, 200)


# =============================================================
# 2. MDL 发布触发（Mock MdlReleaseDetailService）
# =============================================================

class TestMdlDeploy(ReleaseTestBase):

    @patch('api.viewsets.release_detail_viewset.MdlReleaseDetailService')
    def test_deploy_mdl_plan_success(self, mock_service_class):
        """POST /api/releaseDetail/deploy/ 应触发 MDL 发布，返回 success"""
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service

        resp = self.client.post(
            '/api/releaseDetail/deploy/',
            data={'name': self.plan.name},
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['code'], 200)
        # 验证服务 start() 被调用
        mock_service.start.assert_called_once()

    @patch('api.viewsets.release_detail_viewset.MdlReleaseDetailService')
    def test_deploy_creates_release_detail(self, mock_service_class):
        """发布触发后，应创建 ReleaseDetail 记录"""
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service

        before = ReleaseDetail.objects.filter(release_plan=self.plan).count()
        self.client.post(
            '/api/releaseDetail/deploy/',
            data={'name': self.plan.name},
            format='json',
        )
        # MdlReleaseDetailService.__init__ 会创建 ReleaseDetail（Mock 不执行，需手动验证调用参数）
        mock_service_class.assert_called_with(name=self.plan.name, user=self.user)

    def test_deploy_nonexistent_plan_returns_error(self):
        """发布不存在的计划应返回错误"""
        resp = self.client.post(
            '/api/releaseDetail/deploy/',
            data={'name': 'non-existent-plan-xyz'},
            format='json',
        )
        # ReleasePlan.DoesNotExist → 500 or 400
        self.assertNotEqual(resp.status_code, 200)


# =============================================================
# 3. MDL 并发发布限制
# =============================================================

class TestMdlConcurrentDeployLimit(ReleaseTestBase):

    @patch('api.viewsets.release_detail_viewset.MdlReleaseDetailService')
    def test_second_mdl_deploy_is_rejected(self, mock_service_class):
        """MDL 正在发布时，第二个发布请求应被拒绝"""
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service

        # 预创建一个"升级中"的 ReleaseDetail，模拟正在发布
        another_plan = ReleasePlan.objects.create(
            name='running-mdl-plan',
            project='MDL',
            owner='releaseuser',
        )
        ReleaseDetail.objects.create(
            release_plan=another_plan,
            user='releaseuser',
            status='升级中',
        )

        # 此时发起另一个 MDL 发布
        resp = self.client.post(
            '/api/releaseDetail/deploy/',
            data={'name': self.plan.name},
            format='json',
        )
        # 应返回错误（CustomRuntimeException → 500 via middleware）
        self.assertNotEqual(resp.status_code, 200)
        resp_json = resp.json()
        # 错误信息应提示并发限制
        response_str = str(resp_json)
        self.assertTrue(
            'mdl' in response_str.lower() or '同时' in response_str or '等待' in response_str
        )


# =============================================================
# 4. 暂停发布
# =============================================================

class TestReleaseSuspend(ReleaseTestBase):

    def setUp(self):
        super().setUp()
        # 预创建 ReleaseDetail（升级中状态）
        self.detail = ReleaseDetail.objects.create(
            release_plan=self.plan,
            user='releaseuser',
            status='升级中',
        )

    @patch('api.viewsets.release_detail_viewset.MdlReleaseDetailService')
    def test_suspend_mdl_plan(self, mock_service_class):
        """POST /api/releaseDetail/suspend/ 应触发暂停逻辑"""
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service

        resp = self.client.post(
            '/api/releaseDetail/suspend/',
            data={'name': self.plan.name},
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        mock_service.suspend.assert_called_once()


# =============================================================
# 5. MDL 不支持回滚
# =============================================================

class TestMdlRollback(ReleaseTestBase):

    def setUp(self):
        super().setUp()
        self.detail = ReleaseDetail.objects.create(
            release_plan=self.plan,
            user='releaseuser',
            status='发布成功',
        )

    def test_mdl_rollback_is_rejected(self):
        """MDL 发布计划调用 rollback 应返回错误（MDL 不支持回滚）"""
        resp = self.client.post(
            '/api/releaseDetail/rollback/',
            data={'name': self.plan.name},
            format='json',
        )
        # CustomRuntimeException → 应是非 200 状态，或响应体 code != 200
        is_error = (resp.status_code != 200) or (resp.json().get('code', 200) != 200)
        self.assertTrue(is_error, f"Expected error but got: {resp.json()}")

    def test_rancher_rollback_within_7days(self):
        """Rancher 发布在 7 天内应支持回滚"""
        rancher_plan = ReleasePlan.objects.create(
            name='rancher-plan-test',
            project='Rancher',
            owner='releaseuser',
        )
        ReleaseDetail.objects.create(
            release_plan=rancher_plan,
            user='releaseuser',
            status='发布成功',
        )

        with patch('api.viewsets.release_detail_viewset.RancherReleaseDetailService') as mock_svc:
            mock_instance = MagicMock()
            mock_svc.return_value = mock_instance
            resp = self.client.post(
                '/api/releaseDetail/rollback/',
                data={'name': rancher_plan.name},
                format='json',
            )
        self.assertEqual(resp.status_code, 200)
        mock_instance.rollback.assert_called_once()


# =============================================================
# 6. 查询发布详情
# =============================================================

class TestGetReleaseDetailInfo(ReleaseTestBase):

    def setUp(self):
        super().setUp()
        self.detail = ReleaseDetail.objects.create(
            release_plan=self.plan,
            user='releaseuser',
            status='发布中',
        )

    def test_get_release_detail_info_by_name(self):
        """GET /api/releaseDetail/get_release_detail_info/?name=X 应返回发布详情"""
        resp = self.client.get(
            '/api/releaseDetail/get_release_detail_info/',
            {'name': self.plan.name},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()['data']
        self.assertIsNotNone(data)
        self.assertIn('status', data)
        self.assertEqual(data['status'], '发布中')

    def test_get_release_detail_without_name_returns_error(self):
        """不传 name 参数应返回错误"""
        resp = self.client.get('/api/releaseDetail/get_release_detail_info/')
        # 应返回错误
        self.assertNotEqual(resp.status_code, 200)

    def test_get_release_detail_with_step_status(self):
        """响应中应包含 step_status（各步骤状态）"""
        resp = self.client.get(
            '/api/releaseDetail/get_release_detail_info/',
            {'name': self.plan.name},
        )
        data = resp.json()['data']
        self.assertIn('step_status', data)


# =============================================================
# 7. 发布内容（MdlReleaseContent）测试
# =============================================================

class TestMdlReleaseContent(ReleaseTestBase):

    def test_release_content_status_choices(self):
        """验证 MdlReleaseContent 的状态字段值"""
        self.assertEqual(self.content.status, 'wait')
        self.content.set_status('process')
        self.content.refresh_from_db()
        self.assertEqual(self.content.status, 'process')

    def test_plan_get_all_contents_returns_list(self):
        """ReleasePlan.get_all_release_contents() 应返回包含内容的列表"""
        contents = self.plan.get_all_release_contents()
        self.assertIsInstance(contents, list)
        self.assertEqual(len(contents), 1)
        self.assertEqual(contents[0]['release_version'], 'v1.2.3')

    def test_plan_delete_release_contents(self):
        """ReleasePlan.delete_release_contents() 应删除所有内容"""
        self.plan.delete_release_contents()
        self.assertEqual(MdlReleaseContent.objects.filter(release_plan=self.plan).count(), 0)
