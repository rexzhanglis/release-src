from django.db import migrations, models


class Migration(migrations.Migration):
    """
    init_status was added to the MdlServer model without a migration.
    The column may already exist on some databases. We use SeparateDatabaseAndState
    so Django's state is updated regardless, and we only run the DDL if the column
    does not already exist.
    """

    dependencies = [
        ('mdl', '0012_configauditlog'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            # Update Django's internal migration state unconditionally
            state_operations=[
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
            ],
            # Only run DDL if the column doesn't already exist
            database_operations=[
                migrations.RunSQL(
                    sql="""
                        ALTER TABLE mdl_mdlserver
                        ADD COLUMN init_status VARCHAR(20) NOT NULL DEFAULT 'uninitialized';
                    """,
                    reverse_sql="""
                        ALTER TABLE mdl_mdlserver DROP COLUMN init_status;
                    """,
                    hints={'init_status_may_exist': True},
                ),
            ],
        ),
    ]
