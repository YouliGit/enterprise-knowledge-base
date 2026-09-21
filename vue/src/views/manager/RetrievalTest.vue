<template>
  <div>
    <el-card shadow="never">
      <div class="toolbar">
        <div class="test-form">
          <el-select v-model="kbId" filterable placeholder="选择知识库" style="width: 200px">
            <el-option v-for="k in kbOptions" :key="k.id" :label="k.name" :value="k.id" />
          </el-select>
          <el-select v-model="strategyId" clearable placeholder="检索策略（默认库策略）" style="width: 220px">
            <el-option v-for="s in strategyOptions" :key="s.id" :label="s.name" :value="s.id" />
          </el-select>
          <el-input v-model="queryText" placeholder="输入测试问题" clearable style="width: 300px" @keyup.enter="runTest" />
          <el-button type="primary" :icon="Search" :loading="testing" :disabled="!kbId" @click="runTest">单次检索</el-button>
        </div>
        <el-button type="warning" plain :icon="Grid" :disabled="!kbId || compareStrategyIds.length < 2" @click="runCompare">
          召回调试台（{{ compareStrategyIds.length }}/4 套并排）
        </el-button>
      </div>

      <el-form inline label-width="90px" style="margin-bottom: 4px">
        <el-form-item label="对比策略">
          <el-select v-model="compareStrategyIds" multiple collapse-tags collapse-tags-tooltip :max-collapse-tags="3" placeholder="选 2~4 套策略对比" style="width: 380px">
            <el-option v-for="s in strategyOptions" :key="s.id" :label="s.name" :value="s.id" />
          </el-select>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 单次检索结果 -->
    <template v-if="singleResult">
      <el-card shadow="never" style="margin-top: 14px">
        <template #header>
          <div style="display: flex; justify-content: space-between; align-items: center">
            <span>单次检索结果 · 策略：{{ singleResult.strategy.name }}</span>
            <el-button link type="primary" @click="singleResult = null">清除</el-button>
          </div>
        </template>

        <template v-if="singleResult.traces?.length">
          <el-timeline style="padding-left: 6px">
            <el-timeline-item v-for="t in singleResult.traces" :key="t.stage" :timestamp="`${t.stage}`" placement="top">
              <el-card shadow="never" class="trace-card">
                <div class="trace-head">
                  <el-tag size="small" :type="stageTag(t.stage)">{{ t.stage }}</el-tag>
                  <span v-if="t.dimension" class="mono" style="margin-left: 8px">量纲：{{ t.dimension }}</span>
                  <span v-if="t.threshold !== undefined && t.threshold !== null" class="mono" style="margin-left: 8px">阈值：{{ t.threshold }}</span>
                  <span v-if="t.top_k" class="mono" style="margin-left: 8px">top{{ t.top_k }}</span>
                  <span v-if="t.cost_ms" class="mono" style="margin-left: 8px">耗时 {{ t.cost_ms }}ms</span>
                  <el-tag v-if="t.hit >= 0" size="small" :type="t.hit === 0 ? 'danger' : 'success'" style="margin-left: 8px">
                    阈值命中 {{ t.hit }}/{{ t.total || t.candidate_count || '-' }}
                  </el-tag>
                </div>
                <div v-if="t.queries?.length" style="margin-top: 6px; font-size: 12px; color: #606266">
                  改写问题：<el-tag v-for="q in t.queries" :key="q" size="small" effect="plain" style="margin-right: 4px">{{ q }}</el-tag>
                </div>
                <pre v-if="t.notes" class="trace-note">{{ t.notes }}</pre>
              </el-card>
            </el-timeline-item>
          </el-timeline>
        </template>

        <el-divider content-position="left">命中上下文</el-divider>
        <el-table :data="singleResult.contexts" border stripe size="small">
          <el-table-column prop="rank" label="名次" width="60" />
          <el-table-column prop="chunk_id" label="片段ID" width="90" />
          <el-table-column prop="content" label="内容" min-width="320" show-overflow-tooltip />
          <el-table-column label="分数量纲" width="140">
            <template #default="{ row }">
              <el-tooltip v-for="(v, k) in row.scores || {}" :key="k" :content="`${k}: ${fmtScore(v)}`">
                <el-tag size="small" style="margin-right: 4px">{{ k }} {{ fmtScore(v) }}</el-tag>
              </el-tooltip>
            </template>
          </el-table-column>
        </el-table>
      </el-card>
    </template>

    <!-- 召回调试台：多套并排 -->
    <template v-if="compareResult">
      <el-card shadow="never" style="margin-top: 14px">
        <template #header>
          <div style="display: flex; justify-content: space-between; align-items: center">
            <span>召回调试台（{{ compareResult.arms.length }} 套并排）</span>
            <el-button link type="primary" @click="compareResult = null">清除</el-button>
          </div>
        </template>
        <el-row :gutter="14">
          <el-col v-for="arm in compareResult.arms" :key="arm.strategy.id" :span="24 / Math.max(compareResult.arms.length, 1)">
            <el-card shadow="hover" class="arm-card">
              <template #header>
                <div style="display: flex; justify-content: space-between; align-items: center">
                  <strong>{{ arm.strategy.name }}</strong>
                  <span v-if="arm.cost_ms" class="mono" style="font-size: 12px">{{ arm.cost_ms }}ms</span>
                </div>
              </template>
              <el-alert v-if="arm.error" type="error" :closable="false" :title="arm.error" />
              <template v-else>
                <el-table :data="arm.contexts" border stripe size="small" max-height="420">
                  <el-table-column prop="rank" label="#" width="44" />
                  <el-table-column prop="chunk_id" label="片段ID" width="80" />
                  <el-table-column prop="content" label="内容" min-width="180" show-overflow-tooltip />
                  <el-table-column label="分数" width="120">
                    <template #default="{ row }">
                      <span class="mono" style="font-size: 12px">{{ fmtScore(row.scores?.rerank ?? row.scores?.cosine ?? row.scores?.rrf) }}</span>
                    </template>
                  </el-table-column>
                </el-table>
                <el-collapse v-if="arm.traces?.length" style="margin-top: 8px">
                  <el-collapse-item title="阶段追踪" name="traces">
                    <div v-for="t in arm.traces" :key="t.stage" style="font-size: 12px; margin-bottom: 4px">
                      <el-tag size="small" :type="stageTag(t.stage)">{{ t.stage }}</el-tag>
                      <span v-if="t.dimension" class="mono" style="margin-left: 6px">量纲:{{ t.dimension }}</span>
                      <span v-if="t.hit >= 0" class="mono" style="margin-left: 6px">命中 {{ t.hit }}</span>
                      <span class="mono" style="margin-left: 6px">{{ t.cost_ms }}ms</span>
                    </div>
                  </el-collapse-item>
                </el-collapse>
              </template>
            </el-card>
          </el-col>
        </el-row>
      </el-card>
    </template>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Grid, Search } from '@element-plus/icons-vue'
import { apiKbOptions, apiRetrievalCompare, apiRetrievalOptions, apiRetrievalTest } from '@/api'

const kbOptions = ref([])
const strategyOptions = ref([])
const kbId = ref(0)
const strategyId = ref(null)
const queryText = ref('')
const testing = ref(false)
const comparing = ref(false)

const singleResult = ref(null)
const compareResult = ref(null)
const compareStrategyIds = ref([])

const stageTag = (s) => ({ 改写: 'warning', 向量: 'primary', BM25: 'info', 融合: 'success', 父块回填: 'danger', 重排: 'danger' }[s] || 'info')
const fmtScore = (v) => (v === undefined || v === null ? '-' : typeof v === 'number' ? Number(v).toFixed(4) : String(v))

const runTest = async () => {
  if (!kbId.value) {
    ElMessage.warning('请选择知识库')
    return
  }
  if (!queryText.value.trim()) {
    ElMessage.warning('请输入测试问题')
    return
  }
  testing.value = true
  try {
    singleResult.value = await apiRetrievalTest({ kb_id: kbId.value, query: queryText.value, strategy_id: strategyId.value || undefined })
  } finally {
    testing.value = false
  }
}

const runCompare = async () => {
  if (compareStrategyIds.value.length < 2) {
    ElMessage.warning('请至少选择 2 套策略进行对比')
    return
  }
  comparing.value = true
  try {
    compareResult.value = await apiRetrievalCompare({ kb_id: kbId.value, query: queryText.value, strategy_ids: compareStrategyIds.value })
  } finally {
    comparing.value = false
  }
}

onMounted(async () => {
  kbOptions.value = await apiKbOptions()
  strategyOptions.value = await apiRetrievalOptions()
})
</script>

<style scoped>
.test-form {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.trace-card {
  padding: 0;
}
.trace-head {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
}
.trace-note {
  background: #f5f7fa;
  border-radius: 4px;
  padding: 6px 10px;
  font-size: 12px;
  white-space: pre-wrap;
  margin: 6px 0 0;
}
.arm-card {
  margin-bottom: 10px;
}
</style>