import request from '@/utils/request'

export function getCategoryCount() {
  return request({
    url: '/dashboard/get_category_count/',
    method: 'get'
  })
}
