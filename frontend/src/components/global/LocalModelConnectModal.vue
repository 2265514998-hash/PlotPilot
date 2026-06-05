<template>
  <n-modal
    v-model:show="visible"
    preset="card"
    title="本地 AI"
    :style="{ width: '420px', maxWidth: '92vw' }"
    :bordered="true"
    :mask-closable="true"
    @update:show="handleShowChange"
  >
    <LocalModelConnectPanel
      ref="panelRef"
      @open-llm-console="handleOpenLlmConsole"
      @connected="handleConnected"
    />
  </n-modal>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import LocalModelConnectPanel from './LocalModelConnectPanel.vue'

const visible = ref(false)
const panelRef = ref<InstanceType<typeof LocalModelConnectPanel> | null>(null)

const emit = defineEmits<{
  'open-llm-console': []
  connected: []
}>()

function open() {
  visible.value = true
}

function handleShowChange(show: boolean) {
  visible.value = show
  if (show) {
    void panelRef.value?.connectLocalDirect?.({ quiet: false, force: true })
  }
}

function handleOpenLlmConsole() {
  visible.value = false
  emit('open-llm-console')
}

function handleConnected() {
  emit('connected')
}

defineExpose({ open })
</script>
