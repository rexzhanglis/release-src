# Create your models here.

from django.db import models

from common.basemodels import TimestampedModel


class RancherProject(TimestampedModel):
    """rancher 环境中的项目"""
    name = models.CharField("项目名", max_length=100, null=True)
    cluster_id = models.CharField("rancher中项目所属集群id", max_length=100, null=True)
    project_id = models.CharField("rancher中项目id", max_length=100, null=True)
    env = models.CharField("rancher 环境", max_length=30, null=True)

    def __str__(self):
        return self.name


class RancherApp(TimestampedModel):
    """
    rancher中的app
    """
    name = models.CharField("名字", max_length=200)
    project = models.ForeignKey(RancherProject, verbose_name="所属项目", on_delete=models.DO_NOTHING)
    app_id = models.CharField("app id", max_length=200)

    def __str__(self):
        return self.name


class RancherWorkload(TimestampedModel):
    """
    rancher中的workload
    workloadLabels中的app即为该model中的app
    "workloadLabels": {
    "app": "devops-nextcmdb",
    "chart": "13.0.0-devops-nextcmdb-1.0.0-26",
    "component": "devops-nextcmdb",
    "heritage": "Tiller",
    "io.cattle.field/appId": "devops-nextcmdb",
    "release": "devops-nextcmdb"
    }
    """
    name = models.CharField("工作负载名", max_length=100, null=True)
    project_id = models.ForeignKey(RancherProject, on_delete=models.CASCADE)
    namespace_id = models.CharField("命名空间", max_length=300, null=True)
    app = models.ForeignKey(RancherApp, on_delete=models.CASCADE)
    type = models.CharField("类型", max_length=50, null=True)
    # workload id  deployment:aladdin-adventure-clouddeploy:aladdin-adventure-clouddeploy
    workload_id = models.CharField("rancher中workload id", max_length=300, null=True)

    def __str__(self):
        return self.name
