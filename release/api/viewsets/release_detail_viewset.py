"""
author: zhixiong.zeng
python version: 3
time: 2021/10/11 10:26
"""
import datetime

from django.forms import model_to_dict
from django.utils import timezone
from rest_framework import viewsets, serializers
from rest_framework.decorators import action

from api.exception import CustomRuntimeException
from api.models import ReleaseDetail, ReleasePlan
from api.permissions.edit_permission import ReleaseDetailEditPermission
from api.services.mdl_release_detail_service import MdlReleaseDetailService
from api.services.rancher_release_detail_service import RancherReleaseDetailService
from common.utils.apiutil import ApiResponse


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
        获取发布的详细信息
        """
        name = request.query_params.get("name")
        if name:
            release_plan = ReleasePlan.objects.get(name=name)
            obj = ReleaseDetail.objects.filter(release_plan=release_plan)
            if obj:
                data = model_to_dict(obj[0])
                data["created_time"] = obj[0].created_time
                data["last_updated_time"] = obj[0].last_updated_time
                data["step_status"] = release_plan.get_all_release_contents_status()
                return ApiResponse(data=data)
            return ApiResponse(data=None)
        raise CustomRuntimeException("请输入name字段")

    @action(detail=False, methods=["post"], url_path="deploy")
    def deploy(self, request, *args, **kwargs):
        """
        发布
        """
        if ReleasePlan.objects.get(name=request.data["name"]).project == 'MDL' and ReleaseDetail.objects.filter(
                status="升级中", release_plan__project="MDL").exists():
            raise CustomRuntimeException(msg="mdl暂时不支持多个任务同时发布，请等正在发布的任务完成后再发布")
        self._get_release_service(name=request.data["name"])(name=request.data["name"], user=request.user).start()
        return ApiResponse(data="success")


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
