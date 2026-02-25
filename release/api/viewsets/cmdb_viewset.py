"""
author: zhixiong.zeng
python version: 3
time: 2021/9/28 14:06
"""
from rest_framework import viewsets
from rest_framework.decorators import action

from common.utils.apiutil import ApiResponse
from mdl.models import MdlServer, Label


class CmdbViewSet(viewsets.ModelViewSet):
    @action(detail=False, methods=["get"], url_path="get_mdl_release_server")
    def get_mdl_release_server(self, request):
        """
        获取mdl idc机房的服务器信息
        """
        release_object = []
        data = {}
        # 机器信息
        for obj in MdlServer.objects.all():
            release_object.append(obj.fqdn + "__" + obj.ip + "__" + obj.service_name)
        labels = list(Label.objects.all().values_list("name", flat=True))
        release_object.extend(["label_{}".format(label) for label in labels])
        data["release_object"] = release_object
        # 标签信息
        label_to_server = {}
        for label in Label.objects.all():
            mdl_server = []
            for obj in label.mdl_server.all():
                mdl_server.append(obj.fqdn + "__" + obj.ip + "__" + obj.service_name)
            label_to_server["label_{}".format(label.name)] = mdl_server
        data["label_to_server"] = label_to_server
        return ApiResponse(data=data)
