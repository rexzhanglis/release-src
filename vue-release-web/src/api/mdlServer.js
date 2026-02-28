import request from '@/utils/request'

export function getMdlServers(params) {
  return request({ url: '/mdl-servers/', method: 'get', params })
}

export function createMdlServer(data) {
  return request({ url: '/mdl-servers/', method: 'post', data })
}

export function updateMdlServer(id, data) {
  return request({ url: `/mdl-servers/${id}/`, method: 'put', data })
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
