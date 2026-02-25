"""
author: zhixiong.zeng
python version: 3
time: 2021/11/17 11:16
"""
import requests, os, django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "release.settings")
django.setup()

from const.models import Constance

BASE_URL = "http://depconf-fe.respool2.wmcloud-qa.com/app/api/v1/"


class ConfClient(object):
    """
    调用quan.jiang的配置发布接口
    """

    def _post(self, data, path):
        url = Constance.get_value(key="conf_base_url") + path
        res = requests.post(url, json=data, headers={'Content-Type': 'application/json'}).json()
        if res["code"] != 200:
            raise Exception("调用配置发布接口失败 {} {}".format(str(res["message"]), data))
        return "success"

    def create_ticket(self, name, urlparse):
        data = {
            "name": name,
            "creator": "auto_deploy",
            "env": "prd",
            "urlparse": urlparse
        }
        return self._post(data, "createticket")

    def deploy(self, name):
        data = {
            "ticket": name,
            "operator": "auto_deploy",
        }
        return self._post(data, "deployticket")

    def rollback(self, name):
        data = {
            "ticket": name,
            "operator": "auto_deploy",
        }
        return self._post(data, "rollbackconfig")


if __name__ == '__main__':
    # urlparse = ["http://git.datayes.com/consul/devops/-/blob/master/devops-nextcmdb/nextcmdb_nginx.conf"]
    urlparse = "http://git.datayes.com/consul/cloud/-/blob/master/cloud-platform/innermaster/application.properties"
    print (urlparse.split())

    test = urlparse.split("/")
    print(test)
    print(len(test))

    # name = "11.19告警中台_AUTO-1124"
    # ConfClient().deploy(name=name)
