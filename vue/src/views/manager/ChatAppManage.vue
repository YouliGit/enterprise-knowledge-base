<template>
  <div>
    <el-card shadow="never">
      <div class="toolbar">
        <div>
          <el-input v-model="query" placeholder="搜索应用名称" clearable style="width: 220px" @keyup.enter="search" @clear="search" />
          <el-button :icon="Search" style="margin-left: 8px" @click="search">查询</el-button>
        </div>
        <el-button type="primary" :icon="Plus" @click="openEdit()">新建应用</el-button>
      </div>

      <el-table :data="list" v-loading="loading" border stripe>
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="name" label="名称" min-width="140">
          <template #default="{ row }"><strong>{{ row.name }}</strong></template>
        </el-table-column>
        <el-table-column prop="description" label="描述" min-width="160" show-overflow-tooltip />
        <el-table-column prop="kb_names" label="绑定知识库" min-width="180" show-overflow-tooltip />
        <el-table-column prop="prompt_name" label="Prompt" width="120" show-overflow-tooltip />
        <el-table-column label="模式" width="110">
          <template #default="{ row }">
            <el-tag :type="row.use_agent === 1 ? 'danger' : 'info'" size="small" effect="plain">
              {{ row.use_agent === 1 ? 'Agentic RAG' : '单轮检索' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="max_history" label="历史轮数" width="90" />
        <el-table-column label="显示引用" width="90">
          <template #default="{ row }">{{ row.show_ref === 1 ? '是' : '否' }}</template>
        </el-table-column>
        <el-table-column label="启用" width="80">
          <template #default="{ row }">
            <el-tag :type="row.enabled === 1 ? 'success' : 'info'" size="small">{{ row.enabled === 1 ? '启用' : '停用' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="220" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="success" plain @click="goChat(row)">去问答</el-button>
            <el-button size="small" @click="openEdit(row)">编辑</el-button>
            <el-popconfirm title="确认删除该应用？" @confirm="remove(row)">
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

    <el-dialog v-model="dialogVisible" :title="form.id ? '编辑问答应用' : '新建问答应用'" width="620px" destroy-on-close>
      <el-form :model="form" label-width="140px">
        <el-form-item label="名称" required>
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="问答 Prompt 模板">
          <el-select v-model="form.prompt_template_id" style="width: 100%" clearable placeholder="默认模板">
            <el-option v-for="t in promptOptions" :key="t.id" :label="t.name" :value="t.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="对话模型配置">
          <el-select v-model="form.model_config_id" style="width: 100%" clearable placeholder="默认启用的对话模型">
            <el-option v-for="m in chatModels" :key="m.id" :label="`${m.name} (${m.model})`" :value="m.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="检索策略">
          <el-select v-model="form.retrieval_strategy_id" style="width: 100%" clearable placeholder="知识库默认策略">
            <el-option v-for="s in retrievalOptions" :key="s.id" :label="s.name" :value="s.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="绑定知识库">
          <el-select v-model="form.kb_ids" multiple collapse-tags collapse-tags-tooltip style="width: 100%" placeholder="选择知识库">
            <el-option v-for="k in kbOptions" :key="k.id" :label="k.name" :value="k.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="携带历史轮数">
          <el-input-number v-model="form.max_history" :min="0" :max="20" />
        </el-form-item>
        <el-form-item label="展示引用来源">
          <el-switch v-model="form.show_ref" :active-value="1" :inactive-value="0" />
        </el-form-item>
        <el-form-item label="问答模式">
          <el-radio-group v-model="form.use_agent">
            <el-radio :value="1">Agentic RAG 状态图</el-radio>
            <el-radio :value="0">单轮混合检索</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="form.enabled" :active-value="1" :inactive-value="0" />
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
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Plus, Search } from '@element-plus/icons-vue'
import { apiChatAppBindKbs, apiChatAppCreate, apiChatAppDelete, apiChatAppPage, apiChatAppUpdate, apiKbOptions, apiModelPage, apiPromptPage, apiRetrievalOptions } from '@/api'

const router = useRouter()
const loading = ref(false)
const list = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 10
const query = ref('')
const dialogVisible = ref(false)
const saving = ref(false)

const promptOptions = ref([])
const chatModels = ref([])
const retrievalOptions = ref([])
const kbOptions = ref([])

const emptyForm = () => ({
  id: 0, name: '', description: '', prompt_template_id: null, model_config_id: null,
  retrieval_strategy_id: null, kb_ids: [], max_history: 3, show_ref: 1, use_agent: 1, enabled: 1,
})
const form = reactive(emptyForm())

const load = async () => {
  loading.value = true
  try {
    const data = await apiChatAppPage({ query: query.value, page: page.value, page_size: pageSize })
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
    const [prompts, models, retrievals, kbs] = await Promise.all([
      apiPromptPage({ scene: 'qa', page: 1, page_size: 100 }),
      apiModelPage({ type: 'chat', page: 1, page_size: 100 }),
      apiRetrievalOptions(),
      apiKbOptions(),
    ])
    promptOptions.value = (prompts.list || []).filter((p) => p.enabled === 1)
    chatModels.value = (models.list || []).filter((m) => m.enabled === 1)
    retrievalOptions.value = retrievals || []
    kbOptions.value = kbs || []
  } catch (_) {
    /* 忽略 */
  }
}

const openEdit = (row) => {
  Object.assign(form, emptyForm(), row ? { ...row, kb_ids: row.kb_ids || [] } : {})
  dialogVisible.value = true
}

const save = async () => {
  if (!form.name) {
    ElMessage.warning('请填写名称')
    return
  }
  saving.value = true
  try {
    const { kb_ids, ...rest } = { ...form }
    if (form.id) {
      await apiChatAppUpdate(form.id, rest)
      await apiChatAppBindKbs(form.id, { kb_ids: kb_ids || [] })
    } else {
      const data = await apiChatAppCreate(rest)
      await apiChatAppBindKbs(data.id, { kb_ids: kb_ids || [] })
    }
    ElMessage.success('保存成功')
    dialogVisible.value = false
    load()
  } finally {
    saving.value = false
  }
}

const remove = async (row) => {
  await apiChatAppDelete(row.id)
  ElMessage.success('已删除')
  load()
}

const goChat = (row) => {
  router.push({ path: '/chat', query: { app_id: row.id } })
}

onMounted(() => {
  load()
  loadOptions()
})
</script>