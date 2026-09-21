<template>
  <div>
    <el-card shadow="never">
      <el-tabs v-model="tab">
        <!-- ============ 评测集 ============ -->
        <el-tab-pane label="评测集管理" name="dataset">
          <div class="toolbar">
            <div>
              <el-input v-model="dsQuery" placeholder="搜索评测集" clearable style="width: 220px" @keyup.enter="loadDatasets" @clear="loadDatasets" />
              <el-button :icon="Search" style="margin-left: 8px" @click="loadDatasets">查询</el-button>
            </div>
            <el-button type="primary" :icon="Plus" @click="openDataset()">新建评测集</el-button>
          </div>

          <el-table :data="datasets" v-loading="dsLoading" border stripe>
            <el-table-column prop="id" label="ID" width="60" />
            <el-table-column prop="name" label="名称" min-width="150">
              <template #default="{ row }">
                <el-link type="primary" @click="selectDataset(row)">{{ row.name }}</el-link>
              </template>
            </el-table-column>
            <el-table-column prop="description" label="描述" min-width="200" show-overflow-tooltip />
            <el-table-column prop="case_count" label="用例数" width="80" />
            <el-table-column label="操作" width="150" fixed="right">
              <template #default="{ row }">
                <el-button size="small" @click="selectDataset(row)">管理用例</el-button>
                <el-popconfirm title="删除评测集将同时删除其中用例，确认？" @confirm="removeDataset(row)">
                  <template #reference>
                    <el-button size="small" type="danger" plain>删除</el-button>
                  </template>
                </el-popconfirm>
              </template>
            </el-table-column>
          </el-table>
          <div class="pagination-wrap">
            <el-pagination background layout="total, prev, pager, next" :total="dsTotal" :page-size="pageSize" :current-page="dsPage" @current-change="(p) => { dsPage = p; loadDatasets() }" />
          </div>
        </el-tab-pane>

        <!-- ============ 批量测评 ============ -->
        <el-tab-pane label="批量测评" name="run">
          <el-divider content-position="left">发起测评</el-divider>
          <el-form inline label-width="90px">
            <el-form-item label="评测集">
              <el-select v-model="runForm.dataset_id" filterable placeholder="选择评测集" style="width: 180px">
                <el-option v-for="d in datasetOptions" :key="d.id" :label="d.name" :value="d.id" />
              </el-select>
            </el-form-item>
            <el-form-item label="知识库">
              <el-select v-model="runForm.kb_id" filterable placeholder="选择知识库" style="width: 180px">
                <el-option v-for="k in kbOptions" :key="k.id" :label="k.name" :value="k.id" />
              </el-select>
            </el-form-item>
            <el-form-item label="检索策略">
              <el-select v-model="runForm.strategy_id" clearable placeholder="库默认策略" style="width: 180px">
                <el-option v-for="s in strategyOptions" :key="s.id" :label="s.name" :value="s.id" />
              </el-select>
            </el-form-item>
            <el-form-item label="报告名">
              <el-input v-model="runForm.report_name" placeholder="评测报告" style="width: 160px" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :icon="VideoPlay" :loading="running" :disabled="!runForm.dataset_id || !runForm.kb_id" @click="startRun">开始评测</el-button>
            </el-form-item>
          </el-form>

          <el-divider content-position="left">评测记录</el-divider>
          <el-table :data="runs" v-loading="runLoading" border stripe>
            <el-table-column prop="id" label="ID" width="60" />
            <el-table-column prop="report_name" label="报告名" min-width="140" />
            <el-table-column prop="dataset_name" label="评测集" width="130" show-overflow-tooltip />
            <el-table-column prop="kb_name" label="知识库" width="130" show-overflow-tooltip />
            <el-table-column prop="strategy_name" label="策略" width="130" show-overflow-tooltip />
            <el-table-column prop="case_count" label="用例数" width="70" />
            <el-table-column label="四指标" min-width="320">
              <template #default="{ row }">
                <template v-if="row.status === 'done'">
                  <el-tag size="small" effect="plain" style="margin-right: 4px">召回 {{ (row.recall * 100).toFixed(1) }}%</el-tag>
                  <el-tag size="small" effect="plain" type="success" style="margin-right: 4px">精度 {{ (row.precision * 100).toFixed(1) }}%</el-tag>
                  <el-tag size="small" effect="plain" type="warning" style="margin-right: 4px">忠实 {{ (row.faithfulness * 100).toFixed(1) }}%</el-tag>
                  <el-tag size="small" effect="plain" type="danger" style="margin-right: 4px">切题 {{ (row.relevancy * 100).toFixed(1) }}%</el-tag>
                  <strong style="color: #409eff">综合 {{ (row.overall * 100).toFixed(1) }}%</strong>
                </template>
              </template>
            </el-table-column>
            <el-table-column prop="status" label="状态" width="90">
              <template #default="{ row }">
                <el-tag :type="row.status === 'done' ? 'success' : row.status === 'failed' ? 'danger' : 'warning'" size="small">
                  {{ { pending: '等待', running: '运行中', done: '完成', failed: '失败' }[row.status] || row.status }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="error" label="错误" min-width="120" show-overflow-tooltip />
            <el-table-column label="操作" width="150" fixed="right">
              <template #default="{ row }">
                <el-button size="small" type="primary" plain :disabled="row.status !== 'done'" @click="showRunItems(row)">明细</el-button>
                <el-popconfirm title="确认删除该评测记录？" @confirm="removeRun(row)">
                  <template #reference>
                    <el-button size="small" type="danger" plain>删除</el-button>
                  </template>
                </el-popconfirm>
              </template>
            </el-table-column>
          </el-table>
          <div class="pagination-wrap">
            <el-pagination background layout="total, prev, pager, next" :total="runTotal" :page-size="pageSize" :current-page="runPage" @current-change="(p) => { runPage = p; loadRuns() }" />
          </div>
        </el-tab-pane>

        <!-- ============ 策略对比看板 ============ -->
        <el-tab-pane label="策略对比看板" name="compare">
          <el-divider content-position="left">发起策略对比（2~4 套并排）</el-divider>
          <el-form inline label-width="90px">
            <el-form-item label="名称">
              <el-input v-model="cpForm.name" placeholder="策略对比" style="width: 150px" />
            </el-form-item>
            <el-form-item label="知识库">
              <el-select v-model="cpForm.kb_id" filterable placeholder="选择知识库" style="width: 180px">
                <el-option v-for="k in kbOptions" :key="k.id" :label="k.name" :value="k.id" />
              </el-select>
            </el-form-item>
            <el-form-item label="评测集">
              <el-select v-model="cpForm.dataset_id" filterable placeholder="选择评测集" style="width: 180px">
                <el-option v-for="d in datasetOptions" :key="d.id" :label="d.name" :value="d.id" />
              </el-select>
            </el-form-item>
            <el-form-item label="策略">
              <el-select v-model="cpForm.strategy_ids" multiple :multiple-limit="4" collapse-tags placeholder="选 2~4 套" style="width: 320px">
                <el-option v-for="s in strategyOptions" :key="s.id" :label="s.name" :value="s.id" />
              </el-select>
            </el-form-item>
            <el-form-item>
              <el-button type="warning" :icon="VideoPlay" :loading="cpRunning" :disabled="cpForm.strategy_ids.length < 2 || !cpForm.kb_id || !cpForm.dataset_id" @click="startCompare">开始对比</el-button>
            </el-form-item>
          </el-form>

          <el-divider content-position="left">对比记录</el-divider>
          <el-table :data="compares" v-loading="cpLoading" border stripe>
            <el-table-column prop="id" label="ID" width="60" />
            <el-table-column prop="name" label="名称" min-width="130" />
            <el-table-column prop="kb_name" label="知识库" width="130" show-overflow-tooltip />
            <el-table-column prop="dataset_name" label="评测集" width="130" show-overflow-tooltip />
            <el-table-column prop="arm_count" label="臂数" width="70" />
            <el-table-column prop="status" label="状态" width="90">
              <template #default="{ row }">
                <el-tag :type="row.status === 'done' ? 'success' : row.status === 'failed' ? 'danger' : 'warning'" size="small">
                  {{ { pending: '等待', running: '运行中', done: '完成', failed: '失败' }[row.status] || row.status }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="臂对比（综合/召回）" min-width="340">
              <template #default="{ row }">
                <template v-if="row.status === 'done'">
                  <el-tag v-for="arm in row.arms" :key="arm.arm_index" size="small" style="margin-right: 6px; margin-bottom: 2px">
                    {{ arm.strategy_name }}：{{ (arm.overall * 100).toFixed(1) }}% / 召回{{ (arm.recall * 100).toFixed(1) }}%
                  </el-tag>
                </template>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="100" fixed="right">
              <template #default="{ row }">
                <el-popconfirm title="确认删除该对比记录？" @confirm="removeCompare(row)">
                  <template #reference>
                    <el-button size="small" type="danger" plain>删除</el-button>
                  </template>
                </el-popconfirm>
              </template>
            </el-table-column>
          </el-table>
          <div class="pagination-wrap">
            <el-pagination background layout="total, prev, pager, next" :total="cpTotal" :page-size="pageSize" :current-page="cpPage" @current-change="(p) => { cpPage = p; loadCompares() }" />
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <!-- 新建评测集 -->
    <el-dialog v-model="dsDialog" title="新建评测集" width="460px" destroy-on-close>
      <el-form :model="dsForm" label-width="80px">
        <el-form-item label="名称" required><el-input v-model="dsForm.name" /></el-form-item>
        <el-form-item label="描述"><el-input v-model="dsForm.description" type="textarea" :rows="2" /></el-form-item>
        <el-form-item label="关联知识库">
          <el-select v-model="dsForm.kb_id" clearable style="width: 100%" placeholder="选填">
            <el-option v-for="k in kbOptions" :key="k.id" :label="k.name" :value="k.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dsDialog = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveDataset">保存</el-button>
      </template>
    </el-dialog>

    <!-- 用例管理抽屉 -->
    <el-drawer v-model="caseDrawer" :title="`用例管理 - ${currentDataset?.name || ''}`" size="76%">
      <div class="toolbar">
        <div>
          <el-button type="success" :icon="Plus" @click="openCase()">新增用例</el-button>
          <el-button :icon="Upload" @click="openBatch()">批量导入</el-button>
        </div>
        <span style="color: #909399; font-size: 12px">
          提示：可在知识库→片段管理中查得「片段ID」填入 source_chunk_ids，做 Context Recall 集合运算
        </span>
      </div>

      <el-table :data="cases" v-loading="caseLoading" border stripe>
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="question" label="问题" min-width="240" show-overflow-tooltip />
        <el-table-column prop="ground_truth" label="参考答案" min-width="180" show-overflow-tooltip />
        <el-table-column label="来源片段ID" width="180">
          <template #default="{ row }">
            <el-tag v-for="cid in row.source_chunk_ids" :key="cid" size="small" style="margin-right: 4px">{{ cid }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ row }">
            <el-popconfirm title="确认删除该用例？" @confirm="removeCase(row)">
              <template #reference>
                <el-button size="small" type="danger" plain>删除</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
      <div class="pagination-wrap">
        <el-pagination background layout="total, prev, pager, next" :total="caseTotal" :page-size="pageSize" :current-page="casePage" @current-change="(p) => { casePage = p; loadCases() }" />
      </div>
    </el-drawer>

    <!-- 新增/编辑用例 -->
    <el-dialog v-model="caseDialog" title="新增用例" width="560px" destroy-on-close>
      <el-form :model="caseForm" label-width="110px">
        <el-form-item label="问题" required>
          <el-input v-model="caseForm.question" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="参考答案">
          <el-input v-model="caseForm.ground_truth" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="来源片段ID">
          <el-select v-model="caseForm.source_chunk_ids" multiple filterable allow-create default-first-option collapse-tags style="width: 100%" placeholder="输入片段ID后回车">
            <el-option v-for="i in caseForm.source_chunk_ids" :key="i" :label="i" :value="i" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="caseDialog = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveCase">保存</el-button>
      </template>
    </el-dialog>

    <!-- 批量导入 -->
    <el-dialog v-model="batchDialog" title="批量导入用例" width="640px" destroy-on-close>
      <el-alert type="info" :closable="false" show-icon style="margin-bottom: 10px"
        title='JSON 数组格式：[{"question":"问题","ground_truth":"答案","source_chunk_ids":[1,2]}]' />
      <el-input v-model="batchText" type="textarea" :rows="12" class="mono" placeholder='[{"question": "...", "ground_truth": "...", "source_chunk_ids": []}]' />
      <template #footer>
        <el-button @click="batchDialog = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveBatch">导入</el-button>
      </template>
    </el-dialog>

    <!-- 评测明细 -->
    <el-drawer v-model="itemsDrawer" :title="`评测明细 - ${currentRun?.report_name || ''}`" size="78%">
      <el-table :data="items" v-loading="itemsLoading" border stripe size="small">
        <el-table-column prop="case_id" label="用例ID" width="80" />
        <el-table-column prop="question" label="问题" min-width="180" show-overflow-tooltip />
        <el-table-column prop="answer" label="答案" min-width="200" show-overflow-tooltip />
        <el-table-column label="四指标" min-width="220">
          <template #default="{ row }">
            <span style="font-size: 12px">
              召回 {{ (row.recall * 100).toFixed(0) }}% · 精度 {{ (row.precision * 100).toFixed(0) }}% · 忠实 {{ (row.faithfulness * 100).toFixed(0) }}% · 切题 {{ (row.relevancy * 100).toFixed(0) }}%
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="detail_json" label="裁判详情" min-width="160" show-overflow-tooltip />
      </el-table>
    </el-drawer>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus, Search, Upload, VideoPlay } from '@element-plus/icons-vue'
import {
  apiEvalCaseBatch, apiEvalCaseCreate, apiEvalCaseDelete, apiEvalCasePage,
  apiEvalCompareCreate, apiEvalCompareDelete, apiEvalComparePage,
  apiEvalDatasetCreate, apiEvalDatasetDelete, apiEvalDatasetOptions, apiEvalDatasetPage,
  apiEvalRunCreate, apiEvalRunDelete, apiEvalRunItems, apiEvalRunPage,
  apiKbOptions, apiRetrievalOptions,
} from '@/api'

const tab = ref('dataset')
const saving = ref(false)

// ---- 评测集 ----
const dsLoading = ref(false)
const datasets = ref([])
const dsTotal = ref(0)
const dsPage = ref(1)
const dsQuery = ref('')
const dsDialog = ref(false)
const dsForm = reactive({ name: '', description: '', kb_id: null })

// ---- 用例 ----
const caseDrawer = ref(false)
const caseDialog = ref(false)
const caseLoading = ref(false)
const cases = ref([])
const caseTotal = ref(0)
const casePage = ref(1)
const currentDataset = ref(null)
const caseForm = reactive({ question: '', ground_truth: '', source_chunk_ids: [] })
const batchDialog = ref(false)
const batchText = ref('')

// ---- 批量测评 ----
const runForm = reactive({ dataset_id: null, kb_id: null, strategy_id: null, report_name: '评测报告' })
const runs = ref([])
const runTotal = ref(0)
const runPage = ref(1)
const runLoading = ref(false)
const running = ref(false)
const itemsDrawer = ref(false)
const itemsLoading = ref(false)
const items = ref([])
const currentRun = ref(null)

// ---- 策略对比 ----
const cpForm = reactive({ name: '策略对比', kb_id: null, dataset_id: null, strategy_ids: [] })
const compares = ref([])
const cpTotal = ref(0)
const cpPage = ref(1)
const cpLoading = ref(false)
const cpRunning = ref(false)

// ---- 公共选项 ----
const pageSize = 10
const kbOptions = ref([])
const strategyOptions = ref([])
const datasetOptions = ref([])

const loadDatasets = async () => {
  dsLoading.value = true
  try {
    const data = await apiEvalDatasetPage({ query: dsQuery.value, page: dsPage.value, page_size: pageSize })
    datasets.value = data.list
    dsTotal.value = data.total
  } finally {
    dsLoading.value = false
  }
}

const openDataset = () => {
  Object.assign(dsForm, { name: '', description: '', kb_id: null })
  dsDialog.value = true
}

const saveDataset = async () => {
  if (!dsForm.name) {
    ElMessage.warning('请填写名称')
    return
  }
  saving.value = true
  try {
    await apiEvalDatasetCreate({ ...dsForm })
    ElMessage.success('已创建')
    dsDialog.value = false
    loadDatasets()
    loadOptions()
  } finally {
    saving.value = false
  }
}

const removeDataset = async (row) => {
  await apiEvalDatasetDelete(row.id)
  ElMessage.success('已删除')
  loadDatasets()
}

const selectDataset = (row) => {
  currentDataset.value = row
  casePage.value = 1
  caseDrawer.value = true
  loadCases()
}

const loadCases = async () => {
  caseLoading.value = true
  try {
    const data = await apiEvalCasePage({ dataset_id: currentDataset.value.id, page: casePage.value, page_size: pageSize })
    cases.value = data.list
    caseTotal.value = data.total
  } finally {
    caseLoading.value = false
  }
}

const openCase = () => {
  Object.assign(caseForm, { question: '', ground_truth: '', source_chunk_ids: [] })
  caseDialog.value = true
}

const saveCase = async () => {
  if (!caseForm.question) {
    ElMessage.warning('请填写问题')
    return
  }
  saving.value = true
  try {
    const ids = caseForm.source_chunk_ids.map((x) => Number(x)).filter((n) => !isNaN(n))
    await apiEvalCaseCreate(currentDataset.value.id, { question: caseForm.question, ground_truth: caseForm.ground_truth, source_chunk_ids: ids })
    ElMessage.success('已添加')
    caseDialog.value = false
    loadCases()
  } finally {
    saving.value = false
  }
}

const openBatch = () => {
  batchText.value = ''
  batchDialog.value = true
}

const saveBatch = async () => {
  let arr
  try {
    arr = JSON.parse(batchText.value)
    if (!Array.isArray(arr)) throw new Error('不是数组')
  } catch (e) {
    ElMessage.warning('JSON 解析失败：' + e.message)
    return
  }
  saving.value = true
  try {
    const data = await apiEvalCaseBatch(currentDataset.value.id, { cases: arr })
    ElMessage.success(`导入成功 ${data.created} 条`)
    batchDialog.value = false
    loadCases()
  } finally {
    saving.value = false
  }
}

const removeCase = async (row) => {
  await apiEvalCaseDelete(row.id)
  ElMessage.success('已删除')
  loadCases()
}

// ---- 评测运行 ----
const loadRuns = async () => {
  runLoading.value = true
  try {
    const data = await apiEvalRunPage({ page: runPage.value, page_size: pageSize })
    runs.value = data.list
    runTotal.value = data.total
  } finally {
    runLoading.value = false
  }
}

const startRun = async () => {
  running.value = true
  try {
    const data = await apiEvalRunCreate({ ...runForm })
    ElMessage.success(data.msg || '评测已启动')
    setTimeout(loadRuns, 2000)
  } finally {
    running.value = false
  }
}

const removeRun = async (row) => {
  await apiEvalRunDelete(row.id)
  ElMessage.success('已删除')
  loadRuns()
}

const showRunItems = async (row) => {
  currentRun.value = row
  itemsDrawer.value = true
  itemsLoading.value = true
  try {
    items.value = await apiEvalRunItems(row.id)
  } finally {
    itemsLoading.value = false
  }
}

// ---- 策略对比 ----
const loadCompares = async () => {
  cpLoading.value = true
  try {
    const data = await apiEvalComparePage({ page: cpPage.value, page_size: pageSize })
    compares.value = data.list
    cpTotal.value = data.total
  } finally {
    cpLoading.value = false
  }
}

const startCompare = async () => {
  cpRunning.value = true
  try {
    const data = await apiEvalCompareCreate({ ...cpForm })
    ElMessage.success(data.msg || '对比任务已启动')
    setTimeout(loadCompares, 2000)
  } finally {
    cpRunning.value = false
  }
}

const removeCompare = async (row) => {
  await apiEvalCompareDelete(row.id)
  ElMessage.success('已删除')
  loadCompares()
}

const loadOptions = async () => {
  try {
    const [kbs, strategies, dss] = await Promise.all([apiKbOptions(), apiRetrievalOptions(), apiEvalDatasetOptions()])
    kbOptions.value = kbs || []
    strategyOptions.value = strategies || []
    datasetOptions.value = dss || []
  } catch (_) {
    /* 忽略 */
  }
}

onMounted(() => {
  loadDatasets()
  loadRuns()
  loadCompares()
  loadOptions()
})
</script>