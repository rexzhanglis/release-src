"""
author: zhixiong.zeng
python version: 3
time: 2021/10/11 10:26
"""
import datetime
import os

from django.forms import model_to_dict
from django.utils import timezone
from rest_framework import viewsets, serializers
from rest_framework.decorators import action

import api.models as api_models
from api.exception import CustomRuntimeException
from api.models import ReleaseDetail, ReleasePlan, MdlReleaseContent
from api.permissions.edit_permission import ReleaseDetailEditPermission
from api.services.mdl_release_detail_service import MdlReleaseDetailService
from api.services.rancher_release_detail_service import RancherReleaseDetailService
from common.utils.apiutil import ApiResponse

# 标记 ReleaseDetail 处于"运行中"的状态值
_MDL_RUNNING_STATUSES = ["升级中", "发布中"]


class ReleaseDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReleaseDetail
        fields = '__all__'


class ReleaseDetailViewSet(viewsets.ModelViewSet):
    queryset = ReleaseDetail.objects.all()
    serializer_class = ReleaseDetailSerializer
    permission_classes = [ReleaseDetailEditPermission]

    @action(detail=False, methods=["get"], url_path="get_release_detail_info")
    def get_release_detail_info(self, request, *args, **kwargs):
        """
        获取发布的详细信息。

        log 字段来源：
          - 优先读文件 {RELEASE_LOG_DIR}/release_detail_{id}.log
          - 文件不存在时回退到 DB log 列（兼容旧记录）
        """
        name = request.query_params.get("name")
        if name:
            release_plan = ReleasePlan.objects.get(name=name)
            obj = ReleaseDetail.objects.filter(release_plan=release_plan)
            if obj:
                detail = obj[0]
                data = model_to_dict(detail)
                data["created_time"] = detail.created_time
                data["last_updated_time"] = detail.last_updated_time
                data["step_status"] = release_plan.get_all_release_contents_status()
                data["log"] = self._read_release_log(detail)
                return ApiResponse(data=data)
            return ApiResponse(data=None)
        raise CustomRuntimeException("请输入name字段")

    @staticmethod
    def _read_release_log(detail):
        """文件存在则读文件，否则回退 DB log 列。读异常一律回退。"""
        log_path = os.path.join(
            api_models.RELEASE_LOG_DIR, "release_detail_{}.log".format(detail.id),
        )
        try:
            with open(log_path, encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            return detail.log or ""
        except Exception:
            # 读异常时回退 DB 列，不影响整个接口
            return detail.log or ""

    @action(detail=False, methods=["post"], url_path="deploy")
    def deploy(self, request, *args, **kwargs):
        """
        发布

        MDL 并发准入控制（按 (fqdn, service_name) 互斥）：
          1) 同一计划在跑 → 拦（幂等防双击）
          2) 不同计划但目标 (host, service) 与运行中的 MDL 计划重叠 → 拦
          3) 完全不重叠 → 允许并发
        """
        name = request.data["name"]
        plan = ReleasePlan.objects.get(name=name)
        if plan.project == 'MDL':
            self._check_mdl_deploy_conflict(plan)
        self._get_release_service(name=name)(name=name, user=request.user).start()
        return ApiResponse(data="success")

    @staticmethod
    def _extract_targets(plan):
        """
        从 plan 的 MdlReleaseContent 中提取仍占用资源的 (fqdn, service_name) 集合。
          - is_release=True：本次需要发布的模块
          - status != 'success'：尚未完成的模块（success 视为已释放占用）
        release_object 格式：fqdn__ip__service_name；不规范条目静默忽略。
        """
        targets = set()
        qs = MdlReleaseContent.objects.filter(
            release_plan=plan, is_release=True,
        ).exclude(status='success').values_list('release_object', flat=True)
        for ro in qs:
            parts = (ro or '').split('__')
            if len(parts) == 3:
                targets.add((parts[0], parts[2]))
        return targets

    @classmethod
    def _check_mdl_deploy_conflict(cls, plan):
        """
        发起 MDL 部署前的并发准入控制。冲突时抛 CustomRuntimeException。
        """
        # 规则1：同一计划在跑时再次 deploy → 拦
        if ReleaseDetail.objects.filter(
                release_plan=plan, status__in=_MDL_RUNNING_STATUSES).exists():
            raise CustomRuntimeException(msg="该发布计划正在执行中，请勿重复点击")

        # 规则2/3：跨计划检查 (host, service) 是否与运行中 MDL 计划重叠
        new_targets = cls._extract_targets(plan)
        if not new_targets:
            return

        running_plans = ReleasePlan.objects.filter(
            project='MDL',
            releasedetail__status__in=_MDL_RUNNING_STATUSES,
        ).exclude(id=plan.id).distinct()

        conflicts = []
        for rp in running_plans:
            overlap = new_targets & cls._extract_targets(rp)
            for host, svc in overlap:
                conflicts.append((rp.name, host, svc))

        if conflicts:
            detail = "; ".join(
                "{}({}/{})".format(p, h, s) for p, h, s in conflicts
            )
            raise CustomRuntimeException(
                msg="以下目标正在被其他发布计划占用，请等待完成后再试: " + detail
            )


    @action(detail=False, methods=["post"], url_path="suspend")
    def suspend(self, request, *args, **kwargs):
        """
        暂停
        """
        self._get_release_service(name=request.data["name"])(name=request.data["name"], user=request.user).suspend()
        return ApiResponse(data="success")

    @action(detail=False, methods=["post"], url_path="re_deploy")
    def re_deploy(self, request, *args, **kwargs):
        """
        再发布
        """
        self._get_release_service(name=request.data["name"])(name=request.data["name"], user=request.user).re_deploy()
        return ApiResponse(data="success")

    @action(detail=False, methods=["post"], url_path="fail_skip")
    def fail_skip(self, request, *args, **kwargs):
        """
        失败跳过按钮 跳过模块的下一个模块开始升级
        """
        self._get_release_service(name=request.data["name"])(name=request.data["name"], user=request.user).fail_skip()
        return ApiResponse(data="success")

    @action(detail=False, methods=["post"], url_path="fail_retry")
    def fail_retry(self, request, *args, **kwargs):
        """
        失败重试  会从失败的位置继续升级
        """
        self._get_release_service(name=request.data["name"])(name=request.data["name"], user=request.user).fail_retry()
        return ApiResponse(data="success")

    @action(detail=False, methods=["post"], url_path="rollback")
    def rollback(self, request, *args, **kwargs):
        """
         回滚操作  倒叙一起回退到升级前的版本
         超过7天后，回滚操作将被禁止  回滚禁止是出于安全考虑
        """
        release_plan = ReleasePlan.objects.get(name=request.data["name"])
        # mdl不支持回滚操作
        if release_plan.project == 'MDL':
            raise CustomRuntimeException(msg="MDL暂时不支持回滚，可重建发布计划重发布")
        # 超过7天不支持回滚操作
        release_detail = ReleaseDetail.objects.get(release_plan=release_plan)
        if release_detail.last_updated_time + datetime.timedelta(
                days=7) > timezone.now():
            self._get_release_service(name=request.data["name"])(name=request.data["name"], user=request.user).rollback()
            return ApiResponse(data="success")
        raise CustomRuntimeException(msg="超过7天后，回滚操作将被禁止")

    def _get_release_service(self, name):
        """
        根据不同的项目类型，返回不同的实例 不对外提供api
        :return:
        """
        project = ReleasePlan.objects.get(name=name).project
        return MdlReleaseDetailService if project == "MDL" else RancherReleaseDetailService
