from django.db.models import Q
from django.test import TestCase

import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "release.settings")
django.setup()

from app.models import AppModule

from server.models import Server

# Create your tests here.
from account.models import User

for user in User.objects.filter(is_active=False):
    app_modules = AppModule.objects.filter(
        Q(dev_owner=user.username) | Q(ops_owner=user.username) | Q(arch_owner=user.username))
    if app_modules:
        print(user, user.manager)
        for app_module in app_modules:
            print(app_module.name)
    servers = Server.objects.filter(application_user=user.username)
    if servers:
        print('----------------------服务器----------------')
        print(user, user.manager)
        for server in servers:
            print(server.fqdn)

    # user.username
# for group_info in temp["memberOf"]:
#     group_info = group_info.decode("utf-8")
#     cn, _ = group_info.split(',', 1)
#     _, name = cn.split('=')
#     if name.startswith(('dept.', 'team.')):
#         print(name)

# user = User.objects.get(username='zhixiong.zeng')
# if user.groups.filter(name="team.devops").exists():
#     return True
