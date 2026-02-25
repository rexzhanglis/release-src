# Create your views here.
from rest_framework import viewsets, serializers
from rest_framework.decorators import action

from account.models import User
from common.utils.apiutil import ApiResponse
from common.utils.userutil import get_group_users
from const.models import Constance


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
        返回当前用户名和对应的角色
        """
        username = request.user
        data = {
            "roles": self.get_user_roles(username),
            "name": str(username),
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
        if user.username in Constance.get_value("admin"):
            # admin 具有发布权限
            roles.append("admin")
        return roles
