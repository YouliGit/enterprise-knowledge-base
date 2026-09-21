<template>
  <div>
    <el-page-header class="page-header" :content="`文档管理 - ${kbName}`" @back="$router.push('/kb')">
      <template #extra>
        <el-button :icon="Refresh" @click="load">刷新</el-button>
        <el-button type="primary" :icon="Upload" :loading="uploading" @click="uploadRef?.click()">上传文档</el-button>
        <input ref="uploadRef" type="file" multiple style="display: none" :accept="acceptTypes" @change="upload" />
      </template>
    </el-page-header>

    <el-card shadow="never" style="margin-top: 14px">
      <div class="toolbar">
        <div>
          <el-input v-model="query" placeholder="搜索文档名" clearable style="width: 220px" @keyup.enter="search" @clear="search" />
          <el-button :icon="Search" style="margin-left: 8px" @click="search">查询</el-button>
        </div>
        <el-button v-if="selected.length" type="danger" plain :icon="Delete" @click="batchDelete">批量删除({{ selected.length }})</el-button>
      </div>

      <el-table :data="list" v-loading="loading" border stripe @selection-change="(rows) => (selected = rows.map((r) => r.id))">
        <el-table-column type="selection" width="46" />
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="name" label="文件名" min-width="200" show-overflow-tooltip />
        <el-table-column prop="file_type" label="类型" width="80">
          <template #default="{ row }"><el-tag size="small" effect="plain">{{ row.file_type }}</el-tag></template>
        </el-table-column>
        <el-table-column label="大小" width="90">
          <template #default="{ row }">{{ fmtSize(row.file_size) }}</template>
        </el-table-column>
        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="statusTag(row.status)" size="small">
              {{ statusName(row.status) }}
              <el-icon v-if="row.status === 'parsing'" class="is-loading" style="margin-left: 4px"><Loading /></el-icon>
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="chunk_count" label="片段数" width="80" />
        <el-table-column prop="error" label="错误信息" min-width="150" show-overflow-tooltip />
        <el-table-column prop="created_at" label="上传时间" width="170" />
        <el-table-column label="操作" width="260" fixed="right">
          <template #default="{ row }">
            <el-button size="small" :icon="Files" @click="$router.push(`/kb/${row.kb_id}/chunks?doc_id=${row.id}`)">片段</el-button>
            <el-button size="small" :icon="RefreshRight" :disabled="row.status === 'parsing'" @click="reparse(row)">重解析</el-button>
            <el-popconfirm title="确认删除该文档（含片段与向量）？" @confirm="remove(row)">
              <template #reference>
                <el-button size="small" type="danger" plain>删除</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-wrap">
        <el-pagination background layout="total, prev, pager, next" :total="total" :page-size="pageSize" :current-page="page" @current-change="(p) => { page = p; load() }" />
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Delete, Files, Loading, Refresh, RefreshRight, Search, Upload } from '@element-plus/icons-vue'
import { apiDocBatchDelete, apiDocDelete, apiDocPage, apiDocReparse, apiDocUpload, apiKbPage } from '@/api'

const route = useRoute()
const kid = computed(() => Number(route.params.kid))
const kbName = ref('知识库')

const loading = ref(false)
const uploading = ref(false)
const list = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 10
const query = ref('')
const selected = ref([])
const uploadRef = ref(null)

const acceptTypes = '.pdf,.docx,.doc,.xlsx,.xls,.md,.txt,.csv'

const statusName = (s) => ({ pending: '待解析', parsing: '解析中', parsed: '已解析', failed: '失败' }[s] || s)
const statusTag = (s) => ({ pending: 'info', parsing: 'warning', parsed: 'success', failed: 'danger' }[s] || 'info')

const fmtSize = (n) => {
  if (n > 1024 * 1024) return (n / 1024 / 1024).toFixed(1) + 'MB'
  if (n > 1024) return (n / 1024).toFixed(1) + 'KB'
  return n + 'B'
}

const load = async () => {
  loading.value = true
  try {
    const data = await apiDocPage({ kb_id: kid.value, query: query.value, page: page.value, page_size: pageSize })
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

const upload = async (e) => {
  const files = Array.from(e.target.files || [])
  if (!files.length) return
  uploading.value = true
  try {
    for (const f of files) {
      const fd = new FormData()
      fd.append('kb_id', String(kid.value))
      fd.append('file', f)
      const data = await apiDocUpload(fd)
      ElMessage.success(`${f.name}：${data.msg}`)
    }
    load()
  } finally {
    uploading.value = false
    e.target.value = ''
  }
}

const reparse = async (row) => {
  await apiDocReparse(row.id)
  ElMessage.success('已提交重新解析')
  load()
}

const remove = async (row) => {
  await apiDocDelete(row.id)
  ElMessage.success('已删除')
  load()
}

const batchDelete = async () => {
  await apiDocBatchDelete({ ids: selected.value })
  ElMessage.success('删除完成')
  load()
}

onMounted(async () => {
  const kbs = await apiKbPage({ page: 1, page_size: 1 })
  const pageData = await apiKbPage({ query: String(kid.value), page: 1, page_size: 1 })
  const found = (pageData.list || []).find((k) => k.id === kid.value)
  kbName.value = found ? found.name : `#${kid.value}`
  load()
})
</script>