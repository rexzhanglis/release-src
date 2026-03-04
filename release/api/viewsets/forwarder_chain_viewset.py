# -*- coding: utf-8 -*-
"""
转发链路查询
输入消息号（格式：serviceId.msgId，如 6.53 或 2.5），返回：
  - 配置侧：哪些转发机在配置文件里包含该消息
  - 实时侧：哪些转发机当前有下游订阅该消息（via heartbeat?ss=1）
"""
import concurrent.futures

import requests as http_requests
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import viewsets, status as drf_status

from mdl.models import MdlServer, ConfigFile
from common.utils.apiutil import ApiResponse

# Service ID -> 名称映射（来自 mdl-message.txt）
SERVICE_ID_MAP = {
    2:  'MDLSID_MDL_SYS（系统）',
    3:  'MDLSID_MDL_SHL1（沪L1）',
    4:  'MDLSID_MDL_SHL2（沪L2）',
    5:  'MDLSID_MDL_SZL1（深L1）',
    6:  'MDLSID_MDL_SZL2（深L2）',
    7:  'MDLSID_MDL_CFFEX（中金所期货）',
    8:  'MDLSID_MDL_CZCE（郑交所期货）',
    9:  'MDLSID_MDL_SHFE（上期所期货）',
    10: 'MDLSID_MDL_DCE（大商所期货）',
    11: 'MDLSID_MDL_HKEX（港股）',
    12: 'MDLSID_MDL_SWG（申万行业分类）',
    13: 'MDLSID_MDL_BAR（衍生数据）',
    14: 'MDLSID_MDL_NEEQ（新三板）',
    16: 'MDLSID_MDL_SHNY（上期能源）',
    19: 'MDLSID_MDL_CSI（中证指数）',
    20: 'MDLSID_MDL_CNI（国证指数）',
    21: 'MDLSID_MDL_CFFEXL2（中金所期货L2）',
    22: 'MDLSID_MDL_SHFEL2（上期&能源L2）',
    23: 'MDLSID_MDL_CZCEL2（郑商所期货L2）',
    24: 'MDLSID_MDL_DCEL2（大商所期货L2）',
    25: 'MDLSID_MDL_GFEX（广期所期货）',
    26: 'MDLSID_MDL_GFEXL2（广期所期货L2）',
}

# Service Name -> Service ID 反向映射（用于配置文件解析）
SERVICE_NAME_TO_ID = {
    'MDLSID_MDL_SYS': 2,
    'MDLSID_MDL_SHL1': 3,
    'MDLSID_MDL_SHL2': 4,
    'MDLSID_MDL_SZL1': 5,
    'MDLSID_MDL_SZL2': 6,
    'MDLSID_MDL_CFFEX': 7,
    'MDLSID_MDL_CZCE': 8,
    'MDLSID_MDL_SHFE': 9,
    'MDLSID_MDL_DCE': 10,
    'MDLSID_MDL_HKEX': 11,
    'MDLSID_MDL_SWG': 12,
    'MDLSID_MDL_BAR': 13,
    'MDLSID_MDL_NEEQ': 14,
    'MDLSID_MDL_SHNY': 16,
    'MDLSID_MDL_CSI': 19,
    'MDLSID_MDL_CNI': 20,
    'MDLSID_MDL_CFFEXL2': 21,
    'MDLSID_MDL_SHFEL2': 22,
    'MDLSID_MDL_CZCEL2': 23,
    'MDLSID_MDL_DCEL2': 24,
    'MDLSID_MDL_GFEX': 25,
    'MDLSID_MDL_GFEXL2': 26,
}

HEARTBEAT_PORT = 8080
HEARTBEAT_TIMEOUT = 3  # 秒


def parse_query_msg(msg_str):
    """
    解析查询参数，支持两种格式：
      '6.53'  -> service_id=6, msg_id=53
      '53'    -> service_id=None, msg_id=53（匹配所有 service）
    返回 (service_id_or_None, msg_id)，失败返回 None
    """
    msg_str = str(msg_str).strip()
    if '.' in msg_str:
        parts = msg_str.split('.', 1)
        try:
            return int(parts[0]), int(parts[1])
        except ValueError:
            return None
    else:
        try:
            return None, int(msg_str)
        except ValueError:
            return None


def search_config_files(service_id, msg_id):
    """
    在 ConfigFile 的 content 里搜索包含目标消息的转发机。
    配置结构：MSG_FORWARDER.UpStreams[].Services[].{Name, Version, Messages}
    返回 list of dict
    """
    results = []
    config_files = ConfigFile.objects.filter(filename='feeder_handler.cfg').select_related('instance')
    for cf in config_files:
        content = cf.content
        if not content or not isinstance(content, dict):
            continue
        forwarder = content.get('MSG_FORWARDER', {})
        upstreams = forwarder.get('UpStreams', [])
        if not isinstance(upstreams, list):
            continue
        for upstream in upstreams:
            upstream_addr = upstream.get('Address', '')
            services = upstream.get('Services', [])
            if not isinstance(services, list):
                continue
            for svc in services:
                svc_name = svc.get('Name', '')
                messages = svc.get('Messages', [])
                if not isinstance(messages, list):
                    continue
                # 将 service name 转换为 service_id
                svc_id = SERVICE_NAME_TO_ID.get(svc_name)
                # 检查是否匹配
                if msg_id not in messages:
                    continue
                if service_id is not None and svc_id != service_id:
                    continue
                results.append({
                    'fqdn': cf.instance.name,
                    'instance': str(cf.instance),
                    'upstream_address': upstream_addr,
                    'service_name': svc_name,
                    'service_id': svc_id,
                    'msg_label': f'{svc_id}.{msg_id}' if svc_id else str(msg_id),
                    'all_messages': messages,
                })
    return results


def parse_subscriptions(sub_str, service_id, msg_id):
    """
    解析 subscriptions 字符串，如 "2,101,5;6,101,53;"
    格式：version,serviceVersion,msgId; 分号分隔
    返回匹配的订阅列表 [(version, svc_version, msg_id), ...]
    """
    matched = []
    for item in sub_str.split(';'):
        item = item.strip()
        if not item:
            continue
        parts = item.split(',')
        if len(parts) != 3:
            continue
        try:
            v = int(parts[0])
            sv = int(parts[1])
            m = int(parts[2])
        except ValueError:
            continue
        if m != msg_id:
            continue
        if service_id is not None and v != service_id:
            continue
        matched.append({'version': v, 'svc_version': sv, 'msg_id': m,
                        'label': f'{v}.{m}'})
    return matched


def fetch_heartbeat(server):
    """
    请求单台服务器的 heartbeat 接口，返回解析结果。
    """
    ip = server.ip
    url = f'http://{ip}:{HEARTBEAT_PORT}/heartbeat?ss=1'
    try:
        resp = http_requests.get(url, timeout=HEARTBEAT_TIMEOUT)
        resp.raise_for_status()
        return ip, server.fqdn, resp.json(), None
    except Exception as e:
        return ip, server.fqdn, None, str(e)


def search_heartbeat(service_id, msg_id):
    """
    并发请求所有 ready 状态服务器的 heartbeat，
    找出当前有下游订阅目标消息的连接。
    """
    servers = list(MdlServer.objects.filter(init_status='ready'))
    if not servers:
        return [], []

    results = []
    unreachable = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        futures = {executor.submit(fetch_heartbeat, s): s for s in servers}
        for future in concurrent.futures.as_completed(futures):
            ip, fqdn, data, err = future.result()
            if err or not data:
                unreachable.append({'ip': ip, 'fqdn': fqdn, 'error': err or '无响应'})
                continue
            session = data.get('session_status', {})
            connections = session.get('connections', [])
            for conn in connections:
                sub_str = conn.get('subscriptions', '')
                matched = parse_subscriptions(sub_str, service_id, msg_id)
                if matched:
                    results.append({
                        'forwarder_ip': ip,
                        'forwarder_fqdn': fqdn,
                        'client_address': conn.get('address', ''),
                        'start_date': conn.get('start_date', ''),
                        'start_time': conn.get('start_time', ''),
                        'pending_bytes': conn.get('pending_bytes', 0),
                        'matched_subscriptions': matched,
                    })
    return results, unreachable


class ForwarderChainViewSet(viewsets.ViewSet):
    """
    转发链路查询
    GET /mdl-forwarder/chain/?msg=6.53
    GET /mdl-forwarder/chain/?msg=53        # 匹配所有 service 里的 msg 53
    GET /mdl-forwarder/chain/services/      # 返回 service 列表（供前端下拉）
    """

    @action(detail=False, methods=['get'], url_path='services')
    def services(self, request):
        """返回 Service ID 列表"""
        data = [
            {'service_id': sid, 'label': f'{sid} — {name}'}
            for sid, name in sorted(SERVICE_ID_MAP.items())
        ]
        return ApiResponse(data=data)

    def list(self, request):
        msg_param = request.query_params.get('msg', '').strip()
        if not msg_param:
            return Response(
                {'code': 400, 'message': '缺少参数 msg，格式：6.53 或 53'},
                status=drf_status.HTTP_400_BAD_REQUEST
            )

        parsed = parse_query_msg(msg_param)
        if parsed is None:
            return Response(
                {'code': 400, 'message': f'参数格式错误：{msg_param}，支持 "6.53" 或 "53"'},
                status=drf_status.HTTP_400_BAD_REQUEST
            )
        service_id, msg_id = parsed

        # 并行执行配置查询和 heartbeat 查询
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            f_config = executor.submit(search_config_files, service_id, msg_id)
            f_live = executor.submit(search_heartbeat, service_id, msg_id)
            config_results = f_config.result()
            live_results, unreachable = f_live.result()

        # 构建 service 显示名
        service_label = ''
        if service_id is not None:
            service_label = SERVICE_ID_MAP.get(service_id, str(service_id))

        return ApiResponse(data={
            'query': {
                'msg': msg_param,
                'service_id': service_id,
                'msg_id': msg_id,
                'service_label': service_label,
            },
            'config': config_results,
            'live': live_results,
            'unreachable': unreachable,
        })
