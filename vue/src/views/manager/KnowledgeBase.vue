<template>
  <div>
    <el-card shadow="never">
      <div class="toolbar">
        <div>
          <el-input v-model="query" placeholder="搜索知识库名称" clearable style="width: 220px" @keyup.enter="search" @clear="search" />
          <el-button :icon="Search" style="margin-left: 8px" @click="search">查询</el-button>
        </div>
        <div>
          <el-button v-if="selected.length" type="danger" plain :icon="Delete" @click="batchDelete">批量删除({{ selected.length }})</el-button>
          <el-button type="primary" :icon="Plus" @click="openEdit()">新建知识库</el-button>
        </div>
      </div>

      <el-table :data="list" v-loading="loading" border stripe @selection-change="(rows) => (selected = rows.map((r) => r.id))">
        <el-table-column type="selection" width="46" />
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="name" label="名称" min-width="140">
          <template #default="{ row }">
            <el-link type="primary" @click="$router.push(`/kb/${row.id}/docs`)">{{ row.name }}</el-link>
          </template>
        </el-table-column>
        <el-table-column prop="description" label="描述" min-width="180" show-overflow-tooltip />
        <el-table-column prop="vector_model_name" label="向量模型" width="130" />
        <el-table-column prop="split_strategy_name" label="切分策略" width="130" show-overflow-tooltip />
        <el-table-column label="文档数" width="80">
          <template #default="{ row }"><span style="color: #409eff">{{ row.doc_count }}</span></template>
        </el-table-column>
        <el-table-column label="子片段" width="80">
          <template #default="{ row }">{{ row.chunk_count }}</template>
        </el-table-column>
        <el-table-column label="向量数" width="80">
          <template #default="{ row }">{{ row.vector_count }}</template>
        </el-table-column>
        <el-table-column label="操作" width="280" fixed="right">
          <template #default="{ row }">
            <el-button size="small" :icon="Document" @click="$router.push(`/kb/${row.id}/docs`)">文档</el-button>
            <el-button size="small" :icon="Files" @click="$router.push(`/kb/${row.id}/chunks`)">片段</el-button>
            <el-button size="small" :icon="RefreshRight" title="向量模型/维度变更后全量重嵌入" @click="rebuild(row)">重建</el-button>
            <el-button size="small" @click="openEdit(row)">编辑</el-button>
            <el-popconfirm title="删除将同时删除文档、片段与向量索引，确认？" @confirm="remove(row)">
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

    <el-dialog v-model="dialogVisible" :title="form.id ? '编辑知识库' : '新建知识库'" width="560px" destroy-on-close>
      <el-form :model="form" label-width="110px">
        <el-form-item label="名称" required>
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="向量模型" required>
          <el-select v-model="form.vector_model_id" style="width: 100%" placeholder="选择向量模型（embedding 类型）">
            <el-option v-for="m in embeddingModels" :key="m.id" :label="`${m.name} (${m.model})`" :value="m.id" />
          </el-select>
          <div v-if="!embeddingModels.length" style="font-size: 12px; color: #e6a23c">
            暂无向量模型配置，请先到「AI模型配置」新增并启用一个 embedding 模型
          </div>
        </el-form-item>
        <el-form-item label="切分策略">
          <el-select v-model="form.split_strategy_id" style="width: 100%" clearable placeholder="选择切分策略">
            <el-option v-for="s in splitOptions" :key="s.id" :label="`${s.name}（${s.mode === 'parent_child' ? '父子' : '递归'} ${s.chunk_size}字）`" :value="s.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="默认检索策略">
          <el-select v-model="form.retrieval_strategy_id" style="width: 100%" clearable placeholder="选择检索策略">
            <el-option v-for="s in retrievalOptions" :key="s.id" :label="s.name" :value="s.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Delete, Document, Files, Plus, RefreshRight, Search } from '@element-plus/icons-vue'
import { apiKbBatchDelete, apiKbCreate, apiKbDelete, apiKbPage, apiKbRebuild, apiKbUpdate, apiModelPage, apiRetrievalOptions, apiSplitOptions } from '@/api'

const loading = ref(false)
const list = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 10
const query = ref('')
const selected = ref([])
const dialogVisible = ref(false)
const saving = ref(false)

const embeddingModels = ref([])
const splitOptions = ref([])
const retrievalOptions = ref([])

const emptyForm = () => ({ id: 0, name: '', description: '', vector_model_id: null, split_strategy_id: null, retrieval_strategy_id: null })
const form = reactive(emptyForm())

const load = async () => {
  loading.value = true
  try {
    const data = await apiKbPage({ query: query.value, page: page.value, page_size: pageSize })
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

const loadOptions = async () => {
  try {
    const [models, splits, retrievals] = await Promise.all([
      apiModelPage({ type: 'embedding', page: 1, page_size: 100 }),
      apiSplitOptions(),
      apiRetrievalOptions(),
    ])
    embeddingModels.value = models.list || []
    splitOptions.value = splits || []
    retrievalOptions.value = retrievals || []
  } catch (_) {
    /* 忽略 */
  }
}

const openEdit = (row) => {
  Object.assign(form, emptyForm(), row ? { id: row.id, name: row.name, description: row.description, vector_model_id: row.vector_model_id, split_strategy_id: row.split_strategy_id, retrieval_strategy_id: row.retrieval_strategy_id } : {})
  dialogVisible.value = true
}

const save = async () => {
  if (!form.name) {
    ElMessage.warning('请填写名称')
    return
  }
  saving.value = true
  try {
    if (form.id) {
      await apiKbUpdate(form.id, { ...form })
    } else {
      await apiKbCreate({ ...form })
    }
    ElMessage.success('保存成功')
    dialogVisible.value = false
    load()
  } finally {
    saving.value = false
  }
}

const rebuild = async (row) => {
  await ElMessageBox.confirm(`确认重建「${row.name}」的向量索引？将全量重新嵌入。`, '重建索引', { type: 'warning', confirmButtonText: '开始重建' })
  const data = await apiKbRebuild(row.id)
  ElMessage.success(data.msg || '重建任务已启动')
}

const remove = async (row) => {
  await apiKbDelete(row.id)
  ElMessage.success('已删除')
  load()
}

const batchDelete = async () => {
  await ElMessageBox.confirm(`确认批量删除 ${selected.value.length} 个知识库（含文档/片段/向量）？`, '批量删除', { type: 'warning' })
  await apiKbBatchDelete({ ids: selected.value })
  ElMessage.success('删除完成')
  load()
}

onMounted(() => {
  load()
  loadOptions()
})
</script>