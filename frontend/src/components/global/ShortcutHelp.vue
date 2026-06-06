<template>
  <n-modal v-model:show="visible" preset="card" title="⌨️ 快捷键" style="max-width:480px" :mask-closable="true">
    <n-table :single-line="true" size="small">
      <thead><tr><th>快捷键</th><th>功能</th></tr></thead>
      <tbody>
        <tr v-for="s of shortcuts" :key="s.key">
          <td><n-tag :bordered="false" size="small" type="info">{{ s.key }}</n-tag></td>
          <td>{{ s.desc }}</td>
        </tr>
      </tbody>
    </n-table>
  </n-modal>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { NModal, NTag, NTable } from 'naive-ui'

const visible = ref(false)

defineExpose({ open: () => visible.value = true })

const shortcuts = [
  { key: 'Ctrl+Shift+F', desc: '禅模式（全屏写作）' },
  { key: 'Ctrl+S', desc: '保存当前章节' },
  { key: 'Ctrl+K', desc: '全局搜索' },
  { key: 'Ctrl+/', desc: '快捷键帮助' },
  { key: '/', desc: '斜杠命令（编辑器内）' },
  { key: 'Tab', desc: '接受 AI 内联建议' },
  { key: 'Escape', desc: '退出禅模式 / 取消 AI 建议' },
  { key: 'F11', desc: '浏览器全屏' },
]

function onKeydown(e: KeyboardEvent) {
  if ((e.ctrlKey || e.metaKey) && e.key === '/') {
    e.preventDefault()
    visible.value = !visible.value
  }
  if (e.key === '?' && !e.ctrlKey && !e.metaKey && !e.altKey && document.activeElement?.tagName !== 'INPUT' && document.activeElement?.tagName !== 'TEXTAREA') {
    e.preventDefault()
    visible.value = !visible.value
  }
}

onMounted(() => window.addEventListener('keydown', onKeydown))
onUnmounted(() => window.removeEventListener('keydown', onKeydown))
</script>
