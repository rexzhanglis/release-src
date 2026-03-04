# -*- coding: utf-8 -*-
"""
转发链路查询
输入消息号（格式：serviceId.msgId，如 6.53 或 2.5），返回：
  - 配置侧：从包含该消息的转发机开始，递归向上追溯完整链路直到源头
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

# Service Name -> Service ID 反向映射
SERVICE_NAME_TO_ID = {
    'MDLSID_MDL_SYS': 2,   'MDLSID_MDL_SHL1': 3,  'MDLSID_MDL_SHL2': 4,
    'MDLSID_MDL_SZL1': 5,  'MDLSID_MDL_SZL2': 6,  'MDLSID_MDL_CFFEX': 7,
    'MDLSID_MDL_CZCE': 8,  'MDLSID_MDL_SHFE': 9,  'MDLSID_MDL_DCE': 10,
    'MDLSID_MDL_HKEX': 11, 'MDLSID_MDL_SWG': 12,  'MDLSID_MDL_BAR': 13,
    'MDLSID_MDL_NEEQ': 14, 'MDLSID_MDL_SHNY': 16, 'MDLSID_MDL_CSI': 19,
    'MDLSID_MDL_CNI': 20,  'MDLSID_MDL_CFFEXL2': 21, 'MDLSID_MDL_SHFEL2': 22,
    'MDLSID_MDL_CZCEL2': 23, 'MDLSID_MDL_DCEL2': 24, 'MDLSID_MDL_GFEX': 25,
    'MDLSID_MDL_GFEXL2': 26,
}

HEARTBEAT_PORT = 8080
HEARTBEAT_TIMEOUT = 3


def parse_query_msg(msg_str):
    """
    解析查询参数：'6.53' -> (6, 53)，'53' -> (None, 53)
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


def _build_ip_to_config_map():
    """
    预加载所有 feeder_handler.cfg，构建两个索引：
      ip_to_cf:       ip -> ConfigFile（通过 instance.host_ip 或 instance.name 解析）
      ip_port_to_cf:  (ip, port) -> ConfigFile（通过 Publishers.Address 解析）
    返回 (ip_to_cf, ip_port_to_cf, all_cfs)
    """
    all_cfs = list(ConfigFile.objects.filter(filename='feeder_handler.cfg').select_related('instance'))

    ip_to_cf = {}       # ip -> cf（一台机器只有一个主 IP）
    ip_port_to_cf = {}  # (ip, port) -> cf

    for cf in all_cfs:
        # 从 instance.host_ip 或 instance.name（格式通常含IP）获取 IP
        ip = (cf.instance.host_ip or '').strip()
        if not ip:
            # 尝试从 instance name 解析（如 "10.121.21.240_19015"）
            name = cf.instance.name
            ip = name.split('_')[0] if '_' in name else ''
        if ip:
            ip_to_cf[ip] = cf

        # 从 Publishers[].Address 解析监听端口，格式 "0.0.0.0:9010"
        content = cf.content
        if not content or not isinstance(content, dict):
            continue
        publishers = content.get('feeder_handler', {}).get('Publishers', [])
        for pub in publishers:
            addr = pub.get('Address', '')
            if ':' in addr:
                port_str = addr.split(':')[-1]
                try:
                    port = int(port_str)
                    if ip:
                        ip_port_to_cf[(ip, port)] = cf
                except ValueError:
                    pass

    return ip_to_cf, ip_port_to_cf, all_cfs


def _parse_upstream_addrs(address_str):
    """
    解析 UpStreams.Address 字段，支持分号分隔多地址：
    "10.121.21.231:9011;10.121.21.234:9010"
    返回 [(ip, port), ...]
    """
    results = []
    for part in address_str.split(';'):
        part = part.strip()
        if not part or ':' not in part:
            continue
        ip_part, port_part = part.rsplit(':', 1)
        try:
            results.append((ip_part.strip(), int(port_part.strip())))
        except ValueError:
            pass
    return results


def _msg_in_upstream(upstream, service_id, msg_id):
    """
    检查某个 upstream 配置里是否包含目标消息。
    返回匹配的 service 信息列表。
    """
    matched = []
    for svc in upstream.get('Services', []):
        svc_name = svc.get('Name', '')
        messages = svc.get('Messages', [])
        if not isinstance(messages, list):
            continue
        if msg_id not in messages:
            continue
        svc_id = SERVICE_NAME_TO_ID.get(svc_name)
        if service_id is not None and svc_id != service_id:
            continue
        matched.append({
            'service_name': svc_name,
            'service_id': svc_id,
            'msg_label': f'{svc_id}.{msg_id}' if svc_id else str(msg_id),
        })
    return matched


def build_chain(service_id, msg_id):
    """
    递归追溯转发链路，返回链路节点列表（从源头到当前机器的有序链条集合）。

    返回结构：
    {
      'chains': [
        [  # 一条完整链路
          {'node': 'ip:port 或 外部源', 'instance': '实例名', 'type': 'external|forwarder', 'services': [...], 'depth': 0},
          ...
        ],
        ...
      ],
      'nodes': { ip: {...} },   # 所有节点详情（去重）
    }
    """
    ip_to_cf, ip_port_to_cf, all_cfs = _build_ip_to_config_map()

    # 第一步：找所有直接包含目标消息的转发机（起点）
    start_nodes = []  # [(cf, upstream_addr_str, matched_services)]
    for cf in all_cfs:
        content = cf.content
        if not content or not isinstance(content, dict):
            continue
        forwarder = content.get('MSG_FORWARDER', {})
        upstreams = forwarder.get('UpStreams', [])
        if not isinstance(upstreams, list):
            continue
        for upstream in upstreams:
            matched = _msg_in_upstream(upstream, service_id, msg_id)
            if matched:
                start_nodes.append((cf, upstream.get('Address', ''), matched))

    if not start_nodes:
        return {'chains': [], 'nodes': {}}

    # 第二步：对每个起点递归向上追溯
    all_chains = []
    all_nodes = {}

    def trace_upstream(cf, upstream_addr_str, matched_svcs, current_chain, visited_ips, depth):
        """
        递归函数：从当前节点（cf）向上追溯 upstream_addr_str 里的每个地址。
        """
        ip = (cf.instance.host_ip or '').strip()
        if not ip:
            name = cf.instance.name
            ip = name.split('_')[0] if '_' in name else cf.instance.name

        node_key = ip
        current_node = {
            'node': ip,
            'instance': cf.instance.name,
            'type': 'forwarder',
            'services': matched_svcs,
            'depth': depth,
        }
        all_nodes[node_key] = current_node

        # 把当前节点加入链路
        new_chain = [current_node] + current_chain

        # 解析上游地址，递归追溯
        upstream_addrs = _parse_upstream_addrs(upstream_addr_str)
        found_upstream = False

        for upstream_ip, upstream_port in upstream_addrs:
            if upstream_ip in visited_ips:
                continue  # 防止环路

            upstream_cf = ip_port_to_cf.get((upstream_ip, upstream_port))
            if upstream_cf is None:
                # 在已知机器里找不到，说明是外部数据源
                source_key = f'{upstream_ip}:{upstream_port}'
                source_node = {
                    'node': source_key,
                    'instance': source_key,
                    'type': 'external',
                    'services': matched_svcs,
                    'depth': depth + 1,
                }
                all_nodes[source_key] = source_node
                full_chain = [source_node] + new_chain
                all_chains.append(full_chain)
                found_upstream = True
            else:
                # 找到了内部转发机，继续往上追
                upstream_content = upstream_cf.content or {}
                upstream_forwarder = upstream_content.get('MSG_FORWARDER', {})
                upstream_upstreams = upstream_forwarder.get('UpStreams', [])
                new_visited = visited_ips | {upstream_ip}
                found_next = False
                for up in upstream_upstreams:
                    up_matched = _msg_in_upstream(up, service_id, msg_id)
                    if up_matched:
                        trace_upstream(
                            upstream_cf,
                            up.get('Address', ''),
                            up_matched,
                            new_chain,
                            new_visited,
                            depth + 1,
                        )
                        found_next = True
                if not found_next:
                    # 上游机器存在但不转发该消息，视为接入点（源头）
                    upstream_ip_val = (upstream_cf.instance.host_ip or '').strip()
                    if not upstream_ip_val:
                        name = upstream_cf.instance.name
                        upstream_ip_val = name.split('_')[0] if '_' in name else name
                    source_node = {
                        'node': upstream_ip_val,
                        'instance': upstream_cf.instance.name,
                        'type': 'source',
                        'services': matched_svcs,
                        'depth': depth + 1,
                    }
                    all_nodes[upstream_ip_val] = source_node
                    full_chain = [source_node] + new_chain
                    all_chains.append(full_chain)
                found_upstream = True

        if not found_upstream:
            # 没有上游地址，当前节点就是源头
            all_chains.append(new_chain)

    for cf, upstream_addr, matched_svcs in start_nodes:
        ip = (cf.instance.host_ip or '').strip()
        if not ip:
            name = cf.instance.name
            ip = name.split('_')[0] if '_' in name else cf.instance.name
        trace_upstream(cf, upstream_addr, matched_svcs, [], {ip}, 0)

    # 去重链路（按节点序列去重）
    seen = set()
    unique_chains = []
    for chain in all_chains:
        key = '->'.join(n['node'] for n in chain)
        if key not in seen:
            seen.add(key)
            unique_chains.append(chain)

    return {'chains': unique_chains, 'nodes': all_nodes}


def parse_subscriptions(sub_str, service_id, msg_id):
    matched = []
    for item in sub_str.split(';'):
        item = item.strip()
        if not item:
            continue
        parts = item.split(',')
        if len(parts) != 3:
            continue
        try:
            v, sv, m = int(parts[0]), int(parts[1]), int(parts[2])
        except ValueError:
            continue
        if m != msg_id:
            continue
        if service_id is not None and v != service_id:
            continue
        matched.append({'version': v, 'svc_version': sv, 'msg_id': m, 'label': f'{v}.{m}'})
    return matched


def fetch_heartbeat(server):
    ip = server.ip
    url = f'http://{ip}:{HEARTBEAT_PORT}/heartbeat?ss=1'
    try:
        resp = http_requests.get(url, timeout=HEARTBEAT_TIMEOUT)
        resp.raise_for_status()
        return ip, server.fqdn, resp.json(), None
    except Exception as e:
        return ip, server.fqdn, None, str(e)


def search_heartbeat(service_id, msg_id):
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
            connections = data.get('session_status', {}).get('connections', [])
            for conn in connections:
                matched = parse_subscriptions(conn.get('subscriptions', ''), service_id, msg_id)
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
    GET /mdl-forwarder/chain/?msg=6.53   完整链路追溯
    GET /mdl-forwarder/chain/services/   Service 列表
    """

    @action(detail=False, methods=['get'], url_path='services')
    def services(self, request):
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
                {'code': 400, 'message': f'参数格式错误：{msg_param}'},
                status=drf_status.HTTP_400_BAD_REQUEST
            )
        service_id, msg_id = parsed

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            f_chain = executor.submit(build_chain, service_id, msg_id)
            f_live = executor.submit(search_heartbeat, service_id, msg_id)
            chain_result = f_chain.result()
            live_results, unreachable = f_live.result()

        service_label = SERVICE_ID_MAP.get(service_id, '') if service_id else ''

        return ApiResponse(data={
            'query': {
                'msg': msg_param,
                'service_id': service_id,
                'msg_id': msg_id,
                'service_label': service_label,
            },
            'chains': chain_result['chains'],   # 完整链路列表，每条从源头到末端
            'nodes': chain_result['nodes'],     # 所有节点详情
            'live': live_results,
            'unreachable': unreachable,
        })
