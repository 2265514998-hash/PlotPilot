<template>
  <div class="local-model-connect">
    <n-alert
      :type="statusType"
      :show-icon="false"
      :bordered="false"
      class="status-alert"
    >
      {{ statusText }}
    </n-alert>

    <n-button
      type="primary"
      block
      size="large"
      :loading="modelProbing || !!connectingId"
      @click="handleDirectConnect"
    >
      {{ lastConnectedLabel ? '重新连接本地 AI' : '连接本地 AI' }}
    </n-button>

    <n-button quaternary block size="small" @click="$emit('open-llm-console')">
      打开 AI 控制台查看配置
    </n-button>

    <n-collapse v-if="showDetails" class="more-collapse" arrow-placement="right">
      <n-collapse-item title="连接详情" name="detail">
        <div v-if="llmServices.length" class="service-block">
          <div
            v-for="s in llmServices"
            :key="s.id"
            class="service-item"
          >
            <span>{{ s.label }}</span>
            <n-tag size="small" :type="s.reachable ? 'success' : 'default'">
              {{ s.reachable ? (s.suggested_model || '可达') : '未连接' }}
            </n-tag>
          </div>
        </div>
        <n-checkbox
          :checked="autoConnectOnDetect"
          style="margin-top: 10px"
          @update:checked="onAutoConnectChange"
        >
          每次打开 PlotPilot 自动连接
        </n-checkbox>
      </n-collapse-item>
      <n-collapse-item title="手动指定地址" name="manual">
        <n-space vertical :size="8">
          <n-input v-model:value="manualBaseUrl" size="small" placeholder="http://127.0.0.1:11434/v1" />
          <n-input
            v-model:value="manualModel"
            size="small"
            :placeholder="manualModelPlaceholder"
          />
          <n-button size="small" block :loading="!!connectingId" @click="handleManualConnect">
            按地址连接
          </n-button>
        </n-space>
      </n-collapse-item>
    </n-collapse>

    <n-button
      v-else
      text
      size="tiny"
      type="primary"
      @click="showDetails = true"
    >
      显示详情 / 手动地址
    </n-button>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { storeToRefs } from 'pinia'
import {
  pickPrimaryLlmService,
  resolveAutoModelForService,
  useLocalModelStore,
} from '@/stores/localModelStore'

const emit = defineEmits<{
  'open-llm-console': []
  connected: []
}>()

const store = useLocalModelStore()
const {
  modelProbing,
  modelProbeSummary,
  autoConnectOnDetect,
  lastConnectedLabel,
  connectingId,
  modelServices,
} = storeToRefs(store)

const showDetails = ref(false)
const manualBaseUrl = ref('http://127.0.0.1:11434/v1')
const manualModel = ref('')

const llmServices = computed(() =>
  (modelServices.value ?? []).filter((s) => s.kind === 'llm'),
)

const statusType = computed(() => {
  if (lastConnectedLabel.value) return 'success'
  if (modelProbing.value) return 'info'
  return 'warning'
})

const autoModelHint = computed(() => {
  const primary = pickPrimaryLlmService(modelServices.value ?? [])
  if (!primary) return ''
  const name = resolveAutoModelForService(primary)
  return name ? `将自动使用模型：${name}` : ''
})

const manualModelPlaceholder = computed(() => {
  const primary = pickPrimaryLlmService(modelServices.value ?? [])
  const name = primary ? resolveAutoModelForService(primary) : ''
  return name ? `留空则自动：${name}` : '留空则自动匹配本机模型'
})

const statusText = computed(() => {
  if (modelProbing.value) return '正在连接本机 AI…'
  if (lastConnectedLabel.value) return `已连接：${lastConnectedLabel.value}`
  if (autoModelHint.value) return autoModelHint.value
  return modelProbeSummary.value || '将自动探测并匹配 Ollama / LM Studio 模型'
})

function onAutoConnectChange(checked: boolean) {
  store.setAutoConnect(checked)
}

async function handleDirectConnect() {
  const ok = await store.connectLocalDirect({ quiet: false, force: true })
  if (ok) emit('connected')
  else showDetails.value = true
}

async function handleManualConnect() {
  const ok = await store.connectManual(
    'ollama',
    manualBaseUrl.value.trim(),
    manualModel.value.trim(),
    false,
  )
  if (ok) {
    emit('connected')
    emit('open-llm-console')
  }
}

onMounted(() => {
  store.hydrateFromCache()
})

defineExpose({
  connectLocalDirect: (opts?: { quiet?: boolean; force?: boolean }) =>
    store.connectLocalDirect(opts),
  runAutoConnect: (opts?: { quiet?: boolean; force?: boolean }) =>
    store.runAutoConnect(opts),
  connectAndOpen: handleDirectConnect,
})
</script>

<style scoped>
.local-model-connect {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.status-alert {
  padding: 8px 10px;
  font-size: 13px;
  line-height: 1.45;
}

.service-block {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.service-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
}

.more-collapse :deep(.n-collapse-item__header) {
  font-size: 12px;
}
</style>
