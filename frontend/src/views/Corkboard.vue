<template>
  <div class="corkboard-page">
    <div class="corkboard-header">
      <n-space align="center">
        <n-button text @click="$router.back()">←</n-button>
        <h2 style="margin:0">{{ novelTitle }}</h2>
        <n-tag :bordered="false" size="small">剧情版</n-tag>
      </n-space>
      <n-space>
        <n-select v-model:value="filterPov" :options="povOptions" placeholder="POV 过滤" clearable size="small" style="width:140px" />
        <n-button size="small" @click="addSceneCard">+ 添加场景</n-button>
      </n-space>
    </div>

    <div class="corkboard-grid">
      <n-card
        v-for="card of filteredCards" :key="card.id"
        size="small"
        class="card-hover-lift"
        :style="{ borderLeft: `3px solid ${card.color}` }"
        @click="$router.push(`/book/${slug}/chapter/${card.id}`)"
      >
        <template #header>
          <n-space align="center" justify="space-between">
            <n-ellipsis style="max-width:160px">{{ card.title }}</n-ellipsis>
            <n-tag :bordered="false" size="tiny" :color="{ color: card.color, textColor: '#fff' }">
              {{ card.povLabel }}
            </n-tag>
          </n-space>
        </template>
        <n-ellipsis :line-clamp="3" style="font-size:0.8rem;color:var(--text-color-muted)">
          {{ card.summary || '（无摘要）' }}
        </n-ellipsis>
        <template #footer>
          <n-space justify="space-between" style="font-size:0.75rem">
            <span>{{ card.wordCount }} 字</span>
            <span>Ch.{{ card.chapterNumber }}</span>
          </n-space>
        </template>
      </n-card>

      <div v-if="!filteredCards.length" class="empty-state-splash">
        <span style="font-size:3rem">🗂️</span>
        <p>暂无场景卡片</p>
        <n-button size="small" @click="addSceneCard">添加第一张卡片</n-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { NSpace, NButton, NTag, NSelect, NCard, NEllipsis } from 'naive-ui'

interface CorkCard {
  id: number
  title: string
  chapterNumber: number
  wordCount: number
  summary: string
  povLabel: string
  color: string
}

const route = useRoute()
const router = useRouter()
const slug = computed(() => route.params.slug as string)
const novelTitle = ref('')
const filterPov = ref<string | null>(null)
const cards = ref<CorkCard[]>([])

const povOptions = [
  { label: '主角', value: 'protagonist' },
  { label: '对手', value: 'antagonist' },
  { label: '配角', value: 'supporting' },
]

const filteredCards = computed(() => {
  if (!filterPov.value) return cards.value
  return cards.value.filter(c => c.povLabel === povOptions.find(o => o.value === filterPov.value)?.label)
})

function addSceneCard() {
  router.push(`/book/${slug.value}/workbench`)
}

onMounted(async () => {
  try {
    const { apiClient } = await import('@/api/config')
    const data = await apiClient.get<any>(`/novels/${slug.value}`)
    novelTitle.value = data?.title || ''
    if (data?.chapters) {
      cards.value = data.chapters.map((ch: any) => ({
        id: ch.id,
        title: ch.title || `第${ch.number}章`,
        chapterNumber: ch.number,
        wordCount: ch.word_count || ch.wordCount || 0,
        summary: ch.summary || '',
        povLabel: ch.pov_character || '—',
        color: ch.pov_character === '主角' ? '#3b82f6' : ch.pov_character === '对手' ? '#ef4444' : ch.pov_character ? '#f59e0b' : '#9ca3af',
      }))
    }
  } catch { /* fallback */ }
})
</script>

<style scoped>
.corkboard-page { padding: 1rem; min-height: 100vh; background: var(--body-color); }
.corkboard-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem; }
</style>
