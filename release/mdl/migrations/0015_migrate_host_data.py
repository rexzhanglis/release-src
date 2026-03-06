"""
数据迁移：按 (fqdn, ip) 去重创建 Host 记录，填充 MdlServer.host_id。
"""
from django.db import migrations


def forward(apps, schema_editor):
    MdlServer = apps.get_model('mdl', 'MdlServer')
    Host = apps.get_model('mdl', 'Host')

    seen = {}  # fqdn -> Host instance
    for server in MdlServer.objects.all():
        fqdn = server.fqdn
        if fqdn not in seen:
            host, _ = Host.objects.get_or_create(
                fqdn=fqdn,
                defaults={
                    'ip': server.ip,
                    'user': server.user,
                    'remote_python': server.remote_python,
                }
            )
            seen[fqdn] = host
        server.host = seen[fqdn]
        server.save(update_fields=['host'])


def backward(apps, schema_editor):
    MdlServer = apps.get_model('mdl', 'MdlServer')
    MdlServer.objects.update(host=None)
    apps.get_model('mdl', 'Host').objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('mdl', '0014_host_mdlserver_host_fk'),
    ]

    operations = [
        migrations.RunPython(forward, backward),
    ]
