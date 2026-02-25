"""
author: zhixiong.zeng
python version: 3
time: 2021/9/28 15:52

mdl和rancher两种类型发布：

发布计划和发布详情共用同个model

发布内容因差异较大，分别建一个model

"""
import datetime

from django.db import models

from common.basemodels import TimestampedModel


class ReleasePlan(TimestampedModel):
    """发布计划"""
    name = models.CharField("名称", max_length=200, null=False, unique=True)
    project = models.CharField("项目", max_length=100, null=False)
    plan_release_time = models.DateTimeField("计划发布时间", null=True)
    owner = models.CharField("创建人", max_length=100, null=False)
    category = models.CharField("发布类型", max_length=20, null=True, default="正常发布")
    is_auto = models.BooleanField("自动发布", default=False)

    def get_all_release_contents(self):
        if self.project == 'MDL':
            return list(self.mdlreleasecontent_set.all().values("index", "issue_key", "release_version", "release_object",
                                                                "config_file", "type","status"))
        return list(
            self.releasecontent_set.all().values("index", "issue_key", "release_version", "rancher_app_version",
                                                 "config_file", "status"))

    def delete_release_contents(self):
        if self.project == 'MDL':
            return self.mdlreleasecontent_set.all().delete()
        return self.releasecontent_set.all().delete()

    def get_all_release_contents_objs(self):
        if self.project == 'MDL':
            return self.mdlreleasecontent_set.all()
        return self.releasecontent_set.all()

    def get_all_release_contents_status(self):
        if self.project == 'MDL':
            return self.mdlreleasecontent_set.all().values("index", "release_version", "release_object", "status")
        return list(
            self.releasecontent_set.all().values("index", "release_version", "rancher_app_version", "status"))

    def get_release_detail_status(self):
        if self.releasedetail_set.all():
            return self.releasedetail_set.all()[0].status
        return "未发布"

    def get_release_detail_release_time(self):
        """
        获取发布时间
        :return:
        """
        if self.releasedetail_set.all():
            return self.releasedetail_set.all()[0].created_time, self.releasedetail_set.all()[0].last_updated_time
        return None, None

    def __str__(self):
        return self.name


class ReleaseContent(TimestampedModel):
    """
    rancher发布计划内容

    release_version:对应jira单中的Multi Release Version字段
    rancher_app_version: 对应jira单中的Rancher APP 版本号
    """
    STATUS_CHOICES = (
        ("process", "process"),
        ("wait", "wait"),
        ("error", "error"),
        ("success", "success"),
    )
    release_plan = models.ForeignKey(ReleasePlan, verbose_name="所属发布计划", null=False, on_delete=models.CASCADE)
    index = models.IntegerField("发布顺序", null=False)
    issue_key = models.CharField("jira工单", max_length=50, null=False)
    release_version = models.CharField("发布版本", max_length=100, null=False)
    rancher_app_version = models.CharField("rancher app 版本", max_length=200, null=False)
    current_rancher_app_version = models.CharField("发布前的rancher app 版本", max_length=200, null=True)
    is_release = models.BooleanField("是否发布", default=True)
    status = models.CharField("发布状态", choices=STATUS_CHOICES, null=True, max_length=20, default="wait")
    config_file = models.JSONField("配置文件", null=True)  # 保存成字符串
    depconf_ticket_name = models.CharField("配置发布系统中的ticket名称", max_length=50, null=True, blank=True)

    def set_status(self, status):
        self.status = status
        self.save()

    def set_depconf_ticket_name(self, ticket_name):
        self.depconf_ticket_name = ticket_name
        self.save()

    def __str__(self):
        return self.release_plan.name


class MdlReleaseContent(TimestampedModel):
    """
    Mdl发布计划内容

    release_version:对应jira单中的Multi Release Version字段

    """
    STATUS_CHOICES = (
        ("process", "process"),
        ("wait", "wait"),
        ("error", "error"),
        ("success", "success"),
    )
    TYPE_CHOICES = (
        ("config", "仅配置变更"),
        ("version", "版本发布")
    )
    release_plan = models.ForeignKey(ReleasePlan, verbose_name="所属发布计划", null=False, on_delete=models.CASCADE)
    index = models.IntegerField("发布顺序", null=False)
    issue_key = models.CharField("jira工单", max_length=50, null=False, blank=True)
    release_version = models.CharField("发布版本", max_length=100, null=True, blank=True)
    current_version = models.CharField("当前版本", max_length=100, null=True, blank=True)
    is_release = models.BooleanField("是否发布", default=True)
    status = models.CharField("发布状态", choices=STATUS_CHOICES, null=True, max_length=20, default="wait")
    config_file = models.JSONField("配置文件", null=True, blank=True)  # 保存成字符串
    release_object = models.CharField("发布对象 服务器+服务名", max_length=200, null=False)
    type = models.CharField("发布类型", choices=TYPE_CHOICES, null=True, max_length=20)

    def set_status(self, status):
        self.status = status
        self.save()

    def __str__(self):
        return self.release_plan.name


class ReleaseDetail(TimestampedModel):
    """
    发布详细信息

    release_version:对应jira单中的Multi Release Version字段
    rancher_app_version: 对应jira单中的Rancher APP 版本号
    状态分类 升级中 暂停 失败 成功
    """
    STATUS_CHOICES = (
        ("发布中", "发布中"),
        ("发布失败", "发布失败"),
        ("发布成功", "发布成功"),
        ("暂停", "暂停"),
        ("回滚中", "回滚中"),
        ("回滚成功", "回滚成功"),
        ("回滚失败", "回滚失败"),
    )
    release_plan = models.ForeignKey(ReleasePlan, verbose_name="所属发布计划", null=False, on_delete=models.DO_NOTHING)
    user = models.CharField("执行发布用户", max_length=50, null=False)
    status = models.CharField("任务状态", default="升级中", max_length=20, choices=STATUS_CHOICES, null=False)
    prompt = models.TextField(null=True, blank=True)
    log = models.TextField(null=True, blank=True)
    active = models.IntegerField("流程图当前发布的位置", default=1)

    def set_log(self, log, user, level="info"):
        if self.log:
            self.log = self.log + "{} {} {} {}".format(str(datetime.datetime.now()), level, user, log) + "\n"
        else:
            self.log = "{} {} {} {}".format(str(datetime.datetime.now()), level, user, log) + "\n"
        self.prompt = log
        self.save()

    def set_status(self, status):
        self.status = status
        self.save()

    def set_active(self, index):
        self.active = index
        self.save()
