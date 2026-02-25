"""
author: zhixiong.zeng
python version: 3
time: 2021/9/28 14:06
"""
import re

from rest_framework import viewsets
from rest_framework.decorators import action

from api.exception import CustomRuntimeException
from common.utils.apiutil import ApiResponse
from const.models import Constance
from external.jira_client import JiraClient


class JiraViewSet(viewsets.ModelViewSet):
    @action(detail=False, methods=["get"], url_path="get_release_issue_key")
    def get_release_issue_key(self, request):
        """
        获取最近一个月发布申请的问题单
        """
        add_issue_keys = Constance.get_value(key="add_issue_keys")
        data = JiraClient().get_release_issue_key() + add_issue_keys
        return ApiResponse(data=data)

    @action(detail=False, methods=["get"], url_path="get_release_issue_version")
    def get_release_issue_version(self, request):
        """
        获取发布问题单版本配置文件等信息
        """
        config_file_prefix = "http://git.datayes.com/consul"
        issue_key = request.query_params.get("issue_key")
        if issue_key:
            data = JiraClient().get_release_issue_version(issue_key)
            # 校验jira config file 填写是否合规
            if data["config_file"] != '无':
                if re.search(r"(，|,|；|;)", data["config_file"]):
                    raise CustomRuntimeException("jira配置文件填写不规范，不需要包含，,；;等字符")
                for row in data["config_file"].split():
                    if config_file_prefix not in row:
                        raise CustomRuntimeException("jira配置文件填写不规范，请在jira中填写正确的配置文件git链接")
                return ApiResponse(data=data)
            return ApiResponse(data=data)

    @action(detail=False, methods=["get"], url_path="get_mdl_release_issue_key")
    def get_mdl_release_issue_key(self, request):
        """
        获取mdl最近30天的发布申请
        """
        res = JiraClient().jql(jql=Constance.get_value("mdl_release_jql"), field=["key"])
        return ApiResponse(data=[row["key"] for row in res])

    @action(detail=False, methods=["get"], url_path="get_mdl_release_issue_version")
    def get_mdl_release_issue_version(self, request):
        """
        获取mdl发布问题单版本信息
        """
        issue_key = request.query_params.get("issue_key")
        if issue_key:
            data = JiraClient().get_mdl_release_issue_version(issue_key)
            if data:
                for row in data.splitlines():
                    if "mdl-linux" in row:
                        return ApiResponse(data=row)
            raise CustomRuntimeException(msg="jira工单无发布版本信息，请确保流程已走完")
