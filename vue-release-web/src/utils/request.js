import axios from 'axios'
import { Message } from 'element-ui'
import store from '@/store'
import { getToken } from '@/utils/auth'

// import BASE_API from '../../public/config'
// create an axios instance
const service = axios.create({
  baseURL: window.config.BACKEND_BASE_API, // url = base url + request url
  timeout: 1000 * 120, // request timeout
  withCredentials: true
})

// request interceptor
service.interceptors.request.use(
  config => {
    // do something before request is sent

    if (store.getters.token) {
      // let each request carry token
      // ['X-Token'] is a custom headers key
      // please modify it according to the actual situation
      config.headers['X-Token'] = getToken()
    }
    return config
  },
  error => {
    // do something with request error
    console.log(error) // for debug
    return Promise.reject(error)
  }
)

// response interceptor
service.interceptors.response.use(
  /**
   * If you want to get http information such as headers or status
   * Please return  response => response
   */

  /**
   * Determine the request status by custom code
   * Here is just an example
   * You can also judge the status by HTTP Status Code
   */
  response => {
    // 204 No Content（DELETE 等）直接成功返回
    if (response.status === 204) {
      return response
    }

    const res = response.data

    if (res.code === 401) {
      window.location.href = window.config.BACKEND_LOGIN_URL + '?next=' + window.config.WEB_LOGIN_URL
      return res
    }

    // 业务 code：200 成功，201 创建成功，其余视为错误
    if (res.code !== 200 && res.code !== 201) {
      Message({
        message: res.message || 'Error',
        type: 'error',
        duration: 5 * 1000
      })
      return Promise.reject(new Error(res.message || 'Error'))
    } else {
      return res
    }
  },
  error => {
    console.log('err' + error) // for debug
    Message({
      message: error.message,
      type: 'error',
      duration: 5 * 1000
    })
    return Promise.reject(error)
  }
)

export default service
