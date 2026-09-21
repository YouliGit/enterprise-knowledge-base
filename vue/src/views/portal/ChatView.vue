<template>
  <div class="chat-page">
    <!-- 左侧栏 -->
    <div class="chat-side">
      <div class="side-logo">
        <el-icon size="20" color="#409eff"><ChatDotRound /></el-icon>
        <span>智能问答</span>
        <el-button link type="primary" size="small" style="margin-left: auto" @click="$router.push('/dashboard')">管理端</el-button>
      </div>

      <div class="app-select">
        <el-select v-model="appId" placeholder="选择问答应用" style="width: 100%" @change="onAppChange">
          <el-option v-for="a in apps" :key="a.id" :label="a.name" :value="a.id" />
        </el-select>
      </div>

      <div class="session-list">
        <div class="session-head">
          <span>会话</span>
          <el-button link type="primary" size="small" :icon="Plus" @click="newSession">新会话</el-button>
        </div>
        <div v-for="s in sessions" :key="s.id" class="session-item" :class="{ active: s.id === sessionId }" @click="switchSession(s)">
          <span class="text-ellipsis" style="flex: 1">{{ s.title }}</span>
          <el-icon class="del-icon" size="14" @click.stop="deleteSession(s)"><Close /></el-icon>
        </div>
        <el-empty v-if="!sessions.length" description="暂无会话" :image-size="60" />
      </div>
    </div>

    <!-- 聊天主体 -->
    <div class="chat-main">
      <div ref="msgListRef" class="msg-list">
        <div v-if="!messages.length" class="empty-tip">
          <el-icon size="40" color="#c0c4cc"><ChatLineRound /></el-icon>
          <p>基于 FastAPI + LangGraph + RAG 的企业知识库问答</p>
          <p style="font-size: 12px; color: #909399">{{ currentAppName }} · {{ useAgentText }}</p>
        </div>

        <div v-for="m in messages" :key="m.key" class="msg-row" :class="m.role">
          <div class="avatar" :class="m.role">
            <el-icon v-if="m.role === 'user'"><User /></el-icon>
            <el-icon v-else><MagicStick /></el-icon>
          </div>
          <div class="bubble-wrap">
            <div class="bubble" :class="m.role">
              <div v-if="m.streaming" class="typing-cursor">{{ m.content }}</div>
              <div v-else style="white-space: pre-wrap">{{ m.content }}</div>
            </div>

            <!-- 引用来源 -->
            <div v-if="m.refs && m.refs.length" class="refs">
              <el-collapse>
                <el-collapse-item :title="`引用来源（${m.refs.length}）`" name="refs">
                  <el-table :data="m.refs" size="small" border stripe>
                    <el-table-column prop="rank" label="名次" width="60" />
                    <el-table-column prop="chunk_id" label="片段ID" width="90" />
                    <el-table-column label="分数" width="120">
                      <template #default="{ row }">
                        <span class="mono" style="font-size: 12px">{{ fmtScores(row.scores) }}</span>
                      </template>
                    </el-table-column>
                    <el-table-column prop="content" label="内容" min-width="200" show-overflow-tooltip />
                  </el-table>
                </el-collapse-item>
              </el-collapse>
            </div>

            <!-- 操作条 -->
            <div v-if="m.role === 'assistant' && m.finished" class="msg-ops">
              <span class="mono cost" v-if="m.cost_ms">耗时 {{ m.cost_ms }}ms</span>
              <el-icon :class="{ active: m.feedback === 'useful' }" class="op-icon" @click="feedback(m, 'useful')"><CircleCheck /></el-icon>
              <el-icon :class="{ active: m.feedback === 'useless' }" class="op-icon" @click="feedback(m, 'useless')"><CircleClose /></el-icon>
            </div>
          </div>
        </div>
      </div>

      <!-- 输入区 -->
      <div class="input-area">
        <el-input
          v-model="inputText"
          type="textarea"
          :rows="2"
          resize="none"
          placeholder="输入你的问题，Enter 发送，Shift+Enter 换行"
          :disabled="streaming"
          @keydown.enter.prevent="send"
        />
        <div class="input-bar">
          <span v-if="streaming" style="color: #e6a23c; font-size: 12px">⏳ 模型思考中…（支持流式输出）</span>
          <span v-else style="color: #909399; font-size: 12px">Enter 发送</span>
          <el-button type="primary" :icon="Promotion" :loading="streaming" :disabled="!inputText.trim()" @click="send">发送</el-button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ChatLineRound, ChatDotRound, CircleCheck, CircleClose, Close, MagicStick, Plus, Promotion, User } from '@element-plus/icons-vue'
import { useAuth } from '@/store/auth'
import { apiChatAppOptions, apiChatHistory, apiChatFeedback, apiSessionCreate, apiSessionDelete, apiSessionPage } from '@/api'
import { sseFetch } from '@/utils/sse'

const route = useRoute()
const auth = useAuth()

const apps = ref([])
const appId = ref(0)
const sessions = ref([])
const sessionId = ref(0)
const messages = ref([])
const inputText = ref('')
const streaming = ref(false)
const msgListRef = ref(null)

let msgSeq = 0

const currentAppName = computed(() => apps.value.find((a) => a.id === appId.value)?.name || '')
const useAgentText = computed(() => '')

const fmtScores = (scores) => {
  if (!scores) return '-'
  return Object.entries(scores)
    .map(([k, v]) => `${k}:${typeof v === 'number' ? v.toFixed(4) : v}`)
    .join(' ')
}

const scrollBottom = async () => {
  await nextTick()
  const el = msgListRef.value
  if (el) el.scrollTop = el.scrollHeight
}

const loadApps = async () => {
  apps.value = await apiChatAppOptions()
  const qApp = Number(route.query.app_id || 0)
  appId.value = qApp && apps.value.some((a) => a.id === qApp) ? qApp : apps.value[0]?.id || 0
  if (appId.value) await loadSessions()
}

const loadSessions = async () => {
  sessions.value = (await apiSessionPage({ app_id: appId.value, page: 1, page_size: 50 })).list
  if (!sessionId.value || !sessions.value.some((s) => s.id === sessionId.value)) {
    if (sessions.value.length) {
      await switchSession(sessions.value[0])
    } else {
      messages.value = []
      sessionId.value = 0
    }
  }
}

const onAppChange = async () => {
  sessionId.value = 0
  messages.value = []
  await loadSessions()
}

const newSession = async () => {
  if (!appId.value) {
    ElMessage.warning('请先选择应用')
    return
  }
  const s = await apiSessionCreate({ app_id: appId.value, title: '新会话' })
  await switchSession({ id: s.id, title: s.title })
}

const switchSession = async (s) => {
  sessionId.value = s.id
  messages.value = []
  const rows = await apiChatHistory(s.id)
  rows.forEach((r) => {
    let refs = []
    try {
      refs = JSON.parse(r.refs_json || '[]')
    } catch (_) {
      refs = []
    }
    messages.value.push({
      key: `m${msgSeq++}`,
      role: r.role,
      content: r.content,
      refs,
      feedback: r.feedback || '',
      cost_ms: r.cost_ms,
      finished: true,
    })
  })
  scrollBottom()
}

const deleteSession = async (s) => {
  await ElMessageBox.confirm(`确认删除会话「${s.title}」？`, '删除会话', { type: 'warning' })
  await apiSessionDelete(s.id)
  if (s.id === sessionId.value) {
    sessionId.value = 0
    messages.value = []
  }
  await loadSessions()
}

const feedback = async (m, fb) => {
  const target = messages.value.find((x) => x.key === m.key)
  if (!target || !target.message_id) return
  const next = target.feedback === fb ? '' : fb
  target.feedback = next
  await apiChatFeedback({ message_id: target.message_id, feedback: next })
  ElMessage.success(next ? (fb === 'useful' ? '已点赞' : '已反馈：答案待优化') : '已取消反馈')
}

const send = async () => {
  const text = inputText.value.trim()
  if (!text || streaming.value) return
  if (!appId.value) {
    ElMessage.warning('请先选择问答应用')
    return
  }
  if (!sessionId.value) {
    const s = await apiSessionCreate({ app_id: appId.value, title: '新会话' })
    await switchSession({ id: s.id, title: s.title })
  }

  inputText.value = ''
  const userMsg = { key: `m${msgSeq++}`, role: 'user', content: text, finished: true }
  const aiMsg = { key: `m${msgSeq++}`, role: 'assistant', content: '', refs: [], finished: false, streaming: true }
  messages.value.push(userMsg, aiMsg)
  scrollBottom()

  streaming.value = true
  const base = (import.meta.env.VITE_API_BASE || '/api').replace(/\/$/, '')
  await sseFetch(`${base}/chat/ask`, { session_id: sessionId.value, query: text }, {
    token: auth.token,
    onEvent: (ev) => {
      if (ev.type === 'start') {
        aiMsg.app = ev.app
      } else if (ev.type === 'agent_start') {
        aiMsg.content += '\n[Agent 已启动] '
      } else if (ev.type === 'step') {
        const d = ev.data || {}
        aiMsg.content += `\n[${d.node || 'step'}] ${d.action || ''}`
      } else if (ev.type === 'token') {
        aiMsg.content += ev.delta || ''
      } else if (ev.type === 'refs') {
        aiMsg.refs = ev.refs || []
      }
      scrollBottom()
    },
    onDone: (ev) => {
      aiMsg.finished = true
      aiMsg.streaming = false
      aiMsg.cost_ms = ev.cost_ms
      aiMsg.message_id = ev.message_id
      // 更新会话标题
      loadSessions()
      scrollBottom()
    },
    onError: (e) => {
      aiMsg.finished = true
      aiMsg.streaming = false
      if (!aiMsg.content) {
        aiMsg.content = `⚠️ ${e.message || '请求失败'}`
      }
      scrollBottom()
    },
  })
  streaming.value = false
}

onMounted(async () => {
  await loadApps()
})
</script>

<style scoped>
.chat-page {
  height: 100%;
  display: flex;
  background: #f5f7fa;
}
.chat-side {
  width: 260px;
  background: #fff;
  border-right: 1px solid #e8e8e8;
  display: flex;
  flex-direction: column;
}
.side-logo {
  height: 56px;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 0 14px;
  font-weight: 600;
  border-bottom: 1px solid #f0f0f0;
}
.app-select {
  padding: 10px 12px;
  border-bottom: 1px solid #f0f0f0;
}
.session-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}
.session-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 4px 6px;
  font-size: 13px;
  color: #909399;
}
.session-item {
  display: flex;
  align-items: center;
  padding: 9px 10px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
  margin-bottom: 2px;
}
.session-item:hover {
  background: #f5f7fa;
}
.session-item.active {
  background: #ecf5ff;
  color: #409eff;
}
.del-icon {
  color: #c0c4cc;
  visibility: hidden;
}
.session-item:hover .del-icon {
  visibility: visible;
}
.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.msg-list {
  flex: 1;
  overflow-y: auto;
  padding: 20px 24px;
}
.empty-tip {
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #c0c4cc;
}
.msg-row {
  display: flex;
  margin-bottom: 18px;
  gap: 10px;
}
.msg-row.user {
  flex-direction: row-reverse;
}
.avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.avatar.user {
  background: #409eff;
  color: #fff;
}
.avatar.assistant {
  background: #67c23a;
  color: #fff;
}
.bubble-wrap {
  max-width: 72%;
}
.msg-row.user .bubble-wrap {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
}
.bubble {
  padding: 10px 14px;
  border-radius: 10px;
  line-height: 1.6;
  font-size: 14px;
  word-break: break-word;
}
.bubble.assistant {
  background: #fff;
  border: 1px solid #ebeef5;
  color: #303133;
}
.bubble.user {
  background: #409eff;
  color: #fff;
}
.refs {
  margin-top: 6px;
  font-size: 12px;
}
.msg-ops {
  margin-top: 6px;
  display: flex;
  align-items: center;
  gap: 12px;
}
.op-icon {
  cursor: pointer;
  color: #c0c4cc;
  font-size: 16px;
}
.op-icon:hover {
  color: #409eff;
}
.op-icon.active {
  color: #409eff;
}
.cost {
  font-size: 12px;
  color: #909399;
}
.input-area {
  background: #fff;
  border-top: 1px solid #e8e8e8;
  padding: 12px 16px;
}
.input-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 8px;
}
</style>