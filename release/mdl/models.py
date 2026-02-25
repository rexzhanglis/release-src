# Create your models here.

from django.db import models

from common.basemodels import TimestampedModel


class MdlServer(TimestampedModel):
    """
    mdl server 部署上线信息
    fqdn和service_name组成唯一索引
    一台机器上可能部署多个服务
    role_name 定义的是服务所处的角色
    install_dir /datayes/{role_name}/bin/
    """
    fqdn = models.CharField("fqdn", max_length=100)
    role_name = models.CharField("角色名称", max_length=100, null=True)
    ip = models.CharField(max_length=100, null=False)
    user = models.CharField("用户", max_length=30, default="root")
    remote_python = models.CharField("远端python", max_length=100)
    config_git_url = models.CharField("配置文件git链接", max_length=200, null=True, blank=True,
                                      help_text="生产环境需填git配置文件路径,stg环境不需要")
    consul_space = models.CharField("consul 地址", max_length=300)
    consul_token = models.CharField("token", max_length=100)
    install_dir = models.CharField("安装目录", max_length=100)
    backups_dir = models.CharField("备份目录", max_length=100)
    service_name = models.CharField("服务名", max_length=100)
    is_consistent = models.BooleanField("是否与生产信息一致", default=True)
    check_detail = models.CharField("检查结果详细信息", null=True, max_length=200, blank=True)
    consul_files = models.CharField("consul中的配置文件", default="feeder_handler.cfg", max_length=50,
                                    help_text="如果不是feeder_handler.cfg配置文件，请改成实际的配置文件名称")

    def __str__(self):
        return self.fqdn + "_" + self.ip + "_" + self.service_name

    class Meta:
        unique_together = ('fqdn', 'service_name',)


class Label(TimestampedModel):
    """
    增加自定义标签，通过标签前端一次性增加多个服务器，减少不必要的重复
    """
    name = models.CharField('标签名', max_length=150, unique=True)
    mdl_server = models.ManyToManyField(
        MdlServer,
        verbose_name=('mdl_server'),
        blank=True,
    )

    def __str__(self):
        return self.name


# ========== MDL 配置管理模型 ==========

class ServiceType(TimestampedModel):
    """MDL 服务类型，对应 Git 仓库一级目录，如 aliforward、forward、barcal"""
    name = models.CharField("服务类型名称", max_length=100, unique=True)
    description = models.CharField("描述", max_length=200, null=True, blank=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "服务类型"
        verbose_name_plural = "服务类型"


class ConfigInstance(TimestampedModel):
    """MDL 配置实例，对应 Git 仓库二级目录，如 10.121.21.219_19013"""
    service_type = models.ForeignKey(ServiceType, verbose_name="服务类型", on_delete=models.CASCADE)
    name = models.CharField("实例名称", max_length=200)
    host_ip = models.CharField("主机IP", max_length=50, null=True, blank=True)
    port = models.IntegerField("端口", null=True, blank=True)
    config_path = models.CharField("配置目录路径", max_length=300, null=True, blank=True)
    service_name = models.CharField("服务名", max_length=100, null=True, blank=True)
    install_dir = models.CharField("安装目录", max_length=200, null=True, blank=True)
    backups_dir = models.CharField("备份目录", max_length=200, null=True, blank=True)
    consul_space = models.CharField("Consul KV 前缀", max_length=300, null=True, blank=True)
    consul_files = models.CharField("Consul 配置文件列表", max_length=200, default="feeder_handler.cfg")
    remote_python = models.CharField("远端 Python 路径", max_length=100, default="/usr/bin/python3")

    def __str__(self):
        return f"{self.service_type.name}/{self.name}"

    class Meta:
        unique_together = ('service_type', 'name')
        verbose_name = "配置实例"
        verbose_name_plural = "配置实例"


class ConfigFile(TimestampedModel):
    """MDL 配置文件，对应 Git 仓库三级文件，如 feeder_handler.cfg"""
    instance = models.ForeignKey(ConfigInstance, verbose_name="所属实例", on_delete=models.CASCADE)
    filename = models.CharField("文件名", max_length=200)
    content = models.JSONField("配置内容(JSON)", null=True, blank=True)
    raw_content = models.TextField("原始内容", null=True, blank=True)
    git_path = models.CharField("Git 路径", max_length=500, null=True, blank=True)

    def __str__(self):
        return f"{self.instance}/{self.filename}"

    class Meta:
        unique_together = ('instance', 'filename')
        verbose_name = "配置文件"
        verbose_name_plural = "配置文件"


class ConfigDeployTask(TimestampedModel):
    """MDL 配置部署任务"""
    STATUS_CHOICES = [
        ('pending', 'pending'),
        ('running', 'running'),
        ('success', 'success'),
        ('failed', 'failed'),
    ]
    instances = models.ManyToManyField(ConfigInstance, verbose_name="部署实例", blank=True)
    operator = models.CharField("操作人", max_length=100)
    status = models.CharField("任务状态", max_length=20, choices=STATUS_CHOICES, default='pending')
    log = models.TextField("执行日志", null=True, blank=True)
    finished_at = models.DateTimeField("完成时间", null=True, blank=True)

    def __str__(self):
        return f"ConfigDeployTask({self.id}) - {self.status}"

    class Meta:
        verbose_name = "配置部署任务"
        verbose_name_plural = "配置部署任务"
