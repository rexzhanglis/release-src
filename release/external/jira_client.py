"""
author: zhixiong.zeng
python version: 3
time: 2021/6/29 10:02
"""
from atlassian import Jira

import datetime, os, django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "release.settings")
django.setup()

from const.models import Constance

jira_server = "https://jira.datayes.com/"
username = "svc-jira"
password = "f14cK6gSHjM8"

Jira_client = Jira(url=jira_server, username=username, password=password, timeout=2)


class JiraComment(object):
    SUCCESS = '{color:#14892c}成功: %s. \n%s {color}'
    ERROR = '{color:#d04437}错误: %s. \n%s {color}'
    WARNING = '{color:#f79232}警告: %s. \n%s{color}'
    INFO = '{color:#205081}信息: %s. \n%s {color}'

    @classmethod
    def render(cls, level, msg):
        datetime_str = str(datetime.datetime.now())
        if level == 'ERROR':
            result = cls.ERROR % (msg, datetime_str)
        elif level == 'WARNING':
            result = cls.WARNING % (msg, datetime_str)
        elif level == 'SUCCESS':
            result = cls.SUCCESS % (msg, datetime_str)
        else:
            result = cls.INFO % (msg, datetime_str)

        return result


class JiraClient(object):

    def get_release_issue_key(self):
        """
        返回每个app最新发布的版本(基于安全的考虑，不提供发布到之前版本的选项)

        根据工单号的大小决定最新的版本号
        :return:
        """
        release_jql = Constance.get_value("release_jql")
        last_release_version = {}
        for issue in Jira_client.jql(jql=release_jql, fields=["key", "customfield_13336", "resolutiondate"],
                                     limit=2000).get("issues"):
            # 目前只获取rancher app 字段存在的工单
            if issue["fields"]["customfield_13336"]:
                rancher_app_name = issue["fields"]["customfield_13336"].split(":")[0]
                if rancher_app_name not in last_release_version.keys():
                    last_release_version[rancher_app_name] = issue["key"]
                elif int(issue["key"].split("-")[1]) > int(last_release_version.get(rancher_app_name).split("-")[1]):
                    last_release_version[rancher_app_name] = issue["key"]
        return list(last_release_version.values())

    def get_release_issue_version(self, issue_key):
        """
        customfield_13336  rancher app 版本号
        customfield_13410  发布版本信息
        {
        "customfield_13336":  "devops-toolbox:134.0.0-devops-toolbox-1.0.42-304"
        'customfield_13410': [
            {'self': 'https://jira.datayes.com/rest/api/2/version/29282', 'id': '29282', 'description': '',
             'name': 'devops-toolbox-1.0.42', 'archived': False, 'released': False}]
        """
        fields = ["customfield_13336", "customfield_13410", "customfield_15800"]
        res = Jira_client.get_issue(issue_key, fields)
        data = {
            "release_version": res["fields"]["customfield_13410"][0]["name"],
            "rancher_app_version": res["fields"]["customfield_13336"],
            "config_file": res["fields"]["customfield_15800"].strip()
        }
        return data

    def jql(self, jql, field):
        return Jira_client.jql(jql=jql, fields=field).get("issues")

    def get_mdl_release_issue_version(self, issue_key):
        """
        customfield_13823 module build version
        """
        fields = ["customfield_13823"]
        res = Jira_client.get_issue(issue_key, fields)
        return res["fields"]["customfield_13823"]


if __name__ == '__main__':
    # issue_fields = ["customfield_13836", "customfield_13835", "customfield_15200", "customfield_15201",
    #                 "customfield_13366", "customfield_13367", 'customfield_13833']
    # fields = ["customfield_13336", "customfield_13410", "customfield_11613", "customfield_12037"]
    # res = Jira_client.get_issue("RRP-41889", fields)
    print(JiraClient().get_mdl_release_issue_version(issue_key="MDL-346"))
