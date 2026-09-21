<template>
  <div>
    <!-- 统计卡片 -->
    <el-row :gutter="14">
      <el-col v-for="c in cards" :key="c.label" :xs="12" :sm="8" :md="6" :lg="4">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-value" :style="{ color: c.color }">{{ c.value }}</div>
          <div class="stat-label">{{ c.label }}</div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="14" style="margin-top: 14px">
      <!-- 架构概览 -->
      <el-col :span="12">
        <el-card shadow="never">
          <template #header>系统架构概览</template>
          <el-descriptions :column="1" border size="small">
            <el-descriptions-item v-for="(v, k) in summary.architecture || {}" :key="k" :label="k">
              {{ v }}
            </el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-col>
      <!-- 数据分布 -->
      <el-col :span="12">
        <el-card shadow="never">
          <template #header>资源分布</template>
          <div ref="chartRef" style="height: 300px"></div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 待办提示 -->
    <el-alert
      v-if="summary.failed_doc > 0"
      style="margin-top: 14px"
      type="warning"
      :closable="false"
      show-icon
      :title="`有 ${summary.failed_doc} 个文档解析失败，请到「文档管理」查看处理`"
    />
    <el-alert
      v-if="summary.optimize > 0"
      style="margin-top: 14px"
      type="info"
      :closable="false"
      show-icon
      :title="`有 ${summary.optimize} 条答案收到「没用」反馈，可结合召回调试台优化检索策略`"
    />
  </div>
</template>

<script setup>
import { computed, onMounted, onBeforeUnmount, reactive, ref, nextTick } from 'vue'
import * as echarts from 'echarts'
import { apiDashboardSummary } from '@/api'

const summary = reactive({})
const chartRef = ref(null)
let chart = null

const statItems = [
  ['kb', '知识库', '#409eff'],
  ['doc', '文档', '#67c23a'],
  ['chunk', '片段', '#e6a23c'],
  ['vector', '向量', '#f56c6c'],
  ['app', '问答应用', '#909399'],
  ['question', '提问数', '#9b59b6'],
  ['model', '模型配置', '#1abc9c'],
  ['user', '用户', '#3498db'],
  ['agent_run', 'Agent运行', '#e67e22'],
  ['eval_run', '评测运行', '#2ecc71'],
  ['optimize', '待优化反馈', '#ff7675'],
  ['failed_doc', '失败文档', '#d63031'],
]

const cards = computed(() =>
  statItems.map(([key, label, color]) => ({ value: summary[key] ?? 0, label, color }))
)

const renderChart = () => {
  if (!chartRef.value) return
  chart = echarts.init(chartRef.value)
  const data = [
    { name: '知识库', value: summary.kb || 0 },
    { name: '文档', value: summary.doc || 0 },
    { name: '片段(入库)', value: summary.chunk || 0 },
    { name: '向量', value: summary.vector || 0 },
    { name: '问答应用', value: summary.app || 0 },
    { name: '用户', value: summary.user || 0 },
  ].filter((d) => d.value > 0)
  chart.setOption({
    tooltip: { trigger: 'item' },
    legend: { bottom: 0 },
    series: [
      {
        type: 'pie',
        radius: ['38%', '66%'],
        center: ['50%', '44%'],
        avoidLabelOverlap: true,
        itemStyle: { borderRadius: 6, borderColor: '#fff', borderWidth: 2 },
        label: { show: false },
        emphasis: { label: { show: true, fontSize: 16, fontWeight: 'bold' } },
        data: data.length ? data : [{ name: '暂无数据', value: 1, itemStyle: { color: '#eee' } }],
      },
    ],
  })
}

const handleResize = () => chart && chart.resize()

onMounted(async () => {
  const data = await apiDashboardSummary()
  Object.assign(summary, data)
  await nextTick()
  renderChart()
  window.addEventListener('resize', handleResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  chart && chart.dispose()
})
</script>

<style scoped>
.stat-card {
  margin-bottom: 14px;
  text-align: center;
}
.stat-value {
  font-size: 28px;
  font-weight: 700;
}
.stat-label {
  color: #909399;
  font-size: 13px;
  margin-top: 4px;
}
</style>