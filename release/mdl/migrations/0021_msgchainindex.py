from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('mdl', '0020_mdlserver_executable'),
    ]

    operations = [
        migrations.CreateModel(
            name='MsgChainIndex',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('msg_key', models.CharField(max_length=20, unique=True, verbose_name='消息标识')),
                ('chain_json', models.JSONField(verbose_name='链路数据')),
                ('built_at', models.DateTimeField(auto_now=True, verbose_name='重建时间')),
                ('build_ms', models.IntegerField(default=0, verbose_name='重建耗时(ms)')),
            ],
            options={
                'verbose_name': '消息链路索引',
                'verbose_name_plural': '消息链路索引',
            },
        ),
    ]
