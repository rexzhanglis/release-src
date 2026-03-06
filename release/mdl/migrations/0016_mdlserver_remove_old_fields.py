"""
删除 MdlServer 上已迁入 Host 的冗余字段：fqdn、ip、user、remote_python。
同时将 host 外键改为 NOT NULL，unique_together 改为 (host, service_name)。
"""
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('mdl', '0015_migrate_host_data'),
    ]

    operations = [
        # 1. host 改为 NOT NULL
        migrations.AlterField(
            model_name='mdlserver',
            name='host',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='services',
                to='mdl.host',
                verbose_name='物理机',
            ),
        ),
        # 2. 替换 unique_together
        migrations.AlterUniqueTogether(
            name='mdlserver',
            unique_together={('host', 'service_name')},
        ),
        # 3. 删除旧字段
        migrations.RemoveField(model_name='mdlserver', name='fqdn'),
        migrations.RemoveField(model_name='mdlserver', name='ip'),
        migrations.RemoveField(model_name='mdlserver', name='user'),
        migrations.RemoveField(model_name='mdlserver', name='remote_python'),
    ]
