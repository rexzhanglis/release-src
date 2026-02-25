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
        # 1. 获取所有的发布模块信息
        modules = self.release_plan.get_all_release_contents_objs()
        # 2. 开始升级
        self.upgrade(modules)



    def re_deploy(self):
        """
        前端再发布按钮  从当前位置起依次发布
        """
        self.release_detail.set_log("开始再发布", self.user)
        # 1. 获取当前位置
        active_index = self.release_detail.active
        # 2. 获取发布模块
        modules = self.release_plan.get_all_release_contents_objs()[active_index - 1:]
        # 3. 发布
        self.upgrade(modules)

    def fail_skip(self):
        """
        失败跳过 分两种情形 发布失败 回滚失败
         1. 获取当前位置
         2. 获取发布模块 跳过当前位置模块
         3. 发布
        """

        self.release_detail.set_log("开始失败跳过操作", self.user)
        # 1. 获取当前位置
        active_index = self.release_detail.active

        if self.release_detail.status == "发布失败":
            # 2. 获取发布模块
            modules = self.release_plan.get_all_release_contents_objs()[active_index:]
            # 3. 发布
            self.upgrade(modules)
        elif self.release_detail.status == "回滚失败":
            start_index = self.release_plan.get_all_release_contents_objs().count() - active_index
            modules = self.release_plan.get_all_release_contents_objs().order_by("-index")[start_index - 1:]
            # 3. 回滚
            self._rollback(modules)

    def fail_retry(self):
        """
         失败重试 分两种情形 发布失败 回滚失败
         1. 获取当前位置
         2. 获取发布模块 包含当前位置模块
         3. 发布
        """
        self.release_detail.set_log("开始失败重试操作", self.user)
        # 1. 获取当前位置
        active_index = self.release_detail.active
        # 发布失败情形
        if self.release_detail.status == "发布失败":
            # 2. 获取发布模块
            modules = self.release_plan.get_all_release_contents_objs()[active_index - 1:]
            # 3. 发布
            self.upgrade(modules)
        # 回滚失败情形
        elif self.release_detail.status == "回滚失败":
            start_index = self.release_plan.get_all_release_contents_objs().count() - active_index
            modules = self.release_plan.get_all_release_contents_objs().order_by("-index")[start_index:]
            # 3. 回滚
            self._rollback(modules)

    def rollback(self):
        """
         1. 暂停
         2. 获取当前位置
         3. 获取发布模块 倒叙获取
         4. 回滚(也使用升级命令)
        """
        self.release_detail.set_log("开始回滚操作", self.user)
        # 0. 暂停操作
        self.release_plan.get_all_release_contents_objs().update(is_release=False)
        # 1. 获取当前位置
        active_index = self.release_detail.active
        # 2. 获取发布模块
        start_index = self.release_plan.get_all_release_contents_objs().count() - active_index
        modules = self.release_plan.get_all_release_contents_objs().order_by("-index")[start_index:]
        # 3. 回滚
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
