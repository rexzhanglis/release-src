import request from '@/utils/request'

export function createReleasePlan(data) {
  return request({
    url: '/releasePlan/',
    method: 'post',
    data
  })
}

export function getReleasePlans(params) {
  return request({
    url: '/releasePlan/',
    method: 'get',
    params
  })
}

export function getReleasePlanOptions(params) {
  return request({
    url: '/releasePlan/get_release_plan_options/',
    method: 'get',
    params
  })
}


export function getReleasePlanInfo(params) {
  return request({
    url: '/releasePlan/get_release_plan_info/',
    method: 'get',
    params
  })
}

export function getReleasePlanProject() {
  return request({
    url: '/releasePlan/get_release_plan_project/',
    method: 'get'
  })
}

export function updateReleasePlan(data) {
  return request({
    url: '/releasePlan/update_release_plan/',
    method: 'post',
    data
  })
}

export function deleteReleasePlan(data) {
  return request({
    url: '/releasePlan/delete_release_plan/',
    method: 'post',
    data
  })
}

