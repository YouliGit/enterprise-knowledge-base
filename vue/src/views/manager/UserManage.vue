<template>
  <div>
    <el-card shadow="never">
      <div class="toolbar">
        <div>
          <el-input v-model="query" placeholder="搜索账号/昵称" clearable style="width: 220px" @keyup.enter="search" @clear="search" />
          <el-button :icon="Search" style="margin-left: 8px" @click="search">查询</el-button>
        </div>
        <el-button type="primary" :icon="Plus" @click="openEdit()">新增用户</el-button>
      </div>

      <el-table :data="list" v-loading="loading" border stripe>
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="username" label="账号" min-width="120" />
        <el-table-column prop="nickname" label="昵称" min-width="120" />
        <el-table-column prop="email" label="邮箱" min-width="150" show-overflow-tooltip />
        <el-table-column prop="phone" label="手机" width="130" />
        <el-table-column prop="role" label="角色" width="90">
          <template #default="{ row }">
            <el-tag :type="row.role === 'admin' ? 'warning' : 'info'" size="small" effect="dark">{{ row.role === 'admin' ? '管理员' : '用户' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-switch :model-value="row.status === 1" @change="(v) => toggleStatus(row, v)" />
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="注册时间" width="170" />
        <el-table-column label="操作" width="230" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="openEdit(row)">编辑</el-button>
            <el-button size="small" type="warning" plain @click="openResetPwd(row)">重置密码</el-button>
            <el-popconfirm title="确认删除该用户？" @confirm="remove(row)">
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

    <el-dialog v-model="dialogVisible" :title="form.id ? '编辑用户' : '新增用户'" width="480px" destroy-on-close>
      <el-form :model="form" label-width="90px">
        <el-form-item label="账号" required>
          <el-input v-model="form.username" :disabled="!!form.id" />
        </el-form-item>
        <el-form-item v-if="!form.id" label="密码" required>
          <el-input v-model="form.password" type="password" show-password />
        </el-form-item>
        <el-form-item label="昵称">
          <el-input v-model="form.nickname" />
        </el-form-item>
        <el-form-item label="角色">
          <el-select v-model="form.role" style="width: 100%">
            <el-option label="普通用户" value="user" />
            <el-option label="管理员" value="admin" />
          </el-select>
        </el-form-item>
        <el-form-item label="邮箱">
          <el-input v-model="form.email" />
        </el-form-item>
        <el-form-item label="手机">
          <el-input v-model="form.phone" />
        </el-form-item>
        <el-form-item label="状态">
          <el-switch v-model="form.status" :active-value="1" :inactive-value="0" active-text="启用" inactive-text="禁用" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="pwdVisible" title="重置密码" width="400px" destroy-on-close>
      <el-form :model="pwdForm" label-width="90px">
        <el-form-item label="用户">
          <el-input :model-value="`${pwdTarget?.username} (${pwdTarget?.nickname})`" disabled />
        </el-form-item>
        <el-form-item label="新密码" required>
          <el-input v-model="pwdForm.password" type="password" show-password placeholder="至少4位" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="pwdVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="savePwd">确认重置</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus, Search } from '@element-plus/icons-vue'
import { apiUserCreate, apiUserDelete, apiUserPage, apiUserResetPwd, apiUserStatus, apiUserUpdate } from '@/api'

const loading = ref(false)
const list = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 10
const query = ref('')
const dialogVisible = ref(false)
const saving = ref(false)
const pwdVisible = ref(false)
const pwdTarget = ref(null)

const emptyForm = () => ({ id: 0, username: '', password: '', nickname: '', role: 'user', email: '', phone: '', status: 1 })
const form = reactive(emptyForm())
const pwdForm = reactive({ password: '' })

const load = async () => {
  loading.value = true
  try {
    const data = await apiUserPage({ query: query.value, page: page.value, page_size: pageSize })
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
  delete form.password
  dialogVisible.value = true
}

const save = async () => {
  if (!form.username) {
    ElMessage.warning('请填写账号')
    return
  }
  saving.value = true
  try {
    if (form.id) {
      await apiUserUpdate(form.id, { ...form })
    } else {
      if (!form.password) {
        ElMessage.warning('请填写初始密码')
        return
      }
      await apiUserCreate({ ...form })
    }
    ElMessage.success('保存成功')
    dialogVisible.value = false
    load()
  } finally {
    saving.value = false
  }
}

const toggleStatus = async (row, v) => {
  await apiUserStatus(row.id, { status: v ? 1 : 0 })
  row.status = v ? 1 : 0
  ElMessage.success(v ? '已启用' : '已禁用')
}

const openResetPwd = (row) => {
  pwdTarget.value = row
  pwdForm.password = ''
  pwdVisible.value = true
}

const savePwd = async () => {
  if (!pwdForm.password || pwdForm.password.length < 4) {
    ElMessage.warning('新密码至少4位')
    return
  }
  saving.value = true
  try {
    await apiUserResetPwd(pwdTarget.value.id, { password: pwdForm.password })
    ElMessage.success('密码已重置')
    pwdVisible.value = false
  } finally {
    saving.value = false
  }
}

const remove = async (row) => {
  await apiUserDelete(row.id)
  ElMessage.success('已删除')
  load()
}

onMounted(load)
</script>