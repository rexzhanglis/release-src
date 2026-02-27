# Create your views here.
from rest_framework import viewsets, serializers
from rest_framework.decorators import action

from account.models import User
from common.utils.apiutil import ApiResponse
from common.utils.userutil import get_group_users
from const.models import Constance


def _get_constance_list(key):
    """安全读取 Constance 列表，key 不存在时返回空列表"""
    try:
        return Constance.get_value(key)
    except Exception:
        return []


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer

    devops = "team.devops"

    @action(detail=False, methods=["get"], url_path="get_user_info")
    def get_user_info(self, request, *args, **kwargs):
        """
        返回当前用户名、角色列表，以及配置管理专用角色（config_role）
        """
        username = request.user
        data = {
            "roles": self.get_user_roles(username),
            "name": str(username),
            "config_role": self.get_config_role(username),
        }
        return ApiResponse(data=data)

    @action(detail=False, methods=["get"], url_path="get_group_users")
    def get_group_users(self, request):
        return ApiResponse(data=get_group_users(request.user))

    def list(self, request, *args, **kwargs):
        """
        返回所有的用户名
        """
        users = User.objects.all().values_list('username', flat=True)
        return ApiResponse(data=users)

    def get_user_roles(self, user):
        roles = ["other"]
        user = User.objects.get(username=user)
        if user.groups.filter(name=self.devops).exists():
            roles.append("devops")
        if user.username in _get_constance_list("admin"):
            # admin 具有发布权限
            roles.append("admin")
        return roles

    def get_config_role(self, user):
        """
        返回配置管理权限角色：
          config_admin    - 完整权限，包括部署（Constance.admin 列表中）
          config_operator - 可编辑/提交/推送/回滚，不能部署
                           （devops 组成员 或 Constance.deployer 列表中）
          config_viewer   - 只读（其他已登录用户）
        """
        try:
            user_obj = User.objects.get(username=user)
        except User.DoesNotExist:
            return 'config_viewer'

        if user_obj.username in _get_constance_list('admin'):
            return 'config_admin'
        if (user_obj.groups.filter(name=self.devops).exists() or
                user_obj.username in _get_constance_list('deployer')):
            return 'config_operator'
        return 'config_viewer'
