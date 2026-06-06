<template>
  <div class="coach-panel">
    <div class="coach-header">
      <span class="coach-title">🧑‍🏫 写作教练</span>
      <n-button text size="tiny" @click="$emit('close')">✕</n-button>
    </div>

    <n-spin :show="loading" size="small">
      <div v-if="encouragement" class="coach-encourage">{{ encouragement }}</div>

      <div v-if="suggestions.length" class="coach-suggestions">
        <div v-for="(s, i) of suggestions" :key="i" class="coach-card" :style="{ borderLeft: `3px solid ${tagColor(s.tag)}` }">
          <div class="coach-card-tag">
            <n-tag size="tiny" :bordered="false" :color="{ color: tagColor(s.tag), textColor: '#fff' }">{{ tagLabel(s.tag) }}</n-tag>
          </div>
          <p class="coach-card-question">{{ s.question }}</p>
          <p v-if="s.context_hint" class="coach-card-hint">📍 {{ s.context_hint }}</p>
          <n-space v-if="s.actionable" justify="end" size="small">
            <n-button size="tiny" quaternary @click="dismiss(i)">忽略</n-button>
            <n-button size="tiny" type="primary" @click="applyAction(s)">采纳</n-button>
          </n-space>
        </div>
      </div>

      <div v-if="!loading && !suggestions.length && !encouragement" class="coach-empty">
        写作教练将在此提供主动建议
      </div>
    </n-spin>

    <n-divider style="margin:8px 0" />
    <n-button size="small" block @click="requestCoach" :loading="loading">🔄 请求教练建议</n-button>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { NSpace, NButton, NTag, NSpin, NDivider } from 'naive-ui'
import { apiClient } from '@/api/config'

interface Suggestion {
  priority: number
  tag: string
  question: string
  context_hint?: string
  actionable: boolean
}

const props = defineProps<{ chapterContent: string; chapterNumber?: number }>()
const emit = defineEmits<{ apply: [s: Suggestion]; close: [] }>()

const loading = ref(false)
const encouragement = ref('')
const suggestions = ref<Suggestion[]>([])

function tagLabel(tag: string) {
  const m: Record<string, string> = { sensory: '感官', pacing: '节奏', character: '角色', conflict: '冲突', show_dont_tell: '展示vs告知' }
  return m[tag] || tag
}
function tagColor(tag: string) {
  const m: Record<string, string> = { sensory: '#8b5cf6', pacing: '#3b82f6', character: '#f59e0b', conflict: '#ef4444', show_dont_tell: '#10b981' }
  return m[tag] || '#6b7280'
}

async function requestCoach() {
  loading.value = true
  encouragement.value = ''
  suggestions.value = []
  try {
    const res = await apiClient.post<any>('/ai/coach', {
      chapter_content: props.chapterContent?.slice(0, 6000) || '',
      chapter_number: props.chapterNumber || 0,
    })
    encouragement.value = res?.encouragement || ''
    suggestions.value = res?.suggestions || []
  } catch { /* fallback */ } finally { loading.value = false }
}

function dismiss(i: number) { suggestions.value.splice(i, 1) }
function applyAction(s: Suggestion) { emit('apply', s) }
</script>

<style scoped>
.coach-panel { padding: 0.75rem; }
.coach-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem; }
.coach-title { font-weight: 600; font-size: 0.9rem; }
.coach-encourage { font-size: 0.85rem; color: var(--text-color-muted); margin-bottom: 0.5rem; padding: 0.4rem 0.6rem; background: var(--action-color-secondary); border-radius: 8px; }
.coach-suggestions { display: flex; flex-direction: column; gap: 0.5rem; }
.coach-card { padding: 0.5rem 0.75rem; border-radius: 8px; background: var(--body-color); }
.coach-card-tag { margin-bottom: 0.3rem; }
.coach-card-question { font-size: 0.85rem; line-height: 1.5; margin: 0.3rem 0; }
.coach-card-hint { font-size: 0.75rem; color: var(--text-color-muted); }
.coach-empty { text-align: center; padding: 1rem; font-size: 0.85rem; color: var(--text-color-muted); }
</style>
