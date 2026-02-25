# Create your models here.

from django.db import models

from common.basemodels import TimestampedModel

TYPE_CHOICES = (
    ("str", "str"),
    ("json", "json"),
    ("list", "list"),
    ("int", "int"),
)


class Constance(TimestampedModel):
    """
    记录配置常量信息
    """
    key = models.CharField(max_length=50, null=False, default="")
    value = models.TextField(null=False)
    type = models.CharField(default="str", choices=TYPE_CHOICES, max_length=10)
    description = models.CharField("描述信息", max_length=100, null=True, blank=True)

    @classmethod
    def get_value(cls, key):
        obj = cls.objects.get(key=key)
        return obj.value if obj.type == "str" else eval(obj.value)
