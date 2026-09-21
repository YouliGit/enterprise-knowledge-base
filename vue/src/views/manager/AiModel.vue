<template>
  <div>
    <el-card shadow="never">
      <div class="toolbar">
        <div>
          <el-radio-group v-model="typeFilter" @change="load">
            <el-radio-button label="">全部</el-radio-button>
            <el-radio-button label="chat">对话模型</el-radio-button>
            <el-radio-button label="embedding">向量模型</el-radio-button>
            <el-radio-button label="rerank">重排模型</el-radio-button>
          </el-radio-group>
        </div>
        <div>
          <el-button type="primary" :icon="Plus" @click="openEdit()">新增模型</el-button>
          <el-button :icon="Refresh" @click="load">刷新</el-button>
        </div>
      </div>

      <el-table :data="list" v-loading="loading" border stripe>
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="name" label="配置名称" min-width="130" />
        <el-table-column prop="type_name" label="类型" width="90">
          <template #default="{ row }">
            <el-tag :type="typeTag(row.type)" effect="dark">{{ row.type_name }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="model" label="模型名" min-width="150" />
        <el-table-column label="Key" width="80">
          <template #default="{ row }">
            <el-tag v-if="row.has_key" type="success" size="small">已填写</el-tag>
            <el-tag v-else type="danger" size="small">未填写</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="dimension" label="维度" width="70">
          <template #default="{ row }">{{ row.type === 'embedding' ? row.dimension : '-' }}</template>
        </el-table-column>
        <el-table-column prop="temperature" label="温度" width="70">
          <template #default="{ row }">{{ row.type === 'chat' ? row.temperature : '-' }}</template>
        </el-table-column>
        <el-table-column label="启用" width="90">
          <template #default="{ row }">
            <el-switch :model-value="row.enabled === 1" @change="(v) => toggleEnable(row, v)" />
          </template>
        </el-table-column>
        <el-table-column prop="test_info" label="连通性测试" min-width="180" show-overflow-tooltip />
        <el-table-column label="操作" width="210" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" plain :loading="testingId === row.id" @click="test(row)">测试</el-button>
            <el-button size="small" @click="openEdit(row)">编辑</el-button>
            <el-popconfirm title="确认删除该模型配置？" @confirm="remove(row)">
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

    <!-- 编辑弹窗 -->
    <el-dialog v-model="dialogVisible" :title="form.id ? '编辑模型配置' : '新增模型配置'" width="560px" destroy-on-close>
      <el-form :model="form" label-width="100px">
        <el-form-item label="配置名称" required>
          <el-input v-model="form.name" placeholder="例如：生产-对话模型" />
        </el-form-item>
        <el-form-item label="类型" required>
          <el-select v-model="form.type" style="width: 100%">
            <el-option label="对话模型 chat" value="chat" />
            <el-option label="向量模型 embedding" value="embedding" />
            <el-option label="重排模型 rerank" value="rerank" />
          </el-select>
        </el-form-item>
        <el-form-item label="模型名" required>
          <el-input v-model="form.model" placeholder="qwen-plus / text-embedding-v4 / gte-rerank-v2" />
        </el-form-item>
        <el-form-item label="厂商">
          <el-select v-model="form.vendor" style="width: 100%">
            <el-option label="阿里云百炼 dashscope" value="dashscope" />
          </el-select>
        </el-form-item>
        <el-form-item label="API Base">
          <el-input v-model="form.api_base" placeholder="留空自动用百炼兼容地址" />
        </el-form-item>
        <el-form-item label="API Key">
          <el-input v-model="form.api_key" type="password" show-password :placeholder="form.id ? '留空则保留原 Key' : '填写百炼 API Key（付费项，见未完成清单）'" />
        </el-form-item>
        <el-form-item v-if="form.type === 'embedding'" label="向量维度">
          <el-input-number v-model="form.dimension" :min="0" :max="8192" />
        </el-form-item>
        <el-form-item v-if="form.type === 'chat'" label="温度">
          <el-input-number v-model="form.temperature" :min="0" :max="2" :step="0.1" />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="form.enabled" :active-value="1" :inactive-value="0" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.remark" type="textarea" :rows="2" />
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
import { Plus, Refresh } from '@element-plus/icons-vue'
import { apiModelCreate, apiModelDelete, apiModelEnable, apiModelPage, apiModelTest, apiModelUpdate } from '@/api'

const loading = ref(false)
const list = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const typeFilter = ref('')
const dialogVisible = ref(false)
const saving = ref(false)
const testingId = ref(0)

const emptyForm = () => ({ id: 0, name: '', type: 'chat', model: '', vendor: 'dashscope', api_base: '', api_key: '', dimension: 1024, temperature: 0.7, enabled: 1, remark: '' })
const form = reactive(emptyForm())

const typeTag = (t) => ({ chat: 'primary', embedding: 'success', rerank: 'warning' }[t] || 'info')

const load = async () => {
  loading.value = true
  try {
    const data = await apiModelPage({ type: typeFilter.value, page: page.value, page_size: pageSize })
    list.value = data.list
    total.value = data.total
  } finally {
    loading.value = false
  }
}

const openEdit = (row) => {
  Object.assign(form, emptyForm(), row || {})
  dialogVisible.value = true
}

const save = async () => {
  if (!form.name || !form.model) {
    ElMessage.warning('请填写名称与模型名')
    return
  }
  saving.value = true
  try {
    if (form.id) {
      await apiModelUpdate(form.id, { ...form })
    } else {
      await apiModelCreate({ ...form })
    }
    ElMessage.success('保存成功（配置改动 ≤2s 生效，无需重启）')
    dialogVisible.value = false
    load()
  } finally {
    saving.value = false
  }
}

const toggleEnable = async (row, v) => {
  await apiModelEnable(row.id, { enabled: v ? 1 : 0 })
  row.enabled = v ? 1 : 0
  ElMessage.success(v ? '已启用' : '已停用')
}

const test = async (row) => {
  testingId.value = row.id
  try {
    const data = await apiModelTest(row.id)
    ElMessage[data.ok ? 'success' : 'warning'](data.info || '测试完成')
    load()
  } finally {
    testingId.value = 0
  }
}

const remove = async (row) => {
  await apiModelDelete(row.id)
  ElMessage.success('已删除')
  load()
}

onMounted(load)
</script>