"""
author: zhixiong.zeng
python version: 3
time: 2021/7/19 14:39
"""

from rest_framework import permissions

from api.models import ReleasePlan
from common.utils.userutil import get_group_users
from const.models import Constance


class ReleasePlanEditPermission(permissions.BasePermission):
    """
    是否是编辑权限
    """

    def has_permission(self, request, view):
        # Read permissions are allowed to any request,
        # so we'll always allow GET, HEAD or OPTIONS requests.
        if request.method in permissions.SAFE_METHODS:
            return True
        # 排除创建
        if request.path == "/api/releasePlan/" and request.method == "POST":
            return True
        if ReleasePlan.objects.get(id=request.data["id"]).owner == request.user.username:
            return True
        return False


class ReleaseDetailEditPermission(permissions.BasePermission):
    """
    是否有发布权限 devops团队和admin角色拥有发布权限
    """

    def has_permission(self, request, view):
        # Read permissions are allowed to any request,
        # so we'll always allow GET, HEAD or OPTIONS requests.
        if request.method in permissions.SAFE_METHODS:
            return True
        #  devops团队
        if request.user.groups.filter(name="team.devops").exists():
            return True
        #  admin角色
        if request.user.username in Constance.get_value("admin"):
            return True
        #  deploy角色
        if request.user.username in Constance.get_value("deployer"):
            return True

        return False
