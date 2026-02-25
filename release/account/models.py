from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    # 添加字段
    mobile = models.CharField(null=True, blank=True, max_length=11, verbose_name="电话")
    manager = models.CharField(null=True, blank=True, max_length=50, verbose_name="领导")
    last_updated_time = models.DateTimeField(auto_now=True, null=True)
    chinese_name = models.CharField(max_length=30, blank=True)

    def __str__(self):
        return self.username
