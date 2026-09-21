import { createRouter, createWebHashHistory } from 'vue-router'
import { useAuth } from '@/store/auth'
const routes = [
  {
    path: '/login',
    name: 'login',
    component: () => import('@/views/Login.vue'),
    meta: { title: '登录' },
  },
  {
    path: '/',
    component: () => import('@/layouts/AdminLayout.vue'),
    redirect: '/dashboard',
    children: [
      // ---------- 首页 ----------
      {
        path: 'dashboard',
        name: 'dashboard',
        component: () => import('@/views/manager/Dashboard.vue'),
        meta: { title: '系统首页', icon: 'Odometer' },
      },
      // ---------- 用户管理 ----------
      {
        path: 'user-manage',
        name: 'userManage',
        component: () => import('@/views/manager/UserManage.vue'),
        meta: { title: '用户管理', icon: 'User', group: '用户管理', groupIcon: 'User', admin: true },
      },
      {
        path: 'operation-log',
        name: 'operationLog',
        component: () => import('@/views/manager/OperationLog.vue'),
        meta: { title: '操作日志', icon: 'List', group: '用户管理', groupIcon: 'User', admin: true },
      },
      // ---------- 知识库管理 ----------
      {
        path: 'kb',
        name: 'kb',
        component: () => import('@/views/manager/KnowledgeBase.vue'),
        meta: { title: '知识管理', icon: 'Collection', group: '知识库管理', groupIcon: 'Collection' },
      },
      {
        path: 'split-strategy',
        name: 'splitStrategy',
        component: () => import('@/views/manager/SplitStrategy.vue'),
        meta: { title: '切分策略', icon: 'Scissor', group: '知识库管理', groupIcon: 'Collection' },
      },
      {
        path: 'retrieval-strategy',
        name: 'retrievalStrategy',
        component: () => import('@/views/manager/RetrievalStrategy.vue'),
        meta: { title: '检索策略', icon: 'Filter', group: '知识库管理', groupIcon: 'Collection' },
      },
      {
        path: 'kb/:kid/docs',
        name: 'kbDocs',
        component: () => import('@/views/manager/DocManage.vue'),
        meta: { title: '文档管理', group: '知识库管理', groupIcon: 'Collection', hidden: true },
      },
      {
        path: 'kb/:kid/chunks',
        name: 'kbChunks',
        component: () => import('@/views/manager/ChunkManage.vue'),
        meta: { title: '片段管理', group: '知识库管理', groupIcon: 'Collection', hidden: true },
      },
      {
        path: 'retrieval-test',
        name: 'retrievalTest',
        component: () => import('@/views/manager/RetrievalTest.vue'),
        meta: { title: '检索测试', icon: 'Search', group: '知识库管理', groupIcon: 'Collection' },
      },
      // ---------- AI 配置 ----------
      {
        path: 'ai-model',
        name: 'aiModel',
        component: () => import('@/views/manager/AiModel.vue'),
        meta: { title: 'AI模型配置', icon: 'Cpu', group: 'AI配置', groupIcon: 'Setting', admin: true },
      },
      {
        path: 'prompt',
        name: 'prompt',
        component: () => import('@/views/manager/Prompt.vue'),
        meta: { title: 'Prompt模板', icon: 'Document', group: 'AI配置', groupIcon: 'Setting', admin: true },
      },
      {
        path: 'tool',
        name: 'tool',
        component: () => import('@/views/manager/Tool.vue'),
        meta: { title: '工具中心', icon: 'Tools', group: 'AI配置', groupIcon: 'Setting', admin: true },
      },
      // ---------- 问答应用 ----------
      {
        path: 'chat-app',
        name: 'chatApp',
        component: () => import('@/views/manager/ChatAppManage.vue'),
        meta: { title: '应用管理', icon: 'ChatDotRound', group: '问答应用', groupIcon: 'ChatDotRound' },
      },
      {
        path: 'agent-run',
        name: 'agentRun',
        component: () => import('@/views/manager/AgentRun.vue'),
        meta: { title: 'Agent运行记录', icon: 'Connection', group: '问答应用', groupIcon: 'ChatDotRound' },
      },
      // ---------- 效果评测 ----------
      {
        path: 'eval',
        name: 'eval',
        component: () => import('@/views/manager/Eval.vue'),
        meta: { title: '批量评测', icon: 'DataAnalysis', group: '效果评测', groupIcon: 'DataAnalysis' },
      },
    ],
  },
  {
    path: '/chat',
    component: () => import('@/layouts/PortalLayout.vue'),
    children: [
      {
        path: '',
        name: 'chat',
        component: () => import('@/views/portal/ChatView.vue'),
        meta: { title: '智能问答' },
      },
    ],
  },
  { path: '/:pathMatch(.*)*', redirect: '/dashboard' },
]
const router = createRouter({
  history: createWebHashHistory(),
  routes,
})
router.beforeEach((to, from, next) => {
  const auth = useAuth()
  document.title = to.meta.title ? `${to.meta.title} · AI 企业知识库` : 'AI 企业知识库'
  if (to.name !== 'login' && !auth.isLogin) {
    next({ name: 'login', query: { redirect: to.fullPath } })
    return
  }
  if (to.meta.admin && !auth.isAdmin) {
    next({ name: 'dashboard' })
    return
  }
  next()
})
export default router