"""
author: zhixiong.zeng
python version: 3
time: 2021/10/11 13:24
"""
from api.exception import CustomRuntimeException
from api.models import ReleaseDetail, ReleasePlan, ReleaseContent
from app.models import RancherApp
from const.models import Constance
from external.conf_client import ConfClient
from external.rancher_client import RancherClient


class ReleaseDetailService(object):

    def __init__(self, name, user):
        """
        初始化：
        1. 获取或创建发布详情对象
        2. 初始化流程图step的状态
        """
        self.user = user.username
        self.release_plan = ReleasePlan.objects.get(name=name)
        if not ReleaseDetail.objects.filter(release_plan=self.release_plan).exists():
            self.release_detail = ReleaseDetail.objects.create(release_plan=self.release_plan, user=user.username)
        else:
            self.release_detail = ReleaseDetail.objects.get(release_plan=self.release_plan)

    def suspend(self):
        """
        前端暂停按钮
        """
        self.release_detail.set_log("开始暂停操作", self.user)
        self.release_plan.get_all_release_contents_objs().update(is_release=False)
        self.release_detail.set_log("暂停成功", self.user)
        self.release_detail.set_status("暂停")

    def start(self):
        """
        前端发布按钮
        """
        modules = self.release_plan.get_all_release_contents_objs()
        self.upgrade(modules)

    def re_deploy(self):
        """
        前端再发布按钮  从当前位置起依次发布
        """
        self.release_detail.set_log("开始再发布", self.user)
        active_index = self.release_detail.active
        modules = self.release_plan.get_all_release_contents_objs()[active_index - 1:]
        self.upgrade(modules)

    def fail_skip(self):
        """
        失败跳过 分两种情形 发布失败/发布中(卡住) 回滚失败
        """
        self.release_detail.set_log("开始失败跳过操作", self.user)
        active_index = self.release_detail.active
        if self.release_detail.status in ("发布失败", "发布中", "升级中"):
            modules = self.release_plan.get_all_release_contents_objs()[active_index:]
            self.upgrade(modules)
        elif self.release_detail.status == "回滚失败":
            start_index = self.release_plan.get_all_release_contents_objs().count() - active_index
            modules = self.release_plan.get_all_release_contents_objs().order_by("-index")[start_index - 1:]
            self._rollback(modules)

    def fail_retry(self):
        """
        失败重试 分两种情形 发布失败/发布中(卡住) 回滚失败
        """
        self.release_detail.set_log("开始失败重试操作", self.user)
        active_index = self.release_detail.active
        if self.release_detail.status in ("发布失败", "发布中", "升级中"):
            modules = self.release_plan.get_all_release_contents_objs()[active_index - 1:]
            self.upgrade(modules)
        elif self.release_detail.status == "回滚失败":
            start_index = self.release_plan.get_all_release_contents_objs().count() - active_index
            modules = self.release_plan.get_all_release_contents_objs().order_by("-index")[start_index:]
            self._rollback(modules)

    def rollback(self):
        """
        回滚操作
        """
        self.release_detail.set_log("开始回滚操作", self.user)
        self.release_plan.get_all_release_contents_objs().update(is_release=False)
        active_index = self.release_detail.active
        start_index = self.release_plan.get_all_release_contents_objs().count() - active_index
        modules = self.release_plan.get_all_release_contents_objs().order_by("-index")[start_index:]
        self._rollback(modules)

    def deploy_config(self, module):
        """
        发布配置
        """
        pass

    def rollback_config(self, module):
        """
        回滚配置
        """
        pass

    def upgrade(self, modules):
        pass

    def _upgrade(self, module, is_rollback=False):
        pass

    def _rollback(self, modules):
        pass
