from django.contrib import admin

# Register your models here.
from app.models import RancherProject, RancherApp, RancherWorkload


@admin.register(RancherProject)
class RancherProjectAdmin(admin.ModelAdmin):
    list_display = ['name', 'created_time', 'last_updated_time', 'cluster_id', 'project_id', 'env']
    search_fields = ('name', 'env')


@admin.register(RancherApp)
class RancherAppAdmin(admin.ModelAdmin):
    list_display = ['name', 'created_time', 'last_updated_time', 'project', 'app_id']
    search_fields = ('name', 'project__name')


@admin.register(RancherWorkload)
class RancherWorkloadAdmin(admin.ModelAdmin):
    list_display = ['name', 'created_time', 'last_updated_time', 'project_id', 'namespace_id', 'app', 'type',
                    'workload_id']
    search_fields = ('name', 'project_id__name', 'app__name')
