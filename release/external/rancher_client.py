"""
author: zhixiong.zeng
python version: 3
time: 2021/6/2 13:23

api 整理

https://rancher2.wmcloud-qa.com/v3/clusters   // 获取集群

https://rancher2.wmcloud-qa.com/v3/cluster/c-4wfqt/projects  //c-4wfqt 是集群id

https://rancher2.wmcloud-qa.com/v3/cluster/c-4wfqt/namespaces // 所有的命名空间

https://rancher2.wmcloud-qa.com/v3/project/c-4wfqt:p-8dsgv/ingresses 所有的ingress信息


构造url： 项目id    workload类型：命名空间名称：workload名称
https://rancher2.wmcloud-qa.com/p/c-4wfqt:p-8dsgv/workload/statefulset:devops-release:devops-release-mysql

statefulset:devops-release:devops-release-mysql  对应id字段

c-4wfqt:p-8dsgv  对应projectId字段

常用字段
name id namespaceId  projectId clusterId
"""
import os
import requests
import django
import time

from app.models import RancherWorkload, RancherApp

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "release.settings")
django.setup()
from const.models import Constance


class RancherClient(object):
    OK_STATUS = [200, 201, 202, 204]  # post 返回的状态码就是204

    def __init__(self, env):
        self.env = Constance.get_value(key=env)
        self.base_url = self.env["base_url"]
        self.cluster_id = self.env["cluster_id"]
        self.auth = (self.env["access_key"], self.env["secret_key"])

    def _get(self, url):
        response = requests.get(url, auth=self.auth, timeout=10, verify=False)
        if response.status_code not in self.OK_STATUS:
            raise Exception(response.content)
        return response.json()

    # def _put(self, url, data=None):
    #     response = requests.put(url, auth=self.auth, json=data, timeout=10, verify=False)
    #     print(response, response.text)
    #     if response.status_code not in self.OK_STATUS:
    #         raise Exception(response.content)
    #     return response.json()

    def _post(self, url, data=None):
        response = requests.post(url, auth=self.auth, timeout=10, json=data, verify=False)
        print(response, response.text)
        if response.status_code not in self.OK_STATUS:
            print("rancher2 post {} error {}, {}".format(url, response.status_code, response.content))
            raise Exception(response.content)

        return response.json() if response.content else {}

    def get_all_projects(self):
        """
        https://rancher2.wmcloud-qa.com/v3/cluster/c-4wfqt/projects  //c-4wfqt 是集群id
        """
        url = "{}/cluster/{}/projects".format(self.base_url, self.cluster_id)
        return self._get(url)["data"]

    def get_all_apps(self, project_id):
        """
         https://rancher2.wmcloud-qa.com/v3/project/{}/apps   //c-4wfqt 是集群id
        """
        url = "{}/project/{}/apps".format(self.base_url, project_id)
        return self._get(url)["data"]

    def upgrade_app(self, project_id, app_name, app_version, app_id, catalog_name):
        """
        通过该api进行升级
        :param project_id:
        :param app_name:
        :param app_version:
        :param app_id:
        :param catalog_name:
        :return:
        """
        # 1. 升级
        answers = self.get_latest_answer(project_id, app_name, app_version, app_id)
        url = self.base_url + '/project/{}/apps/{}?action=upgrade'.format(project_id, app_id)
        data = {
            "answers": answers,
            "externalId": "catalog://?catalog=%s&template=%s&version=%s" % (catalog_name, app_name, app_version),
        }
        self._post(url, data)
        # 2. 判断是否升级成功 app状态是否改变成active
        count = Constance.get_value("success_delay")  # 单位s
        success_delay = count
        # 先暂停10s,防止rancher系统异常导致判断错误
        time.sleep(10)
        while count > 0:
            if self.get_app_state(project_id, app_id) == 'active':
                # 判断workload版本与目标版本是否一致，背景是rancher存在app升级但workload不升级的bug
                target_version = app_name + ":" + app_version
                workloads = RancherWorkload.objects.filter(app=RancherApp.objects.get(name=app_name))
                if workloads:
                    workload_version = self.get_workload_current_version(project_id=project_id, workload_id=workloads[0].workload_id)
                    if target_version == workload_version:
                        return "success"
                    else:
                        raise Exception(
                            "升级失败，app目标版本是{}，当前workload版本是{}，两者不匹配，请手动升级".format(target_version, workload_version))
                return Exception("app目标版本升级成功，但发布系统无法获取到对应的workload信息，请确认workload的版本是否是目标版本")
            time.sleep(10)
            count = count - 10
        raise Exception("升级失败，{}分钟内app的状态仍未变成active，发布系统判定升级".format(int(success_delay / 60)))

    def get_latest_answer(self, project_id, app_name, app_version, app_id):
        url = self.base_url + '/project/%s/apps/%s' % (project_id, app_id)
        payload = self._get(url)
        if not payload:
            print("unable to get_latest_answer in %s:%s." % (app_name, app_version))
        if "answers" in payload:
            return payload["answers"]

        print("no answers found in %s:%s." % (app_name, app_version))
        return None

    def get_current_version(self, project_id, app_id):
        """
        "externalId": "catalog://?catalog=helm-repo-qa&template=devops-nextcmdb&version=8.0.0-devops-nextcmdb-1.0.0-21"
        """
        url = self.base_url + '/project/%s/apps/%s' % (project_id, app_id)
        return self._get(url)["externalId"].split("version=")[1]

    def get_workload_current_version(self, project_id, workload_id):
        """
        由rancher app版本 由app:chart组成
        "workloadLabels": {
            "app": "devops-nextcmdb",
            "chart": "13.0.0-devops-nextcmdb-1.0.0-26",
            "component": "devops-nextcmdb",
            "heritage": "Tiller",
            "io.cattle.field/appId": "devops-nextcmdb",
            "release": "devops-nextcmdb"
        }
        """
        url = self.base_url + '/project/%s/workloads/%s' % (project_id, workload_id)
        res = self._get(url)
        return res["workloadLabels"]["app"] + ":" + res["workloadLabels"]["chart"]

    def get_all_workloads(self, project_id):
        """
        https://rancher2.wmcloud-qa.com/v3/project/c-4wfqt:p-8dsgv/workloads //c-4wfqt c-4wfqt:p-8dsgv 项目id
        """
        url = "{}/project/{}/workloads".format(self.base_url, project_id)
        return self._get(url)["data"]

    def get_app_state(self, project_id, app_id):
        url = self.base_url + '/project/{}/apps/{}'.format(project_id, app_id)
        return self._get(url)["state"]

    def get_refresh_catalog_state(self, catalog):
        url = self.base_url + '/catalogs/{}'.format(catalog)
        return self._get(url)["state"]

    def refresh_catalog(self, catalog):
        """
        http://v3/catalogs/helm-repo-production?action=refresh
        """
        url = self.base_url + '/catalogs/{}?action=refresh'.format(catalog)
        self._post(url)
        # 判断是否成功的延时
        delay = 60
        while delay > 0:
            if self.get_refresh_catalog_state(catalog) == 'active':
                time.sleep(10)  # 停顿10s 看能否解决rancher 升级app但不升级workload的问题
                return "success"
            time.sleep(2)
            delay = delay - 2
        raise Exception("刷新应用商店异常，请登录rancher进行确认")


if __name__ == '__main__':
    # project_id = "c-4wfqt:p-8dsgv"
    # prod_project_id = "c-g6lcf:p-drrj9"
    # app_name = "devops-nextcmdb"
    # prod_app_name = "devops-alertcenter-web"
    # # app_version = "9.0.0-devops-nextcmdb-1.0.0-22"
    # app_version = "8.0.0-devops-nextcmdb-1.0.0-21"
    # prod_app_version="7.0.0-devops-alertcenter-web-1.0.5-13"
    # # prod_app_version="6.0.0-devops-alertcenter-web-1.0.4-11"
    # app_id = "p-8dsgv:devops-nextcmdb"
    # prod_app_id = "p-drrj9:devops-alertcenter-web"
    # catalog_name = "helm-repo-qa"
    # prod_catalog_name = "helm-repo-production"
    # url = "https://rancher2.wmcloud-qa.com/v3/project/c-4wfqt:p-8dsgv/apps/p-8dsgv:devops-nextcmdb"
    # print(RancherClient().get(url))
    # print(RancherClient(Constance.get_value("release_env")).refresh_catalog(Constance.get_value("rancher_catalog")))
    # RancherClient("rancher_qa").refresh_catalog(catalog_name)
    # redeploy 发布系统
    pass
    # url = "https://rancher2.wmcloud-qa.com/v3/project/c-4wfqt:p-8dsgv/workloads/deployment:devops-nextcmdb:devops-nextcmdb"
    # data = RancherClient("rancher_qa")._get(url)
    # data["annotations"]["cattle.io/timestamp"] = str(datetime.datetime.now())
    # print(RancherClient("rancher_qa")._put(url, data=data))  # 使用put方法实现

    # RancherClient("rancher_qa")._post(url)

    # RancherClient("rancher_prod").upgrade_app(project_id=prod_project_id, app_name=prod_app_name,
    #                                           app_version=prod_app_version,
    #                                           app_id=prod_app_id,
    #                                           catalog_name=prod_catalog_name)
