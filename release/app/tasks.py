import os, django, logging

from common.decorator import cron_log

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "release.settings")
django.setup()

from const.models import Constance
from external.rancher_client import RancherClient

from app.models import RancherProject, RancherApp, RancherWorkload

cron_logger = logging.getLogger("cron")


@cron_log
def update_rancher_projects_task():
    """
     浏览器直接访问可看到所有字段信息
     https://rancher2.wmcloud-qa.com/v3/cluster/c-4wfqt/projects
    """
    project_list = []
    for env in Constance.get_value("env"):
        for project in RancherClient(env).get_all_projects():
            info = {
                "name": project['name'],
                "cluster_id": project['clusterId'],
                "project_id": project['id'],
                "env": env
            }
            project_list.append(project["id"])
            RancherProject.objects.update_or_create(name=project['name'], cluster_id=project['clusterId'],
                                                    defaults=info)
    # 删除rancher上不存在的项目
    RancherProject.objects.exclude(project_id__in=project_list).delete()


@cron_log
def update_rancher_app_id_task():
    """
     浏览器直接访问可看到所有字段信息
     https://rancher2.wmcloud-qa.com/v3/cluster/c-4wfqt/projects
    """
    app_list = []
    for project in RancherProject.objects.all():
        try:
            for app in RancherClient(project.env).get_all_apps(project.project_id):
                data = {
                    "name": app["name"],
                    "app_id": app["id"],
                    "project": project,
                }
                app_list.append(app["id"])
                RancherApp.objects.update_or_create(app_id=app["id"], defaults=data)
                print("update app {} {}".format(project.name, app['name']))
        except Exception:
            print("abnormal app {} {}".format(project.name, app['name']))
    # 删除rancher上不存在的app
    RancherApp.objects.exclude(app_id__in=app_list).delete()


@cron_log
def update_rancher_workloads_task():
    """
     浏览器直接访问可看到所有字段信息
     https://rancher2.wmcloud-qa.com/v3/cluster/c-4wfqt/projects
    """
    RancherWorkload.objects.all().delete()
    projects = RancherProject.objects.all()
    if not projects:
        raise Exception("no project")
    for project in projects:
        for workload in RancherClient(project.env).get_all_workloads(project.project_id):
            try:
                data = {
                    "name": workload['name'],
                    "project_id": project,
                    "namespace_id": workload['namespaceId'],
                    "app": RancherApp.objects.get(name=workload['workloadLabels']["app"]),
                    "type": workload['type'],
                    "workload_id": workload['id']
                }
                RancherWorkload.objects.create(**data)
                print("update {} success".format(workload['name']))
            except Exception as ex:
                print("update {} abnormal {}".format(workload['name'], str(ex)))


@cron_log
def update_rancher_app_task():
    update_rancher_projects_task()
    update_rancher_app_id_task()
    update_rancher_workloads_task()


if __name__ == '__main__':
    update_rancher_app_id_task()
    # update_rancher_workloads_task()
    # RancherApp.objects.all().delete()
    # RancherProject.objects.all().delete()
