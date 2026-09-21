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

      <el-table :data="list" v-loading="loading" border stripe>
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="name" label="名称" min-width="150" />
        <el-table-column prop="mode" label="模式" width="110">
          <template #default="{ row }">
            <el-tag :type="row.mode === 'parent_child' ? 'primary' : 'info'" effect="plain">
              {{ row.mode === 'parent_child' ? '父子分块' : '递归分块' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="子块大小/重叠" width="140">
          <template #default="{ row }">{{ row.chunk_size }} / {{ row.chunk_overlap }}</template>
        </el-table-column>
        <el-table-column label="父块大小/重叠" width="140">
          <template #default="{ row }">
            {{ row.mode === 'parent_child' ? `${row.parent_chunk_size} / ${row.parent_chunk_overlap}` : '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="separators_json" label="分隔符" min-width="180" show-overflow-tooltip class-name="mono" />
        <el-table-column prop="kb_count" label="被引用" width="80">
          <template #default="{ row }">
            <el-tag v-if="row.kb_count > 0" type="warning" size="small">{{ row.kb_count }} 个库</el-tag>
            <span v-else style="color: #909399">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="remark" label="备注" min-width="120" show-overflow-tooltip />
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

    <el-dialog v-model="dialogVisible" :title="form.id ? '编辑切分策略' : '新建切分策略'" width="560px" destroy-on-close>
      <el-form :model="form" label-width="130px">
        <el-form-item label="名称" required>
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="模式" required>
          <el-radio-group v-model="form.mode">
            <el-radio value="parent_child">父子分块（小块找、大块答）</el-radio>
            <el-radio value="recursive">递归分块</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="子块大小" required>
              <el-input-number v-model="form.chunk_size" :min="50" :max="5000" :step="50" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="子块重叠" required>
              <el-input-number v-model="form.chunk_overlap" :min="0" :max="1000" :step="10" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row v-if="form.mode === 'parent_child'" :gutter="12">
          <el-col :span="12">
            <el-form-item label="父块大小">
              <el-input-number v-model="form.parent_chunk_size" :min="200" :max="10000" :step="100" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="父块重叠">
              <el-input-number v-model="form.parent_chunk_overlap" :min="0" :max="2000" :step="10" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="递归分隔符">
          <el-input v-model="form.separators_json" class="mono" placeholder='["\n\n", "\n", "。", "；", "，", " "]' />
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
import { Plus, Search } from '@element-plus/icons-vue'
import { apiSplitCreate, apiSplitDelete, apiSplitPage, apiSplitUpdate } from '@/api'

const loading = ref(false)
const list = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const query = ref('')
const dialogVisible = ref(false)
const saving = ref(false)

const emptyForm = () => ({
  id: 0, name: '', mode: 'parent_child', chunk_size: 500, chunk_overlap: 50,
  parent_chunk_size: 1500, parent_chunk_overlap: 100,
  separators_json: '["\\n\\n", "\\n", "。", "；", "，", " "]', remark: '',
})
const form = reactive(emptyForm())

const load = async () => {
  loading.value = true
  try {
    const data = await apiSplitPage({ query: query.value, page: page.value, page_size: pageSize })
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
      await apiSplitUpdate(form.id, { ...form })
    } else {
      await apiSplitCreate({ ...form })
    }
    ElMessage.success('保存成功')
    dialogVisible.value = false
    load()
  } finally {
    saving.value = false
  }
}

const remove = async (row) => {
  await apiSplitDelete(row.id)
  ElMessage.success('已删除')
  load()
}

onMounted(load)
</script>