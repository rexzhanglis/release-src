from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('mdl', '0011_configdeploytask_configfile_configinstance_servicetype'),
    ]

    operations = [
        migrations.CreateModel(
            name='ConfigAuditLog',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_time', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('last_updated_time', models.DateTimeField(auto_now=True, verbose_name='最后更新时间')),
                ('action', models.CharField(choices=[
                    ('save',         '保存配置'),
                    ('batch_update', '批量修改'),
                    ('text_replace', '文本替换'),
                    ('git_commit',   '提交 Git'),
                    ('push_consul',  '推送 Consul'),
                    ('deploy',       'Ansible 部署'),
                    ('sync',         '同步 GitLab'),
                ], max_length=30, verbose_name='操作类型')),
                ('operator', models.CharField(max_length=100, verbose_name='操作人')),
                ('status', models.CharField(choices=[
                    ('success', '成功'),
                    ('failed',  '失败'),
                    ('partial', '部分成功'),
                ], default='success', max_length=20, verbose_name='结果')),
                ('instance_names', models.TextField(blank=True, default='', verbose_name='实例列表')),
                ('filename', models.CharField(blank=True, default='', max_length=200, verbose_name='配置文件')),
                ('summary', models.TextField(blank=True, default='', verbose_name='操作摘要')),
                ('detail', models.TextField(blank=True, default='', verbose_name='详情(JSON)')),
                ('deploy_task', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='audit_logs',
                    to='mdl.configdeploytask',
                    verbose_name='关联部署任务',
                )),
            ],
            options={
                'verbose_name': '配置审计日志',
                'verbose_name_plural': '配置审计日志',
                'ordering': ['-created_time'],
            },
        ),
    ]
