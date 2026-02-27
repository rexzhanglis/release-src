from django.urls import path, include
from django.http import JsonResponse
from rest_framework.routers import DefaultRouter


def dashboard_category_count(request):
    return JsonResponse({'code': 200, 'message': None, 'data': {
        'appModule': 0, 'db': 0, 'server': 0, 'network': 0
    }})

from api.viewsets.auth_viewset import AuthViewSet
from api.viewsets.cmdb_viewset import CmdbViewSet
from api.viewsets.jira_viewset import JiraViewSet
from api.viewsets.release_detail_viewset import ReleaseDetailViewSet
from api.viewsets.release_plan_viewset import ReleasePlanViewSet
from api.viewsets.user_viewset import UserViewSet
from api.viewsets.config_mgmt_viewset import (
    ConfigTreeViewSet,
    ConfigFileViewSet,
    ConfigSyncViewSet,
    ConfigDeployViewSet,
    ConfigInstanceViewSet,
    ServiceTypeViewSet,
    ConfigAuditLogViewSet,
    ConfigHistoryViewSet,
)

router = DefaultRouter()

router.register(r'auth', AuthViewSet, basename="auth")
router.register(r'user', UserViewSet, basename="user")
router.register(r'jira', JiraViewSet, basename="jira")
router.register(r'cmdb', CmdbViewSet, basename="cmdb")
router.register(r'releasePlan', ReleasePlanViewSet, basename="releasePlan")
router.register(r'releaseDetail', ReleaseDetailViewSet, basename="releaseDetail")

# MDL 配置管理
router.register(r'config-mgmt/tree', ConfigTreeViewSet, basename="config-tree")
router.register(r'config-mgmt/configs', ConfigFileViewSet, basename="config-file")
router.register(r'config-mgmt/sync', ConfigSyncViewSet, basename="config-sync")
router.register(r'config-mgmt/deploy', ConfigDeployViewSet, basename="config-deploy")
router.register(r'config-mgmt/instances', ConfigInstanceViewSet, basename="config-instance")
router.register(r'config-mgmt/service-types', ServiceTypeViewSet, basename="config-service-type")
router.register(r'config-mgmt/audit-logs', ConfigAuditLogViewSet, basename="config-audit-log")
router.register(r'config-mgmt/history', ConfigHistoryViewSet, basename="config-history")

urlpatterns = [
    path('', include(router.urls)),
    path('dashboard/get_category_count/', dashboard_category_count),
]
