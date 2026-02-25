from django.db import models


class TimestampedModel(models.Model):
    created_time = models.DateTimeField(auto_now_add=True, null=True)
    last_updated_time = models.DateTimeField(auto_now=True, null=True)

    class Meta:
        abstract = True


class UserModel(models.Model):
    created_user = models.CharField(max_length=30, default="")
    last_updated_user = models.CharField(max_length=30, default="")

    class Meta:
        abstract = True


class DeleteModel(models.Model):
    is_deleted = models.BooleanField("是否删除", default=False)

    class Meta:
        abstract = True
