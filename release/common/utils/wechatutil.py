"""
author: zhixiong.zeng
python version: 3
time: 2023/9/6 16:54
"""
import requests

from release.settings import ENTERPRISE_WECHAT_ACCESS_TOKEN, ENTERPRISE_WECHAT_URL


def send_to_enterprise_wechat(receiver, message):
    """通过企业微信云平台账号通知到用户 api接口云平台维护"""
    headers = {
        'access-token': ENTERPRISE_WECHAT_ACCESS_TOKEN,
        'content-type': "application/json",
    }
    data = {
        "toList": receiver,
        "subject": "发布系统自动发布结果",
        "content": message,
        "args": None
    }
    res = requests.post(url=ENTERPRISE_WECHAT_URL, json=data, headers=headers).json()
    if res["message"] != 'Success':
        raise Exception(res["message"])
