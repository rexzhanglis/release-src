import re

from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin

UNAUTHORIZED_STATUS = 401

WHITE_LIST_PATH = ["/admin", "/login", "/adminlogin/", "/api/auth/user_login/", "/api/serverIssue/","get_server_options","jira"]

RE_LIST_PATH = ["^/api/releasePlan/$"]


class AuthMiddleware(MiddlewareMixin):
    def process_request(self, request):

        # 1. 如果请求路径在白名单里 直接放行
        if self.is_white_list(request.path):
            pass
        # 2. 公司用户未认证，直接返回，让用户先cas认证
        elif not request.user.is_authenticated:
            print("no auth {}".format(request.user))
            res_body = {
                'code': UNAUTHORIZED_STATUS,
                'message': "no auth",
                'data': ""
            }
            return JsonResponse(res_body)

    def is_white_list(self, path):
        for white in WHITE_LIST_PATH:
            if white in path:
                return True
        for re_mode in RE_LIST_PATH:
            if re.match(re_mode, path):
                return True
        return False
