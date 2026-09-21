<template>
  <div class="login-page">
    <div class="login-card">
      <!-- 左侧品牌区（深蓝） -->
      <div class="brand-side">
        <div class="brand-logo">
          <el-icon :size="22"><DataAnalysis /></el-icon>
          <span>AI Agentic RAG 企业知识库平台</span>
        </div>
        <h1 class="brand-title">让企业知识<br />真正被检索到</h1>
        <p class="brand-sub">基于 FastAPI + LangChain + LangGraph + RAG + PGVector</p>
        <ul class="feature-list">
          <li><el-icon><Select /></el-icon>混合检索 + RRF 融合，型号与语义双命中</li>
          <li><el-icon><Select /></el-icon>父子分块，小块精准命中、大块完整作答</li>
          <li><el-icon><Select /></el-icon>Agentic RAG 多轮检索，答案可回放</li>
          <li><el-icon><Select /></el-icon>LLM-as-judge 四指标量化评测</li>
        </ul>
        <div class="tech-tags">
          <span>FastAPI</span><span>LangChain</span><span>LangGraph</span>
          <span>PGVector</span><span>Vue3</span><span>Element-Plus</span>
        </div>
      </div>
      <!-- 右侧表单区（白） -->
      <div class="form-side">
        <div class="form-head">
          <h2>欢迎回来</h2>
          <p>请输入你的账号</p>
        </div>
        <el-tabs v-model="tab" stretch class="login-tabs">
          <el-tab-pane label="登录" name="login">
            <el-form :model="loginForm" @keyup.enter="doLogin">
              <el-form-item>
                <el-input v-model="loginForm.username" placeholder="请输入账号" size="large" :prefix-icon="User" />
              </el-form-item>
              <el-form-item>
                <el-input v-model="loginForm.password" type="password" placeholder="请输入密码" size="large" show-password :prefix-icon="Lock" />
              </el-form-item>
              <el-button type="primary" size="large" class="submit-btn" :loading="loading" @click="doLogin">
                登 录
              </el-button>
            </el-form>
          </el-tab-pane>
          <el-tab-pane label="注册" name="register">
            <el-form :model="regForm" @keyup.enter="doRegister">
              <el-form-item>
                <el-input v-model="regForm.username" placeholder="账号（至少2个字符）" size="large" :prefix-icon="User" />
              </el-form-item>
              <el-form-item>
                <el-input v-model="regForm.nickname" placeholder="昵称（选填）" size="large" :prefix-icon="Postcard" />
              </el-form-item>
              <el-form-item>
                <el-input v-model="regForm.password" type="password" placeholder="密码（至少4位）" size="large" show-password :prefix-icon="Lock" />
              </el-form-item>
              <el-button type="primary" size="large" class="submit-btn" :loading="loading" @click="doRegister">
                注 册
              </el-button>
            </el-form>
          </el-tab-pane>
        </el-tabs>
        <div class="login-tip">默认管理员：admin / admin</div>
      </div>
    </div>
  </div>
</template>
<script setup>
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { User, Lock, Postcard, Select } from '@element-plus/icons-vue'
import { useAuth } from '@/store/auth'
import { apiLogin, apiRegister } from '@/api'
const route = useRoute()
const router = useRouter()
const auth = useAuth()
const tab = ref('login')
const loading = ref(false)
const loginForm = reactive({ username: '', password: '' })
const regForm = reactive({ username: '', nickname: '', password: '' })
const doLogin = async () => {
  if (!loginForm.username || !loginForm.password) {
    ElMessage.warning('请输入账号和密码')
    return
  }
  loading.value = true
  try {
    const data = await apiLogin(loginForm)
    auth.login({ token: data.token, user: data })
    ElMessage.success('欢迎回来，' + (data.nickname || data.username))
    router.push(route.query.redirect || '/dashboard')
  } finally {
    loading.value = false
  }
}
const doRegister = async () => {
  if (!regForm.username || !regForm.password) {
    ElMessage.warning('请输入账号和密码')
    return
  }
  loading.value = true
  try {
    const data = await apiRegister(regForm)
    auth.login({ token: data.token, user: data })
    ElMessage.success('注册成功')
    router.push('/chat')
  } finally {
    loading.value = false
  }
}
</script>
<style scoped>
.login-page {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f0f2f5;
  padding: 20px;
}
.login-card {
  width: 920px;
  max-width: 100%;
  min-height: 560px;
  display: flex;
  background: #fff;
  border-radius: 16px;
  overflow: hidden;
  box-shadow: 0 12px 40px rgba(0, 21, 41, 0.12);
}
/* ---------- 左侧品牌区 ---------- */
.brand-side {
  width: 46%;
  background: linear-gradient(150deg, #2a364d 0%, #1e2a3d 100%);
  color: #fff;
  padding: 44px 38px;
  display: flex;
  flex-direction: column;
}
.brand-logo {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: rgba(255, 255, 255, 0.75);
  margin-bottom: 44px;
}
.brand-title {
  font-size: 28px;
  line-height: 1.4;
  font-weight: 700;
  margin: 0 0 12px;
  color: #fff;
}
.brand-sub {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.55);
  margin: 0 0 32px;
  line-height: 1.6;
}
.feature-list {
  list-style: none;
  padding: 0;
  margin: 0 0 auto;
}
.feature-list li {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: rgba(255, 255, 255, 0.8);
  margin-bottom: 14px;
  line-height: 1.5;
}
.feature-list .el-icon {
  color: #409eff;
  flex-shrink: 0;
}
.tech-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 28px;
}
.tech-tags span {
  font-size: 12px;
  padding: 4px 10px;
  border-radius: 4px;
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.12);
  color: rgba(255, 255, 255, 0.7);
}
/* ---------- 右侧表单区 ---------- */
.form-side {
  flex: 1;
  padding: 56px 48px 32px;
  display: flex;
  flex-direction: column;
  justify-content: center;
}
.form-head h2 {
  margin: 0 0 6px;
  font-size: 24px;
  color: #303133;
  font-weight: 600;
}
.form-head p {
  margin: 0 0 24px;
  font-size: 13px;
  color: #909399;
}
.login-tabs :deep(.el-tabs__header) {
  margin-bottom: 22px;
}
.login-tabs :deep(.el-tabs__item) {
  font-size: 15px;
}
.submit-btn {
  width: 100%;
  margin-top: 4px;
  letter-spacing: 4px;
}
.login-tip {
  margin-top: 20px;
  font-size: 12px;
  color: #909399;
  text-align: center;
}
/* ---------- 响应式 ---------- */
@media (max-width: 860px) {
  .brand-side {
    display: none;
  }
  .login-card {
    width: 420px;
    min-height: auto;
  }
  .form-side {
    padding: 40px 32px 28px;
  }
}
</style>