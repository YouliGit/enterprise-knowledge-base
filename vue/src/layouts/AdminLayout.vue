<template>
  <div class="admin-layout">
    <!-- ========== 侧边栏（抽屉式：可折叠为图标窄条） ========== -->
    <aside class="sidebar" :class="{ collapsed: isCollapse }">
      <div class="logo" @click="$router.push('/dashboard')">
        <div class="logo-mark">
          <el-icon :size="20"><DataAnalysis /></el-icon>
        </div>
        <transition name="fade">
          <span v-show="!isCollapse" class="logo-text">企业知识库</span>
        </transition>
      </div>
      <el-scrollbar class="menu-scroll">
        <el-menu
          :default-active="activeMenu"
          :default-openeds="defaultOpeneds"
          :collapse="isCollapse"
          :collapse-transition="false"
          router
          unique-opened
          class="side-menu"
        >
          <template v-for="item in menus" :key="item.path">
            <!-- 有子菜单：一级折叠 -->
            <el-sub-menu v-if="item.children && item.children.length" :index="item.path">
              <template #title>
                <el-icon><component :is="item.meta.icon || 'Menu'" /></el-icon>
                <span>{{ item.meta.title }}</span>
              </template>
              <el-menu-item v-for="child in item.children" :key="child.path" :index="child.path">
                <span class="dot" />
                <span>{{ child.meta.title }}</span>
              </el-menu-item>
            </el-sub-menu>
            <!-- 无子菜单：普通项 -->
            <el-menu-item v-else :index="item.path">
              <el-icon><component :is="item.meta.icon || 'Document'" /></el-icon>
              <template #title>{{ item.meta.title }}</template>
            </el-menu-item>
          </template>
        </el-menu>
      </el-scrollbar>
      <!-- 底部收起按钮 -->
      <div class="sidebar-footer" @click="isCollapse = !isCollapse">
        <el-icon :size="18">
          <component :is="isCollapse ? 'Expand' : 'Fold'" />
        </el-icon>
        <transition name="fade">
          <span v-show="!isCollapse">收起侧边栏</span>
        </transition>
      </div>
    </aside>
    <!-- ========== 主区域 ========== -->
    <div class="main-wrap">
      <header class="header">
        <div class="header-left">
          <!-- 移动端抽屉触发 -->
          <el-icon class="drawer-trigger" :size="20" @click="drawerVisible = true"><Operation /></el-icon>
          <el-breadcrumb separator="/">
            <el-breadcrumb-item>{{ parentTitle || '首页' }}</el-breadcrumb-item>
            <el-breadcrumb-item v-if="parentTitle && currentTitle">{{ currentTitle }}</el-breadcrumb-item>
          </el-breadcrumb>
        </div>
        <div class="header-right">
          <el-button link type="primary" @click="$router.push('/chat')">
            <el-icon><ChatDotRound /></el-icon>&nbsp;进入智能问答
          </el-button>
          <el-divider direction="vertical" />
          <el-dropdown trigger="click" @command="onCommand">
            <span class="user-badge">
              <el-avatar :size="30" :src="auth.user?.avatar || ''">
                {{ (auth.user?.nickname || auth.user?.username || 'U').slice(0, 1) }}
              </el-avatar>
              <span class="uname">{{ auth.user?.nickname || auth.user?.username }}</span>
              <el-tag v-if="auth.isAdmin" size="small" effect="light" class="role-tag">管理员</el-tag>
              <el-icon class="arrow"><ArrowDown /></el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="profile"><el-icon><User /></el-icon>个人资料</el-dropdown-item>
                <el-dropdown-item command="password"><el-icon><Lock /></el-icon>修改密码</el-dropdown-item>
                <el-dropdown-item divided command="logout"><el-icon><SwitchButton /></el-icon>退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </header>
      <main class="main">
        <router-view v-slot="{ Component }">
          <transition name="fade-slide" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </main>
    </div>
    <!-- ========== 移动端抽屉侧边栏 ========== -->
    <el-drawer v-model="drawerVisible" direction="ltr" size="240px" :with-header="false" class="mobile-drawer">
      <div class="drawer-logo">
        <el-icon :size="20"><DataAnalysis /></el-icon>
        <span>企业知识库</span>
      </div>
      <el-menu :default-active="activeMenu" router unique-opened class="side-menu drawer-menu">
        <template v-for="item in menus" :key="item.path">
          <el-sub-menu v-if="item.children && item.children.length" :index="item.path">
            <template #title>
              <el-icon><component :is="item.meta.icon || 'Menu'" /></el-icon>
              <span>{{ item.meta.title }}</span>
            </template>
            <el-menu-item v-for="child in item.children" :key="child.path" :index="child.path">
              {{ child.meta.title }}
            </el-menu-item>
          </el-sub-menu>
          <el-menu-item v-else :index="item.path">
            <el-icon><component :is="item.meta.icon || 'Document'" /></el-icon>
            <template #title>{{ item.meta.title }}</template>
          </el-menu-item>
        </template>
      </el-menu>
    </el-drawer>
    <!-- 个人资料 -->
    <el-dialog v-model="profileVisible" title="个人资料" width="440px">
      <el-form :model="profileForm" label-width="70px">
        <el-form-item label="账号"><el-input :model-value="auth.user?.username" disabled /></el-form-item>
        <el-form-item label="昵称"><el-input v-model="profileForm.nickname" /></el-form-item>
        <el-form-item label="邮箱"><el-input v-model="profileForm.email" /></el-form-item>
        <el-form-item label="手机"><el-input v-model="profileForm.phone" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="profileVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveProfile">保存</el-button>
      </template>
    </el-dialog>
    <!-- 修改密码 -->
    <el-dialog v-model="pwdVisible" title="修改密码" width="440px">
      <el-form :model="pwdForm" label-width="90px">
        <el-form-item label="原密码"><el-input v-model="pwdForm.old_password" type="password" show-password /></el-form-item>
        <el-form-item label="新密码"><el-input v-model="pwdForm.new_password" type="password" show-password /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="pwdVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="savePassword">修改</el-button>
      </template>
    </el-dialog>
  </div>
</template>
<script setup>
import { computed, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuth } from '@/store/auth'
import { apiChangePassword, apiUpdateProfile } from '@/api'
const route = useRoute()
const router = useRouter()
const auth = useAuth()
const isCollapse = ref(false)
const drawerVisible = ref(false)
// 构建多级菜单树
const menus = computed(() => {
  const all = router.options.routes.find((r) => r.path === '/')?.children || []
  const visible = all.filter(
    (m) => m.meta && m.meta.title && !m.meta.hidden && (auth.isAdmin || !m.meta.admin)
  )
  const tree = []
  const groupMap = {}
  visible.forEach((m) => {
    const g = m.meta.group
    if (g) {
      if (!groupMap[g]) {
        groupMap[g] = { path: '/group-' + g, meta: { title: g, icon: m.meta.groupIcon || 'Menu' }, children: [] }
        tree.push(groupMap[g])
      }
      groupMap[g].children.push({ path: '/' + m.path, meta: m.meta })
    } else {
      tree.push({ path: '/' + m.path, meta: m.meta })
    }
  })
  return tree
})
const activeMenu = computed(() => '/' + route.path.split('/').filter(Boolean)[0])
const currentTitle = computed(() => route.meta.title || '')
const parentTitle = computed(() => route.meta.group || '')
const defaultOpeneds = computed(() =>
  menus.value.filter((m) => m.children?.some((c) => c.path === activeMenu.value)).map((m) => m.path)
)
const profileVisible = ref(false)
const pwdVisible = ref(false)
const saving = ref(false)
const profileForm = reactive({ nickname: '', email: '', phone: '' })
const pwdForm = reactive({ old_password: '', new_password: '' })
const onCommand = (cmd) => {
  if (cmd === 'profile') {
    Object.assign(profileForm, {
      nickname: auth.user?.nickname || '',
      email: auth.user?.email || '',
      phone: auth.user?.phone || '',
    })
    profileVisible.value = true
  } else if (cmd === 'password') {
    pwdForm.old_password = ''
    pwdForm.new_password = ''
    pwdVisible.value = true
  } else if (cmd === 'logout') {
    auth.logout()
    router.push('/login')
  }
}
const saveProfile = async () => {
  saving.value = true
  try {
    const u = await apiUpdateProfile(profileForm)
    auth.setUser(u)
    ElMessage.success('保存成功')
    profileVisible.value = false
  } finally {
    saving.value = false
  }
}
const savePassword = async () => {
  saving.value = true
  try {
    await apiChangePassword(pwdForm)
    ElMessage.success('密码已修改，请重新登录')
    pwdVisible.value = false
    auth.logout()
    router.push('/login')
  } finally {
    saving.value = false
  }
}
</script>
<style scoped>
.admin-layout {
  display: flex;
  height: 100%;
  background: var(--page-bg);
}
/* ==================== 侧边栏 ==================== */
.sidebar {
  width: var(--sidebar-width);
  background: #fff;
  border-right: 1px solid var(--border-lighter);
  display: flex;
  flex-direction: column;
  transition: width 0.25s ease;
  flex-shrink: 0;
}
.sidebar.collapsed {
  width: var(--sidebar-collapsed);
}
.logo {
  height: var(--header-height);
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 18px;
  cursor: pointer;
  border-bottom: 1px solid var(--border-lighter);
  overflow: hidden;
  white-space: nowrap;
}
.logo-mark {
  width: 32px;
  height: 32px;
  border-radius: var(--radius-md);
  background: linear-gradient(135deg, #409eff, #337ecc);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.logo-text {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-main);
}
.menu-scroll {
  flex: 1;
  overflow: hidden;
}
.side-menu {
  border-right: none;
  padding: 8px 0;
}
.side-menu :deep(.el-menu-item),
.side-menu :deep(.el-sub-menu__title) {
  height: 46px;
  line-height: 46px;
  margin: 2px 10px;
  border-radius: var(--radius-md);
  color: var(--text-regular);
  font-size: 14px;
}
.side-menu :deep(.el-menu-item:hover),
.side-menu :deep(.el-sub-menu__title:hover) {
  background: #f5f7fa;
  color: var(--brand);
}
/* 选中态：淡蓝底 + 蓝字（参考截图） */
.side-menu :deep(.el-menu-item.is-active) {
  background: var(--brand-light);
  color: var(--brand);
  font-weight: 600;
}
.side-menu :deep(.el-sub-menu.is-active > .el-sub-menu__title) {
  color: var(--brand);
}
.side-menu :deep(.el-sub-menu .el-menu-item) {
  min-width: auto;
  padding-left: 42px !important;
}
.dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: currentColor;
  opacity: 0.5;
  margin-right: 8px;
  display: inline-block;
  vertical-align: middle;
}
.sidebar-footer {
  height: 46px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  border-top: 1px solid var(--border-lighter);
  color: var(--text-secondary);
  cursor: pointer;
  font-size: 13px;
  white-space: nowrap;
  overflow: hidden;
}
.sidebar-footer:hover {
  color: var(--brand);
  background: #f5f7fa;
}
/* ==================== 主区域 ==================== */
.main-wrap {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.header {
  height: var(--header-height);
  background: #fff;
  border-bottom: 1px solid var(--border-lighter);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  flex-shrink: 0;
}
.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}
.drawer-trigger {
  display: none;
  cursor: pointer;
  color: var(--text-regular);
}
.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}
.user-badge {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  outline: none;
  padding: 4px 8px;
  border-radius: var(--radius-md);
  transition: background 0.2s;
}
.user-badge:hover {
  background: #f5f7fa;
}
.uname {
  font-size: 14px;
  color: var(--text-main);
}
.role-tag {
  background: var(--brand-light) !important;
  border-color: #b3d8ff !important;
  color: var(--brand) !important;
}
.arrow {
  color: var(--text-secondary);
  font-size: 12px;
}
.main {
  flex: 1;
  padding: 16px;
  overflow-y: auto;
  background: var(--page-bg);
}
/* ==================== 移动端抽屉 ==================== */
.drawer-logo {
  height: 60px;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 20px;
  font-size: 16px;
  font-weight: 600;
  border-bottom: 1px solid var(--border-lighter);
  color: var(--brand);
}
.drawer-menu {
  border-right: none;
}
:deep(.mobile-drawer .el-drawer__body) {
  padding: 0;
}
/* ==================== 响应式 ==================== */
@media (max-width: 900px) {
  .sidebar {
    display: none;
  }
  .drawer-trigger {
    display: block;
  }
  .uname {
    display: none;
  }
}
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>