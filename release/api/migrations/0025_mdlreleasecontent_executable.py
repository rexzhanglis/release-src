from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0024_releaseplan_is_auto'),
    ]

    operations = [
        migrations.AddField(
            model_name='mdlreleasecontent',
            name='executable',
            field=models.CharField(
                blank=True,
                help_text='部署的可执行文件，如 feeder_handler、feeder_receive、feeder_client',
                max_length=100,
                null=True,
                verbose_name='可执行文件名',
            ),
        ),
    ]
