<template>
  <div>
    <el-card shadow="never">
      <el-tabs v-model="tab">
        <!-- 工具管理 -->
        <el-tab-pane label="工具管理" name="tools">
          <div class="toolbar">
            <div>
              <el-input v-model="query" placeholder="搜索名称/编码" clearable style="width: 220px" @keyup.enter="search" @clear="search" />
              <el-button :icon="Search" style="margin-left: 8px" @click="search">查询</el-button>
            </div>
            <div>
              <el-button type="success" :icon="Download" @click="importBuiltin">写入内置工具</el-button>
              <el-button type="primary" :icon="Plus" @click="openEdit()">新建工具</el-button>
            </div>
          </div>

          <el-table :data="list" v-loading="loading" border stripe>
            <el-table-column prop="id" label="ID" width="60" />
            <el-table-column prop="code" label="编码" width="160" />
            <el-table-column prop="name" label="名称" width="150" />
            <el-table-column prop="description" label="说明" min-width="200" show-overflow-tooltip />
            <el-table-column label="内置" width="70">
              <template #default="{ row }">
                <el-tag v-if="row.built_in === 1" type="success" size="small">内置</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="启用" width="80">
              <template #default="{ row }">
                <el-switch :model-value="row.enabled === 1" @change="(v) => toggleEnable(row, v)" />
              </template>
            </el-table-column>
            <el-table-column label="操作" width="220" fixed="right">
              <template #default="{ row }">
                <el-button size="small" type="primary" plain @click="openTest(row)">测试</el-button>
                <el-button size="small" @click="openEdit(row)">编辑</el-button>
                <el-popconfirm title="内置工具不可删除，只能停用；确认删除？" @confirm="remove(row)">
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
        </el-tab-pane>

        <!-- 工具调用日志 -->
        <el-tab-pane label="调用日志" name="logs">
          <div class="toolbar">
            <div>
              <el-input v-model="logQuery" placeholder="搜索工具编码" clearable style="width: 220px" @keyup.enter="searchLog" @clear="searchLog" />
              <el-button :icon="Search" style="margin-left: 8px" @click="searchLog">查询</el-button>
            </div>
          </div>
          <el-table :data="logs" v-loading="loadingLog" border stripe>
            <el-table-column prop="id" label="ID" width="70" />
            <el-table-column prop="tool_code" label="工具" width="150" />
            <el-table-column prop="args_json" label="参数" min-width="180" show-overflow-tooltip />
            <el-table-column prop="result" label="结果" min-width="220" show-overflow-tooltip />
            <el-table-column prop="status" label="状态" width="80">
              <template #default="{ row }">
                <el-tag :type="row.status === 'ok' ? 'success' : 'danger'" size="small">{{ row.status }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="cost_ms" label="耗时(ms)" width="100" />
            <el-table-column prop="created_at" label="时间" width="170" />
          </el-table>
          <div class="pagination-wrap">
            <el-pagination background layout="total, prev, pager, next" :total="logTotal" :page-size="pageSize" :current-page="logPage" @current-change="(p) => { logPage = p; loadLog() }" />
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <!-- 新建/编辑工具 -->
    <el-dialog v-model="dialogVisible" :title="form.id ? '编辑工具' : '新建工具'" width="640px" destroy-on-close>
      <el-form :model="form" label-width="90px">
        <el-form-item label="编码" required>
          <el-input v-model="form.code" placeholder="唯一编码" :disabled="!!form.id" />
        </el-form-item>
        <el-form-item label="名称" required>
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="说明">
          <el-input v-model="form.description" type="textarea" :rows="2" placeholder="给模型看的工具说明" />
        </el-form-item>
        <el-form-item label="Schema">
          <el-input v-model="form.schema_json" type="textarea" :rows="6" class="mono" placeholder='{"type":"object","properties":{...}}' />
        </el-form-item>
        <el-form-item label="处理器">
          <el-input v-model="form.handler" placeholder="内置处理器名（自定义工具留空）" />
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

    <!-- 手动测试 -->
    <el-dialog v-model="testVisible" :title="`测试工具：${current?.name || ''}`" width="560px" destroy-on-close>
      <el-form label-width="90px">
        <el-form-item label="参数">
          <el-input v-model="testArgs" type="textarea" :rows="5" class="mono" placeholder='{"a": 3, "b": 4}' />
        </el-form-item>
        <el-form-item v-if="testResult" label="结果">
          <el-input :model-value="testResult" type="textarea" :rows="5" readonly class="mono" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="testVisible = false">关闭</el-button>
        <el-button type="primary" :loading="testing" @click="runTest">执行</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Download, Plus, Search } from '@element-plus/icons-vue'
import { apiToolCreate, apiToolDelete, apiToolExecute, apiToolImportBuiltin, apiToolLogPage, apiToolPage, apiToolUpdate } from '@/api'

const tab = ref('tools')
const loading = ref(false)
const list = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const query = ref('')

const loadingLog = ref(false)
const logs = ref([])
const logTotal = ref(0)
const logPage = ref(1)
const logQuery = ref('')

const dialogVisible = ref(false)
const saving = ref(false)
const testVisible = ref(false)
const testing = ref(false)
const current = ref(null)
const testArgs = ref('{}')
const testResult = ref('')

const emptyForm = () => ({ id: 0, code: '', name: '', description: '', schema_json: '{}', handler: '', enabled: 1 })
const form = reactive(emptyForm())

const load = async () => {
  loading.value = true
  try {
    const data = await apiToolPage({ query: query.value, page: page.value, page_size: pageSize })
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

const loadLog = async () => {
  loadingLog.value = true
  try {
    const data = await apiToolLogPage({ query: logQuery.value, page: logPage.value, page_size: pageSize })
    logs.value = data.list
    logTotal.value = data.total
  } finally {
    loadingLog.value = false
  }
}

const searchLog = () => {
  logPage.value = 1
  loadLog()
}

const openEdit = (row) => {
  Object.assign(form, emptyForm(), row || {})
  dialogVisible.value = true
}

const save = async () => {
  if (!form.code || !form.name) {
    ElMessage.warning('请填写编码与名称')
    return
  }
  saving.value = true
  try {
    if (form.id) {
      await apiToolUpdate(form.id, { ...form })
    } else {
      await apiToolCreate({ ...form })
    }
    ElMessage.success('保存成功')
    dialogVisible.value = false
    load()
  } finally {
    saving.value = false
  }
}

const toggleEnable = async (row, v) => {
  await apiToolUpdate(row.id, { ...row, enabled: v ? 1 : 0 })
  row.enabled = v ? 1 : 0
  ElMessage.success(v ? '已启用' : '已停用')
}

const remove = async (row) => {
  await apiToolDelete(row.id)
  ElMessage.success('已删除')
  load()
}

const importBuiltin = async () => {
  const data = await apiToolImportBuiltin()
  ElMessage.success(`内置工具写入完成，新增 ${data.created} 条`)
  load()
}

const openTest = (row) => {
  current.value = row
  testArgs.value = row.schema_json && row.schema_json !== '{}' ? '{}' : '{}'
  testResult.value = ''
  testVisible.value = true
}

const runTest = async () => {
  testing.value = true
  try {
    let args = {}
    try {
      args = JSON.parse(testArgs.value || '{}')
    } catch (_) {
      ElMessage.warning('参数不是合法 JSON')
      return
    }
    const data = await apiToolExecute({ code: current.value.code, args })
    testResult.value = typeof data.result === 'string' ? data.result : JSON.stringify(data.result, null, 2)
  } finally {
    testing.value = false
  }
}

onMounted(() => {
  load()
  loadLog()
})
</script>