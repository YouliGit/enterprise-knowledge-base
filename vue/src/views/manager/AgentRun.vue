<template>
  <div>
    <el-card shadow="never">
      <div class="toolbar">
        <div>
          <el-input v-model="query" placeholder="搜索问题" clearable style="width: 240px" @keyup.enter="search" @clear="search" />
          <el-button :icon="Search" style="margin-left: 8px" @click="search">查询</el-button>
        </div>
        <div>
          <el-select v-model="appFilter" clearable placeholder="按应用筛选" style="width: 220px" @change="search">
            <el-option v-for="a in appOptions" :key="a.id" :label="a.name" :value="a.id" />
          </el-select>
          <el-button :icon="Refresh" style="margin-left: 8px" @click="load">刷新</el-button>
        </div>
      </div>

      <el-table :data="list" v-loading="loading" border stripe>
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="app_id" label="应用ID" width="80" />
        <el-table-column prop="query" label="问题" min-width="260" show-overflow-tooltip />
        <el-table-column prop="status" label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="row.status === 'done' ? 'success' : row.status === 'failed' ? 'danger' : 'warning'" size="small">
              {{ row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="rounds" label="检索轮次" width="90" />
        <el-table-column prop="total_cost_ms" label="总耗时(ms)" width="110" />
        <el-table-column prop="final_answer" label="答案" min-width="220" show-overflow-tooltip />
        <el-table-column prop="created_at" label="时间" width="170" />
        <el-table-column label="操作" width="110" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" plain @click="openTimeline(row)">时间线</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-wrap">
        <el-pagination background layout="total, prev, pager, next" :total="total" :page-size="pageSize" :current-page="page" @current-change="(p) => { page = p; load() }" />
      </div>
    </el-card>

    <!-- 时间线回放 -->
    <el-drawer v-model="drawerVisible" :title="`Agent 时间线 · 运行 #${currentRun?.id || ''}`" size="68%">
      <el-result v-if="timeline.length === 0" icon="info" title="暂无步骤记录" />
      <template v-else>
        <el-timeline style="padding-left: 6px">
          <el-timeline-item
            v-for="s in timeline"
            :key="s.id"
            :timestamp="`#${s.seq} · ${s.node} · ${s.cost_ms || 0}ms`"
            placement="top"
            :type="timelineType(s)"
            :hollow="s.status !== 'ok'"
          >
            <el-card shadow="never">
              <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 6px; flex-wrap: wrap">
                <el-tag size="small" :type="nodeTag(s.node)" effect="dark">{{ nodeName(s.node) }}</el-tag>
                <span style="font-weight: 600">{{ s.action }}</span>
                <el-tag v-if="s.status !== 'ok'" size="small" type="danger">{{ s.status }}</el-tag>
              </div>
              <div v-if="s.thought" style="font-size: 13px; color: #606266; background: #f5f7fa; padding: 6px 10px; border-radius: 4px; margin-bottom: 6px">
                💭 {{ s.thought }}
              </div>
              <el-collapse>
                <el-collapse-item v-if="s.input_json && s.input_json !== '{}'" title="输入" name="in">
                  <pre class="json-block">{{ pretty(s.input_json) }}</pre>
                </el-collapse-item>
                <el-collapse-item v-if="s.output_json && s.output_json !== '{}'" title="输出" name="out">
                  <pre class="json-block">{{ pretty(s.output_json) }}</pre>
                </el-collapse-item>
              </el-collapse>
            </el-card>
          </el-timeline-item>
        </el-timeline>
      </template>
    </el-drawer>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { Refresh, Search } from '@element-plus/icons-vue'
import { apiAgentRunPage, apiAgentSteps, apiChatAppOptions } from '@/api'

const loading = ref(false)
const list = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 10
const query = ref('')
const appFilter = ref(null)
const appOptions = ref([])

const drawerVisible = ref(false)
const currentRun = ref(null)
const timeline = ref([])

const nodeName = (n) => ({ retrieve: '检索', evaluate: '评估', rewrite: '改写', generate: '生成', self_check: '自查', tool: '工具调用' }[n] || n)
const nodeTag = (n) => ({ retrieve: 'primary', evaluate: 'warning', rewrite: 'success', generate: 'info', self_check: 'danger', tool: 'danger' }[n] || 'info')
const timelineType = (s) => (s.status !== 'ok' ? 'danger' : s.node === 'self_check' ? 'primary' : 'primary')

const pretty = (s) => {
  try {
    return JSON.stringify(JSON.parse(s), null, 2)
  } catch (_) {
    return s
  }
}

const load = async () => {
  loading.value = true
  try {
    const data = await apiAgentRunPage({ query: query.value, page: page.value, page_size: pageSize })
    list.value = data.list
    total.value = data.total
  } finally {
    loading.value = false
  }
}

const search = () => {
  page.value = 1
  load()
}

const openTimeline = async (row) => {
  currentRun.value = row
  drawerVisible.value = true
  timeline.value = await apiAgentSteps(row.id)
}

onMounted(async () => {
  appOptions.value = await apiChatAppOptions()
  load()
})
</script>

<style scoped>
.json-block {
  background: #1e1e1e;
  color: #d4d4d4;
  padding: 10px;
  border-radius: 4px;
  font-size: 12px;
  max-height: 220px;
  overflow: auto;
  margin: 0;
}
</style>