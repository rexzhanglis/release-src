"""
author: zhixiong.zeng
python version: 3
time: 2021/5/13 10:53
"""
import os, django, logging

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "release.settings")
django.setup()

from functools import wraps

cron_logger = logging.getLogger("cron")


def cron_log(func):
    @wraps(func)
    def func_wrapper(*args, **kwargs):
        try:
            cron_logger.info('{} start'.format(func.__name__))
            func(*args, **kwargs)
            cron_logger.info('{} end'.format(func.__name__))
        except Exception as ex:
            cron_logger.exception('{} {}'.format(func.__name__, ex))

    return func_wrapper
