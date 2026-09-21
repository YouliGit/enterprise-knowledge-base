<template>
  <div>
    <el-card shadow="never">
      <div class="toolbar">
        <div>
          <el-input v-model="query" placeholder="搜索策略名称" clearable style="width: 220px" @keyup.enter="search" @clear="search" />
          <el-button :icon="Search" style="margin-left: 8px" @click="search">查询</el-button>
        </div>
        <el-button type="primary" :icon="Plus" @click="openEdit()">新建策略</el-button>
      </div>

      <el-alert type="info" :closable="false" show-icon style="margin-bottom: 12px"
        title="分数阈值按量纲分开配：余弦相似度(0~1)与重排相关分(0~1)各自配阈值；BM25无上界、RRF名次分不参与阈值过滤，页面上标记「本次不适用」" />

      <el-table :data="list" v-loading="loading" border stripe>
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="name" label="名称" min-width="150">
          <template #default="{ row }"><strong>{{ row.name }}</strong></template>
        </el-table-column>
        <el-table-column prop="description" label="描述" min-width="160" show-overflow-tooltip />
        <el-table-column label="向量" width="80">
          <template #default="{ row }">top{{ row.vector_top_k }}</template>
        </el-table-column>
        <el-table-column label="BM25" width="100">
          <template #default="{ row }">
            <el-tag v-if="row.bm25_top_k > 0" size="small">top{{ row.bm25_top_k }}</el-tag>
            <el-tag v-else size="small" type="info">关闭</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="改写" width="90">
          <template #default="{ row }">{{ row.use_rewrite === 1 ? modeName(row.rewrite_mode) : '关' }}</template>
        </el-table-column>
        <el-table-column label="重排" width="90">
          <template #default="{ row }">
            <el-tag v-if="row.rerank_enabled === 1" type="warning" size="small">top{{ row.rerank_top_n }}</el-tag>
            <el-tag v-else size="small" type="info">关</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="cosine_threshold" label="余弦阈值" width="90">
          <template #default="{ row }">{{ row.cosine_threshold?.toFixed?.(2) ?? row.cosine_threshold }}</template>
        </el-table-column>
        <el-table-column prop="rerank_threshold" label="重排阈值" width="90">
          <template #default="{ row }">{{ row.rerank_threshold?.toFixed?.(2) ?? row.rerank_threshold }}</template>
        </el-table-column>
        <el-table-column prop="max_retrieval" label="最大检索轮" width="100" />
        <el-table-column label="被引用" width="80">
          <template #default="{ row }">
            <el-tag v-if="row.kb_count > 0" type="warning" size="small">{{ row.kb_count }} 个库</el-tag>
            <span v-else style="color: #909399">-</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="140" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="openEdit(row)">编辑</el-button>
            <el-popconfirm title="确认删除该策略？" @confirm="remove(row)">
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

    <el-dialog v-model="dialogVisible" :title="form.id ? '编辑检索策略' : '新建检索策略'" width="680px" destroy-on-close>
      <el-form :model="form" label-width="140px">
        <el-form-item label="名称" required>
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" />
        </el-form-item>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="向量召回数">
              <el-input-number v-model="form.vector_top_k" :min="1" :max="50" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="BM25召回数">
              <el-input-number v-model="form.bm25_top_k" :min="0" :max="50" />
              <div style="font-size: 12px; color: #909399">0 = 关闭 BM25</div>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="RRF 常数 k">
              <el-input-number v-model="form.rrf_k" :min="1" :max="200" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="重排候选上限">
              <el-input-number v-model="form.candidate_limit" :min="1" :max="100" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="查询改写">
          <el-switch v-model="form.use_rewrite" :active-value="1" :inactive-value="0" />
          <el-select v-model="form.rewrite_mode" style="width: 200px; margin-left: 12px" :disabled="form.use_rewrite !== 1">
            <el-option label="多查询扩展 multi_query" value="multi_query" />
            <el-option label="HyDE 假设文档" value="hyde" />
            <el-option label="指代消解 coref" value="coref" />
          </el-select>
        </el-form-item>
        <el-form-item label="余弦相似度阈值" required>
          <el-input-number v-model="form.cosine_threshold" :min="0" :max="1" :step="0.05" :precision="2" />
          <div style="font-size: 12px; color: #909399">量纲 0~1（实测相关片段 0.46~0.77）</div>
        </el-form-item>
        <el-form-item label="重排">
          <el-switch v-model="form.rerank_enabled" :active-value="1" :inactive-value="0" />
          <el-input-number v-model="form.rerank_top_n" :min="1" :max="20" style="margin-left: 12px" :disabled="form.rerank_enabled !== 1" />
        </el-form-item>
        <el-form-item label="重排相关分阈值" required>
          <el-input-number v-model="form.rerank_threshold" :min="0" :max="1" :step="0.01" :precision="3" :disabled="form.rerank_enabled !== 1" />
          <div style="font-size: 12px; color: #909399">量纲 0~1（实测相关片段 0.14~0.20）</div>
        </el-form-item>
        <el-form-item label="Agent 最大检索轮">
          <el-input-number v-model="form.max_retrieval" :min="1" :max="5" />
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
import { ElMessage } from 'element-plus'
import { Plus, Search } from '@element-plus/icons-vue'
import { apiRetrievalCreate, apiRetrievalDelete, apiRetrievalPage, apiRetrievalUpdate } from '@/api'

const loading = ref(false)
const list = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const query = ref('')
const dialogVisible = ref(false)
const saving = ref(false)

const modeName = (m) => ({ multi_query: '多查询', hyde: 'HyDE', coref: '指代' }[m] || m)

const emptyForm = () => ({
  id: 0, name: '', description: '', vector_top_k: 8, bm25_top_k: 8, rrf_k: 60,
  use_rewrite: 1, rewrite_mode: 'multi_query', candidate_limit: 20,
  cosine_threshold: 0.3, rerank_enabled: 1, rerank_top_n: 5, rerank_threshold: 0.05,
  max_retrieval: 2,
})
const form = reactive(emptyForm())

const load = async () => {
  loading.value = true
  try {
    const data = await apiRetrievalPage({ query: query.value, page: page.value, page_size: pageSize })
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

const openEdit = (row) => {
  Object.assign(form, emptyForm(), row || {})
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
      await apiRetrievalUpdate(form.id, { ...form })
    } else {
      await apiRetrievalCreate({ ...form })
    }
    ElMessage.success('保存成功')
    dialogVisible.value = false
    load()
  } finally {
    saving.value = false
  }
}

const remove = async (row) => {
  await apiRetrievalDelete(row.id)
  ElMessage.success('已删除')
  load()
}

onMounted(load)
</script>