import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
      ('mdl', '0017_host_init_status'),
    ]

    operations = [
        migrations.CreateModel(
            name='MdlOperationLog',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('service_name', models.CharField(blank=True, default='', max_length=100, verbose_name='服务名')),
                ('action', models.CharField(choices=[
                    ('service_create', '新增服务实例'),
                    ('service_edit', '编辑服务实例'),
                    ('service_delete', '删除服务实例'),
                    ('service_init', '初始化服务实例'),
                    ('host_init', '初始化服务器'),
                    ('systemd_start', 'systemd start'),
                    ('systemd_stop', 'systemd stop'),
                    ('systemd_restart', 'systemd restart'),
                    ('systemd_enable', 'systemd enable'),
                    ('systemd_disable', 'systemd disable'),
                ], max_length=30, verbose_name='操作类型')),
                ('operator', models.CharField(default='system', max_length=100, verbose_name='操作人')),
                ('status', models.CharField(choices=[('success', '成功'), ('failed', '失败')], default='success', max_length=20, verbose_name='结果')),
                ('detail', models.TextField(blank=True, default='', verbose_name='详情')),
                ('created_time', models.DateTimeField(auto_now_add=True, verbose_name='操作时间')),
                ('host', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='operation_logs', to='mdl.host', verbose_name='物理机')),
            ],
            options={
                'verbose_name': '操作日志',
                'verbose_name_plural': '操作日志',
                'ordering': ['-created_time'],
            },
        ),
        migrations.CreateModel(
            name='SystemdServiceCache',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('services', models.JSONField(default=list, verbose_name='服务列表快照')),
                ('refreshed_at', models.DateTimeField(blank=True, null=True, verbose_name='最后刷新时间')),
                ('error', models.TextField(blank=True, default='', verbose_name='错误信息')),
                ('host', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='systemd_cache', to='mdl.host', verbose_name='物理机')),
            ],
            options={
                'verbose_name': 'systemd 缓存',
                'verbose_name_plural': 'systemd 缓存',
            },
        ),
    ]
