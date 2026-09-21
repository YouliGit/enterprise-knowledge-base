<template>
  <div>
    <el-page-header class="page-header" :content="`片段管理 - ${kbName}`" @back="$router.push('/kb')">
      <template #extra>
        <el-button :icon="Refresh" @click="load">刷新</el-button>
      </template>
    </el-page-header>

    <el-card shadow="never" style="margin-top: 14px">
      <div class="toolbar">
        <div>
          <el-select v-model="docFilter" clearable filterable placeholder="按文档筛选" style="width: 260px" @change="search">
            <el-option v-for="d in docOptions" :key="d.id" :label="d.name" :value="d.id" />
          </el-select>
          <el-input v-model="query" placeholder="搜索片段内容" clearable style="width: 220px; margin-left: 8px" @keyup.enter="search" @clear="search" />
          <el-button :icon="Search" style="margin-left: 8px" @click="search">查询</el-button>
        </div>
        <el-switch v-model="onlyChild" active-text="仅子片段" @change="search" />
      </div>

      <el-table :data="list" v-loading="loading" border stripe>
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="doc_name" label="文档" min-width="160" show-overflow-tooltip />
        <el-table-column prop="seq" label="序" width="60" />
        <el-table-column prop="content" label="内容" min-width="320" show-overflow-tooltip>
          <template #default="{ row }">{{ row.content }}</template>
        </el-table-column>
        <el-table-column prop="char_len" label="字数" width="70" />
        <el-table-column label="父块预览" min-width="140" show-overflow-tooltip>
          <template #default="{ row }">
            <span v-if="row.parent_preview" style="color: #909399; font-size: 12px">…{{ row.parent_preview }}…</span>
            <el-tag v-else-if="row.is_parent === 1" size="small" type="warning">父块</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="启用" width="80">
          <template #default="{ row }">
            <el-switch :model-value="row.enabled === 1" @change="(v) => toggle(row, v)" />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="110" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" plain @click="openEdit(row)">修正</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-wrap">
        <el-pagination background layout="total, prev, pager, next" :total="total" :page-size="pageSize" :current-page="page" @current-change="(p) => { page = p; load() }" />
      </div>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="`修正片段 #${current?.id || ''}`" width="720px" destroy-on-close>
      <el-alert type="info" :closable="false" show-icon style="margin-bottom: 12px" title="片段内容修改后会自动重新向量化（重嵌入）" />
      <el-input v-model="editContent" type="textarea" :rows="10" />
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveEdit">保存并重新向量化</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Refresh, Search } from '@element-plus/icons-vue'
import { apiChunkPage, apiChunkStatus, apiChunkUpdate, apiDocPage, apiKbPage } from '@/api'

const route = useRoute()
const kid = computed(() => Number(route.params.kid))
const kbName = ref('知识库')
const docFilter = ref(route.query.doc_id ? Number(route.query.doc_id) : 0)
const onlyChild = ref(true)

const loading = ref(false)
const list = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 10
const query = ref('')
const docOptions = ref([])

const dialogVisible = ref(false)
const saving = ref(false)
const current = ref(null)
const editContent = ref('')

const load = async () => {
  loading.value = true
  try {
    const data = await apiChunkPage({
      kb_id: kid.value,
      doc_id: docFilter.value || 0,
      query: query.value,
      only_child: onlyChild.value ? 1 : 0,
      page: page.value,
      page_size: pageSize,
    })
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

const toggle = async (row, v) => {
  await apiChunkStatus(row.id, { enabled: v ? 1 : 0 })
  row.enabled = v ? 1 : 0
  ElMessage.success(v ? '已启用（重新向量化）' : '已禁用（移除向量）')
}

const openEdit = (row) => {
  current.value = row
  editContent.value = row.content
  dialogVisible.value = true
}

const saveEdit = async () => {
  saving.value = true
  try {
    await apiChunkUpdate(current.value.id, { content: editContent.value })
    ElMessage.success('已保存并重新向量化')
    dialogVisible.value = false
    load()
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  const data = await apiKbPage({ query: String(kid.value), page: 1, page_size: 1 })
  const found = (data.list || []).find((k) => k.id === kid.value)
  kbName.value = found ? found.name : `#${kid.value}`
  const docs = await apiDocPage({ kb_id: kid.value, page: 1, page_size: 200 })
  docOptions.value = docs.list || []
  load()
})
</script>