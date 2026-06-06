<template>
  <div class="dashboard-page">
    <header class="dashboard-header">
      <h1>✍️ 写作仪表盘</h1>
      <n-space><n-button size="small" @click="$router.push('/')">← 回到首页</n-button></n-space>
    </header>

    <n-grid :cols="3" :x-gap="16" :y-gap="16" responsive="screen">
      <n-grid-item span="3 m:1">
        <n-card title="今日进度" size="small">
          <div class="stat-ring">
            <n-progress type="circle" :percentage="todayPercent" :color="todayPercent >= 100 ? '#22c55e' : '#3b82f6'" :stroke-width="10" :height="120" />
            <p class="stat-label">{{ todayWords }} / {{ dailyGoal }} 字</p>
          </div>
        </n-card>
      </n-grid-item>

      <n-grid-item span="3 m:1">
        <n-card title="连续写作" size="small">
          <div class="stat-ring">
            <span class="streak-flame">{{ streak > 0 ? '🔥' : '💤' }}</span>
            <p class="stat-number">{{ streak }}</p>
            <p class="stat-label">连续天数</p>
            <n-tag :type="streak >= 7 ? 'success' : streak >= 3 ? 'warning' : 'default'" size="small">
              {{ streakMessage }}
            </n-tag>
          </div>
        </n-card>
      </n-grid-item>

      <n-grid-item span="3 m:1">
        <n-card title="总计" size="small">
          <div class="stat-ring">
            <p class="stat-number">{{ totalWords.toLocaleString() }}</p>
            <p class="stat-label">总字数</p>
            <n-space justify="center" size="small">
              <n-tag size="tiny">{{ totalChapters }} 章</n-tag>
              <n-tag size="tiny">{{ totalBooks }} 部作品</n-tag>
            </n-space>
          </div>
        </n-card>
      </n-grid-item>
    </n-grid>

    <n-card title="近期活动" size="small" style="margin-top:16px">
      <n-timeline v-if="recentActivity.length">
        <n-timeline-item v-for="act of recentActivity" :key="act.time" :type="act.type" :title="act.title" :time="act.time">
          {{ act.desc }}
        </n-timeline-item>
      </n-timeline>
      <div v-else class="empty-state-splash" style="min-height:120px">
        <p>还没有写作活动记录</p>
      </div>
    </n-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { NGrid, NGridItem, NCard, NProgress, NTag, NSpace, NButton, NTimeline, NTimelineItem } from 'naive-ui'
import { apiClient } from '@/api/config'

const todayWords = ref(0)
const dailyGoal = ref(2000)
const todayPercent = ref(0)
const streak = ref(0)
const totalWords = ref(0)
const totalChapters = ref(0)
const totalBooks = ref(0)
const recentActivity = ref<Array<{ type: string; title: string; desc: string; time: string }>>([])

const streakMessage = ref('继续加油！')

onMounted(async () => {
  try {
    const data = await apiClient.get<any>('/stats/global')
    if (data) {
      totalWords.value = data.total_words || 0
      totalChapters.value = data.total_chapters || 0
      totalBooks.value = data.total_books || 0
      todayWords.value = data.today_words || 0
      streak.value = data.streak || 0
      todayPercent.value = Math.min(100, Math.round((todayWords.value / dailyGoal.value) * 100))
    }
    streakMessage.value = streak.value >= 30 ? '传奇！' : streak.value >= 14 ? '太厉害了' : streak.value >= 7 ? '坚持一周了' : streak.value >= 3 ? '势头不错' : '开始吧'
  } catch { /* offline */ }
})
</script>

<style scoped>
.dashboard-page { padding: 1.5rem; min-height: 100vh; background: var(--body-color); }
.dashboard-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem; }
.stat-ring { display: flex; flex-direction: column; align-items: center; gap: 0.5rem; padding: 1rem 0; }
.streak-flame { font-size: 2.5rem; }
.stat-number { font-size: 2rem; font-weight: 700; margin: 0; }
.stat-label { font-size: 0.85rem; color: var(--text-color-muted); margin: 0; }
</style>
