from urllib.parse import urljoin

import requests

ENDPOINT_URL = "https://rancher2.wmcloud-qa.com/v3"
ACCESS_KEY = "token-p7v85"
SECRET_KEY = "h6cqm6zpqh7sgbkfp2zg2n628w4c4x7w9hsstffv6rsntg4nshph2q"


class RancherClient(object):
    OK_STATUS = [200, 201, 202, 204]  # post 返回的状态码就是204

    def __init__(self):
        self.auth = (ACCESS_KEY, SECRET_KEY)

    def get(self, url):
        response = requests.get(url, auth=self.auth, timeout=10, verify=False)
        if response.status_code not in self.OK_STATUS:
            raise Exception(response.content)
        return response.json()

    def post(self, url, data=None):
        response = requests.post(url, auth=self.auth, timeout=10, json=data, verify=False)
        print(response, response.text)
        if response.status_code not in self.OK_STATUS:
            print("rancher2 post {} error {}, {}".format(url, response.status_code, response.content))
            raise Exception(response.content)

        return response.json() if response.content else {}


def get_latest_answer(project_id, app_name, app_version, app_id):
    url = ENDPOINT_URL + '/project/%s/apps/%s' % (project_id, app_id)
    payload = RancherClient().get(url)

    if not payload:
        print("unable to get_latest_answer in %s:%s." % (app_name, app_version))
    if "answers" in payload:
        return payload["answers"]

    print("no answers found in %s:%s." % (app_name, app_version))
    return None


def _post(self, url, data=None):
    response = requests.post(url, auth=self.auth, timeout=self.REQUEST_TIMEOUT, data=json.dumps(data), verify=False)

    if response.status_code not in self.OK_STATUS:
        print("rancher2 post {} error {}, {}".format(url, response.status_code, response.content))
        raise Exception(response.content)

    return response.json() if response.content else {}


def upgrade_app(project_id, app_name, app_version, app_id, catalog_name):
    answers = get_latest_answer(project_id, app_name, app_version, app_id)
    url = ENDPOINT_URL + '/project/{}/apps/{}?action=upgrade'.format(project_id, app_id)
    data = {
        "answers": answers,
        "externalId": "catalog://?catalog=%s&template=%s&version=%s" % (catalog_name, app_name, app_version),
    }
    payload = RancherClient().post(url, data)
    print(get_app_state())
    print(payload)
    return payload


def get_app_state():
    url = "https://rancher2.wmcloud-qa.com/v3/project/c-4wfqt:p-8dsgv/apps/p-8dsgv:devops-nextcmdb"

    return RancherClient().get(url)["state"]


if __name__ == '__main__':
    project_id = "c-4wfqt:p-8dsgv"
    app_name = "devops-nextcmdb"
    # app_version = "9.0.0-devops-nextcmdb-1.0.0-22"
    app_version = "8.0.0-devops-nextcmdb-1.0.0-21"
    app_id = "p-8dsgv:devops-nextcmdb"
    catalog_name = "helm-repo-qa"
    url = "https://rancher2.wmcloud-qa.com/v3/project/c-4wfqt:p-8dsgv/apps/p-8dsgv:devops-nextcmdb"
    # print(RancherClient().get(url))
    upgrade_app(project_id=project_id, app_name=app_name, app_version=app_version, app_id=app_id,
                catalog_name=catalog_name)

# 获取项目目录下所有app信息的api接口 https://rancher2.wmcloud-qa.com/v3/project/c-4wfqt:p-8dsgv/apps

# 主要获取字段 id name   通过定时任务拉取该信息 先更新项目 再根据项目获取对应的信息
