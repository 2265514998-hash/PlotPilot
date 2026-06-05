<template>
  <div v-if="visible" class="ai-floating-menu" :style="menuStyle">
    <n-space :size="4" align="center">
      <n-button size="tiny" secondary type="primary" @click="handleAction('rewrite')" :loading="loading">
        🔄 改写
      </n-button>
      <n-button size="tiny" secondary type="info" @click="handleAction('expand')" :loading="loading">
        📝 扩写
      </n-button>
      <n-button size="tiny" secondary type="warning" @click="handleAction('shorten')" :loading="loading">
        ✂️ 缩写
      </n-button>
      <n-button size="tiny" secondary @click="handleAction('dialogue')" :loading="loading">
        💬 对白化
      </n-button>
      <n-button size="tiny" quaternary type="error" @click="close" :disabled="loading">
        ✕
      </n-button>
    </n-space>
    <!-- AI 结果预览 -->
    <div v-if="aiResult" class="ai-result">
      <n-divider style="margin: 8px 0" />
      <div class="ai-result-text">{{ aiResult }}</div>
      <n-space :size="4" style="margin-top: 8px">
        <n-button size="tiny" type="primary" @click="applyResult">应用</n-button>
        <n-button size="tiny" @click="aiResult = ''">取消</n-button>
      </n-space>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onBeforeUnmount } from 'vue'
import type { Editor } from '@tiptap/vue-3'

const props = defineProps<{
  editor: Editor | null
}>()

const visible = ref(false)
const loading = ref(false)
const aiResult = ref('')
const selectedText = ref('')
const menuPos = ref({ top: 0, left: 0 })

const menuStyle = computed(() => ({
  top: `${menuPos.value.top}px`,
  left: `${menuPos.value.left}px`,
}))

let hideTimer: number | null = null

function showMenu() {
  if (!props.editor) return
  const { from, to } = props.editor.state.selection
  const text = props.editor.state.doc.textBetween(from, to, ' ')
  if (!text.trim()) {
    visible.value = false
    return
  }
  selectedText.value = text

  // 计算菜单位置（基于选区）
  const coords = props.editor.view.domAtPos(from)
  const node = coords.node as HTMLElement
  const rect = node.parentElement?.getBoundingClientRect() || node.getBoundingClientRect()
  const editorRect = props.editor.view.dom.getBoundingClientRect()

  menuPos.value = {
    top: rect.top - editorRect.top - 40,
    left: Math.max(10, (rect.left + rect.right) / 2 - editorRect.left - 120),
  }
  visible.value = true
  aiResult.value = ''
}

function close() {
  visible.value = false
  aiResult.value = ''
}

async function handleAction(action: 'rewrite' | 'expand' | 'shorten' | 'dialogue') {
  if (!selectedText.value || loading.value) return
  loading.value = true
  aiResult.value = ''

  try {
    const actionLabels: Record<string, string> = {
      rewrite: '改写以下文本，保持原意但换一种表达方式',
      expand: '扩写以下文本，增加细节和描写，使内容更丰富',
      shorten: '缩写以下文本，保留核心信息，去除冗余',
      dialogue: '将以下叙述转换为角色对白形式，保持信息完整',
    }

    const prompt = actionLabels[action]
    const response = await fetch('/api/v1/llm-control/models', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        provider: 'openai',
        api_key: '',
        base_url: '',
      }),
    })

    // 使用简化的 LLM 调用（通过现有工作台的 AI 能力）
    // 这里先用 placeholder，实际接入时替换为真实 LLM 调用
    aiResult.value = `[${action === 'rewrite' ? '改写' : action === 'expand' ? '扩写' : action === 'shorten' ? '缩写' : '对白化'}结果将在此显示]\n\n原文：${selectedText.value.slice(0, 50)}...`
  } catch (e) {
    aiResult.value = `AI 处理失败: ${e instanceof Error ? e.message : '未知错误'}`
  } finally {
    loading.value = false
  }
}

function applyResult() {
  if (!props.editor || !aiResult.value) return
  const { from, to } = props.editor.state.selection
  props.editor.chain().focus().deleteRange({ from, to }).insertContentAt(from, aiResult.value).run()
  close()
}

// 监听选区变化
function onSelectionUpdate() {
  if (hideTimer) clearTimeout(hideTimer)
  hideTimer = window.setTimeout(() => {
    if (props.editor) {
      const { empty } = props.editor.state.selection
      if (!empty) {
        showMenu()
      } else {
        visible.value = false
      }
    }
  }, 200)
}

// 由父组件注册 editor.on('selectionUpdate', onSelectionUpdate)
defineExpose({ onSelectionUpdate, close })

onBeforeUnmount(() => {
  if (hideTimer) clearTimeout(hideTimer)
})
</script>

<style scoped>
.ai-floating-menu {
  position: absolute;
  z-index: 100;
  background: var(--n-color, #fff);
  border: 1px solid var(--n-border-color, #e0e0e6);
  border-radius: 8px;
  padding: 8px 10px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.12);
  max-width: 500px;
  min-width: 300px;
}

.ai-result {
  font-size: 13px;
  line-height: 1.6;
  color: var(--n-text-color, #333);
  max-height: 200px;
  overflow-y: auto;
}

.ai-result-text {
  white-space: pre-wrap;
  background: var(--n-color-embedded, #f5f5f5);
  padding: 8px;
  border-radius: 4px;
}
</style>
