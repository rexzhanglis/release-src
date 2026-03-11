import logging
import threading

from django.apps import AppConfig

logger = logging.getLogger('forwarder_chain')


class MdlConfig(AppConfig):
    name = 'mdl'
    verbose_name = 'MDL 管理'
    default_auto_field = 'django.db.models.BigAutoField'

    def ready(self):
        # 注册 signals
        import mdl.signals  # noqa

        # 服务启动后在后台线程做一次全量初始索引
        # 延迟 5 秒：等待数据库连接池和迁移都已就绪
        t = threading.Timer(5.0, self._initial_rebuild)
        t.daemon = True
        t.name = 'chain-index-init'
        t.start()

    @staticmethod
    def _initial_rebuild():
        try:
            from api.viewsets.forwarder_chain_viewset import rebuild_all_chain_indexes
            from django.db import close_old_connections
            close_old_connections()
            logger.info('[ChainIndex] 服务启动，开始初始全量重建...')
            rebuild_all_chain_indexes()
        except Exception as e:
            logger.error(f'[ChainIndex] 启动初始重建失败: {e}')
