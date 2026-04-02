"""
author: zhixiong.zeng
python version: 3
time: 2021/9/28 16:07
"""
from datetime import datetime

from django.db import transaction, IntegrityError
from django.db.models import Q
from django.forms import model_to_dict
from rest_framework import serializers, viewsets
from rest_framework.decorators import action

from api.models import ReleasePlan, ReleaseContent, MdlReleaseContent, ReleaseDetail
from api.permissions.edit_permission import ReleasePlanEditPermission
from common.pagination import CustomPagination
from api.exception import CustomRuntimeException
from common.utils.apiutil import ApiResponse
from const.models import Constance
from mdl.models import MdlServer


class ReleasePlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReleasePlan
        fields = '__all__'


class ReleaseContentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReleaseContent
        fields = ['issue_key', 'release_version', 'rancher_app_version']


class ReleasePlanViewSet(viewsets.ModelViewSet):
    """
    rancher和mdl创建发布计划都统一通过该类处理
    """
    queryset = ReleasePlan.objects.all()
    serializer_class = ReleasePlanSerializer
    release_content_serializer_class = ReleaseContentSerializer
    permission_classes = [ReleasePlanEditPermission]

    def list(self, request, *args, **kwargs):
        # 1. 获取数据
        type = request.query_params.get("type")
        queryset = ReleasePlan.objects.filter(project='MDL').order_by(
            "-created_time") if type == 'MDL' else ReleasePlan.objects.exclude(project='MDL').order_by("-created_time")
        # 2. 基于前端选择框过滤
        filter_option_value = eval(request.query_params.get("optionValue") or "{}")
        for field, value in filter_option_value.items():
            # 只取出值存在的查询参数过滤
            if field == 'status' and value:
                if value == '未发布':
                    queryset = queryset.filter(releasedetail__isnull=True)
                else:
                    queryset = queryset.filter(releasedetail__status=value)
            elif value:
                queryset = queryset.filter(**{field: value})
        # 3. 基于前端搜索框过滤
        search = request.query_params.get("search")
        if search:
            queryset = queryset.filter(Q(name__icontains=search) | Q(owner__icontains=search))
        # 4. 分页处理
        custom_pagination = CustomPagination()
        total_count = queryset.count()
        res_page = custom_pagination.paginate_queryset(queryset=queryset, request=request, )
        # 5. 批量预取关联数据，避免 N+1 查询
        plan_ids = [p.id for p in res_page]
        # 批量查询 ReleaseDetail
        detail_map = {}
        for d in ReleaseDetail.objects.filter(release_plan_id__in=plan_ids):
            detail_map[d.release_plan_id] = d
        # 批量查询 release contents
        if type == 'MDL':
            # 构建 role_name 映射
            role_map = {}
            for obj in MdlServer.objects.select_related('host').all():
                key = obj.host.fqdn + "__" + obj.host.ip + "__" + obj.service_name
                if obj.role_name:
                    role_map[key] = obj.role_name
            contents_map = {}
            for c in MdlReleaseContent.objects.filter(release_plan_id__in=plan_ids).values(
                    "release_plan_id", "index", "issue_key", "release_version",
                    "release_object", "config_file", "type", "status", "executable"):
                c["role_name"] = role_map.get(c["release_object"], "")
                contents_map.setdefault(c["release_plan_id"], []).append(c)
        else:
            contents_map = {}
            for c in ReleaseContent.objects.filter(release_plan_id__in=plan_ids).values(
                    "release_plan_id", "index", "issue_key", "release_version",
                    "rancher_app_version", "config_file", "status"):
                contents_map.setdefault(c["release_plan_id"], []).append(c)
        # 6. 组装数据
        data = []
        for release_plan in res_page:
            release_plan_dict = model_to_dict(release_plan)
            release_plan_dict["created_time"] = release_plan.created_time
            release_plan_dict["release_contents"] = contents_map.get(release_plan.id, [])
            detail = detail_map.get(release_plan.id)
            release_plan_dict["status"] = detail.status if detail else "未发布"
            release_plan_dict["release_time"] = detail.created_time if detail else None
            release_plan_dict["last_updated_time"] = detail.last_updated_time if detail else None
            data.append(release_plan_dict)
        res = {
            'count': total_count,
            'previous': custom_pagination.get_previous_link(),  # 获取上一页链接，如果没有则是None
            'next': custom_pagination.get_next_link(),  # 获取下一页链接，如果没有则是None
            'results': data,  # 当前页的序列化数据
        }
        return ApiResponse(data=res)

    @action(detail=False, methods=["get"], url_path="get_release_plan_info")
    def get_release_plan_info(self, request, *args, **kwargs):
        """
        获取发布的详细信息
        """
        name = request.query_params.get("name")
        if name:
            release_plan = ReleasePlan.objects.get(name=name)
            release_plan_dict = model_to_dict(release_plan)
            release_plan_dict["created_time"] = release_plan.created_time
            release_plan_dict["release_contents"] = release_plan.get_all_release_contents()
            return ApiResponse(data=release_plan_dict)

    def create(self, request, *args, **kwargs):
        data = request.data
        is_auto = data.get("is_auto") if data.get("is_auto") else False
        owner = data.get("owner") if data.get("owner") else request.user  # 针对jira自动创建发布计划场景 传递owner参数
        try:
            with transaction.atomic():
                plan_release_time = datetime.strptime(data["plan_release_time"], '%Y-%m-%d %H:%M:%S')
                release_plan = ReleasePlan.objects.create(name=data["name"], project=data["project"],
                                                          plan_release_time=plan_release_time, owner=owner,
                                                          is_auto=is_auto, category=data.get("category"))
                for index, content in enumerate(data["selectList"], start=1):
                    obj = {
                        "index": index,
                        "release_plan": release_plan,
                        "config_file": None if '无' in content["config_file"] else content["config_file"].strip()
                    }
                    # 3.1 针对mdl项目创建发布内容
                    if data["project"] == "MDL":
                        obj["release_object"] = content["release_object"]
                        obj["type"] = data["type"]
                        obj["issue_key"] = data["issue_key"]
                        if data["type"] == "version":
                            obj["release_version"] = content["release_version"]
                            obj["executable"] = content.get("executable") or "feeder_handler"
                        MdlReleaseContent.objects.create(**obj)
                    # 3.2 rancher项目创建发布内容
                    else:
                        obj["rancher_app_version"] = content["rancher_app_version"]
                        obj["issue_key"] = content["issue_key"]
                        obj["release_version"] = content["release_version"]
                        ReleaseContent.objects.create(**obj)
        except IntegrityError:
            raise CustomRuntimeException("发布计划名称已存在，请更换名称后重试")
        return ApiResponse(data="success")

    @action(detail=False, methods=["post"], url_path="update_release_plan")
    def update_release_plan(self, request, *args, **kwargs):
        """
        1. 更新发布计划
        2. 删除与发布计划相关的发布内容
        3. 创建与发布计划相关的发布内容
        """
        data = request.data
        is_auto = data.get("is_auto") if data.get("is_auto") else False
        try:
            with transaction.atomic():
                # 1. 更新发布计划
                plan_release_time = datetime.strptime(data["plan_release_time"], '%Y-%m-%d %H:%M:%S')
                ReleasePlan.objects.filter(id=data["id"]).update(name=data["name"], plan_release_time=plan_release_time,
                                                                 is_auto=is_auto, project=data["project"],
                                                                 category=data.get("category"))
                # 2. 删除与发布计划相关的发布内容
                release_plan = ReleasePlan.objects.get(id=data["id"])
                release_plan.delete_release_contents()
                # 3. 创建与发布计划相关的发布内容
                for index, content in enumerate(data["selectList"], start=1):
                    obj = {
                        "index": index,
                        "release_plan": release_plan,
                        "config_file": None if not content["config_file"] or '无' in content["config_file"] else content[
                            "config_file"].strip()
                    }
                    # 3.1 针对mdl项目创建发布内容
                    if data["project"] == "MDL":
                        obj["release_object"] = content["release_object"]
                        obj["type"] = data["type"]
                        obj["issue_key"] = data["issue_key"]
                        if data["type"] == "version":
                            obj["release_version"] = content["release_version"]
                            obj["executable"] = content.get("executable") or "feeder_handler"
                        MdlReleaseContent.objects.create(**obj)
                    # 3.2 rancher项目创建发布内容
                    else:
                        obj["rancher_app_version"] = content["rancher_app_version"]
                        obj["issue_key"] = content["issue_key"]
                        obj["release_version"] = content["release_version"]
                        ReleaseContent.objects.create(**obj)
        except IntegrityError:
            raise CustomRuntimeException("发布计划名称已存在，请更换名称后重试")
        return ApiResponse(data="success")

    @action(detail=False, methods=["post"], url_path="delete_release_plan")
    def delete_release_plan(self, request, *args, **kwargs):
        """
        删除发布计划
        """
        data = request.data
        ReleasePlan.objects.filter(id=data["id"]).delete()
        return ApiResponse(data="success")

    @action(detail=False, methods=["get"], url_path="get_release_plan_project")
    def get_release_plan_project(self, request, *args, **kwargs):
        """
        前端发布计划创建时的项目选项
        """
        return ApiResponse(data=Constance.get_value("release_plan_project"))

    @action(detail=False, methods=["get"], url_path="get_release_plan_options")
    def get_release_plan_options(self, request, *args, **kwargs):
        """
        发布计划过滤选项
        """
        type = request.query_params.get("type")
        if type == 'MDL':
            data = {
                "owner": list(ReleasePlan.objects.filter(project='MDL').values_list("owner", flat=True).distinct()),
                "status": [status[0] for status in ReleaseDetail.STATUS_CHOICES]
            }
        else:
            data = {
                "project": Constance.get_value("release_plan_project"),
                "owner": list(ReleasePlan.objects.exclude(project='MDL').values_list("owner", flat=True).distinct()),
                "status": [status[0] for status in ReleaseDetail.STATUS_CHOICES]
            }
        return ApiResponse(data=data)
