"""
author: zhixiong.zeng
python version: 3
time: 2021/12/29 16:33
"""
import yaml
import requests
import os, django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "release.settings")
django.setup()
from mdl.models import MdlServer


def get_fqdn_by_ip(ip):
    # # 通过cmdb获取对应的fqdn
    cmdb_url = "https://cmdb-backend.wmcloud.com/api/server/?ip={}".format(ip)
    data = requests.get(url=cmdb_url).json()
    if len(data["data"]) == 1:
        fqdn = data["data"][0]["fqdn"]
        return fqdn


def get_env_by_ip(ip):
    # # 通过cmdb获取对应的fqdn
    cmdb_url = "https://cmdb-backend.wmcloud.com/api/server/?ip={}".format(ip)
    data = requests.get(url=cmdb_url).json()
    if len(data["data"]) == 1:
        env = data["data"][0]["env"]
        return env


def write_db(file_name, file_data):
    try:
        ip = file_data["consul_space"].split("/")[-2].split("_")[-1]
        fqdn = get_fqdn_by_ip(ip)
        if fqdn:
            data = {
                "fqdn": fqdn,
                "ip": ip,
                "role_name": file_name,
                "consul_space": file_data["consul_space"],
                "remote_python": file_data["remote_python"],
                "user": file_data["user"],
                "consul_token": file_data["consul_token"],
                "install_dir": file_data["install_dir"],
                "backups_dir": file_data["backups_dir"],
                "service_name": file_data["service_name"].replace(".service", "") if ".service" in file_data[
                    "service_name"] else file_data["service_name"],
            }
            MdlServer.objects.update_or_create(fqdn=fqdn, service_name=data["service_name"], defaults=data)
            print("update success {}".format(file_name))
    except Exception as ex:
        print("abnormal", file_name, file_data)
        print(ex)


def main():
    DIR = "/tmp/temp/group_vars"
    for file in os.listdir(DIR):
        file_name = file.strip(".yml")
        file_path = DIR + "/" + file
        with open(file_path) as f:
            file_data = yaml.load(f, Loader=yaml.FullLoader)
            write_db(file_name, file_data)


def update_config_git_url():
    import gitlab
    git_base_url = "http://git.datayes.com/consul/mdl/-/blob/master/"
    gl = gitlab.Gitlab('http://git.datayes.com', private_token='DqAwkHrpw5TvjAwW26V6')
    mdl_project = gl.projects.get(6481)
    res = mdl_project.repository_tree(all=True, recursive=True)
    i = 0
    j = 0
    for filename in res:
        if filename["name"] == 'feeder_handler.cfg':
            try:
                path = str(filename["path"]).strip("feeder_handler.cfg")
                obj = MdlServer.objects.get(consul_space__contains=path)
                obj.config_git_url = git_base_url + filename["path"]
                obj.save()
                print(filename["path"], "success")
                i = i + 1
            except Exception as ex:
                j = j + 1
                print(filename["path"], "fail", str(ex))
    print(i, j)


if __name__ == '__main__':
    main()
