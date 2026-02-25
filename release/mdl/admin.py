from django import forms
from django.contrib import admin

from mdl.models import MdlServer, Label


class MdlServerForm(forms.ModelForm):

    def clean(self):
        from external.cmdb_client import CmdbClient
        cleaned_data = super().clean()
        data = cleaned_data['config_git_url']
        # 1. 生产环境机器请填写git对应的配置文件路径信息
        if not data and CmdbClient().get_server_info_by_ip(ip=cleaned_data['ip'])["env"] == 'prod':
            raise forms.ValidationError('生产环境机器请填写git对应的配置文件路径信息')
        if data:
            # 2. 非生产环境机器请不要填写git配置文件
            if CmdbClient().get_server_info_by_ip(ip=cleaned_data['ip'])["env"] != 'prod':
                raise forms.ValidationError('非生产环境机器请不要填写git配置文件')
            # 3. consul space与git配置文件不一致
            mdl_consul_base_path = "http://consul.wmcloud.com/v1/kv/configs/mdl/"
            config_git_path = str(cleaned_data['consul_space']).lstrip(mdl_consul_base_path) + cleaned_data['consul_files']
            if config_git_path not in data:
                raise forms.ValidationError('consul space与git配置文件不一致')
        return cleaned_data

    class Meta:
        model = MdlServer
        fields = '__all__'


@admin.register(MdlServer)
class MdlServerAdmin(admin.ModelAdmin):
    list_display = ['fqdn', 'role_name', 'ip', 'user', 'remote_python', 'config_git_url', 'consul_space',
                    'consul_token', 'install_dir', 'backups_dir', 'service_name', 'is_consistent']
    search_fields = ('fqdn', 'role_name', 'ip')
    form = MdlServerForm


@admin.register(Label)
class LabelAdmin(admin.ModelAdmin):
    search_fields = ('name',)
    ordering = ('name',)
    filter_horizontal = ('mdl_server',)
