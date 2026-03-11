"""
ConfigFile post_save 信号：
每当配置文件内容被保存，在后台线程异步触发全量重建消息链路索引。

使用全量重建而非精确重建的原因：
  一个配置文件的变更可能影响多条消息链路，且 _build_ip_to_config_map 本身
  是全量加载的，精确判断哪些 msg_key 受影响的成本与全量重建相近。
"""
import logging
import threading

from django.db.models.signals import post_save
from django.dispatch import receiver

from mdl.models import ConfigFile

logger = logging.getLogger('forwarder_chain')

# 防抖：上一次重建还没完成时不再重复触发
_rebuild_lock = threading.Lock()
_rebuild_running = False


def _run_rebuild():
    global _rebuild_running
    try:
        # 延迟导入，避免循环依赖（signal 在 app ready 阶段注册，viewset 尚未全部加载）
        from api.viewsets.forwarder_chain_viewset import rebuild_all_chain_indexes
        from django.db import close_old_connections
        close_old_connections()
        rebuild_all_chain_indexes()
    except Exception as e:
        logger.error(f'[ChainIndex] 后台重建异常: {e}')
    finally:
        global _rebuild_running
        with _rebuild_lock:
            _rebuild_running = False


@receiver(post_save, sender=ConfigFile)
def on_config_file_saved(sender, instance, **kwargs):
    """ConfigFile 保存后异步触发全量重建。"""
    global _rebuild_running
    with _rebuild_lock:
        if _rebuild_running:
            logger.debug('[ChainIndex] 重建已在进行中，跳过本次触发')
            return
        _rebuild_running = True

    logger.info(f'[ChainIndex] ConfigFile({instance.id}) 已保存，触发异步重建...')
    t = threading.Thread(target=_run_rebuild, daemon=True, name='chain-index-rebuild')
    t.start()
