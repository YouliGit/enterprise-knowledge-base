// 全局登录态（localStorage 持久化，无需 Pinia）
import { reactive } from 'vue'

const KEY = 'ai_system_auth'

function load() {
  try {
    return JSON.parse(localStorage.getItem(KEY) || 'null') || {}
  } catch (_) {
    return {}
  }
}

const state = reactive({
  token: load().token || '',
  user: load().user || null,
})

export function useAuth() {
  return {
    get token() {
      return state.token
    },
    get user() {
      return state.user
    },
    get isLogin() {
      return !!state.token
    },
    get isAdmin() {
      return state.user?.role === 'admin'
    },
    login(payload) {
      state.token = payload.token || ''
      state.user = payload.user || payload
      localStorage.setItem(KEY, JSON.stringify({ token: state.token, user: state.user }))
    },
    setUser(user) {
      state.user = user
      localStorage.setItem(KEY, JSON.stringify({ token: state.token, user: state.user }))
    },
    logout() {
      state.token = ''
      state.user = null
      localStorage.removeItem(KEY)
    },
  }
}