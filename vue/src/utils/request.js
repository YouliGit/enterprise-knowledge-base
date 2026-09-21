// 统一 axios 封装：{code,msg,data} 结构、Token 注入、401 自动登出
import axios from 'axios'
import { ElMessage } from 'element-plus'
import { useAuth } from '@/store/auth'

const http = axios.create({
  baseURL: import.meta.env.VITE_API_BASE || '/api',
  timeout: 120000,
})

http.interceptors.request.use((config) => {
  const auth = useAuth()
  if (auth.token) {
    config.headers.Authorization = `Bearer ${auth.token}`
  }
  return config
})

http.interceptors.response.use(
  (resp) => {
    const body = resp.data
    // 非标准结构（如文件流）直接放行
    if (body === null || typeof body !== 'object' || !('code' in body)) {
      return body
    }
    if (body.code === 0) {
      return body.data
    }
    // 业务异常：HTTP 200 + code != 0
    if (body.code === 401 || body.code === 403) {
      const auth = useAuth()
      auth.logout()
      if (location.hash !== '#/login') {
        ElMessage.error(body.msg || '登录已失效，请重新登录')
        location.hash = '#/login'
      }
    } else {
      ElMessage.error(body.msg || '请求失败')
    }
    return Promise.reject(new Error(body.msg || '请求失败'))
  },
  (err) => {
    if (err.response && err.response.status === 401) {
      const auth = useAuth()
      auth.logout()
      location.hash = '#/login'
    }
    ElMessage.error(err.response?.data?.msg || err.message || '网络错误')
    return Promise.reject(err)
  }
)

export default http