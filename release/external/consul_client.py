"""
author: zhixiong.zeng
python version: 3
time: 2022/1/14 14:40
"""

import os, django, requests

# c = consul.Consul(host='consul.wmcloud-qa.com', port=80, token="9e29026f-a58c-3e00-8b92-062ac41d4f23")

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "release.settings")
django.setup()

from mdl.models import MdlServer

_CONSUL_BASE_URL = 'http://consul.wmcloud.com'
_CONSUL_TOKEN = "dbb8cd09-96db-36f8-fcba-a3f84e496241"


class ConsulClient(object):

    def put(self, key, value):
        """
        f.encode("utf-8")
        "container/devops/devops-nextcmdb-CI/latest/feeder_handler.cfg"
        """
        url = "{}/v1/kv/{}".format(_CONSUL_BASE_URL, key)
        resp = requests.put(url, data=value, headers={"X-Consul-Token": _CONSUL_TOKEN}, timeout=30)
        resp.raise_for_status()


if __name__ == '__main__':
    consul_path = MdlServer.objects.get(fqdn="mdl-fwd-cnc01.wmcloud.com", service_name="mdl-forward").consul_space
    key = consul_path.split("/kv/")[1] + "feeder_handler.cfg"
    print(key)
    # c.kv.put(key="container/devops/devops-nextcmdb-CI/latest/feeder_handler.cfg", value=f.encode("utf-8"))
    # with open('conf_temp', 'wb') as f:
    #     mdl_project.files.raw(file_path='monitor/monitor01_10.24.71.110/feeder_monitor.cfg', ref='master',
    #                           streamed=True, action=f.write)
    #     print(u"下载AppConfig.h成功")
