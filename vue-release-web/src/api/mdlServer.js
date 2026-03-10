import request from '@/utils/request'

// ========== Host（物理机）==========

export function getHosts(params) {
  return request({ url: '/mdl-hosts/', method: 'get', params })
}

export function createHost(data) {
  return request({ url: '/mdl-hosts/', method: 'post', data })
}

export function getHost(id) {
  return request({ url: `/mdl-hosts/${id}/`, method: 'get' })
}

export function updateHost(id, data) {
  return request({ url: `/mdl-hosts/${id}/`, method: 'put', data })
}

export function deleteHost(id) {
  return request({ url: `/mdl-hosts/${id}/`, method: 'delete' })
}

export function initHost(id, data) {
  return request({ url: `/mdl-hosts/${id}/init/`, method: 'post', data })
}

export function getHostInitStatus(id, taskId) {
  return request({ url: `/mdl-hosts/${id}/init_status/`, method: 'get', params: { task_id: taskId } })
}

export function getOperationLogs(hostId, params) {
  return request({ url: `/mdl-hosts/${hostId}/operation_logs/`, method: 'get', params })
}

export function batchListServices(data) {
  return request({ url: '/mdl-hosts/batch_list_services/', method: 'post', data })
}

export function batchRestartHosts(data) {
  return request({ url: '/mdl-hosts/batch_restart/', method: 'post', data })
}

// ========== MdlServer（服务实例）==========

export function getMdlServers(params) {
  return request({ url: '/mdl-servers/', method: 'get', params })
}

export function createMdlServer(data) {
  return request({ url: '/mdl-servers/', method: 'post', data })
}

export function getMdlServer(id) {
  return request({ url: `/mdl-servers/${id}/`, method: 'get' })
}

export function updateMdlServer(id, data) {
  return request({ url: `/mdl-servers/${id}/`, method: 'patch', data })
}

export function deleteMdlServer(id) {
  return request({ url: `/mdl-servers/${id}/`, method: 'delete' })
}

export function initMdlServer(id, data) {
  const isFormData = data instanceof FormData
  return request({
    url: `/mdl-servers/${id}/init/`,
    method: 'post',
    data,
    headers: isFormData ? { 'Content-Type': 'multipart/form-data' } : {},
  })
}

export function getInitStatus(id, taskId) {
  return request({ url: `/mdl-servers/${id}/init_status/`, method: 'get', params: { task_id: taskId } })
}

export function getLabels(params) {
  return request({ url: '/mdl-labels/', method: 'get', params })
}

export function createLabel(data) {
  return request({ url: '/mdl-labels/', method: 'post', data })
}

export function deleteLabel(id) {
  return request({ url: `/mdl-labels/${id}/`, method: 'delete' })
}

export function getSystemdServices(id, params) {
  return request({ url: `/mdl-servers/${id}/systemd_services/`, method: 'get', params })
}

export function controlSystemdService(id, data) {
  return request({ url: `/mdl-servers/${id}/systemd_control/`, method: 'post', data })
}

export function getSystemdServiceFile(id, name) {
  return request({ url: `/mdl-servers/${id}/systemd_service_file/`, method: 'get', params: { name } })
}

export function manageSystemdService(id, data) {
  return request({ url: `/mdl-servers/${id}/systemd_manage_service/`, method: 'post', data })
}
