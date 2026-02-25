import request from '@/utils/request'

export function getReleaseDetailInfo(params) {
  return request({
    url: '/releaseDetail/get_release_detail_info/',
    method: 'get',
    params
  })
}

export function deploy(data) {
  // 发布操作
  return request({
    url: '/releaseDetail/deploy/',
    method: 'post',
    data
  })
}

export function suspend(data) {
  // 暂停操作
  return request({
    url: '/releaseDetail/suspend/',
    method: 'post',
    data
  })
}

export function reDeploy(data) {
  // 再发布操作
  return request({
    url: '/releaseDetail/re_deploy/',
    method: 'post',
    data
  })
}

export function rollback(data) {
  // 回滚操作
  return request({
    url: '/releaseDetail/rollback/',
    method: 'post',
    data
  })
}

export function failSkip(data) {
  // 回滚操作
  return request({
    url: '/releaseDetail/fail_skip/',
    method: 'post',
    data
  })
}

export function failRetry(data) {
  // 回滚操作
  return request({
    url: '/releaseDetail/fail_retry/',
    method: 'post',
    data
  })
}
