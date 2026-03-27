# -*- coding: utf-8 -*-
"""
转发链路查询
输入消息号（格式：serviceId.msgId，如 6.53 或 2.5），返回：
  - 配置侧：从包含该消息的转发机开始，递归向上追溯完整链路直到源头
  - 实时侧：哪些转发机当前有下游订阅该消息（via heartbeat?ss=1）
"""
import concurrent.futures

import requests as http_requests
from django.db import close_old_connections, connection
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

# 我司接收机 IP → 接收的交易所名称映射
# 来源：接收机.xlsx（我司业务服务器IP列）+ 交易所专线路由（主备）.doc
# 消息链路中"外部源"节点的 IP 是接收机 IP（feeder_receiver 向上游交易所拉取数据的本地侧地址）
# key 格式：纯 IP（匹配任意端口），或 IP:port（精确匹配）
EXCHANGE_IP_MAP = {
    # 大商所（DCE）- 联通：10.22.240.122，移动：10.22.240.123
    '10.22.240.122': '大商所',   '10.22.240.123': '大商所',
    # 大商所指数 - 电信：10.24.71.135，联通：10.24.71.136（端口 9011）
    '10.24.71.135':  '大商所指数', '10.24.71.136':  '大商所指数',
    # 郑商所（CZCE）- 移动：10.22.240.37，联通：10.22.240.68
    '10.22.240.37':  '郑商所',   '10.22.240.68':  '郑商所',
    # 中金所（CFFEX）- 移动：10.22.240.55，联通：10.22.240.86
    '10.22.240.55':  '中金所',   '10.22.240.86':  '中金所',
    # 上期所（SHFE）组播 - 移动：10.21.249.51，联通：10.21.249.52
    '10.21.249.51':  '上期所',   '10.21.249.52':  '上期所',
    # 上交所（SSE）- 电信：10.22.240.109，联通：10.22.240.60
    '10.22.240.109': '上交所',   '10.22.240.60':  '上交所',
    # 黄金交易所（SGE）
    '10.22.240.79':  '上海黄金交易所',
    # 广期所（GFEX）- 移动：10.22.240.58，联通：10.22.240.59
    '10.22.240.58':  '广期所',   '10.22.240.59':  '广期所',
    # 深交所L2（SZSE L2）- 移动：10.226.21.197，联通：10.226.99.2（东莞南方数据中心）
    '10.226.21.197': '深交所L2', '10.226.99.2':   '深交所L2',
    # 深交所L1（SZSE L1）- 电信：10.22.240.206，备(VDE)：10.22.240.96，备(L2转)：10.22.241.200
    '10.22.240.206': '深交所L1', '10.22.241.200': '深交所L1',
    # 深交所新三板（NEEQ）- 电信：10.22.240.111，联通：10.22.240.112
    '10.22.240.111': '新三板',   '10.22.240.112': '新三板',
    # 北交所债券（BSE Bond）- 复用新三板电信：10.22.240.91，复用上交所联通VDE：10.22.240.96
    '10.22.240.91':  '北交所债券',
    # 10.22.240.96 同时服务深L1期权和北交所债券（VDE），按端口区分：
    #   :9010 → 深L1备(VDE)   :9011 → 北交所债券VDE
    '10.22.240.96:9010': '深交所L1(VDE)',
    '10.22.240.96:9011': '北交所债券(VDE)',
    # 港交所恒指（经济通）- 电信：10.22.240.207
    '10.22.240.207': '港交所(恒指)',
    # 港交所跨境直连 - HK机柜：10.45.1.2
    '10.45.1.2':     '港交所(直连)',
    # 国证指数 - 主：10.24.71.135，备：10.24.71.136（端口 9010，与大商所指数同机器不同端口）
    '10.24.71.135:9010': '国证指数',
    '10.24.71.136:9010': '国证指数',
    # 中证指数 - 主：10.24.71.45，备：10.24.71.23
    '10.24.71.45':   '中证指数',  '10.24.71.23':   '中证指数',
    # 申万指数 - 主：10.24.71.36，备：10.24.71.70
    '10.24.71.36':   '申万指数',  '10.24.71.70':   '申万指数',
    # 南华指数 - 主：10.22.240.113，备：10.22.240.114（端口 9010）
    '10.22.240.113:9010': '南华指数',
    '10.22.240.114:9010': '南华指数',
    # 福汇 - 主：10.22.240.113，备：10.22.240.114（端口 9011，与南华指数同机器不同端口）
    '10.22.240.113:9011': '福汇',
    '10.22.240.114:9011': '福汇',
    # 上证云（通过跳板机 VPN 接入，Windows 接收机，无法追溯专线路由）
    '10.20.205.181': '上证云',
}


def lookup_exchange(ip_or_ip_port):
    """
    根据 IP 或 'IP:port' 字符串查找交易所名称，找不到返回 None。
    先尝试精确的 IP:port 匹配（同一机器不同端口可能接不同交易所），再回退到纯 IP 匹配。
    """
    if ':' in ip_or_ip_port:
        exact = EXCHANGE_IP_MAP.get(ip_or_ip_port)
        if exact:
            return exact
        ip = ip_or_ip_port.split(':')[0]
    else:
        ip = ip_or_ip_port
    return EXCHANGE_IP_MAP.get(ip)


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
    ).select_related('instance', 'instance__service_type'))

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
                # 只在该 IP 尚未被 handler 占位时才索引 receiver，避免 receiver 覆盖 handler
                if ip not in ip_to_cf:
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
    条件：filename==feeder_receiver.cfg，或 service_type 名称含 'receiver'。
    """
    if cf.filename == 'feeder_receiver.cfg':
        return True
    try:
        st_name = cf.instance.service_type.name or ''
    except Exception:
        st_name = ''
    return 'receiver' in st_name.lower()


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

    # 所有在 MdlServer 表里的 IP 都是内部机器，不应归为外部源
    internal_ip_set = set(
        MdlServer.objects.select_related('host').values_list('host__ip', flat=True)
    ) | receiver_ip_set

    # 域名 -> IP 映射（fqdn/hostname -> ip），用于解析上游地址里写的是域名的情况
    from mdl.models import Host
    fqdn_to_ip = {
        h.fqdn: h.ip
        for h in Host.objects.all()
        if h.fqdn and h.ip
    }

    nodes = {}   # node_id -> node_info
    edges = set()  # (from_id, to_id) 去重
    edge_list = []

    def get_or_create_node(node_id, instance_name, node_type, svcs, service_type_name=''):
        if node_id not in nodes:
            node = {
                'id': node_id,
                'instance': instance_name,
                'type': node_type,
                'services': svcs,
                'service_type': service_type_name,
            }
            if node_type == 'external':
                exchange = lookup_exchange(node_id)
                if exchange:
                    node['exchange'] = exchange
            nodes[node_id] = node
        else:
            # 合并 services
            existing = {s['msg_label'] for s in nodes[node_id]['services']}
            for s in svcs:
                if s['msg_label'] not in existing:
                    nodes[node_id]['services'].append(s)
            # 补充 service_type（首次建节点时可能还不知道）
            if service_type_name and not nodes[node_id].get('service_type'):
                nodes[node_id]['service_type'] = service_type_name
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

        try:
            st_name = cf.instance.service_type.name or ''
        except Exception:
            st_name = ''
        this_node = get_or_create_node(this_ip, cf.instance.name, this_type, [], st_name)

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
                # 域名转 IP（配置里写的是 fqdn，如 mdl-fwd-prd01.wmcloud.com）
                if up_ip and up_ip.count('.') != 3:
                    up_ip = fqdn_to_ip.get(up_ip, up_ip)
                if up_ip in visited_ips:
                    continue

                upstream_cf = ip_port_to_cf.get((up_ip, up_port))
                # IP+端口未命中，尝试仅用 IP 查（端口不同但同一台机器）
                if upstream_cf is None:
                    upstream_cf = ip_to_cf.get(up_ip)

                # 修复 A：端口兜底匹配增加 IP 校验
                # 只有当 up_ip 无法解析为有效 IP 时（如实例名不含 IP 的虚拟名称），才尝试仅凭端口匹配；
                # 如果 up_ip 已经是明确的 IP 地址（x.x.x.x 格式），说明我们明确知道目标机器 IP，
                # 此时若上述索引中找不到，不应盲目兜底，否则匹配到的候选极可能是不同机器。
                if upstream_cf is None:
                    up_ip_looks_valid = bool(up_ip and up_ip.count('.') == 3)
                    candidates = port_to_cfs.get(up_port, [])
                    if len(candidates) == 1 and not up_ip_looks_valid:
                        upstream_cf = candidates[0]
                    elif len(candidates) >= 1 and up_ip:
                        # 多个候选时（或 IP 已知时），尝试通过实例名中解析出的 IP 精确匹配
                        for c in candidates:
                            if _cf_ip(c) == up_ip:
                                upstream_cf = c
                                break

                # 修复 C：所有索引均未命中时，遍历 handler_cfs 按 IP 精确匹配
                if upstream_cf is None:
                    for hc in handler_cfs:
                        if _cf_ip(hc) == up_ip:
                            upstream_cf = hc
                            break

                if upstream_cf is None:
                    if up_ip in receiver_ip_set:
                        # 接收机（IP 已知但配置文件未能建立索引）
                        get_or_create_node(up_ip, up_ip, 'receiver', matched_svcs)
                        add_edge(up_ip, this_ip, matched_svcs)
                    elif up_ip in internal_ip_set:
                        # 修复 D：内部转发机但无配置文件，无法验证是否处理目标消息，跳过以避免误报
                        # 如果该机器确实在链路中，它的配置文件会被上面的索引/遍历找到并走 Fix B 验证
                        continue
                    else:
                        # 真正的外部源（交易所，IP 在平台上没有任何记录）
                        ext_id = f'{up_ip}:{up_port}'
                        get_or_create_node(ext_id, ext_id, 'external', matched_svcs)
                        add_edge(ext_id, this_ip, matched_svcs)
                else:
                    # 内部机器（转发机或接收机）
                    # 修复 B：上游消息验证
                    # 验证上游配置确实包含目标消息。如果上游配置中没有该消息，说明下游的引用有误或已过期，跳过。
                    # 接收机不受此检查影响（接收机从交易所接收全量数据，其 UpStreams 通常为空或指向外部）。
                    up_content = upstream_cf.content or {}
                    is_receiver = _is_receiver_cf(upstream_cf)
                    if not is_receiver:
                        up_valid_entries = _get_upstreams_from_content(up_content, service_id, msg_id)
                        if not up_valid_entries:
                            continue

                    up_ip_real = _cf_ip(upstream_cf) or up_ip  # 解析失败时用上游地址里的 IP
                    if is_receiver:
                        up_type = 'receiver'
                    elif up_content.get('TEAMING_HANDLER'):
                        up_type = 'aggregator'
                    else:
                        up_type = 'forwarder'

                    try:
                        up_st_name = upstream_cf.instance.service_type.name or ''
                    except Exception:
                        up_st_name = ''
                    get_or_create_node(up_ip_real, upstream_cf.instance.name, up_type, matched_svcs, up_st_name)
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


def _collect_all_msg_keys():
    """
    扫描所有 feeder_handler.cfg 配置内容，收集出现过的所有消息 key。
    返回 set，元素格式为 'service_id.msg_id'（如 '6.53'）或 'msg_id'（如 '53'，service 未知时）。
    """
    keys = set()
    all_cfs = ConfigFile.objects.filter(filename='feeder_handler.cfg').only('content')
    for cf in all_cfs:
        content = cf.content
        if not content or not isinstance(content, dict):
            continue
        for handler_key in ('MSG_FORWARDER', 'TEAMING_HANDLER'):
            handler = content.get(handler_key, {})
            if not isinstance(handler, dict):
                continue
            for upstream in handler.get('UpStreams', []):
                for svc in upstream.get('Services', []):
                    svc_name = svc.get('Name', '')
                    svc_id = SERVICE_NAME_TO_ID.get(svc_name)
                    for msg_id in svc.get('Messages', []):
                        if svc_id is not None:
                            keys.add(f'{svc_id}.{msg_id}')
                        else:
                            keys.add(str(msg_id))
    return keys


def rebuild_chain_index(msg_key):
    """
    重建单条消息的链路索引，写入 MsgChainIndex 表。
    线程安全（update_or_create），可在后台线程中调用。
    """
    import time
    from mdl.models import MsgChainIndex

    parsed = parse_query_msg(msg_key)
    if parsed is None:
        return
    service_id, msg_id = parsed

    t0 = time.monotonic()
    chain_result = build_chain(service_id, msg_id)
    elapsed_ms = int((time.monotonic() - t0) * 1000)

    MsgChainIndex.objects.update_or_create(
        msg_key=msg_key,
        defaults={
            'chain_json': chain_result,
            'build_ms': elapsed_ms,
        },
    )


def rebuild_all_chain_indexes():
    """
    全量重建所有消息链路索引。
    策略：复用同一次 _build_ip_to_config_map() 加载的数据，避免对每条消息重复查库。
    用于：服务启动时初始化 / 手动触发刷新。
    """
    import time
    import logging
    from mdl.models import MsgChainIndex

    logger = logging.getLogger('forwarder_chain')
    logger.info('[ChainIndex] 开始全量重建消息链路索引...')

    msg_keys = _collect_all_msg_keys()
    if not msg_keys:
        logger.warning('[ChainIndex] 未找到任何消息，跳过重建')
        return 0

    logger.info(f'[ChainIndex] 共发现 {len(msg_keys)} 条消息，开始逐一重建')
    success, failed = 0, 0
    t_all = time.monotonic()

    for msg_key in sorted(msg_keys):
        try:
            rebuild_chain_index(msg_key)
            success += 1
        except Exception as e:
            logger.error(f'[ChainIndex] 重建 {msg_key} 失败: {e}')
            failed += 1

    elapsed = time.monotonic() - t_all
    logger.info(f'[ChainIndex] 全量重建完成: 成功={success} 失败={failed} 耗时={elapsed:.1f}s')
    return success


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
    # 只查接收机和转发机，其他服务（barcal/dispatcher等）不支持 heartbeat
    HEARTBEAT_EXECUTABLES = ('feeder_receiver', 'feeder_handler')
    servers = list(MdlServer.objects.filter(
        init_status='ready',
        executable__in=HEARTBEAT_EXECUTABLES,
    ).select_related('host'))
    if not servers:
        return [], []

    # 一次性批量加载所有 feeder_handler.cfg，构建 ip -> HttpPort 映射，避免循环内逐个查库
    ip_to_http_port = {}
    all_handler_cfs = ConfigFile.objects.filter(
        filename='feeder_handler.cfg'
    ).select_related('instance').only('content', 'instance__host_ip', 'instance__name')
    for cf in all_handler_cfs:
        cf_ip = _cf_ip(cf)
        if not cf_ip or cf_ip in ip_to_http_port:
            continue
        content = cf.content or {}
        port = HEARTBEAT_PORT
        fh = content.get('feeder_handler', {})
        if isinstance(fh, dict) and 'HttpPort' in fh:
            try:
                port = int(fh['HttpPort'])
            except (ValueError, TypeError):
                pass
        elif 'HttpPort' in content:
            try:
                port = int(content['HttpPort'])
            except (ValueError, TypeError):
                pass
        ip_to_http_port[cf_ip] = port

    seen_ips = set()
    server_infos = []
    for s in servers:
        if s.host.ip not in seen_ips:
            seen_ips.add(s.host.ip)
            port = ip_to_http_port.get(s.host.ip, HEARTBEAT_PORT)
            server_infos.append((s.host.ip, s.host.fqdn, port))

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
        close_old_connections()
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

    @action(detail=False, methods=['get'], url_path='exchange_map')
    def exchange_map(self, request):
        """
        GET /mdl-forwarder/chain/exchange_map/
        返回 EXCHANGE_IP_MAP 的列表形式：[{ ip, exchange }, ...]
        """
        data = [
            {'ip': ip, 'exchange': exchange}
            for ip, exchange in sorted(EXCHANGE_IP_MAP.items(), key=lambda x: x[1])
        ]
        return ApiResponse(data=data)

    @action(detail=False, methods=['post'], url_path='rebuild_index')
    def rebuild_index(self, request):
        """
        POST /mdl-forwarder/chain/rebuild_index/
        触发全量重建消息链路索引，在后台线程异步执行，立即返回。
        可通过 GET rebuild_index_status/ 查询重建状态。
        """
        import threading
        from mdl.signals import _rebuild_lock, _rebuild_running
        import mdl.signals as _sig

        with _rebuild_lock:
            if _sig._rebuild_running:
                return ApiResponse(data={'status': 'running', 'message': '索引重建已在进行中，请稍后'})
            _sig._rebuild_running = True

        def _do_rebuild():
            try:
                from django.db import close_old_connections
                close_old_connections()
                rebuild_all_chain_indexes()
            except Exception as e:
                import logging
                logging.getLogger('forwarder_chain').error(f'[ChainIndex] 手动重建异常: {e}')
            finally:
                with _sig._rebuild_lock:
                    _sig._rebuild_running = False

        t = threading.Thread(target=_do_rebuild, daemon=True, name='chain-index-manual-rebuild')
        t.start()
        return ApiResponse(data={'status': 'started', 'message': '索引重建已启动，后台执行中'})

    @action(detail=False, methods=['get'], url_path='rebuild_index_status')
    def rebuild_index_status(self, request):
        """
        GET /mdl-forwarder/chain/rebuild_index_status/
        返回当前索引状态：索引条数、最新重建时间、是否正在重建。
        """
        import mdl.signals as _sig
        from mdl.models import MsgChainIndex
        from django.db import OperationalError as DBOperationalError
        from django.db.models import Max, Count

        close_old_connections()
        try:
            qs = MsgChainIndex.objects.aggregate(total=Count('id'), latest=Max('built_at'))
            total = qs['total']
            latest_dt = qs['latest']
            latest_built_at = latest_dt.strftime('%Y-%m-%d %H:%M:%S') if latest_dt else None
        except DBOperationalError:
            # 表尚未创建（未执行 migrate），返回空状态
            return ApiResponse(data={
                'total': 0,
                'latest_built_at': None,
                'is_running': False,
                'warning': '索引表不存在，请执行 python manage.py migrate',
            })
        return ApiResponse(data={
            'total': total,
            'latest_built_at': latest_built_at,
            'is_running': _sig._rebuild_running,
        })

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

        # 请求开始前关闭已失效的旧连接，防止连接池复用超时断开的连接导致 OperationalError
        close_old_connections()

        # 优先从索引表读取（毫秒级），未命中时 fallback 到实时计算并写入索引
        from mdl.models import MsgChainIndex
        force_rebuild = bool(request.query_params.get('refresh'))
        chain_result = None
        if not force_rebuild:
            idx = MsgChainIndex.objects.filter(msg_key=msg_param).first()
            if idx:
                chain_result = idx.chain_json
        if chain_result is None:
            chain_result = build_chain(service_id, msg_id)
            # 写入索引供后续查询使用（不阻塞，出错也不影响当次响应）
            try:
                MsgChainIndex.objects.update_or_create(
                    msg_key=msg_param,
                    defaults={'chain_json': chain_result, 'build_ms': 0},
                )
            except Exception:
                pass

        # search_heartbeat 实时查询，不缓存
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
