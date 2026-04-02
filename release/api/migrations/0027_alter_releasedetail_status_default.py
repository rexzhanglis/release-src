from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0026_alter_mdlreleasecontent_executable'),
    ]

    operations = [
        migrations.AlterField(
            model_name='releasedetail',
            name='status',
            field=models.CharField(
                choices=[
                    ('发布中', '发布中'),
                    ('发布失败', '发布失败'),
                    ('发布成功', '发布成功'),
                    ('暂停', '暂停'),
                    ('回滚中', '回滚中'),
                    ('回滚成功', '回滚成功'),
                    ('回滚失败', '回滚失败'),
                ],
                default='发布中',
                max_length=20,
                verbose_name='任务状态',
            ),
        ),
    ]
