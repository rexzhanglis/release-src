import request from '@/utils/request'

/**
 * 查询消息转发链路
 * @param {string} msg - 消息号，格式 "6.53" 或 "53"
 */
export function queryMsgChain(msg) {
  return request({ url: '/mdl-forwarder/chain/', method: 'get', params: { msg } })
}

/**
 * 获取 Service ID 列表（用于下拉选择）
 */
export function getServices() {
  return request({ url: '/mdl-forwarder/chain/services/', method: 'get' })
}

/**
 * 获取交易所对端 IP 映射表
 */
export function getExchangeMap() {
  return request({ url: '/mdl-forwarder/chain/exchange_map/', method: 'get' })
}
