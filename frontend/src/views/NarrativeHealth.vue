<template>
  <div class="narrative-health-page">
    <header class="nh-header">
      <n-space align="center">
        <n-button text @click="$router.back()">←</n-button>
        <h2 style="margin:0">📊 叙事健康大屏</h2>
        <n-tag v-if="novelTitle" :bordered="false" size="small">{{ novelTitle }}</n-tag>
      </n-space>
      <n-button size="small" @click="refreshAll">🔄 刷新全部</n-button>
    </header>

    <n-grid :cols="2" :x-gap="12" :y-gap="12" responsive="screen">
      <!-- 结构分类卡片 -->
      <n-grid-item span="2 m:1">
        <n-card title="📐 故事结构" size="small">
          <template #header-extra><n-tag size="tiny" :type="structure.act_phase ? 'success' : 'default'">{{ structure.act_phase || '待分析' }}</n-tag></template>
          <div v-if="structure.story_beat" class="nh-card-body">
            <n-progress type="line" :percentage="Math.round((structure.progress_estimate || 0) * 100)" :indicator-placement="'inside'" />
            <n-space style="margin-top:8px" :size="4">
              <n-tag v-for="t of structure.structure_tags" :key="t" size="tiny" :bordered="false" :type="t.includes('ACT') ? 'info' : 'default'">{{ t }}</n-tag>
            </n-space>
            <p style="font-size:0.8rem;color:var(--text-color-muted);margin-top:4px">{{ structure.beat_label_cn }} · 下一节点：{{ structure.next_milestone || '—' }}</p>
          </div>
          <div v-else class="nh-empty">尚未进行结构分析</div>
        </n-card>
      </n-grid-item>

      <!-- 情感弧线图 -->
      <n-grid-item span="2 m:1">
        <n-card title="💭 角色情感弧线" size="small">
          <div ref="emotionChartRef" style="width:100%;height:200px" />
        </n-card>
      </n-grid-item>

      <!-- 节奏分析 -->
      <n-grid-item span="2 m:1">
        <n-card title="⏱️ 节奏分析" size="small">
          <template #header-extra><n-tag size="tiny" :type="pacing.pace_label === 'fast' ? 'warning' : pacing.pace_label === 'slow' ? 'info' : 'success'">{{ pacingPaceLabel }}</n-tag></template>
          <div class="nh-card-body">
            <div class="nh-metrics-row">
              <div class="nh-metric"><span class="nh-metric-value">{{ pacing.avg_sentence_length }}</span><span class="nh-metric-label">平均句长</span></div>
              <div class="nh-metric"><span class="nh-metric-value">{{ Math.round(pacing.dialogue_ratio * 100) }}%</span><span class="nh-metric-label">对话比例</span></div>
              <div class="nh-metric"><span class="nh-metric-value">{{ pacing.action_verb_density }}</span><span class="nh-metric-label">动作密度</span></div>
              <div class="nh-metric"><span class="nh-metric-value">{{ pacing.paragraph_rhythm_score }}</span><span class="nh-metric-label">节奏得分</span></div>
            </div>
          </div>
        </n-card>
      </n-grid-item>

      <!-- 情节漏洞列表 -->
      <n-grid-item span="2 m:1">
        <n-card title="🔍 情节漏洞" size="small">
          <template #header-extra><n-tag size="tiny" :type="plotHoles.length === 0 ? 'success' : 'error'">{{ plotHoles.length }} 个</n-tag></template>
          <div v-if="plotHoles.length" class="nh-card-body">
            <n-list>
              <n-list-item v-for="hole of plotHoles" :key="hole.id">
                <n-thing :title="hole.description" :title-extra="hole.severity">
                  <template #description>涉及第 {{ hole.chapters_involved?.join('、') }} 章 · {{ hole.suggested_fix }}</template>
                </n-thing>
              </n-list-item>
            </n-list>
          </div>
          <div v-else class="nh-empty">✅ 未发现明显漏洞</div>
        </n-card>
      </n-grid-item>

      <!-- 角色一致性 -->
      <n-grid-item span="2 m:1">
        <n-card title="👤 角色一致性" size="small">
          <template #header-extra><n-tag size="tiny" :type="oocScore > 0.3 ? 'error' : oocScore > 0.1 ? 'warning' : 'success'">OOC {{ Math.round(oocScore * 100) }}%</n-tag></template>
          <n-list v-if="characterViolations.length">
            <n-list-item v-for="(v, i) of characterViolations" :key="i">
              <n-thing :title="`${v.character_name} · ${v.dimensionCn}`">
                <template #description>{{ v.suggestion }}</template>
              </n-thing>
            </n-list-item>
          </n-list>
          <div v-else class="nh-empty">✅ 角色一致性良好</div>
        </n-card>
      </n-grid-item>

      <!-- 主题漂移 -->
      <n-grid-item span="2 m:1">
        <n-card title="🎯 主题漂移" size="small">
          <template #header-extra><n-tag size="tiny" :type="themeDrift.drift_score > 0.5 ? 'error' : 'success'">漂移 {{ Math.round(themeDrift.drift_score * 100) }}%</n-tag></template>
          <div v-if="themeDrift.missing_themes?.length" class="nh-card-body">
            <n-tag v-for="t of themeDrift.missing_themes" :key="t" size="tiny" type="warning" style="margin:2px">{{ t }}</n-tag>
            <p style="font-size:0.8rem;margin-top:4px">{{ themeDrift.suggestion }}</p>
          </div>
          <div v-else class="nh-empty">✅ 主题覆盖完整</div>
        </n-card>
      </n-grid-item>
    </n-grid>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import { NGrid, NGridItem, NCard, NTag, NSpace, NButton, NProgress, NList, NListItem, NThing } from 'naive-ui'
import { apiClient } from '@/api/config'
import { init as echartsInit, type ECharts } from 'echarts/core'

const route = useRoute()
const slug = ref((route.params.slug as string) || '')
const novelTitle = ref('')

const structure = ref<Record<string, any>>({})
const pacing = ref<Record<string, any>>({ avg_sentence_length: 0, dialogue_ratio: 0, action_verb_density: 0, paragraph_rhythm_score: 0, pace_label: 'unknown' })
const plotHoles = ref<any[]>([])
const characterViolations = ref<any[]>([])
const oocScore = ref(0)
const themeDrift = ref<Record<string, any>>({ drift_score: 0, missing_themes: [], suggestion: '' })

let emotionChart: ECharts | null = null
const emotionChartRef = ref<HTMLElement | null>(null)

const pacingPaceLabel: Record<string, string> = { fast: '快速', slow: '慢速', dialogue_heavy: '对话为主', balanced: '均衡', unknown: '—' }

async function refreshAll() {
  try {
    const res = await apiClient.get<any>(`/novels/${slug.value}/narrative-health`)
    const d = res || {}
    structure.value = d.structure || {}
    pacing.value = d.pacing || pacing.value
    plotHoles.value = d.plot_holes || []
    characterViolations.value = d.violations || []
    oocScore.value = d.ooc_score || 0
    themeDrift.value = d.theme_drift || themeDrift.value
    await renderEmotionChart(d.emotions || [])
  } catch { /* offline */ }
}

async function renderEmotionChart(emotions: any[]) {
  await nextTick()
  if (!emotionChartRef.value) return
  if (!emotionChart) {
    const { init, LineChart } = await import('echarts/charts')
    const { GridComponent, TooltipComponent } = await import('echarts/components')
    const { CanvasRenderer } = await import('echarts/renderers')
    import('echarts/core').then(m => { m.use([LineChart, GridComponent, TooltipComponent, CanvasRenderer]) })
    emotionChart = init(emotionChartRef.value)
  }

  if (!emotions.length) {
    emotionChart.setOption({
      title: { text: '暂无情感数据', left: 'center', top: 'center', textStyle: { fontSize: 14, color: '#999' } },
    })
    return
  }

  const chars = [...new Set(emotions.map((e: any) => e.character_name))]
  const chapters = [...new Set(emotions.map((e: any) => e.chapter_number))].sort((a: any,b: any) => a-b)
  const series = chars.map((name: any) => ({
    name, type: 'line', smooth: true, symbol: 'circle', symbolSize: 6,
    data: chapters.map((ch: any) => {
      const pt = emotions.find((e: any) => e.character_name === name && e.chapter_number === ch)
      return pt ? pt.intensity ?? 5 : null
    }),
  }))

  emotionChart.setOption({
    tooltip: { trigger: 'axis' },
    legend: { bottom: 0, data: chars },
    grid: { top: 10, right: 10, bottom: 30, left: 40 },
    xAxis: { type: 'category', data: chapters.map((c: any) => `Ch${c}`), axisLabel: { fontSize: 10 } },
    yAxis: { type: 'value', min: 0, max: 10, axisLabel: { fontSize: 10 } },
    series,
  })
}

onMounted(refreshAll)
</script>

<style scoped>
.narrative-health-page { padding: 1rem; min-height: 100vh; background: var(--body-color); }
.nh-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; }
.nh-card-body { padding: 0.5rem 0; }
.nh-empty { text-align: center; padding: 1.5rem; color: var(--text-color-muted); font-size: 0.85rem; }
.nh-metrics-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 0.5rem; text-align: center; }
.nh-metric-value { display: block; font-size: 1.5rem; font-weight: 700; }
.nh-metric-label { font-size: 0.75rem; color: var(--text-color-muted); }
</style>
