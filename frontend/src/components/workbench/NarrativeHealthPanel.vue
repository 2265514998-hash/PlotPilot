<template>
  <div class="narrative-health-panel">
    <!-- 加载状态 -->
    <n-spin :show="loading" description="加载中...">
      <div v-if="error" style="padding: 16px">
        <n-alert type="error" :title="error" />
      </div>

      <div v-else-if="health" class="health-content">
        <!-- 综合健康分 -->
        <div class="score-section">
          <n-progress
            type="dashboard"
            :percentage="health.health_score"
            :color="scoreColor"
            :rail-color="scoreRailColor"
            :stroke-width="10"
            :size="120"
          >
            <div style="text-align: center">
              <div style="font-size: 28px; font-weight: 700">{{ health.health_score }}</div>
              <div style="font-size: 12px; opacity: 0.6">健康分</div>
            </div>
          </n-progress>
          <n-text depth="3" style="font-size: 12px; margin-top: 8px">
            {{ scoreLabel }}
          </n-text>
        </div>

        <!-- 伏笔状态 -->
        <n-card title="伏笔状态" size="small" :bordered="false" style="margin-bottom: 12px">
          <template #header-extra>
            <n-tag :type="health.foreshadowing.overdue > 0 ? 'warning' : 'success'" size="small">
              {{ health.foreshadowing.overdue }} 逾期
            </n-tag>
          </template>
          <n-space :size="8" vertical>
            <div class="stat-row">
              <n-text depth="3">总计</n-text>
              <n-text strong>{{ health.foreshadowing.total }}</n-text>
            </div>
            <n-space :size="4">
              <n-tag type="success" size="small">已解决 {{ health.foreshadowing.resolved }}</n-tag>
              <n-tag type="info" size="small">已埋设 {{ health.foreshadowing.planted }}</n-tag>
              <n-tag type="default" size="small">已放弃 {{ health.foreshadowing.abandoned }}</n-tag>
            </n-space>
            <div class="stat-row">
              <n-text depth="3">T0 上下文窗口</n-text>
              <n-text strong>{{ health.foreshadowing.t0_count }}</n-text>
            </div>
            <div class="stat-row">
              <n-text depth="3">延迟队列</n-text>
              <n-text strong>{{ health.foreshadowing.deferred_count }}</n-text>
            </div>
            <div class="stat-row">
              <n-text depth="3">即将到期（3 章内）</n-text>
              <n-text strong>{{ health.foreshadowing.upcoming_window }}</n-text>
            </div>
          </n-space>
        </n-card>

        <!-- 叙事债务 -->
        <n-card title="叙事债务" size="small" :bordered="false" style="margin-bottom: 12px">
          <template #header-extra>
            <n-tag :type="health.narrative_debts.overdue > 0 ? 'error' : 'success'" size="small">
              {{ health.narrative_debts.overdue }} 逾期
            </n-tag>
          </template>
          <n-space :size="8" vertical>
            <n-space :size="4">
              <n-tag type="warning" size="small">活跃 {{ health.narrative_debts.active }}</n-tag>
              <n-tag type="error" size="small">逾期 {{ health.narrative_debts.overdue }}</n-tag>
              <n-tag type="success" size="small">已解决 {{ health.narrative_debts.resolved }}</n-tag>
            </n-space>
            <div v-if="Object.keys(health.narrative_debts.by_type).length">
              <n-text depth="3" style="font-size: 12px">按类型：</n-text>
              <n-space :size="4" style="margin-top: 4px">
                <n-tag v-for="(count, type) in health.narrative_debts.by_type" :key="type" size="small">
                  {{ debtTypeLabel(type) }} {{ count }}
                </n-tag>
              </n-space>
            </div>
          </n-space>
        </n-card>

        <!-- 张力曲线 -->
        <n-card title="张力曲线" size="small" :bordered="false" style="margin-bottom: 12px">
          <div v-if="health.tension_curve.length >= 2" ref="chartRef" style="height: 200px" />
          <n-empty v-else description="至少需要 2 章数据" size="small" />
        </n-card>

        <!-- 道具生命周期 -->
        <n-card title="道具状态" size="small" :bordered="false" style="margin-bottom: 12px">
          <template #header-extra>
            <n-tag v-if="health.props.stale_count > 0" type="warning" size="small">
              {{ health.props.stale_count }} 僵尸道具
            </n-tag>
          </template>
          <n-space :size="4" vertical>
            <div class="stat-row">
              <n-text depth="3">总计</n-text>
              <n-text strong>{{ health.props.total }}</n-text>
            </div>
            <n-space :size="4">
              <n-tag v-for="(count, state) in health.props.by_state" :key="state" size="small" :type="propStateType(state)">
                {{ state }} {{ count }}
              </n-tag>
            </n-space>
          </n-space>
        </n-card>

        <!-- 声纹漂移 -->
        <n-card title="声纹漂移" size="small" :bordered="false">
          <n-space :size="8" vertical>
            <div class="stat-row">
              <n-text depth="3">最新漂移分</n-text>
              <n-text strong :type="health.voice_drift.alert ? 'error' : 'default'">
                {{ health.voice_drift.latest_score.toFixed(2) }}
              </n-text>
            </div>
            <n-tag :type="health.voice_drift.alert ? 'error' : 'success'" size="small">
              {{ health.voice_drift.alert ? '漂移告警' : '风格稳定' }}
            </n-tag>
          </n-space>
        </n-card>
      </div>

      <div v-else-if="!loading" style="padding: 40px; text-align: center">
        <n-empty description="暂无数据" />
      </div>
    </n-spin>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, nextTick } from 'vue'
import { useNarrativeHealthStore } from '../../stores/narrativeHealthStore'
import type { EChartsCoreOption } from 'echarts/core'

const props = defineProps<{
  novelId: string
  visible: boolean
}>()

const store = useNarrativeHealthStore()
const chartRef = ref<HTMLElement | null>(null)
let chartInstance: any = null

const health = computed(() => store.data)
const loading = computed(() => store.loading)
const error = computed(() => store.error)

const scoreColor = computed(() => {
  const s = health.value?.health_score ?? 0
  if (s >= 80) return '#10b981'
  if (s >= 60) return '#f59e0b'
  return '#ef4444'
})

const scoreRailColor = computed(() => {
  return 'rgba(0,0,0,0.06)'
})

const scoreLabel = computed(() => {
  const s = health.value?.health_score ?? 0
  if (s >= 80) return '叙事状态良好'
  if (s >= 60) return '需要关注'
  return '存在风险'
})

function debtTypeLabel(type: string): string {
  const map: Record<string, string> = {
    foreshadowing: '伏笔',
    causal_chain: '因果链',
    storyline: '故事线',
    character_arc: '角色弧',
  }
  return map[type] || type
}

function propStateType(state: string): string {
  const map: Record<string, string> = {
    DORMANT: 'default',
    INTRODUCED: 'info',
    ACTIVE: 'success',
    DAMAGED: 'warning',
    RESOLVED: 'default',
  }
  return (map[state] || 'default') as any
}

function renderChart() {
  if (!chartRef.value || !health.value?.tension_curve.length) return
  const data = health.value.tension_curve

  // 按需引入 echarts 核心
  import('echarts/core').then(({ init: echartsInit }) => {
    if (chartInstance) chartInstance.dispose()
    chartInstance = echartsInit(chartRef.value)
    const option: EChartsCoreOption = {
      tooltip: { trigger: 'axis' },
      legend: { data: ['综合', '情节', '情感', '节奏'], bottom: 0, textStyle: { fontSize: 11 } },
      grid: { top: 10, bottom: 30, left: 35, right: 10 },
      xAxis: {
        type: 'category',
        data: data.map(d => `Ch${d.chapter}`),
        axisLabel: { fontSize: 10 },
      },
      yAxis: { type: 'value', min: 0, max: 100, axisLabel: { fontSize: 10 } },
      series: [
        { name: '综合', type: 'line', data: data.map(d => d.composite), smooth: true, lineStyle: { width: 2 } },
        { name: '情节', type: 'line', data: data.map(d => d.plot), smooth: true, lineStyle: { width: 1, type: 'dashed' } },
        { name: '情感', type: 'line', data: data.map(d => d.emotional), smooth: true, lineStyle: { width: 1, type: 'dashed' } },
        { name: '节奏', type: 'line', data: data.map(d => d.pacing), smooth: true, lineStyle: { width: 1, type: 'dashed' } },
      ],
    }
    chartInstance.setOption(option)
  })
}

// 面板可见时加载数据
watch(() => props.visible, async (v) => {
  if (v && props.novelId) {
    await store.loadHealth(props.novelId)
    await nextTick()
    renderChart()
  }
})

onMounted(async () => {
  if (props.visible && props.novelId) {
    await store.loadHealth(props.novelId)
    await nextTick()
    renderChart()
  }
})
</script>

<style scoped>
.narrative-health-panel {
  padding: 12px;
}
.health-content {
  display: flex;
  flex-direction: column;
  gap: 0;
}
.score-section {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 16px 0 12px;
}
.stat-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
