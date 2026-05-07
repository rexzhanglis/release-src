"""
ReleaseDetailViewSet 并发发布准入控制 单测

直接测试 viewset 上的策略 helper（绕过 APIClient/URL 解析），
避免触发 test_release.py 中已知的 django_cas_ng 环境问题。

业务规则（仅 MDL）：
  1. 同一发布计划在跑时，再次 deploy → 拦（幂等防双击）
  2. 不同计划但目标 (host, service) 与运行中的计划重叠 → 拦
  3. 不同计划且目标 (host, service) 完全不重叠 → 允许并发
  4. 重叠目标在对方计划中已 status='success'（占用已释放） → 允许并发

release_object 格式：fqdn__ip__service_name；互斥粒度取 (fqdn, service_name)，
IP 不参与（避免同机不同 IP 写法不一致漏判）。
"""

from django.test import TestCase

from api.exception import CustomRuntimeException
from api.models import ReleasePlan, MdlReleaseContent, ReleaseDetail
from api.viewsets.release_detail_viewset import ReleaseDetailViewSet


def _make_plan_with_targets(name, targets):
    """
    创建一个 MDL 发布计划，含若干模块。
    targets: [(release_object, status), ...]
    """
    plan = ReleasePlan.objects.create(name=name, project='MDL', owner='u')
    for idx, (release_object, status) in enumerate(targets, start=1):
        MdlReleaseContent.objects.create(
            release_plan=plan,
            index=idx,
            issue_key='MDL-X',
            release_version='v0.0.1',
            release_object=release_object,
            type='version',
            is_release=True,
            status=status,
        )
    return plan


def _mark_running(plan):
    """把 plan 标记为正在跑（创建 status='升级中' 的 ReleaseDetail）"""
    return ReleaseDetail.objects.create(release_plan=plan, user='u', status='升级中')


class TestMdlConcurrentDeployHelper(TestCase):
    """ReleaseDetailViewSet._check_mdl_deploy_conflict 策略测试"""

    def setUp(self):
        # 待发布的目标计划：hostA/svcA
        self.plan = _make_plan_with_targets(
            'plan-target',
            [('hostA__1.2.3.4__svcA', 'wait')],
        )

    # 规则1：同一计划重复 deploy → 拦
    def test_same_plan_already_running_is_rejected(self):
        _mark_running(self.plan)
        with self.assertRaises(CustomRuntimeException) as ctx:
            ReleaseDetailViewSet._check_mdl_deploy_conflict(self.plan)
        self.assertIn('该发布计划正在执行中', str(ctx.exception.message))

    # 规则2：不同计划但 (host, svc) 重叠 → 拦，错误信息含冲突详情
    def test_overlapping_target_is_rejected(self):
        other = _make_plan_with_targets(
            'plan-conflict',
            [('hostA__9.9.9.9__svcA', 'process')],   # IP 不同也算冲突
        )
        _mark_running(other)
        with self.assertRaises(CustomRuntimeException) as ctx:
            ReleaseDetailViewSet._check_mdl_deploy_conflict(self.plan)
        msg = str(ctx.exception.message)
        self.assertIn('hostA', msg)
        self.assertIn('svcA', msg)
        self.assertIn('plan-conflict', msg)

    # 规则3：不同计划且目标完全不重叠 → 通过
    def test_non_overlapping_target_is_allowed(self):
        other = _make_plan_with_targets(
            'plan-allow',
            [('hostB__1.1.1.1__svcB', 'process')],
        )
        _mark_running(other)
        # 不应抛异常
        ReleaseDetailViewSet._check_mdl_deploy_conflict(self.plan)

    # 规则4：重叠目标在对方计划中已 success（占用已释放） → 通过
    def test_overlapping_target_already_success_is_allowed(self):
        other = _make_plan_with_targets(
            'plan-partly-done',
            [
                ('hostA__9.9.9.9__svcA', 'success'),  # 重叠但已释放
                ('hostZ__1.1.1.1__svcZ', 'process'),  # 不重叠，对方还在跑
            ],
        )
        _mark_running(other)
        # 不应抛异常
        ReleaseDetailViewSet._check_mdl_deploy_conflict(self.plan)

    # 边界：对方计划虽有重叠目标，但 ReleaseDetail 状态非升级中/发布中（已结束） → 通过
    def test_finished_other_plan_does_not_block(self):
        other = _make_plan_with_targets(
            'plan-finished',
            [('hostA__9.9.9.9__svcA', 'success')],
        )
        ReleaseDetail.objects.create(
            release_plan=other, user='u', status='发布成功',
        )
        # 不应抛异常
        ReleaseDetailViewSet._check_mdl_deploy_conflict(self.plan)
