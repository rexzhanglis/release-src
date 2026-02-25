import json
import logging
import traceback

from django.http import JsonResponse

logger = logging.getLogger("global_exception")


class ExceptionMiddleware(object):
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_exception(self, request, exception):
        if not issubclass(exception.__class__, Exception):
            return None
        ret_json = {
            'code': getattr(exception, 'status_code', 500),
            'message': getattr(exception, 'message', str(exception.__class__.__name__)),
            'data': None
        }
        # 特殊处理 用于前端及时处理异常情况
        if "/api/releaseDetail/" in request.path:
            ret_json = {
                'code': 200,
                'message': getattr(exception, 'message', str(exception.__class__.__name__)),
                'data': 'fail'
            }
        response = JsonResponse(ret_json)
        # response.status_code = getattr(exception, 'status_code', 500)

        _logger = logger.error if response.status_code >= 500 else logger.warning
        _logger('status_code->{status_code}, error_code->{code}, url->{url}, '
                'method->{method}, param->{param},traceback->{traceback}'.format(
            status_code=response.status_code, code=ret_json['code'], url=request.path,
            method=request.method, param=json.dumps(getattr(request, request.method, {})),
            traceback=traceback.format_exc()
        ))
        return response
