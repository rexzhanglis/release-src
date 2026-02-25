"""
author: zhixiong.zeng
python version: 3
time: 2021/8/25 10:20
"""
import os, django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "release.settings")
django.setup()
from account.models import User


def get_group_users(user):
    """
    获取同一个组内的用户
    :return:
    """
    manager = user
    if not is_manager(user):
        manager = User.objects.get(username=user).manager
    group_users = list(User.objects.filter(manager=manager).values_list("username", flat=True)) + [manager.lower()]
    return group_users


def is_manager(user):
    """
    判断是否是管理者
    :return:
    """
    manager_set = set(User.objects.values_list("manager", flat=True))
    managers = [manager.lower() for manager in manager_set if manager]
    return user in managers


if __name__ == '__main__':
    print(get_group_users('zhixiong.zeng'))
