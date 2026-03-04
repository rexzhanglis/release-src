# -*- coding: utf-8 -*-
"""
转发链路查询
输入消息号（格式：serviceId.msgId，如 6.53 或 2.5），返回：
  - 配置侧：从包含该消息的转发机开始，递归向上追溯完整链路直到源头
  - 实时侧：哪些转发机当前有下游订阅该消息（via heartbeat?ss=1）
"""
import concurrent.futures

import requests as http_requests
from django.db import close_old_connections
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
    预加载所有 feeder_handler.cfg 和 feeder_receiver.cfg，构建两个索引：
      ip_to_cf:       ip -> ConfigFile（通过 instance.host_ip 或 instance.name 解析）
      ip_port_to_cf:  (ip, port) -> ConfigFile（通过 Publishers.Address 解析）
    返回 (ip_to_cf, ip_port_to_cf, all_cfs)
    注意：all_cfs 只包含 feeder_handler.cfg（转发/聚合机），
          receiver_ip_set 记录已知接收机 IP，用于区分"接收机"和"外部源"。
    """
    all_cfs = list(ConfigFile.objects.filter(
        filename__in=['feeder_handler.cfg', 'feeder_receiver.cfg']
    ).select_related('instance'))

    ip_to_cf = {}       # ip -> cf
    ip_port_to_cf = {}  # (ip, port) -> cf
    port_to_cfs = {}    # port -> [cf, ...]  当 IP 解析失败时的兜底索引
    receiver_ip_set = set()

    handler_cfs = []

    for cf in all_cfs:
        # 从 instance.host_ip 或 instance.name 解析 IP
        ip = (cf.instance.host_ip or '').strip()
        # host_ip 可能存的是节点名（如 'szcombine'）而非 IP，需校验格式
        if ip and ip.count('.') != 3:
            ip = ''
        if not ip:
            name = cf.instance.name
            parts = name.replace('-', '_').split('_')
            for p in reversed(parts):
                if p.count('.') == 3:
                    ip = p
                    break
            if not ip:
                ip = name.split('_')[0] if '_' in name else name

        def _index_publisher_ports(cf_, ip_, content_):
            """
            从配置内容中提取 Publishers 端口，建立索引。
            实际配置结构：content['feeder_handler']['Publishers'] 或
                         content['feeder_receiver']['Publishers']
            也兼容直接挂在顶层的情况。
            """
            # 收集所有可能存放 Publishers 的位置
            candidates = []
            for section_key in ('feeder_handler', 'feeder_receiver'):
                section = content_.get(section_key)
                if isinstance(section, dict):
                    candidates.append(section.get('Publishers', []))
            # 兼容直接挂顶层的情况
            if 'Publishers' in content_ and isinstance(content_['Publishers'], list):
                candidates.append(content_['Publishers'])

            for publishers in candidates:
                for pub in publishers:
                    addr = pub.get('Address', '')
                    if ':' in addr:
                        port_str = addr.split(':')[-1]
                        try:
                            port = int(port_str)
                            if ip_:
                                ip_port_to_cf[(ip_, port)] = cf_
                            port_to_cfs.setdefault(port, []).append(cf_)
                        except ValueError:
                            pass

        if _is_receiver_cf(cf):
            if ip:
                receiver_ip_set.add(ip)
                ip_to_cf[ip] = cf
                inst_port = cf.instance.port
                if inst_port:
                    ip_port_to_cf[(ip, inst_port)] = cf
                    port_to_cfs.setdefault(inst_port, []).append(cf)
            content = cf.content
            if content and isinstance(content, dict):
                _index_publisher_ports(cf, ip, content)
        else:
            handler_cfs.append(cf)
            if ip:
                ip_to_cf[ip] = cf
            content = cf.content
            if not content or not isinstance(content, dict):
                continue
            _index_publisher_ports(cf, ip, content)

    return ip_to_cf, ip_port_to_cf, port_to_cfs, handler_cfs, receiver_ip_set


def _parse_upstream_addrs(address_str):
    """
    解析 UpStreams.Address，支持多种分隔符：
      MSG_FORWARDER  用分号:  "10.x.x.x:9011;10.y.y.y:9010"
      TEAMING_HANDLER 用竖线: "10.x.x.x:9010|10.y.y.y:9010"
    返回 [(ip, port), ...]
    """
    results = []
    # 统一把 | 替换为 ; 再分割
    for part in address_str.replace('|', ';').split(';'):
        part = part.strip()
        if not part or ':' not in part:
            continue
        ip_part, port_part = part.rsplit(':', 1)
        try:
            results.append((ip_part.strip(), int(port_part.strip())))
        except ValueError:
            pass
    return results


def _get_upstreams_from_content(content, service_id, msg_id):
    """
    从配置文件内容中提取包含目标消息的上游地址列表。
    支持两种结构：
      1. 顶层 UpStreams: { "UpStreams": [...], "Publishers": [...] }
      2. 嵌套在 MSG_FORWARDER / TEAMING_HANDLER 下
    返回 [(address_str, matched_services), ...]
    """
    results = []

    # 收集所有 UpStreams 列表
    # 实际结构：content['MSG_FORWARDER']['UpStreams'] 或 content['TEAMING_HANDLER']['UpStreams']
    # 兼容直接挂顶层的情况
    upstream_lists = []
    for handler_key in ('MSG_FORWARDER', 'TEAMING_HANDLER'):
        handler = content.get(handler_key, {})
        if isinstance(handler, dict):
            ups = handler.get('UpStreams', [])
            if ups:
                upstream_lists.append(ups)
    # 兼容直接挂顶层
    if not upstream_lists and 'UpStreams' in content and isinstance(content['UpStreams'], list):
        upstream_lists.append(content['UpStreams'])

    for upstreams in upstream_lists:
        for upstream in upstreams:
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
            if matched:
                results.append((upstream.get('Address', ''), matched))
    return results


def _is_receiver_cf(cf):
    """判断配置文件是否属于接收机节点。
    条件：filename==feeder_receiver.cfg，或 service_type 名称含 'receiver'，
    或配置内容里没有 MSG_FORWARDER/TEAMING_HANDLER（纯接收机用 feeder_handler.cfg 的情况）。
    """
    if cf.filename == 'feeder_receiver.cfg':
        return True
    st_name = (cf.instance.service_type.name if cf.instance.service_type_id else '') if hasattr(cf.instance, 'service_type') else ''
    if 'receiver' in st_name.lower():
        return True
    content = cf.content or {}
    if isinstance(content, dict) and not content.get('MSG_FORWARDER') and not content.get('TEAMING_HANDLER'):
        return True
    return False


def _cf_ip(cf):
    """获取 ConfigFile 对应机器的 IP。"""
    ip = (cf.instance.host_ip or '').strip()
    # host_ip 可能存的是节点名（如 'szcombine'）而非 IP，需校验格式
    if ip and ip.count('.') != 3:
        ip = ''
    if not ip:
        name = cf.instance.name
        # 与 _build_ip_to_config_map 保持相同的解析逻辑：
        # 支持 "bjs_10.51.201.209"、"read010_10.24.71.48" 等格式
        parts = name.replace('-', '_').split('_')
        for p in reversed(parts):
            if p.count('.') == 3:
                ip = p
                break
        if not ip:
            ip = name.split('_')[0] if '_' in name else name
    return ip


def build_chain(service_id, msg_id):
    """
    构建消息转发的拓扑图（DAG）。

    返回结构：
    {
      'nodes': {
        node_id: {
          'id': str,           # 唯一标识（ip 或 ip:port）
          'instance': str,     # 实例名
          'type': str,         # 'forwarder' | 'receiver' | 'external'
          'services': [...],
        },
        ...
      },
      'edges': [
        {'from': node_id, 'to': node_id, 'services': [...]},
        ...
      ],
      'chains': [...],   # 保留向后兼容的链路列表（用于前端展示）
    }
    """
    ip_to_cf, ip_port_to_cf, port_to_cfs, all_cfs, receiver_ip_set = _build_ip_to_config_map()

    nodes = {}   # node_id -> node_info
    edges = set()  # (from_id, to_id) 去重
    edge_list = []

    def get_or_create_node(node_id, instance_name, node_type, svcs):
        if node_id not in nodes:
            nodes[node_id] = {
                'id': node_id,
                'instance': instance_name,
                'type': node_type,
                'services': svcs,
            }
        else:
            # 合并 services
            existing = {s['msg_label'] for s in nodes[node_id]['services']}
            for s in svcs:
                if s['msg_label'] not in existing:
                    nodes[node_id]['services'].append(s)
        return nodes[node_id]

    def add_edge(from_id, to_id, svcs):
        key = (from_id, to_id)
        if key not in edges:
            edges.add(key)
            edge_list.append({'from': from_id, 'to': to_id, 'services': svcs})

    visited_cfs = set()  # 防止重复处理同一个 cf

    def process_cf(cf, visited_ips=None):
        """
        处理一个 ConfigFile：
        - 找出该机器所有包含目标消息的 upstream 条目
        - 为每个 upstream address 递归向上追溯
        """
        if visited_ips is None:
            visited_ips = set()

        cf_id = cf.id
        if cf_id in visited_cfs:
            return
        visited_cfs.add(cf_id)

        content = cf.content
        if not content or not isinstance(content, dict):
            return

        this_ip = _cf_ip(cf)

        # 判断节点类型：TEAMING_HANDLER 是聚合转发机，MSG_FORWARDER 是普通转发机
        has_teaming = bool(content.get('TEAMING_HANDLER'))
        this_type = 'aggregator' if has_teaming else 'forwarder'

        upstream_entries = _get_upstreams_from_content(content, service_id, msg_id)
        if not upstream_entries:
            return

        this_node = get_or_create_node(this_ip, cf.instance.name, this_type, [])

        for addr_str, matched_svcs in upstream_entries:
            # 更新本节点的 services
            for s in matched_svcs:
                existing = {x['msg_label'] for x in this_node['services']}
                if s['msg_label'] not in existing:
                    this_node['services'].append(s)

            upstream_addrs = _parse_upstream_addrs(addr_str)
            for up_ip, up_port in upstream_addrs:
                # 127.0.0.1 表示本机，替换为当前配置文件所在机器的真实 IP
                if up_ip in ('127.0.0.1', '0.0.0.0', 'localhost'):
                    up_ip = this_ip
                if up_ip in visited_ips:
                    continue

                upstream_cf = ip_port_to_cf.get((up_ip, up_port))
                # IP+端口未命中，尝试仅用 IP 查（端口不同但同一台机器）
                if upstream_cf is None:
                    upstream_cf = ip_to_cf.get(up_ip)
                # IP 也解析不到时，仅凭端口匹配（实例名不含 IP 的情况）
                if upstream_cf is None:
                    candidates = port_to_cfs.get(up_port, [])
                    if len(candidates) == 1:
                        upstream_cf = candidates[0]
                    elif len(candidates) > 1 and up_ip:
                        # 多个候选时，尝试通过实例名中解析出的 IP 精确匹配
                        for c in candidates:
                            if _cf_ip(c) == up_ip:
                                upstream_cf = c
                                break

                if upstream_cf is None:
                    if up_ip in receiver_ip_set:
                        # 接收机（IP 已知但配置文件未能建立索引）
                        recv_instance = up_ip
                        get_or_create_node(up_ip, recv_instance, 'receiver', matched_svcs)
                        add_edge(up_ip, this_ip, matched_svcs)
                    else:
                        # 真正的外部源（交易所，IP 在平台上没有任何配置文件）
                        ext_id = f'{up_ip}:{up_port}'
                        get_or_create_node(ext_id, ext_id, 'external', matched_svcs)
                        add_edge(ext_id, this_ip, matched_svcs)
                else:
                    # 内部机器（转发机或接收机），继续往上追
                    up_ip_real = _cf_ip(upstream_cf) or up_ip  # 解析失败时用上游地址里的 IP
                    up_content = upstream_cf.content or {}
                    if _is_receiver_cf(upstream_cf):
                        up_type = 'receiver'
                    elif up_content.get('TEAMING_HANDLER'):
                        up_type = 'aggregator'
                    else:
                        up_type = 'forwarder'
                    get_or_create_node(up_ip_real, upstream_cf.instance.name, up_type, matched_svcs)
                    add_edge(up_ip_real, this_ip, matched_svcs)

                    # 接收机是终点，不再递归
                    if up_type != 'receiver':
                        new_visited = visited_ips | {up_ip, up_ip_real}
                        process_cf(upstream_cf, new_visited)

    # 入口：找所有直接包含目标消息的配置文件
    for cf in all_cfs:
        content = cf.content
        if not content or not isinstance(content, dict):
            continue
        if _get_upstreams_from_content(content, service_id, msg_id):
            process_cf(cf)

    if not nodes:
        return {'chains': [], 'nodes': {}, 'edges': []}

    # 将图结构转换为前端可展示的链路（从根节点到叶节点的路径）
    # 找到没有入边的节点（根节点 = 外部源）
    all_targets = {e['to'] for e in edge_list}
    root_ids = [nid for nid in nodes if nid not in all_targets]

    # BFS 生成所有从根到叶的路径
    chains = []
    def dfs_paths(node_id, path, path_set):
        children = [e['to'] for e in edge_list if e['from'] == node_id]
        if not children:
            # 叶节点，记录完整路径
            chains.append([nodes[n] for n in path])
            return
        for child in children:
            if child in path_set:
                continue  # 防止环路
            dfs_paths(child, path + [child], path_set | {child})

    for root in root_ids:
        dfs_paths(root, [root], {root})

    # 去重链路
    seen = set()
    unique_chains = []
    for chain in chains:
        key = '->'.join(n['id'] for n in chain)
        if key not in seen:
            seen.add(key)
            unique_chains.append(chain)

    # 将节点的 id 字段同时作为旧版 'node' 字段（前端兼容）
    for nid, nd in nodes.items():
        nd['node'] = nd['id']

    return {
        'chains': unique_chains,
        'nodes': nodes,
        'edges': edge_list,
    }


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


def _get_http_port(ip):
    """
    从该 IP 对应的 feeder_handler.cfg 配置中读取 HttpPort，默认 8080。
    支持顶层 HttpPort 和嵌套在 feeder_handler 下的 HttpPort。
    """
    cf = ConfigFile.objects.filter(
        filename='feeder_handler.cfg',
        instance__host_ip=ip,
    ).select_related('instance').first()
    if cf is None:
        # 尝试从 instance.name 解析 IP 匹配
        for cf2 in ConfigFile.objects.filter(filename='feeder_handler.cfg').select_related('instance'):
            if _cf_ip(cf2) == ip:
                cf = cf2
                break
    if cf and cf.content and isinstance(cf.content, dict):
        content = cf.content
        # HttpPort 在 feeder_handler 节下
        fh = content.get('feeder_handler', {})
        if isinstance(fh, dict) and 'HttpPort' in fh:
            try:
                return int(fh['HttpPort'])
            except (ValueError, TypeError):
                pass
        # 兼容直接挂顶层
        if 'HttpPort' in content:
            try:
                return int(content['HttpPort'])
            except (ValueError, TypeError):
                pass
    return HEARTBEAT_PORT


def fetch_heartbeat(ip, fqdn, port):
    url = f'http://{ip}:{port}/heartbeat?ss=1'
    try:
        resp = http_requests.get(url, timeout=HEARTBEAT_TIMEOUT)
        resp.raise_for_status()
        return ip, fqdn, resp.json(), None
    except Exception as e:
        return ip, fqdn, None, str(e)


def search_heartbeat(service_id, msg_id):
    servers = list(MdlServer.objects.filter(init_status='ready'))
    if not servers:
        return [], []

    # 在主线程预先查好每台服务器的 HttpPort，避免子线程中查库引发 OperationalError
    server_infos = [(s.ip, s.fqdn, _get_http_port(s.ip)) for s in servers]

    results = []
    unreachable = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        futures = {executor.submit(fetch_heartbeat, ip, fqdn, port): (ip, fqdn)
                   for ip, fqdn, port in server_infos}
        for future in concurrent.futures.as_completed(futures):
            try:
                ip, fqdn, data, err = future.result()
            except Exception as e:
                ip, fqdn = futures[future]
                unreachable.append({'ip': ip, 'fqdn': fqdn, 'error': str(e)})
                continue
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

    @action(detail=False, methods=['get'], url_path='debug_index')
    def debug_index(self, request):
        """
        调试接口：查看 ip_to_cf / ip_port_to_cf 索引内容
        GET /mdl-forwarder/chain/debug_index/?ip=10.21.238.101
        GET /mdl-forwarder/chain/debug_index/?port=9012
        """
        ip_to_cf, ip_port_to_cf, port_to_cfs, handler_cfs, receiver_ip_set = _build_ip_to_config_map()

        filter_ip = request.query_params.get('ip', '').strip()
        filter_port = request.query_params.get('port', '').strip()

        def cf_info(cf):
            return {
                'id': cf.id,
                'filename': cf.filename,
                'instance': cf.instance.name,
                'host_ip': cf.instance.host_ip,
                'inst_port': cf.instance.port,
                'service_type': cf.instance.service_type.name,
            }

        result = {}

        if filter_ip:
            result['ip_to_cf'] = cf_info(ip_to_cf[filter_ip]) if filter_ip in ip_to_cf else None
            result['ip_port_keys'] = [
                {'port': p, 'cf': cf_info(c)}
                for (i, p), c in ip_port_to_cf.items() if i == filter_ip
            ]

        if filter_port:
            try:
                port_int = int(filter_port)
                result['port_to_cfs'] = [cf_info(c) for c in port_to_cfs.get(port_int, [])]
                result['ip_port_exact'] = {
                    ip: cf_info(c)
                    for (ip, p), c in ip_port_to_cf.items() if p == port_int
                }
            except ValueError:
                pass

        # 查看某个 IP 对应配置文件的实际内容
        if filter_ip and request.query_params.get('content'):
            cf_obj = ip_to_cf.get(filter_ip)
            if cf_obj:
                result['content'] = cf_obj.content
                result['raw_content_preview'] = (cf_obj.raw_content or '')[:500]

        if not filter_ip and not filter_port:
            result['ip_to_cf_keys'] = sorted(ip_to_cf.keys())
            result['ip_port_to_cf_keys'] = [f'{i}:{p}' for (i, p) in sorted(ip_port_to_cf.keys())]
            result['receiver_ip_set'] = sorted(receiver_ip_set)
            result['handler_cfs_count'] = len(handler_cfs)

        # 追踪特定 IP:Port 的链路查找过程
        trace_msg = request.query_params.get('trace_msg', '').strip()
        if filter_ip and filter_port and trace_msg:
            parsed = parse_query_msg(trace_msg)
            if parsed:
                t_svc, t_msg = parsed
                port_int = int(filter_port)
                upstream_cf = ip_port_to_cf.get((filter_ip, port_int))
                if upstream_cf is None:
                    upstream_cf = ip_to_cf.get(filter_ip)
                if upstream_cf is None:
                    candidates = port_to_cfs.get(port_int, [])
                    upstream_cf = candidates[0] if len(candidates) == 1 else None
                result['trace'] = {
                    'found_cf': cf_info(upstream_cf) if upstream_cf else None,
                    'upstreams_in_cf': _get_upstreams_from_content(
                        upstream_cf.content or {}, t_svc, t_msg
                    ) if upstream_cf else [],
                }

        return ApiResponse(data=result)

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

        # build_chain 包含大量 ORM 查询，search_heartbeat 在主线程预查端口后子线程只做 HTTP
        # 先串行执行 build_chain（主线程 ORM），再并发 fetch heartbeat（子线程纯 HTTP）
        chain_result = build_chain(service_id, msg_id)
        # build_chain 耗时较长，之后 MySQL 连接可能已超时，主动关闭旧连接
        close_old_connections()
        live_results, unreachable = search_heartbeat(service_id, msg_id)

        service_label = SERVICE_ID_MAP.get(service_id, '') if service_id else ''

        return ApiResponse(data={
            'query': {
                'msg': msg_param,
                'service_id': service_id,
                'msg_id': msg_id,
                'service_label': service_label,
            },
            'chains': chain_result['chains'],
            'nodes': chain_result['nodes'],
            'edges': chain_result['edges'],
            'live': live_results,
            'unreachable': unreachable,
        })
