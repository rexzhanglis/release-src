"""
author: zhixiong.zeng
python version: 3
time: 2021/8/24 14:22
"""
from django.core.mail import send_mail

from common.decorator import cron_log


@cron_log
def send_to_mail(receivers, subject, message=None, html_message=None):
    res = send_mail(subject, message, 'svc-devops@datayes.com', receivers, fail_silently=False,
                    html_message=html_message)
    if not res == 1:
        raise Exception('send_mail fail {} {} {},res:'.format(subject, message, receivers, res))


if __name__ == '__main__':
    message = "helooo,gsdgsdgsd"
    # message = """
    # <p>{}你好</p>
    # <p>你组内{}同学已离职,请尽快修改其名下的资产负责人信息<a href="{}">{}</a></p>
    # """.format("zhixiong.zeng","zhixiong.zeng","zhixiong.zeng")
    # message = """{}你好，你组内{}同学已离职，请尽快修改其名下的资产负责人信息{}""".format(data["manager_chinese_name"], data["resign_chinese_name"],
    #                                                           resignation_web_url + data["username"])
    subject = "员工离职资源负责人修改"
    receivers = ["yinyin.zhang@datayes.com"]
    send_to_mail(receivers, subject, html_message=message)