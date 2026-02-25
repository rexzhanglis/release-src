# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import logging
import json


class AccessLogMiddleware(object):
    def __init__(self, get_response):
        self.get_response = get_response
        self.access_logger = logging.getLogger('access')

    def __call__(self, request):
        try:
            body = json.loads(request.body)
        except Exception:
            body = dict()
        body.update(dict(request.POST))
        response = self.get_response(request)
        self.access_logger.info("{} {} {} {} {} {}".format(
            request.user, request.method, request.path, body,
            response.status_code, response.reason_phrase))
        return response
