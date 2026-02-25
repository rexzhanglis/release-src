import Cookies from 'js-cookie'
import store from '@/store'

const TokenKey = 'vue_admin_template_token'

export function getToken() {
  return Cookies.get(TokenKey)
}

export function setToken(token) {
  return Cookies.set(TokenKey, token)
}

export function removeToken() {
  return Cookies.remove(TokenKey)
}

export function isVisible(team) {
  const roles = store.getters.roles
  if (roles.includes(team)) {
    return true
  }
  return false
}

