"""
author: zhixiong.zeng
python version: 3
time: 2021/10/11 13:24
"""
import time

import yaml
import os, django

try:
    import ansible_runner
except ImportError:
    ansible_runner = None

from external.consul_client import ConsulClient
from external.gitlab_client import GitlabClient
from external.ssh_client import SshClient

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "release.settings")
django.setup()

from api.models import MdlReleaseContent
from api.services.release_detail_service import ReleaseDetailService
from const.models import Constance
from mdl.models import MdlServer


class MdlReleaseDetailService(ReleaseDetailService):

    def upgrade(self, modules):
        try:
            # 1. 发布
            for module in modules:
                # 只有当is_release = true时，才被允许发布
                if MdlReleaseContent.objects.filter(release_plan=module.release_plan,
                                                    release_object=module.release_object,
                                                    is_release=True).exists():
                    self.release_detail.set_active(module.index)
                    self.deploy_config(module)
                    self.release_detail.set_log("{} {} 开始升级".format(module.release_object, module.release_version),
                                                self.user)
                    module.set_status("process")
                    self._upgrade(module)
                    self.release_detail.set_log("{} {} 升级成功".format(module.release_object, module.release_version),
                                                self.user)
                    module.set_status("success")
            # 3 结束打日志
            if not MdlReleaseContent.objects.filter(release_plan=self.release_plan, is_release=False).exists():
                self.release_detail.set_status("发布成功")
            else:
                # 这一步是因为mysql 存储的特性决定的
                self.release_detail.set_status("暂停")

        except Exception as ex:
            self.release_detail.set_log("{} {} 升级失败，错误：{}".format(module.release_object, module.release_version, ex),
                                        user=self.user,
                                        level="error")
            self.release_detail.set_status("发布失败")
            module.set_status("error")
            raise ex

    def _upgrade(self, module, is_rollback=False):
        """
        1. 获取当前版本信息
        2. 升级
        3. 校验
        发布对象 test1_10.42.16.157_mdl-test  fqdn_ip_serviceName
        """
        # 1. 生成对应hosts和host_vars文件
        obj_list = module.release_object.split("__")
        if len(obj_list) != 3:
            raise Exception("发布对象的格式异常")
        server_fqdn = obj_list[0]
        service_name = obj_list[2]
        self._create_ansible_host(server_fqdn, service_name)
        self._create_ansible_host_vars(server_fqdn, service_name)
        # 2. 如果是回滚操作则回退配置
        if is_rollback:
            self.rollback_config(module)
        # 3.第一次升级时 获取升级前的版本 用于回滚操作
        if not module.current_version and not is_rollback and module.type == 'version':
            module.current_version = self._get_current_version(server_fqdn, service_name)
            module.save()
        # 4. 升级
        if module.type == 'version':
            release_version = module.release_version.split(":")[1].strip()
            out, err, rc = ansible_runner.run_command(executable_cmd='ansible-playbook',
                                                      cmdline_args=['ansi/mdl/deploy_feeder.yml', '-i',
                                                                    'ansi/mdl/hosts',
                                                                    '--extra-vars',
                                                                    'version={}'.format(release_version)])
        elif module.type == 'config':
            out, err, rc = ansible_runner.run_command(executable_cmd='ansible-playbook',
                                                      cmdline_args=['ansi/mdl/deploy_config.yml', '-i',
                                                                    'ansi/mdl/hosts'])
        if rc != 0:
            raise Exception(out)
        self.release_detail.set_log(out, self.user)
        self._get_upgrade_log(server_fqdn, service_name)

    def _rollback(self, modules):
        try:
            self.release_detail.set_status("回滚中")
            for module in modules:
                if module.current_version:
                    self.release_detail.set_active(module.index)
                    self.release_detail.set_log("{} 开始回滚到 {}".format(module.release_object, module.current_version),
                                                self.user)
                    module.set_status("process")
                    self._upgrade(module, is_rollback=True)
                    self.release_detail.set_log("{} 回滚成功".format(module.release_object), self.user)
                    module.set_status("wait")
            self.release_detail.set_status("回滚成功")
        except Exception as ex:
            self.release_detail.set_log("{} 回滚失败，错误：{}".format(module.release_object, ex), user=self.user,
                                        level="error")
            module.set_status("error")
            self.release_detail.set_status("回滚失败")
            raise ex

    def _create_ansible_host(self, server, service_name):
        """
        创建ansible 主机文件
        1. 生成获取主机信息
        2. 生成对应的文件
        3. 验证文件
        """
        # 1. 生成获取主机信息 "D:\\dev\\python\\release\\ansi\\mdl\\host"
        ansible_hosts_path = Constance.get_value("ansible_hosts_path")
        ip = MdlServer.objects.get(fqdn=server, service_name=service_name).ip
        ansible_ssh_user = Constance.get_value("ansible_ssh_user")
        ansible_ssh_pass = Constance.get_value("ansible_ssh_pass")
        host_info = "release ansible_ssh_host={} ansible_ssh_user={} ansible_ssh_pass={}".format(ip, ansible_ssh_user,
                                                                                                 ansible_ssh_pass)
        # 2. 生成对应的文件
        with open(ansible_hosts_path, "w") as f:
            f.write(host_info)
        # 3. 验证是否正确
        with open(ansible_hosts_path) as f:
            line = f.read().strip()
            if line == host_info:
                return
            raise Exception("ansible hosts文件生成异常")

    def _create_ansible_host_vars(self, server, service_name):
        """
        创建ansible 主机文件
        1. 生成获取主机信息
        2. 生成对应的文件
        3. 验证文件
        """
        # 1. 生成主机部署信息"D:\\dev\\python\\release\\ansi\\mdl\\host_vars\\release1.yml"
        ansible_host_vars_path = Constance.get_value("ansible_host_vars_path")
        data = MdlServer.objects.filter(fqdn=server, service_name=service_name).values("user", "remote_python",
                                                                                       "consul_space", "consul_token",
                                                                                       "install_dir", "backups_dir",
                                                                                       "service_name", "consul_files")
        #  2. 生成对应的文件
        with open(ansible_host_vars_path, "w") as f:
            yaml.dump(data[0], f)
        # 3. 验证是否正确
        with open(ansible_host_vars_path) as f:
            file_data = yaml.load(f, Loader=yaml.FullLoader)
            if file_data == data[0]:
                return
            raise Exception("ansible host_vars文件生成异常")

    def _get_current_version(self, server, service_name):
        ip = MdlServer.objects.get(fqdn=server, service_name=service_name).ip
        username = Constance.get_value("ansible_ssh_user")
        password = Constance.get_value("ansible_ssh_pass")
        install_dir = MdlServer.objects.get(fqdn=server, service_name=service_name).install_dir
        cmd = 'cat {}/version'.format(install_dir)
        res = SshClient(ip=ip, username=username, password=password).send_cmd(cmd)
        return res[0].strip() if res else ''

    def _get_upgrade_log(self, server, service_name):
        """
        获取最近1分钟内的日志
        grep $(date '+%Y-%m-%d') feeder_handler.log | awk -v dt="$(date '+%Y-%m-%d %T' -d '-2 minutes')" -F, '$1 > dt'
        """
        ip = MdlServer.objects.get(fqdn=server, service_name=service_name).ip
        self.release_detail.set_log("开始抓取{}_{}_{}日志信息....".format(server, ip, service_name), self.user)
        time.sleep(30)
        username = Constance.get_value("ansible_ssh_user")
        password = Constance.get_value("ansible_ssh_pass")
        install_dir = MdlServer.objects.get(fqdn=server, service_name=service_name).install_dir
        log_file = "/".join(install_dir.split("/")[:-1]) + "/logs/feeder_handler.log"
        cmd = """grep -a $(date '+%Y-%m-%d') {} | awk -v dt="$(date '+%Y-%m-%d %T' -d '-1 minutes')" -F, '$1 > dt'""".format(
            log_file)
        res = SshClient(ip=ip, username=username, password=password).send_cmd(cmd)
        self.release_detail.log = self.release_detail.log + "feeder_handler.log信息如下：\n" + "\n".join(res)
        self.release_detail.save()

    def deploy_config(self, module):
        """
        发布配置 生产环境每次发布都会同步一次git配置文件
        """
        # 1. 获取对应的git配置文件
        obj_list = module.release_object.split("__")
        if len(obj_list) != 3:
            raise Exception("发布对象的格式异常")
        server_fqdn = obj_list[0]
        service_name = obj_list[2]
        mdl_server_obj = MdlServer.objects.get(fqdn=server_fqdn, service_name=service_name)
        # 2. 发布配置
        if mdl_server_obj.config_git_url:
            self.release_detail.set_log("{} 开始配置发布，gitlab路径{}".format(module.release_object, mdl_server_obj.config_git_url), self.user)
            # 1 下载gitlab
            file_path = mdl_server_obj.config_git_url.replace("http://git.datayes.com/consul/mdl/-/blob/master/", "")
            file_content = GitlabClient().get_project_file(file_path=file_path)
            # 2 上传到consul
            key = mdl_server_obj.consul_space.split("/kv/")[1] + mdl_server_obj.config_git_url.split("/")[-1]
            ConsulClient().put(key=key, value=file_content.encode("utf-8"))
            self.release_detail.set_log("{} 配置发布成功".format(module.release_object), self.user)
        else:
            self.release_detail.set_log("{} 无配置发布".format(module.release_object), self.user)

    def rollback_config(self, module):
        """
        回滚配置
        """
        raise Exception("暂时不支持回滚配置")
        # if module.config_file:
        #     self.release_detail.set_log("{} 开始配置回滚".format(module.release_version), self.user)
        #     if module.release_plan.project == 'MDL':
        #         name = module.release_plan.name + "_" + module.server
        #     else:
        #         name = module.release_plan.name + "_" + module.issue_key
        #     # ConfClient().rollback(name=name)
        #     self.release_detail.set_log("{} 配置回滚成功".format(module.release_version), self.user)
        # else:
        #     self.release_detail.set_log("{} 无配置回滚".format(module.release_version), self.user)


if __name__ == '__main__':
    pass
