<template>
  <div class="chapter-tabs-bar">
    <n-tabs
      v-model:value="activeTabId"
      type="card"
      :closable="true"
      :addable="false"
      size="small"
      @close="closeTab"
      @update:value="switchTab"
    >
      <n-tab-pane
        v-for="tab of tabs"
        :key="tab.id"
        :name="String(tab.id)"
        :tab="tab.label"
      />
    </n-tabs>
    <n-button size="tiny" quaternary @click="toggleSplit" title="分屏编辑">
      {{ splitMode ? '📄' : '📑' }}
    </n-button>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'

interface Tab { id: number; label: string }

interface Props {
  chapters: Array<{ id: number; number: number; title: string }>
  currentChapterId?: number | null
  splitMode?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  currentChapterId: null,
  splitMode: false,
})

const emit = defineEmits<{
  switch: [id: number]
  close: [id: number]
  toggleSplit: []
}>()

const tabs = ref<Tab[]>([])

// 当前章节自动加入标签页
watch(() => props.currentChapterId, (newId) => {
  if (!newId) return
  const exists = tabs.value.find(t => t.id === newId)
  if (!exists) {
    const ch = props.chapters.find(c => c.id === newId)
    tabs.value.push({
      id: newId,
      label: ch ? `Ch.${ch.number} ${ch.title || ''}` : `Ch.${newId}`,
    })
  }
  activeTabId.value = String(newId)
}, { immediate: true })

const activeTabId = ref(String(props.currentChapterId || ''))

function switchTab(name: string) {
  emit('switch', Number(name))
}

function closeTab(name: string) {
  const id = Number(name)
  tabs.value = tabs.value.filter(t => t.id !== id)
  emit('close', id)
  // 切换到第一个剩余标签页
  if (activeTabId.value === name && tabs.value.length > 0) {
    activeTabId.value = String(tabs.value[0].id)
    emit('switch', tabs.value[0].id)
  }
}

function toggleSplit() {
  emit('toggleSplit')
}
</script>

<style scoped>
.chapter-tabs-bar {
  display: flex; align-items: center; gap: 0.25rem;
  border-bottom: 1px solid var(--divider-color, rgba(0,0,0,0.06));
  padding: 0 0.25rem;
}
.chapter-tabs-bar :deep(.n-tabs) { flex: 1; }
.chapter-tabs-bar :deep(.n-tabs-tab) { font-size: 0.75rem; max-width: 140px; }
.chapter-tabs-bar :deep(.n-tabs-tab__label) { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
</style>
