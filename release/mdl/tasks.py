"""
author: zhixiong.zeng
python version: 3
time: 2022/1/18 16:12
判断mdl服务器是否存在对应的mdl服务信息

[ -f /tmp/test.sh ] && echo yes || echo no   判断文件是否存在
[ -d /tmp/temp ] && echo yes || echo no   判断目录是否存在

"""
import os, django, logging

from common.utils.mailutil import send_to_mail
from external.cmdb_client import CmdbClient

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "release.settings")
django.setup()

from common.decorator import cron_log
from external.ssh_client import SshClient
from mdl.models import MdlServer
from const.models import Constance

cron_logger = logging.getLogger("cron")

MDL_CONSUL_BASE_PATH = "http://consul.wmcloud.com/v1/kv/configs/mdl/"


def send_mail(message):
    subject = "发布系统mdl信息与生产不一致通知"
    receivers = Constance.get_value(key="mail_receiver")
    send_to_mail(receivers, subject, message=message)


def get_consul_space(mdl_server, ssh_client):
    """
    获取生产环境的consul配置文件信息与系统记录的进行比对
    """
    consul_pull_file_path = mdl_server.install_dir + "/consul_pull.py"
    consul_space_cmd = "cat {} | grep 'CONSUL_SPACE ='".format(consul_pull_file_path)
    res = ssh_client.send_cmd2(consul_space_cmd)
    if len(res) == 1:
        """
        CONSUL_SPACE = 'http://consul.wmcloud.com/v1/kv/container/devops/devops-nextcmdb-CI/latest/'
        """
        prod_consul_space = res[0].strip().split("=")[1].strip()[1:-1]
        if prod_consul_space == mdl_server.consul_space:
            return "yes"
        return "no"
    return "no"


@cron_log
def check_mdl_service_task():
    """
     检查生产机器上mdl service是否存在，检验存储的信息是否正确
    """
    username = Constance.get_value("ansible_ssh_user")
    password = Constance.get_value("ansible_ssh_pass")
    check_abnormal_res = []
    for mdl_server in MdlServer.objects.all():
        # if mdl_server.ip not in ["10.24.87.124","10.24.87.161"]:
        #     continue
        # if mdl_server.ip not in ["10.22.240.86"]:
        #     continue
        try:
            ssh_client = SshClient(ip=mdl_server.ip, username=username, password=password)
            # 1. 判断安装目录是否存在 dir
            install_dir_exist_cmd = "[ -d {} ] && echo yes || echo no".format(mdl_server.install_dir)
            install_dir_if_exist = ssh_client.send_cmd2(install_dir_exist_cmd)[0].strip()
            # 2. 判断服务名称是否存在 file
            service_name_exist_cmd = "[ -f /lib/systemd/system/{}.service -o -f /etc/init/{}.conf ] && echo yes || echo no".format(
                mdl_server.service_name, mdl_server.service_name)
            service_name_if_exist = ssh_client.send_cmd2(service_name_exist_cmd)[0].strip()
            # 3. 判断日志目录是否存在 dir
            log_dir = "/".join(mdl_server.install_dir.split("/")[:-1]) + "/logs"
            log_dir_exist_cmd = "[ -d {} ] && echo yes || echo no".format(log_dir)
            log_dir_if_exist = ssh_client.send_cmd2(log_dir_exist_cmd)[0].strip()
            # 4. 判断consul配置文件目录是否与记录一致
            consul_space_consistent = get_consul_space(mdl_server, ssh_client)
            # 5. 处理校验结果
            if install_dir_if_exist != 'yes' or service_name_if_exist != 'yes' or log_dir_if_exist != 'yes' or consul_space_consistent != 'yes':
                detail = {
                    "install dir": install_dir_if_exist,
                    "service name": service_name_if_exist,
                    "log dir": log_dir_if_exist,
                    "consul space consistent": consul_space_consistent
                }
                print('server {},{}'.format(mdl_server.ip, detail))
                mdl_server.is_consistent = False
                mdl_server.check_detail = str(detail)
                mdl_server.save()
                check_abnormal_res.append('{} {}'.format(mdl_server.ip, str(detail)))
            else:
                print("server {}_{} 正常".format(mdl_server.ip, mdl_server.service_name))
            ssh_client.close()
        except Exception as ex:
            import traceback
            check_abnormal_res.append('{} {} {}'.format(mdl_server.ip, str(ex), str(traceback.format_exc())))
            mdl_server.check_detail = str(traceback.format_exc())
            mdl_server.save()

    # 如果存在异常 发送邮件
    if check_abnormal_res:
        send_mail(str(check_abnormal_res))


@cron_log
def check_config_git_url_task():
    """
    校验 mdlserver中的git配置文件是否正确
    1. 生产环境的机器必须要有config git url
    2. consul目录与git配置文件目录是否一致
    """
    check_abnormal_res = []
    for obj in MdlServer.objects.all():
        # if obj.ip not in ["10.22.240.55"]:
        #     continue
        # if obj.ip not in ["10.22.139.29","10.22.139.30","10.22.240.95","10.24.87.124","10.24.87.161"]:
        #     continue
        try:
            # 1. 生产环境的机器必须要有config git url
            if CmdbClient().get_server_info_by_ip(ip=obj.ip)["env"] == "prod" and not obj.config_git_url:
                check_abnormal_res.append("生产机器{}无git配置文件".format(obj.fqdn))
                print("生产机器{}无git配置文件".format(obj.fqdn))
            # 2. 非生产环境机器不需要有config git url路径
            if CmdbClient().get_server_info_by_ip(ip=obj.ip)["env"] != "prod" and obj.config_git_url:
                check_abnormal_res.append("非生产机器{}有git配置文件".format(obj.fqdn))
                print("非生产机器{}有git配置文件".format(obj.fqdn))
            # 3. consul目录与git配置文件目录是否一致
            if obj.config_git_url:
                config_git_path = str(obj.consul_space).lstrip(MDL_CONSUL_BASE_PATH) + obj.consul_files
                if config_git_path not in obj.config_git_url:
                    check_abnormal_res.append("{} consul与git配置文件不一致".format(obj.fqdn))
                    print("{} consul与git配置文件不一致".format(obj.fqdn))
        except Exception as ex:
            import traceback
            check_abnormal_res.append('{} {} {}'.format(obj.ip, str(ex), str(traceback.format_exc())))
            print('{} {} {}'.format(obj.ip, str(ex), str(traceback.format_exc())))

    # 如果存在异常 发送邮件
    if check_abnormal_res:
        send_mail(str(check_abnormal_res))


def _fetch_systemd_for_host(host, ssh_user, ssh_pass, ansible_env):
    """对单台机器跑 ansible 查 systemd 状态，返回 (host_id, services, error)"""
    import shutil, subprocess, tempfile
    tmpdir = tempfile.mkdtemp(prefix='mdl_sysd_cache_')
    try:
        hosts_path = os.path.join(tmpdir, 'hosts')
        with open(hosts_path, 'w') as f:
            f.write(
                f"release ansible_ssh_host={host.ip} "
                f"ansible_ssh_user={ssh_user} "
                f"ansible_ssh_pass={ssh_pass}\n"
            )

        def _extract(output):
            idx = output.find('>>')
            if idx != -1:
                return output[idx + 2:].lstrip('\r\n ')
            return output

        cmd = 'systemctl list-units "mdl-*.service" --all --plain --no-legend 2>/dev/null'
        proc = subprocess.run(
            ['ansible', 'release', '-i', hosts_path, '-m', 'shell', '-a', cmd],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, env=ansible_env, timeout=30
        )
        services = []
        for line in _extract(proc.stdout).splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split(None, 4)
            if len(parts) >= 4 and parts[0].startswith('mdl-') and parts[0].endswith('.service'):
                services.append({
                    'name': parts[0],
                    'load_state': parts[1],
                    'active_state': parts[2],
                    'sub_state': parts[3],
                    'description': parts[4] if len(parts) > 4 else '',
                    'enabled': None,
                })

        if services:
            names = ' '.join(s['name'] for s in services)
            proc2 = subprocess.run(
                ['ansible', 'release', '-i', hosts_path, '-m', 'shell',
                 '-a', f'systemctl is-enabled {names} 2>/dev/null || true'],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, env=ansible_env, timeout=30
            )
            enabled_lines = [l.strip() for l in _extract(proc2.stdout).splitlines() if l.strip()]
            for i, svc in enumerate(services):
                if i < len(enabled_lines):
                    svc['enabled'] = enabled_lines[i]

        return host.id, services, ''
    except Exception as e:
        return host.id, [], str(e)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


@cron_log
def refresh_systemd_cache():
    """
    并发刷新所有 ready 状态机器的 systemd 服务状态缓存（每台独立线程）。
    django_crontab 配置（settings.py）：
        CRONJOBS = [('*/5 * * * *', 'mdl.tasks.refresh_systemd_cache')]
    """
    import concurrent.futures
    from datetime import datetime, timezone
    from mdl.models import Host, SystemdServiceCache

    ssh_pass = Constance.get_value('ansible_ssh_pass') or os.environ.get('ANSIBLE_SSH_PASS', '')
    ssh_user = Constance.get_value('ansible_ssh_user') or os.environ.get('ANSIBLE_SSH_USER', 'root')
    ansible_env = os.environ.copy()
    ansible_env['ANSIBLE_HOST_KEY_CHECKING'] = 'False'

    hosts = list(Host.objects.filter(init_status='ready'))
    if not hosts:
        return

    now = datetime.now(timezone.utc)
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        futures = {
            executor.submit(_fetch_systemd_for_host, h, ssh_user, ssh_pass, ansible_env): h
            for h in hosts
        }
        for future in concurrent.futures.as_completed(futures, timeout=120):
            host_id, services, error = future.result(timeout=60)
            SystemdServiceCache.objects.update_or_create(
                host_id=host_id,
                defaults={'services': services, 'refreshed_at': now, 'error': error}
            )


@cron_log
def sync_config_from_gitlab():
    """
    定时从 GitLab 同步配置文件到数据库。
    解决配置在 Git 更新后数据库未同步导致链路数据过期的问题。

    django_crontab 配置（settings.py）：
        ('*/10 * * * *', 'mdl.tasks.sync_config_from_gitlab')
    """
    from django.db import close_old_connections
    close_old_connections()

    try:
        from api.viewsets.config_mgmt_viewset import _sync_from_gitlab
        result = _sync_from_gitlab()
        cron_logger.info(
            f'[ConfigSync] GitLab 同步完成: '
            f'service_types={result["service_types"]} '
            f'instances={result["instances"]} '
            f'configs={result["configs"]}'
        )
        # 注意：ConfigFile 的 post_save signal 会自动触发链路索引重建，
        # 所以这里不需要手动调用 rebuild_all_chain_indexes()
    except Exception as e:
        cron_logger.error(f'[ConfigSync] GitLab 同步失败: {e}')
        raise


if __name__ == '__main__':
    # check_mdl_service_task()
    check_config_git_url_task()
