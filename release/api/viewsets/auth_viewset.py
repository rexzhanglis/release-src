"""
author: zhixiong.zeng
python version: 3
time: 2021/5/13 17:01
"""
from django.contrib.auth import authenticate, login, logout
from django.http import HttpResponseRedirect
from rest_framework import viewsets
from rest_framework.decorators import action

from api.exception import CustomRuntimeException
from common.utils.apiutil import ApiResponse


class AuthViewSet(viewsets.ModelViewSet):
    @action(detail=False, methods=["post"], url_path="user_login")
    def user_login(self, request):
        username = request.data.get("username")
        password = request.data.get("password")
        user = authenticate(username=username, password=password)
        if user is not None:
            login(request, user)
            if request.GET.get('next'):
                return HttpResponseRedirect(request.GET.get('next'))
            return ApiResponse(data="success")
        raise CustomRuntimeException(msg="认证失败，用户名或密码错误")

    @action(detail=False, methods=["get"], url_path="user_logout")
    def user_logout(self, request):
        logout(request)
        return ApiResponse(data="success")
