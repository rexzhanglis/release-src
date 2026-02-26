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
 * 获取服务类型列表
 */
export function getServiceTypes() {
  return request({
    url: '/config-mgmt/service-types/',
    method: 'get'
  })
}
