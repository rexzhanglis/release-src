"""
inherit rest_framework response
"""

from rest_framework.response import Response
from rest_framework.renderers import JSONRenderer

OK_STATUS_CODE = 200


class ApiResponse(Response):
    def __init__(self, status_code=OK_STATUS_CODE, message=None, data=None):
        res_body = {
            'code': status_code,
            'message': message,
            'data': data
        }
        super().__init__(data=res_body)


class FitJSONRenderer(JSONRenderer):
    """
    自行封装的渲染器
    """

    def render(self, data, accepted_media_type=None, renderer_context=None):
        """
        如果使用这个render，
        普通的response将会被包装成：
            {"code":200,"data":"X","msg":"X"}
        这样的结果
        使用方法：
            - 全局
                REST_FRAMEWORK = {
                'DEFAULT_RENDERER_CLASSES': ('utils.response.FitJSONRenderer', ),
                }
            - 局部
                class UserCountView(APIView):
                    renderer_classes = [FitJSONRenderer]

        """
        # 处理自定义apiResponse场景
        if isinstance(data, dict):
            return super().render(data, accepted_media_type, renderer_context)
        # 处理django rest 自带的response场景
        else:
            res = {
                'code': renderer_context["response"].status_code,
                'message': None,
                'data': data
            }
            return super().render(res, accepted_media_type, renderer_context)
