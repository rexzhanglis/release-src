"""
author: zhixiong.zeng
python version: 3
time: 2022/1/14 11:51
"""
import gitlab

gl = gitlab.Gitlab('http://git.datayes.com', private_token='aHo8e9gFFQGGqjeAE9x7')

class GitlabClient(object):

    def get_project_file(self, file_path, project_id=6481):
        mdl_project = gl.projects.get(project_id)
        file = mdl_project.files.get(file_path=file_path, ref='master').decode().decode('utf8')
        return file


if __name__ == '__main__':
    config_file = "http://git.datayes.com/consul/mdl/-/blob/master/forward/forward_cnc01_10.24.71.83/feeder_handler.cfg"
    file_path = config_file.replace("http://git.datayes.com/consul/mdl/-/blob/master/", "")
    # file_path = 'monitor/monitor01_10.24.71.110/feeder_monitor.cfg'
    print(file_path)
    print(GitlabClient().get_project_file(file_path=file_path))

# c.kv.put(key="container/devops/devops-nextcmdb-CI/latest/feeder_handler.cfg", value=f.encode("utf-8"))
# with open('conf_temp', 'wb') as f:
#     mdl_project.files.raw(file_path='monitor/monitor01_10.24.71.110/feeder_monitor.cfg', ref='master',
#                           streamed=True, action=f.write)
#     print(u"下载AppConfig.h成功")
