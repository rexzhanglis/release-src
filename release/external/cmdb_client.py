"""
author: zhixiong.zeng
python version: 3
time: 2021/6/29 10:02
"""
import os, django, requests

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "release.settings")
django.setup()

CMDB_SERVER_URL = "https://cmdb-backend.wmcloud.com/api/server/"


class CmdbClient(object):

    def get_server_info_by_ip(self, ip):
        """
        获取服务器详细信息
        """
        # # 通过cmdb获取对应的fqdn
        cmdb_url = "{}?ip={}".format(CMDB_SERVER_URL, ip)
        data = requests.get(url=cmdb_url).json()
        if len(data["data"]) == 1:
            return data["data"][0]


if __name__ == '__main__':
    print(CmdbClient().get_server_info_by_ip(ip="10.22.109.38")["env"])
