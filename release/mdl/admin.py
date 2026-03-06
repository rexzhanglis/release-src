from django.contrib import admin

from mdl.models import MdlServer, Host, Label


@admin.register(Host)
class HostAdmin(admin.ModelAdmin):
    list_display = ['fqdn', 'ip', 'user', 'remote_python', 'init_status', 'created_time']
    search_fields = ('fqdn', 'ip')
    ordering = ('fqdn',)


@admin.register(MdlServer)
class MdlServerAdmin(admin.ModelAdmin):
    list_display = ['get_fqdn', 'role_name', 'get_ip', 'service_name', 'install_dir',
                    'consul_space', 'consul_token', 'backups_dir', 'is_consistent', 'init_status']
    search_fields = ('host__fqdn', 'host__ip', 'role_name', 'service_name')

    @admin.display(description='FQDN', ordering='host__fqdn')
    def get_fqdn(self, obj):
        return obj.host.fqdn

    @admin.display(description='IP 地址', ordering='host__ip')
    def get_ip(self, obj):
        return obj.host.ip


@admin.register(Label)
class LabelAdmin(admin.ModelAdmin):
    search_fields = ('name',)
    ordering = ('name',)
    filter_horizontal = ('mdl_server',)
