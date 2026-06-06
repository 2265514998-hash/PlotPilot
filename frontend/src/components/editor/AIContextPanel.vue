<template>
  <div class="ai-context-panel">
    <div class="ai-panel-header">
      <span class="ai-panel-title">AI 助手</span>
      <n-button text size="tiny" @click="$emit('close')">✕</n-button>
    </div>

    <div v-if="!selectedText" class="ai-panel-hint">
      选中文本后在此选择操作
    </div>

    <template v-else>
      <div class="ai-preset-grid">
        <n-button
          v-for="preset of presets" :key="preset.id"
          size="small" :type="preset.id === activePreset ? 'primary' : 'default'"
          :disabled="loading"
          @click="runPreset(preset)"
        >
          {{ preset.icon }} {{ preset.label }}
        </n-button>
      </div>

      <n-divider />

      <div v-if="result" class="ai-result">
        <div class="ai-result-text">{{ result }}</div>
        <n-space justify="end" style="margin-top:0.5rem">
          <n-button size="tiny" @click="discard">丢弃</n-button>
          <n-button size="tiny" type="primary" @click="apply">应用</n-button>
        </n-space>
      </div>

      <n-spin v-if="loading" size="small" />
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { NButton, NDivider, NSpace, NSpin } from 'naive-ui'

interface AIPreset { id: string; icon: string; label: string; prompt: string }

const props = defineProps<{ selectedText: string; chapterId?: number; novelId?: string }>()
const emit = defineEmits<{ apply: [text: string]; close: [] }>()

const activePreset = ref<string | null>(null)
const loading = ref(false)
const result = ref('')
let controller: AbortController | null = null

const presets: AIPreset[] = [
  { id: 'rewrite', icon: '🔄', label: '改写', prompt: '请改写以下文本，保持原意，优化表达：' },
  { id: 'expand', icon: '⬍', label: '扩写', prompt: '请扩充以下文本，增加细节和描写：' },
  { id: 'shorten', icon: '⬆', label: '缩写', prompt: '请精简以下文本，保留核心内容：' },
  { id: 'formal', icon: '👔', label: '正式', prompt: '请将以下文本改写为更正式的语气：' },
  { id: 'casual', icon: '💬', label: '轻松', prompt: '请将以下文本改写为更轻松口语化的语气：' },
  { id: 'urgent', icon: '⚡', label: '紧张', prompt: '请将以下文本改写为更有紧迫感和张力的语气：' },
]

async function runPreset(preset: AIPreset) {
  activePreset.value = preset.id
  loading.value = true
  result.value = ''
  if (controller) controller.abort()
  controller = new AbortController()

  try {
    const res = await fetch('/api/v1/ai/assist', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        prompt: preset.prompt,
        text: props.selectedText,
        novel_id: props.novelId,
        chapter_id: props.chapterId,
      }),
      signal: controller.signal,
    })

    if (res.ok && res.body) {
      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buf = ''
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buf += decoder.decode(value, { stream: true })
        const lines = buf.split('\n'); buf = lines.pop() || ''
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try { result.value += JSON.parse(line.slice(6)).text } catch { /* skip */ }
          }
        }
      }
    }
  } catch (e) {
    if ((e as Error).name !== 'AbortError') console.warn('[AIContext]', e)
  } finally { loading.value = false }
}

function apply() {
  if (result.value) emit('apply', result.value)
  result.value = ''
}

function discard() {
  result.value = ''
  activePreset.value = null
}
</script>

<style scoped>
.ai-context-panel { padding: 0.75rem; max-height: 100%; overflow-y: auto; }
.ai-panel-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem; }
.ai-panel-title { font-weight: 600; font-size: 0.875rem; }
.ai-panel-hint { font-size: 0.8rem; color: var(--text-color-muted); text-align: center; padding: 1rem 0; }
.ai-preset-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 0.4rem; }
.ai-result { background: var(--action-color-secondary); border-radius: 8px; padding: 0.6rem; }
.ai-result-text { font-size: 0.85rem; line-height: 1.6; white-space: pre-wrap; }
</style>
