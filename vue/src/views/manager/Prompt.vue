<template>
  <div>
    <el-card shadow="never">
      <div class="toolbar">
        <div>
          <el-input v-model="query" placeholder="搜索名称/编码" clearable style="width: 240px" @keyup.enter="search" @clear="search" />
          <el-button :icon="Search" style="margin-left: 8px" @click="search">查询</el-button>
        </div>
        <div>
          <el-button type="success" :icon="Download" @click="importBuiltin">写入内置模板</el-button>
          <el-button type="primary" :icon="Plus" @click="openEdit()">新建模板</el-button>
        </div>
      </div>

      <el-table :data="list" v-loading="loading" border stripe>
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="code" label="编码" width="200" show-overflow-tooltip />
        <el-table-column prop="name" label="名称" min-width="140" />
        <el-table-column prop="scene" label="场景" width="110">
          <template #default="{ row }">
            <el-tag :type="sceneTag(row.scene)" effect="plain">{{ sceneName(row.scene) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="content" label="内容" min-width="260" show-overflow-tooltip>
          <template #default="{ row }">
            <span class="mono" style="font-size: 12px">{{ row.content }}</span>
          </template>
        </el-table-column>
        <el-table-column label="启用" width="80">
          <template #default="{ row }">
            <el-tag :type="row.enabled === 1 ? 'success' : 'info'" size="small">{{ row.enabled === 1 ? '启用' : '停用' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="170" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="openEdit(row)">编辑</el-button>
            <el-popconfirm title="确认删除该模板？" @confirm="remove(row)">
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

    <el-dialog v-model="dialogVisible" :title="form.id ? '编辑 Prompt 模板' : '新建 Prompt 模板'" width="760px" destroy-on-close>
      <el-form :model="form" label-width="90px">
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="编码" required>
              <el-input v-model="form.code" placeholder="唯一编码，如 qa_answer_concise" :disabled="!!form.id" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="名称" required>
              <el-input v-model="form.name" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="场景" required>
          <el-select v-model="form.scene" style="width: 100%">
            <el-option label="qa - 问答生成" value="qa" />
            <el-option label="rewrite - 查询改写" value="rewrite" />
            <el-option label="agent - 智能体判断" value="agent" />
            <el-option label="judge - 评测裁判" value="judge" />
          </el-select>
        </el-form-item>
        <el-form-item label="内容" required>
          <el-input v-model="form.content" type="textarea" :rows="10" placeholder="支持 {variable} 占位符" />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="form.enabled" :active-value="1" :inactive-value="0" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.remark" />
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
import { Download, Plus, Search } from '@element-plus/icons-vue'
import { apiPromptCreate, apiPromptDelete, apiPromptImportBuiltin, apiPromptPage, apiPromptUpdate } from '@/api'

const loading = ref(false)
const list = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const query = ref('')
const dialogVisible = ref(false)
const saving = ref(false)

const emptyForm = () => ({ id: 0, code: '', name: '', scene: 'qa', content: '', enabled: 1, remark: '' })
const form = reactive(emptyForm())

const sceneName = (s) => ({ qa: '问答', rewrite: '改写', agent: '智能体', judge: '评测' }[s] || s)
const sceneTag = (s) => ({ qa: 'primary', rewrite: 'warning', agent: 'success', judge: 'danger' }[s] || 'info')

const load = async () => {
  loading.value = true
  try {
    const data = await apiPromptPage({ query: query.value, page: page.value, page_size: pageSize })
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
  if (!form.code || !form.content) {
    ElMessage.warning('请填写编码与内容')
    return
  }
  saving.value = true
  try {
    if (form.id) {
      await apiPromptUpdate(form.id, { ...form })
    } else {
      await apiPromptCreate({ ...form })
    }
    ElMessage.success('保存成功')
    dialogVisible.value = false
    load()
  } finally {
    saving.value = false
  }
}

const remove = async (row) => {
  await apiPromptDelete(row.id)
  ElMessage.success('已删除')
  load()
}

const importBuiltin = async () => {
  const data = await apiPromptImportBuiltin()
  ElMessage.success(`内置模板写入完成，新增 ${data.created} 条（已存在的跳过）`)
  load()
}

onMounted(load)
</script>