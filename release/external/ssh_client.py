"""
author: zhixiong.zeng
python version: 3
time: 2021/12/29 9:28
"""

import paramiko


class SshClient(object):

    def __init__(self, ip, username, password):
        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.client.connect(ip, username=username, password=password, timeout=5)

    def send_cmd(self, cmd):
        stdin, stdout, stderr = self.client.exec_command(cmd, timeout=10)
        if stderr.readline():
            print(stderr.readline())
            return ''
        self.client.close()
        return stdout.readlines()

    def send_cmd2(self, cmd):
        """发送命令 但不关闭客户端"""
        stdin, stdout, stderr = self.client.exec_command(cmd, timeout=10)
        if stderr.readline():
            raise Exception("exec command {} error, {}".format(cmd, stderr.readline()))
        return stdout.readlines()

    def close(self):
        """关闭客户端"""
        self.client.close()


if __name__ == '__main__':
    import os, django

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "release.settings")
    django.setup()
    from mdl.models import MdlServer

    consul_space = MdlServer.objects.get(role_name='write-stg01').consul_space
    cmd = "cat /tmp/consul_pull.py | grep 'CONSUL_SPACE ='"
    res = SshClient(ip="10.20.201.123", username='han.bao', password='datayes@123').send_cmd(cmd)
    if len(res) == 1:
        print(res[0].strip())
        prod_consul_space = res[0].strip().split("=")[1].strip()[1:-1]
        print(prod_consul_space, consul_space)
        if prod_consul_space == consul_space:
            print("zxzeng")
