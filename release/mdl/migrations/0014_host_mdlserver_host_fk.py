from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('mdl', '0013_mdlserver_init_status'),
    ]

    operations = [
        migrations.CreateModel(
            name='Host',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_time', models.DateTimeField(auto_now_add=True, null=True)),
                ('last_updated_time', models.DateTimeField(auto_now=True, null=True)),
                ('fqdn', models.CharField(max_length=100, unique=True, verbose_name='FQDN')),
                ('ip', models.CharField(max_length=100, verbose_name='IP 地址')),
                ('user', models.CharField(default='root', max_length=30, verbose_name='SSH 用户')),
                ('remote_python', models.CharField(default='/usr/bin/python3', max_length=100, verbose_name='远端 Python 路径')),
            ],
            options={
                'verbose_name': '物理机',
                'verbose_name_plural': '物理机',
            },
        ),
        migrations.AddField(
            model_name='mdlserver',
            name='host',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='services',
                to='mdl.host',
                verbose_name='物理机',
            ),
        ),
    ]
