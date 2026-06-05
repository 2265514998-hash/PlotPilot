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
      </n-space>
    </div>

    <!-- 编辑器内容 -->
    <div style="position: relative">
      <editor-content :editor="editor" class="tiptap-content" />
      <AIWritingAssist ref="aiAssistRef" :editor="editor" />
    </div>

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
import { ref, watch, onBeforeUnmount, computed } from 'vue'
import { useEditor, EditorContent } from '@tiptap/vue-3'
import StarterKit from '@tiptap/starter-kit'
import Placeholder from '@tiptap/extension-placeholder'
import Highlight from '@tiptap/extension-highlight'
import Underline from '@tiptap/extension-underline'
import CharacterCount from '@tiptap/extension-character-count'
import AIWritingAssist from './AIWritingAssist.vue'

const props = defineProps<{
  modelValue: string
  placeholder?: string
  editable?: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string]
  'save': []
}>()

const isFocused = ref(false)
const aiAssistRef = ref<InstanceType<typeof AIWritingAssist> | null>(null)

const editor = useEditor({
  content: props.modelValue || '',
  editable: props.editable !== false,
  extensions: [
    StarterKit.configure({
      heading: { levels: [2, 3] },
      history: { depth: 100 },
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
    editor.value.commands.setContent(newVal || '', false)
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
  // 中文按字符计，英文按空格分词
  const chinese = text.match(/[一-鿿]/g)?.length ?? 0
  const english = text.replace(/[一-鿿]/g, '').trim().split(/\s+/).filter(Boolean).length
  return chinese + english
})

onBeforeUnmount(() => {
  editor.value?.destroy()
})
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
