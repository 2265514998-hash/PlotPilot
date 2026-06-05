<template>
  <n-card class="local-connect-card" :bordered="false">
    <template #header>
      <div class="local-connect-head">
        <span class="local-connect-icon">📂</span>
        <div>
          <h3 class="local-connect-title">扫描本地 · 快速连接</h3>
          <p class="local-connect-sub">
            指定书稿文件夹（.txt / .md / .docx），扫描后一键导入为书目并进入工作台。
          </p>
        </div>
      </div>
    </template>

    <n-space vertical :size="14">
      <n-input
        v-model:value="folderPath"
        placeholder="例如 D:\Novels\我的长篇"
        :disabled="scanning || connecting"
        clearable
      />
      <n-space :size="10" wrap>
        <n-button type="primary" :loading="scanning" @click="runScan">
          扫描目录
        </n-button>
        <n-button quaternary :loading="probing" @click="runProbe">
          检测后端
        </n-button>
        <n-button
          quaternary
          :loading="modelProbing || !!connectingId"
          @click="connectPrimaryOnHome"
        >
          连接本地 AI
        </n-button>
      </n-space>

      <n-text
        v-if="probeHint || modelProbeSummary"
        depth="3"
        class="local-status-line"
      >
        {{ modelProbeSummary || probeHint }}
      </n-text>

      <n-alert v-for="(w, i) in scanWarnings" :key="'w-' + i" type="warning" :show-icon="true">
        {{ w }}
      </n-alert>

      <n-list v-if="candidates.length" bordered class="candidate-list">
        <n-list-item v-for="(c, idx) in candidates" :key="idx">
          <div class="candidate-row">
            <div class="candidate-main">
              <n-tag size="small" :type="c.kind === 'manuscript_folder' ? 'success' : 'info'">
                {{ kindLabel(c.kind) }}
              </n-tag>
              <strong class="candidate-title">{{ c.title_guess }}</strong>
              <span class="candidate-meta">
                {{ c.chapter_files }} 个文件 · 约 {{ formatWords(c.total_words_estimate) }} 字
                · 置信 {{ (c.confidence * 100).toFixed(0) }}%
              </span>
              <n-text depth="3" class="candidate-path">{{ c.path }}</n-text>
              <n-text v-if="c.extra?.note" depth="3" class="candidate-note">
                {{ c.extra.note }}
              </n-text>
            </div>
            <n-button
              v-if="c.kind === 'manuscript_folder'"
              type="primary"
              size="small"
              :loading="connecting && connectTarget === c.path"
              @click="runConnect(c)"
            >
              导入并打开
            </n-button>
          </div>
        </n-list-item>
      </n-list>

      <n-empty v-else-if="scannedOnce && !scanning" description="未发现可导入的书稿目录" />
    </n-space>

  </n-card>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { storeToRefs } from 'pinia'
import { useRouter } from 'vue-router'
import { useMessage } from 'naive-ui'
import {
  localWorkspaceApi,
  type ScanCandidate,
} from '@/api/localWorkspace'
import { useLocalModelStore } from '@/stores/localModelStore'

const router = useRouter()
const message = useMessage()
const localModelStore = useLocalModelStore()
const { modelProbing, modelProbeSummary, connectingId } = storeToRefs(localModelStore)

async function connectPrimaryOnHome() {
  await localModelStore.connectLocalDirect({ quiet: false, force: true })
}

const folderPath = ref('')
const scanning = ref(false)
const connecting = ref(false)
const probing = ref(false)
const scannedOnce = ref(false)
const scanWarnings = ref<string[]>([])
const candidates = ref<ScanCandidate[]>([])
const connectTarget = ref('')
const probeHint = ref('')
const probeOk = ref(false)

function kindLabel(kind: string) {
  if (kind === 'manuscript_folder') return '书稿目录'
  if (kind === 'plotpilot_data_dir') return '数据目录'
  return kind
}

function formatWords(n: number) {
  if (n >= 10000) return `${(n / 10000).toFixed(1)} 万`
  return String(n)
}

async function runScan() {
  const path = folderPath.value.trim()
  if (!path) {
    message.warning('请输入本地文件夹路径')
    return
  }
  scanning.value = true
  scannedOnce.value = true
  try {
    const { data } = await localWorkspaceApi.scan([path])
    scanWarnings.value = data.warnings || []
    candidates.value = (data.candidates || []).filter((c) => c.kind === 'manuscript_folder')
    if (!candidates.value.length && data.candidates?.length) {
      candidates.value = data.candidates
    }
    if (!data.candidates?.length) {
      message.info('扫描完成，未发现候选目录')
    }
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } } }
    message.error(err.response?.data?.detail || '扫描失败')
  } finally {
    scanning.value = false
  }
}

async function runConnect(c: ScanCandidate) {
  if (c.kind !== 'manuscript_folder') {
    message.warning('请选择书稿目录类型的候选')
    return
  }
  connecting.value = true
  connectTarget.value = c.path
  try {
    const { data } = await localWorkspaceApi.connect(c.path, c.title_guess)
    message.success(`已导入 ${data.imported_chapters} 章：${data.title}`)
    await router.push({
      name: 'Workbench',
      params: { slug: data.novel_id },
    })
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } } }
    message.error(err.response?.data?.detail || '导入失败')
  } finally {
    connecting.value = false
    connectTarget.value = ''
  }
}

async function runProbe() {
  probing.value = true
  try {
    const { data } = await localWorkspaceApi.healthProbe()
    const hit = data.probes?.find((p) => p.reachable)
    probeOk.value = !!hit
    probeHint.value = hit
      ? `后端已连接：${hit.base_url}（${hit.detail}）`
      : '未检测到后端，请先启动 uvicorn（127.0.0.1:8005）'
  } catch {
    probeOk.value = false
    probeHint.value = '探测请求失败，请确认 API 已启动'
  } finally {
    probing.value = false
  }
}
</script>

<style scoped>
.local-connect-card {
  margin-top: 20px;
  background: var(--app-surface-elevated, rgba(255, 255, 255, 0.04));
  border-radius: 12px;
}

.local-connect-head {
  display: flex;
  gap: 12px;
  align-items: flex-start;
}

.local-connect-icon {
  font-size: 22px;
  line-height: 1;
}

.local-connect-title {
  margin: 0;
  font-size: 16px;
  font-weight: 650;
}

.local-connect-sub {
  margin: 4px 0 0;
  font-size: 12px;
  color: var(--app-text-muted, #888);
}

.local-status-line {
  display: block;
  font-size: 12px;
  line-height: 1.45;
}

.candidate-list {
  max-height: 320px;
  overflow: auto;
}

.candidate-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  width: 100%;
}

.candidate-main {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.candidate-title {
  font-size: 14px;
}

.candidate-meta {
  font-size: 12px;
  color: var(--app-text-muted, #888);
}

.candidate-path,
.candidate-note {
  font-size: 11px;
  word-break: break-all;
}
</style>
