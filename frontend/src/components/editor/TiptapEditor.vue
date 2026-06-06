<template>
  <div class="tiptap-editor" :class="{ 'is-focused': isFocused }">
    <!-- 工具栏 -->
    <div class="tiptap-toolbar" v-if="editor">
      <n-space :size="2" align="center">
        <n-button
          size="tiny" quaternary
          :type="editor.isActive('bold') ? 'primary' : 'default'"
          @click="editor.chain().focus().toggleBold().run()"
          :disabled="!editor.can().chain().focus().toggleBold().run()"
        >
          <template #icon><b>B</b></template>
        </n-button>
        <n-button
          size="tiny" quaternary
          :type="editor.isActive('italic') ? 'primary' : 'default'"
          @click="editor.chain().focus().toggleItalic().run()"
        >
          <template #icon><i>I</i></template>
        </n-button>
        <n-button
          size="tiny" quaternary
          :type="editor.isActive('underline') ? 'primary' : 'default'"
          @click="editor.chain().focus().toggleUnderline().run()"
        >
          <template #icon><u>U</u></template>
        </n-button>
        <n-button
          size="tiny" quaternary
          :type="editor.isActive('strike') ? 'primary' : 'default'"
          @click="editor.chain().focus().toggleStrike().run()"
        >
          <template #icon><s>S</s></template>
        </n-button>
        <n-divider vertical style="margin: 0 4px" />
        <n-button
          size="tiny" quaternary
          :type="editor.isActive('heading', { level: 2 }) ? 'primary' : 'default'"
          @click="editor.chain().focus().toggleHeading({ level: 2 }).run()"
        >
          H2
        </n-button>
        <n-button
          size="tiny" quaternary
          :type="editor.isActive('heading', { level: 3 }) ? 'primary' : 'default'"
          @click="editor.chain().focus().toggleHeading({ level: 3 }).run()"
        >
          H3
        </n-button>
        <n-divider vertical style="margin: 0 4px" />
        <n-button
          size="tiny" quaternary
          :type="editor.isActive('bulletList') ? 'primary' : 'default'"
          @click="editor.chain().focus().toggleBulletList().run()"
        >
          • 列表
        </n-button>
        <n-button
          size="tiny" quaternary
          :type="editor.isActive('blockquote') ? 'primary' : 'default'"
          @click="editor.chain().focus().toggleBlockquote().run()"
        >
          引用
        </n-button>
        <n-divider vertical style="margin: 0 4px" />
        <n-button
          size="tiny" quaternary
          @click="editor.chain().focus().setHorizontalRule().run()"
        >
          — 分隔
        </n-button>
        <n-button
          size="tiny" quaternary
          @click="editor.chain().focus().undo().run()"
          :disabled="!editor.can().undo()"
        >
          ↩
        </n-button>
        <n-button
          size="tiny" quaternary
          @click="editor.chain().focus().redo().run()"
          :disabled="!editor.can().redo()"
        >
          ↪
        </n-button>
        <n-divider vertical style="margin: 0 4px" />
        <n-button size="tiny" quaternary @click="formatChapter" title="一键格式化">📐</n-button>
        <n-button size="tiny" quaternary @click="toggleFocus" title="禅模式 (Ctrl+Shift+F)">🧘</n-button>
      </n-space>
    </div>

    <!-- 编辑器内容 -->
    <div style="position: relative">
      <editor-content :editor="editor" class="tiptap-content" />
      <AIWritingAssist ref="aiAssistRef" :editor="editor ?? null" />
      <SlashCommandMenu :visible="slashOpen" :query="slashQuery" @select="onSlashSelect" @close="slashOpen = false" />
      <!-- Ghost text indicator -->
      <div v-if="aiSuggestion" class="ai-ghost-badge">
        AI 建议就绪 · Tab 接受
      </div>
    </div>

    <!-- AI Context Panel -->
    <n-drawer v-model:show="aiPanelOpen" :width="320" placement="right">
      <n-drawer-content>
        <AIContextPanel :selected-text="aiSelectedText" @apply="applyAIText" @close="aiPanelOpen = false" />
      </n-drawer-content>
    </n-drawer>

    <!-- 底部状态栏 -->
    <div class="tiptap-footer">
      <n-space :size="8" align="center">
        <n-text depth="3" style="font-size: 12px">{{ characterCount }} 字</n-text>
        <n-divider vertical />
        <n-text depth="3" style="font-size: 12px">{{ wordCount }} 词</n-text>
      </n-space>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onBeforeUnmount, computed, onMounted, onUnmounted } from 'vue'
import { useEditor, EditorContent } from '@tiptap/vue-3'
import StarterKit from '@tiptap/starter-kit'
import Placeholder from '@tiptap/extension-placeholder'
import Highlight from '@tiptap/extension-highlight'
import Underline from '@tiptap/extension-underline'
import CharacterCount from '@tiptap/extension-character-count'
import AIWritingAssist from './AIWritingAssist.vue'
import AIContextPanel from './AIContextPanel.vue'
import SlashCommandMenu, { type SlashCommand } from './SlashCommandMenu.vue'
import { useFocusMode } from '@/composables/useFocusMode'
import { useAICompletion } from '@/composables/useAICompletion'

const props = defineProps<{
  modelValue: string
  placeholder?: string
  editable?: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string]
  'save': []
}>()

const { active: focusActive, toggle: toggleFocus, exit: exitFocus } = useFocusMode()
const { suggestion: aiSuggestion, request: requestAI, accept: acceptAI, dismiss: dismissAI } = useAICompletion()

const isFocused = ref(false)
const aiAssistRef = ref<any>(null)

const slashOpen = ref(false)
const slashQuery = ref('')
const aiPanelOpen = ref(false)
const aiSelectedText = ref('')
const aiSelectedRange = ref<{ from: number; to: number } | null>(null)

const editor = useEditor({
  content: props.modelValue || '',
  editable: props.editable !== false,
  extensions: [
    StarterKit.configure({
      heading: { levels: [2, 3] },
    }),
    Placeholder.configure({
      placeholder: props.placeholder || '开始写作…\n\nCtrl+S 保存 · 自动保存约 30 秒',
    }),
    Highlight,
    Underline,
    CharacterCount,
  ],
  editorProps: {
    attributes: {
      class: 'tiptap-prose',
    },
    handleKeyDown: (_view, event) => {
      // Ctrl+S 保存
      if ((event.ctrlKey || event.metaKey) && event.key === 's') {
        event.preventDefault()
        emit('save')
        return true
      }
      return false
    },
  },
  onUpdate: ({ editor: e }) => {
    emit('update:modelValue', e.getText())
  },
  onFocus: () => { isFocused.value = true },
  onBlur: () => { isFocused.value = false },
  onSelectionUpdate: () => {
    aiAssistRef.value?.onSelectionUpdate()
  },
})

// 外部内容变化时同步到编辑器
watch(() => props.modelValue, (newVal) => {
  if (!editor.value) return
  const current = editor.value.getText()
  if (newVal !== current) {
    // 避免光标跳动：仅在内容确实不同时更新
    editor.value.commands.setContent(newVal || '', { emitUpdate: false })
  }
})

// 可编辑状态变化
watch(() => props.editable, (val) => {
  editor.value?.setEditable(val !== false)
})

const characterCount = computed(() => {
  if (!editor.value) return 0
  return editor.value.storage.characterCount?.characters?.() ?? editor.value.getText().length
})

const wordCount = computed(() => {
  if (!editor.value) return 0
  const text = editor.value.getText().trim()
  if (!text) return 0
  const chinese = text.match(/[一-鿿]/g)?.length ?? 0
  const english = text.replace(/[一-鿿]/g, '').trim().split(/\s+/).filter(Boolean).length
  return chinese + english
})

// ── Slash command handling ──
function onSlashKeydown(e: KeyboardEvent) {
  if (!slashOpen.value) return
  if (e.key === '/') { e.preventDefault(); slashOpen.value = false; return }
}
function onSlashSelect(cmd: SlashCommand) {
  slashOpen.value = false
  if (!editor.value) return
  editor.value.chain().focus()
  switch (cmd.action) {
    case 'heading': editor.value.commands.toggleHeading({ level: 1 }); break
    case 'paragraph': editor.value.commands.setParagraph(); break
    case 'divider': editor.value.commands.setHorizontalRule(); break
    case 'scene-break': editor.value.commands.insertContent('<p style="text-align:center">* * *</p>'); break
    case 'pov-switch': editor.value.commands.insertContent('<span class="pov-tag pov-tag--protagonist">👁 视角切换</span>'); break
    case 'time-jump': editor.value.commands.insertContent('<p><em>—— 片刻之后 ——</em></p>'); break
    case 'flashback': editor.value.commands.insertContent('<blockquote><p>（回忆）</p></blockquote>'); break
    case 'ai-continue': requestAI(editor.value.getText().slice(-500)); break
    case 'ai-rewrite': openAIPanel(); break
    case 'ai-expand': openAIPanel(); break
    case 'ai-shorten': openAIPanel(); break
    case 'ai-tone': openAIPanel(); break
  }
}

// ── AI Panel ──
function openAIPanel() {
  if (!editor.value) return
  const { from, to } = editor.value.state.selection
  const text = editor.value.state.doc.textBetween(from, to)
  if (text) {
    aiSelectedText.value = text
    aiSelectedRange.value = { from, to }
    aiPanelOpen.value = true
  }
}
function applyAIText(text: string) {
  if (!editor.value || !aiSelectedRange.value) return
  editor.value.chain().focus().setTextSelection(aiSelectedRange.value).deleteSelection().insertContent(text).run()
  aiPanelOpen.value = false
  aiSelectedText.value = ''
  aiSelectedRange.value = null
}

// ── Format chapter ──
function formatChapter() {
  if (!editor.value) return
  const { doc } = editor.value.state
  // Normalize all headings to consistent levels
  doc.descendants((node, pos) => {
    if (node.type.name === 'paragraph' && !node.textContent.trim()) {
      // Remove empty paragraphs
      editor.value?.chain().focus().setTextSelection({ from: pos, to: pos + node.nodeSize }).deleteSelection().run()
    }
  })
  // Set first-line indent on all paragraphs via CSS (no DOM mutation needed for that)
  editor.value.chain().focus().setTextSelection(0).run()
}

// ── Ghost text keyboard handling ──
function onEditorKeydown(view: any, event: KeyboardEvent) {
  if (event.key === 'Tab' && aiSuggestion.value) {
    event.preventDefault()
    const text = acceptAI()
    if (text && editor.value) {
      editor.value.commands.insertContent(text)
    }
    return true
  }
  if (event.key === 'Escape' && aiSuggestion.value) {
    dismissAI()
    return true
  }
  if (event.key === '/') {
    // Only open slash menu at start of line or after space
    const { $from } = view.state.selection
    const textBefore = $from.nodeBefore?.text || ''
    const atLineStart = $from.parentOffset === 0
    const afterSpace = textBefore.endsWith(' ') || textBefore === ''
    if (atLineStart || afterSpace) {
      slashOpen.value = true
      slashQuery.value = ''
    }
  }
  if ((event.ctrlKey || event.metaKey) && event.key === 's') {
    event.preventDefault()
    emit('save')
    return true
  }
  if ((event.ctrlKey || event.metaKey) && event.shiftKey && event.key === 'F') {
    toggleFocus()
    return true
  }
  return false
}

// ── Text change triggers ghost text AI ──
let ghostTextTimer: ReturnType<typeof setTimeout> | null = null
watch(() => editor.value?.getText(), (text) => {
  if (!text || text.length < 20) return
  if (ghostTextTimer) clearTimeout(ghostTextTimer)
  ghostTextTimer = setTimeout(() => {
    requestAI(text.slice(-300))
  }, 2000)
})

onBeforeUnmount(() => {
  editor.value?.destroy()
  if (ghostTextTimer) clearTimeout(ghostTextTimer)
})

// Override editorProps handleKeyDown
if (editor.value) {
  // handleKeyDown is set in options; we need to pass it there
}
</script>

<style scoped>
.tiptap-editor {
  border: 1px solid var(--n-border-color, #e0e0e6);
  border-radius: 6px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  background: var(--n-color, #fff);
}

.tiptap-editor.is-focused {
  border-color: var(--n-primary-color, #667eea);
  box-shadow: 0 0 0 2px rgba(102, 126, 234, 0.15);
}

.tiptap-toolbar {
  padding: 6px 10px;
  border-bottom: 1px solid var(--n-border-color, #e0e0e6);
  background: var(--n-color, #fafafa);
  flex-shrink: 0;
}

.tiptap-content {
  flex: 1;
  min-height: 400px;
  overflow-y: auto;
}

.tiptap-content :deep(.tiptap-prose) {
  outline: none;
  padding: 16px 20px;
  min-height: 400px;
  font-size: 15px;
  line-height: 1.8;
  color: var(--n-text-color, #333);
}

.tiptap-content :deep(.tiptap-prose p) {
  margin: 0 0 0.75em;
  text-indent: 2em;
}

.tiptap-content :deep(.tiptap-prose h2) {
  font-size: 1.3em;
  font-weight: 700;
  margin: 1.5em 0 0.5em;
  text-indent: 0;
}

.tiptap-content :deep(.tiptap-prose h3) {
  font-size: 1.1em;
  font-weight: 600;
  margin: 1.2em 0 0.4em;
  text-indent: 0;
}

.tiptap-content :deep(.tiptap-prose blockquote) {
  border-left: 3px solid var(--n-primary-color, #667eea);
  padding-left: 12px;
  margin: 1em 0;
  color: var(--n-text-color-2, #666);
  font-style: italic;
}

.tiptap-content :deep(.tiptap-prose hr) {
  border: none;
  border-top: 1px solid var(--n-border-color, #ddd);
  margin: 1.5em 0;
}

.tiptap-content :deep(.tiptap-prose ul) {
  padding-left: 1.5em;
  margin: 0.5em 0;
}

.tiptap-content :deep(.tiptap-prose mark) {
  background: #fef08a;
  padding: 1px 2px;
  border-radius: 2px;
}

/* Placeholder */
.tiptap-content :deep(.tiptap-prose p.is-editor-empty:first-child::before) {
  content: attr(data-placeholder);
  float: left;
  color: var(--n-placeholder-color, #aaa);
  pointer-events: none;
  height: 0;
}

.tiptap-footer {
  padding: 4px 12px;
  border-top: 1px solid var(--n-border-color, #e0e0e6);
  background: var(--n-color, #fafafa);
  flex-shrink: 0;
}
</style>
