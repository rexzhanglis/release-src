#!/usr/bin/env python3
"""
release-agent: 采集本环境所有转发机心跳，汇总后推送给 release-src 中心。

部署路径: /opt/release-agent/agent.py
依赖: Python 3.6+，无第三方库（仅用标准库）
"""

import configparser
import concurrent.futures
import json
import logging
import os
import socket
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime

# ---------------------------------------------------------------------------
# 日志
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
    ]
)
logger = logging.getLogger('release-agent')


# ---------------------------------------------------------------------------
# 配置加载
# ---------------------------------------------------------------------------
def load_config(path):
    cfg = configparser.ConfigParser()
    cfg.read(path, encoding='utf-8')

    conf = {
        # 中心接收接口
        'center_url':      cfg.get('center', 'url'),
        'center_token':    cfg.get('center', 'token', fallback=''),
        # 本环境标识（如 IDC、aliyun、hk）
        'env_name':        cfg.get('agent', 'env_name'),
        'agent_id':        cfg.get('agent', 'agent_id', fallback=socket.gethostname()),
        # 心跳采集参数
        'heartbeat_port':  cfg.getint('agent', 'heartbeat_port', fallback=8080),
        'heartbeat_timeout': cfg.getfloat('agent', 'heartbeat_timeout', fallback=3.0),
        'collect_workers': cfg.getint('agent', 'collect_workers', fallback=20),
        'report_interval': cfg.getint('agent', 'report_interval', fallback=30),
        # 转发机列表：逗号分隔的 IP 或 IP:fqdn 或 IP:fqdn:port
        # 留空则从 servers_file 读取
        'servers_inline':  cfg.get('agent', 'servers', fallback='').strip(),
        'servers_file':    cfg.get('agent', 'servers_file', fallback='').strip(),
        # 推送失败最大重试次数
        'report_retry':    cfg.getint('agent', 'report_retry', fallback=3),
        'report_retry_delay': cfg.getfloat('agent', 'report_retry_delay', fallback=5.0),
    }
    return conf


def load_servers(conf):
    """
    解析服务器列表，返回 [(ip, fqdn, port), ...]
    支持格式（每行或逗号分隔）：
      10.121.21.236
      10.121.21.236:mdl-fwd-01
      10.121.21.236:mdl-fwd-01:8080
    """
    raw_lines = []

    inline = conf['servers_inline']
    if inline:
        # 逗号分隔
        raw_lines.extend([s.strip() for s in inline.split(',') if s.strip()])

    servers_file = conf['servers_file']
    if servers_file and os.path.isfile(servers_file):
        with open(servers_file, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    raw_lines.append(line)

    servers = []
    seen = set()
    for line in raw_lines:
        parts = line.split(':')
        ip = parts[0]
        fqdn = parts[1] if len(parts) >= 2 else ip
        port = int(parts[2]) if len(parts) >= 3 else conf['heartbeat_port']
        if ip not in seen:
            seen.add(ip)
            servers.append((ip, fqdn, port))

    return servers


# ---------------------------------------------------------------------------
# 心跳采集
# ---------------------------------------------------------------------------
def fetch_heartbeat(ip, fqdn, port, timeout):
    """
    请求单台转发机的心跳接口。
    返回 dict，包含 ip/fqdn/data/error/fetched_at 字段。
    """
    url = f'http://{ip}:{port}/heartbeat?ss=1'
    fetched_at = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode('utf-8')
            data = json.loads(body)
        return {'ip': ip, 'fqdn': fqdn, 'port': port,
                'data': data, 'error': None, 'fetched_at': fetched_at}
    except Exception as e:
        return {'ip': ip, 'fqdn': fqdn, 'port': port,
                'data': None, 'error': str(e), 'fetched_at': fetched_at}


def collect_all(servers, timeout, workers):
    """
    并发采集所有服务器心跳，返回 (results, unreachable) 两个列表。
    results:     成功拿到数据的条目
    unreachable: 失败的条目
    """
    results = []
    unreachable = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(fetch_heartbeat, ip, fqdn, port, timeout): (ip, fqdn)
            for ip, fqdn, port in servers
        }
        for future in concurrent.futures.as_completed(futures):
            try:
                item = future.result()
            except Exception as e:
                ip, fqdn = futures[future]
                unreachable.append({'ip': ip, 'fqdn': fqdn, 'error': str(e)})
                continue

            if item['error']:
                unreachable.append({
                    'ip': item['ip'],
                    'fqdn': item['fqdn'],
                    'error': item['error'],
                    'fetched_at': item['fetched_at'],
                })
            else:
                results.append(item)

    return results, unreachable


# ---------------------------------------------------------------------------
# 推送到中心
# ---------------------------------------------------------------------------
def report_to_center(conf, results, unreachable):
    """
    POST 心跳数据到 release-src 中心接口。
    失败时按 report_retry 重试。
    """
    payload = {
        'env':         conf['env_name'],
        'agent_id':    conf['agent_id'],
        'reported_at': datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'),
        'reports':     results,
        'unreachable': unreachable,
    }
    body = json.dumps(payload).encode('utf-8')
    url = conf['center_url'].rstrip('/') + '/api/agent-heartbeat/'

    headers = {
        'Content-Type': 'application/json',
    }
    if conf['center_token']:
        headers['Authorization'] = f'Token {conf["center_token"]}'

    for attempt in range(1, conf['report_retry'] + 1):
        try:
            req = urllib.request.Request(url, data=body, headers=headers, method='POST')
            with urllib.request.urlopen(req, timeout=10) as resp:
                resp_body = resp.read().decode('utf-8')
                logger.info(
                    f'推送成功: {len(results)} 台可达，{len(unreachable)} 台不可达 | '
                    f'中心响应: {resp.status} {resp_body[:80]}'
                )
                return True
        except Exception as e:
            logger.warning(f'推送失败 (第{attempt}次): {e}')
            if attempt < conf['report_retry']:
                time.sleep(conf['report_retry_delay'])

    logger.error(f'推送彻底失败，已重试 {conf["report_retry"]} 次')
    return False


# ---------------------------------------------------------------------------
# 主循环
# ---------------------------------------------------------------------------
def main():
    config_path = os.environ.get('AGENT_CONFIG', os.path.join(os.path.dirname(__file__), 'config.ini'))
    if not os.path.isfile(config_path):
        logger.error(f'找不到配置文件: {config_path}')
        sys.exit(1)

    conf = load_config(config_path)
    servers = load_servers(conf)

    if not servers:
        logger.error('服务器列表为空，请检查 config.ini 中 servers 或 servers_file 配置')
        sys.exit(1)

    logger.info(
        f'启动 release-agent | env={conf["env_name"]} agent_id={conf["agent_id"]} '
        f'servers={len(servers)} interval={conf["report_interval"]}s'
    )

    while True:
        start = time.time()

        servers = load_servers(conf)  # 每轮重新读取，支持热更新 servers_file
        logger.info(f'开始采集 {len(servers)} 台转发机心跳...')

        results, unreachable = collect_all(
            servers,
            timeout=conf['heartbeat_timeout'],
            workers=conf['collect_workers'],
        )

        logger.info(f'采集完成: {len(results)} 成功，{len(unreachable)} 失败')
        for u in unreachable:
            logger.debug(f'  不可达: {u["ip"]} ({u["fqdn"]}) - {u["error"]}')

        report_to_center(conf, results, unreachable)

        elapsed = time.time() - start
        sleep_time = max(0, conf['report_interval'] - elapsed)
        logger.info(f'本轮耗时 {elapsed:.1f}s，{sleep_time:.1f}s 后开始下一轮')
        time.sleep(sleep_time)


if __name__ == '__main__':
    main()
