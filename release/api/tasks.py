"""
author: zhixiong.zeng
python version: 3
time: 2023/9/6 14:24
"""
import logging
import threading, os, django
import time
from datetime import datetime, timedelta

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "release.settings")
django.setup()

from api.models import ReleasePlan
from account.models import User
from api.services.rancher_release_detail_service import RancherReleaseDetailService
from common.decorator import cron_log
from common.utils.wechatutil import send_to_enterprise_wechat

logger = logging.getLogger("cron")


class AutoReleaseThread(threading.Thread):

    def __init__(self, obj):
        threading.Thread.__init__(self)
        self.obj = obj

    def run(self):
        try:
            RancherReleaseDetailService(name=self.obj.name, user=User.objects.get(username=self.obj.owner)).start()
            send_to_enterprise_wechat([self.obj.owner], "发布计划{}: 发布成功".format(self.obj.name))
        except Exception as ex:
            logger.exception(str(ex))
            send_to_enterprise_wechat([self.obj.owner], "发布计划{}: 发布失败".format(self.obj.name))


def get_auto_release_plans():
    """
    1. 先过滤最近二分钟的自动发布计划
    2. 判断是否已不发布
    :return:
    """
    auto_release_plans = []
    start_time = datetime.now() - timedelta(seconds=60)
    end_time = datetime.now() + timedelta(seconds=60)
    objects = ReleasePlan.objects.exclude(project='MDL').filter(is_auto=True,
                                                                plan_release_time__range=(start_time, end_time))
    for obj in objects:
        if not obj.releasedetail_set.exists():
            auto_release_plans.append(obj)
    return auto_release_plans


@cron_log
def auto_release_task():
    """
    定时任务5分钟执行一次
    1. 获取自动发布计划
    2. 并发
    :return:
    """
    objects = get_auto_release_plans()
    logger.info("自动发布对象:{}".format(str(objects)))
    if objects:
        threads = []
        for obj in objects:
            thread = AutoReleaseThread(obj)
            threads.append(thread)
            thread.start()
            time.sleep(10)  # 暂停10s 同时刷新rancher应用商店会报错
            # 等待所有线程完成
        for thread in threads:
            thread.join()


if __name__ == '__main__':
    auto_release_task()
