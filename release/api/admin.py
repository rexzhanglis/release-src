from django.contrib import admin

# Register your models here.
from api.models import ReleaseDetail, ReleaseContent, ReleasePlan, MdlReleaseContent


@admin.register(ReleaseDetail)
class ReleaseDetailAdmin(admin.ModelAdmin):
    list_display = ['release_plan', 'user', 'status', 'prompt']
    search_fields = ('user', 'release_plan', 'status')


@admin.register(ReleaseContent)
class ReleaseContentAdmin(admin.ModelAdmin):
    list_display = ['release_plan', 'index', 'issue_key', 'release_version', 'rancher_app_version',
                    'current_rancher_app_version', 'status',
                    'is_release']
    search_fields = ('release_plan', 'release_version', 'issue_key')


@admin.register(ReleasePlan)
class ReleasePlanAdmin(admin.ModelAdmin):
    list_display = ['name', 'project', 'created_time', 'last_updated_time', 'owner']
    search_fields = ('name', 'project', 'owner')


@admin.register(MdlReleaseContent)
class MdlReleaseContentAdmin(admin.ModelAdmin):
    list_display = ['release_plan', 'index', 'release_object', 'issue_key', 'release_version', 'current_version',
                    'type', 'status', 'is_release']
    search_fields = ('release_plan', 'server', 'issue_key', 'release_version')
