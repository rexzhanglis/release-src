from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('mdl', '0016_mdlserver_remove_old_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='host',
            name='init_status',
            field=models.CharField(
                choices=[
                    ('uninitialized', '未初始化'),
                    ('initializing', '初始化中'),
                    ('ready', '已初始化'),
                    ('failed', '初始化失败'),
                ],
                default='uninitialized',
                max_length=20,
                verbose_name='初始化状态',
            ),
        ),
    ]
