import request from '@/utils/request'

/**
 * 配置树（ServiceType → Instance → ConfigFile）
 */
export function getConfigTree(params) {
  return request({
    url: '/config-mgmt/tree/',
    method: 'get',
    params
  })
}

/**
 * 配置文件列表
 */
export function getConfigs(params) {
  return request({
    url: '/config-mgmt/configs/',
    method: 'get',
    params
  })
}

/**
 * 获取单个配置文件详情
 */
export function getConfigDetail(id) {
  return request({
    url: `/config-mgmt/configs/${id}/`,
    method: 'get'
  })
}

/**
 * 更新配置文件内容
 */
export function updateConfig(id, data) {
  return request({
    url: `/config-mgmt/configs/${id}/`,
    method: 'put',
    data
  })
}

/**
 * 批量修改同一 key 到多个实例的同一配置文件
 */
export function batchUpdateConfig(data) {
  return request({
    url: '/config-mgmt/configs/batch_update/',
    method: 'post',
    data
  })
}

/**
 * 获取多实例合并 schema
 * @param {Object} params - { instance_ids: [...], filename: 'xxx' }
 */
export function getConfigSchema(params) {
  return request({
    url: '/config-mgmt/configs/schema/',
    method: 'get',
    params
  })
}

/**
 * 从 GitLab 同步配置树到数据库
 */
export function syncFromGitlab() {
  return request({
    url: '/config-mgmt/sync/',
    method: 'post'
  })
}

/**
 * 提交选中配置到 GitLab
 * @param {Object} data - { config_ids: [...], message: 'commit message' }
 */
export function gitCommit(data) {
  return request({
    url: '/config-mgmt/configs/git_commit/',
    method: 'post',
    data
  })
}

/**
 * 推送选中配置到 Consul KV
 * @param {Object} data - { config_ids: [...] }
 */
export function pushConsul(data) {
  return request({
    url: '/config-mgmt/configs/push_consul/',
    method: 'post',
    data
  })
}

/**
 * 获取部署预览（实例详情：配置文件、目标路径、主机等）
 * @param {Object} data - { instance_ids: [...] }
 */
export function getDeployPreview(data) {
  return request({
    url: '/config-mgmt/deploy/preview/',
    method: 'post',
    data
  })
}

/**
 * 创建部署任务
 * @param {Object} data - { instance_ids: [...] }
 */
export function createDeployTask(data) {
  return request({
    url: '/config-mgmt/deploy/',
    method: 'post',
    data
  })
}

/**
 * 获取部署任务列表
 */
export function getDeployTasks() {
  return request({
    url: '/config-mgmt/deploy/',
    method: 'get'
  })
}

/**
 * 获取部署任务详情
 */
export function getDeployTaskDetail(id) {
  return request({
    url: `/config-mgmt/deploy/${id}/`,
    method: 'get'
  })
}

/**
 * 文本查找替换
 * @param {Object} data - { instance_ids, filename, search_text, replace_text, preview }
 */
export function textReplace(data) {
  return request({
    url: '/config-mgmt/configs/text_replace/',
    method: 'post',
    data
  })
}

/**
 * 获取配置实例列表
 */
export function getConfigInstances(params) {
  return request({
    url: '/config-mgmt/instances/',
    method: 'get',
    params
  })
}

/**
 * 新增配置实例
 */
export function createConfigInstance(data) {
  return request({
    url: '/config-mgmt/instances/',
    method: 'post',
    data
  })
}

/**
 * 删除配置实例
 */
export function deleteConfigInstance(id) {
  return request({
    url: `/config-mgmt/instances/${id}/`,
    method: 'delete'
  })
}

/**
 * 新增配置文件
 */
export function createConfigFile(data) {
  return request({
    url: '/config-mgmt/configs/',
    method: 'post',
    data
  })
}

/**
 * 获取审计日志列表
 * @param {Object} params - { action, operator, date_from, date_to, keyword, page, page_size }
 */
export function getAuditLogs(params) {
  return request({
    url: '/config-mgmt/audit-logs/',
    method: 'get',
    params
  })
}

/**
 * 获取服务类型列表
 */
export function getServiceTypes() {
  return request({
    url: '/config-mgmt/service-types/',
    method: 'get'
  })
}

/**
 * 获取配置历史列表
 * @param {Object} params - { config_id, page, page_size }
 */
export function getConfigHistory(params) {
  return request({
    url: '/config-mgmt/history/',
    method: 'get',
    params
  })
}

/**
 * 获取单条历史详情（含 content）
 */
export function getConfigHistoryDetail(id) {
  return request({
    url: `/config-mgmt/history/${id}/`,
    method: 'get'
  })
}

/**
 * 回滚到指定历史版本
 */
export function rollbackConfig(historyId) {
  return request({
    url: `/config-mgmt/history/${historyId}/rollback/`,
    method: 'post'
  })
}

/**
 * 回滚部署任务（恢复到部署前快照）
 */
export function rollbackDeployTask(taskId) {
  return request({
    url: `/config-mgmt/deploy/${taskId}/rollback/`,
    method: 'post'
  })
}

/**
 * 一致性巡检
 * @param {Object} params - { service_type_id?, filename? }
 */
export function consistencyCheck(params) {
  return request({
    url: '/config-mgmt/configs/consistency_check/',
    method: 'get',
    params
  })
}
