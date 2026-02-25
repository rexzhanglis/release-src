import request from '@/utils/request'

export function getMdlReleaseServer() {
  return request({
    url: '/cmdb/get_mdl_release_server/',
    method: 'get'
  })
}

