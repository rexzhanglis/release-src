from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('mdl', '0012_configauditlog'),
    ]

    operations = [
        migrations.AddField(
            model_name='mdlserver',
            name='init_status',
            field=models.CharField(
                choices=[
                    ('uninitialized', '未初始化'),
                    ('initializing', '初始化中'),
                    ('ready', '运行中'),
                    ('failed', '初始化失败'),
                    ('retired', '已退役'),
                ],
                default='uninitialized',
                max_length=20,
                verbose_name='初始化状态',
            ),
        ),
    ]
