"""
author: zhixiong.zeng
python version: 3
time: 2021/12/29 9:28
"""

import paramiko


class SshClient(object):

    # 默认 transport socket 硬超时（秒）。即使 paramiko transport 线程卡在 TCP 读，
    # OS 也会在该时间后抛 socket.timeout，避免无限阻塞。
    DEFAULT_SOCK_TIMEOUT = 30

    def __init__(self, ip, username, password, sock_timeout=DEFAULT_SOCK_TIMEOUT):
        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.client.connect(ip, username=username, password=password,
                            timeout=5, banner_timeout=15, auth_timeout=15)
        # connect() 之后 transport 的底层 socket 默认是阻塞的（无超时）。
        # 即便 exec_command(timeout=10) 设了 channel 级超时，paramiko 的 transport
        # 后台线程仍可能卡在 socket.recv 上。给 transport socket 加硬超时是兜底。
        transport = self.client.get_transport()
        if transport is not None and transport.sock is not None and sock_timeout:
            try:
                transport.sock.settimeout(sock_timeout)
            except Exception:
                # 极少数自定义 transport 不支持 settimeout，忽略不影响主流程
                pass

    def send_cmd(self, cmd):
        stdin, stdout, stderr = self.client.exec_command(cmd, timeout=10)
        err = stderr.readline()
        if err:
            print(err)
            return []
        return stdout.readlines()

    def send_cmd2(self, cmd):
        """发送命令 但不关闭客户端"""
        stdin, stdout, stderr = self.client.exec_command(cmd, timeout=10)
        err = stderr.readline()
        if err:
            raise Exception("exec command {} error, {}".format(cmd, err))
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
