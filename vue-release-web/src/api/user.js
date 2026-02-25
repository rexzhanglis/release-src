import request from '@/utils/request'

export function login(data) {
  return request({
    url: '/auth/user_login/',
    method: 'post',
    data
  })
}

export function getInfo() {
  return request({
    url: '/user/get_user_info/',
    method: 'get'
  })
}

export function getAllUsers() {
  return request({
    url: '/user/',
    method: 'get'
  })
}

export function getGroupUsers() {
  return request({
    url: '/user/get_group_users/',
    method: 'get'
  })
}

export function logout() {
  return request({
    url: '/auth/user_logout/',
    method: 'get'
  })
}
