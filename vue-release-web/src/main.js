import Vue from 'vue'

import 'normalize.css/normalize.css' // A modern alternative to CSS resets

import ElementUI from 'element-ui'
import 'element-ui/lib/theme-chalk/index.css'

import '@/styles/index.scss' // global css

import App from './App'
import store from './store'
import router from './router'

import '@/icons' // icon
import '@/permission' // permission control

import Moment from 'moment'


Vue.filter('formatDate', function(value) {
  if (value) {
    return Moment(value).format('YYYY-MM-DD HH:mm:ss')
  }
  return null
})


// Vue.use(ElementUI, { locale })
// 如果想要中文版 element-ui
Vue.use(ElementUI)

Vue.config.productionTip = false

new Vue({
  el: '#app',
  router,
  store,
  render: h => h(App)
})
