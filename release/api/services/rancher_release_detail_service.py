"""
author: zhixiong.zeng
python version: 3
time: 2021/10/11 13:24
"""
import random

from api.models import ReleaseContent
from api.services.release_detail_service import ReleaseDetailService
from app.models import RancherApp
from const.models import Constance
from external.conf_client import ConfClient
from external.rancher_client import RancherClient


class RancherReleaseDetailService(ReleaseDetailService):

    def upgrade(self, modules):
        try:
            # 1. 刷新应用商店
            self.release_detail.set_status("发布中")
            self.release_plan.get_all_release_contents_objs().update(is_release=True)
            RancherClient(Constance.get_value("release_env")).refresh_catalog(Constance.get_value("rancher_catalog"))
            # 2. 发布
            for module in modules:
                # 只有当is_release = true时，才被允许发布
                if ReleaseContent.objects.filter(release_plan=module.release_plan, issue_key=module.issue_key,
                                                 is_release=True).exists():
                    self.release_detail.set_active(module.index)
                    self.deploy_config(module)
                    self.release_detail.set_log("{} 开始升级".format(module.release_version), self.user)
                    module.set_status("process")
                    self._upgrade(module)
                    self.release_detail.set_log("{} 升级成功".format(module.release_version), self.user)
                    module.set_status("success")
            # 3 结束打日志

            if not ReleaseContent.objects.filter(release_plan=self.release_plan, is_release=False).exists():
                self.release_detail.set_status("发布成功")
            else:
                # 这一步是因为mysql 存储的特性决定的
                self.release_detail.set_status("暂停")

        except Exception as ex:
            self.release_detail.set_log("{} 升级失败，错误：{}".format(module.release_version, ex), user=self.user,
                                        level="error")
            self.release_detail.set_status("发布失败")
            module.set_status("error")
            raise ex

    def _upgrade(self, module, is_rollback=False):
        # 1. 获取基本信息
        rancher_app_version = module.rancher_app_version
        app_name, app_version = rancher_app_version.split(":")[0], rancher_app_version.split(":")[1]
        rancher_app = RancherApp.objects.filter(name=app_name)
        if len(rancher_app) == 0:
            raise Exception("生产rancher系统没有名为{}的app,请先确保生产rancher系统已经创建了当前app".format(app_name))
        if len(rancher_app) > 1:
            raise Exception("生产rancher系统存在多个名为{}的app，请联系管理员处理。".format(app_name))
        project_id = rancher_app[0].project.project_id
        app_id = rancher_app[0].app_id
        # 如果是回滚，则使用升级前的版本
        if is_rollback:
            self.rollback_config(module)
            app_version = module.current_rancher_app_version
        # 2. 第一次升级时 获取升级前的版本 用于回滚操作
        if not module.current_rancher_app_version:
            version = RancherClient(Constance.get_value("release_env")).get_current_version(project_id=project_id,
                                                                                            app_id=app_id)
            module.current_rancher_app_version = version
            module.save()
        # 3. 升级
        release_env = Constance.get_value("release_env")
        RancherClient(release_env).upgrade_app(project_id=project_id, app_name=app_name,
                                               app_version=app_version,
                                               app_id=app_id,
                                               catalog_name=Constance.get_value("rancher_catalog"))

    def _rollback(self, modules):
        try:
            self.release_detail.set_status("回滚中")
            for module in modules:
                if module.current_rancher_app_version:
                    self.release_detail.set_active(module.index)
                    self.release_detail.set_log("{} 开始回滚".format(module.release_version), self.user)
                    module.set_status("process")
                    self._upgrade(module, is_rollback=True)
                    self.release_detail.set_log("{} 回滚成功".format(module.release_version), self.user)
                    module.set_status("wait")
            self.release_detail.set_status("回滚成功")
        except Exception as ex:
            self.release_detail.set_log("{} 回滚失败，错误：{}".format(module.release_version, ex), user=self.user,
                                        level="error")
            module.set_status("error")
            self.release_detail.set_status("回滚失败")
            raise ex

    def deploy_config(self, module):
        """
        发布配置
        """
        if module.config_file:
            self.release_detail.set_log("{} 开始配置发布".format(module.release_version), self.user)
            name = "{}_{}_{}".format(module.release_plan.name, module.issue_key, random.randint(0, 100))
            module.set_depconf_ticket_name(name)
            ConfClient().create_ticket(name=name, urlparse=module.config_file.split())
            ConfClient().deploy(name=name)
            self.release_detail.set_log("{} 配置发布成功".format(module.release_version), self.user)
        else:
            self.release_detail.set_log("{} 无配置变更".format(module.release_version), self.user)

    def rollback_config(self, module):
        """
        回滚配置
        """
        if module.config_file:
            self.release_detail.set_log("{} 开始配置回滚".format(module.release_version), self.user)
            ConfClient().rollback(name=module.depconf_ticket_name)
            self.release_detail.set_log("{} 配置回滚成功".format(module.release_version), self.user)
        else:
            self.release_detail.set_log("{} 无配置回滚".format(module.release_version), self.user)
