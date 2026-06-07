<template>
  <div class="api-quick-setup">
    <div class="api-hero">
      <span class="api-hero-icon">🔑</span>
      <div>
        <h3 class="api-hero-title">接入 AI 模型</h3>
        <p class="api-hero-desc">填入 API 密钥即可使用，系统自动路由到对应模型。</p>
      </div>
    </div>

    <n-space vertical :size="20">
      <!-- Agnes AI -->
      <n-card size="medium" :bordered="true" class="provider-card">
        <template #header>
          <div class="provider-header">
            <div class="provider-brand" style="color: #6366f1">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/></svg>
            </div>
            <span class="provider-name">Agnes AI</span>
            <n-tag :bordered="false" size="small" :type="agnesStatus === 'connected' ? 'success' : 'default'">
              {{ agnesStatus === 'connected' ? '已连接' : agnesStatus === 'checking' ? '检测中…' : '未连接' }}
            </n-tag>
          </div>
        </template>
        <n-input
          v-model:value="agnesKey"
          type="password"
          show-password-on="click"
          placeholder="sk-... 输入 Agnes AI API 密钥"
          size="large"
          clearable
          @blur="checkAgnes"
        />
        <template #footer>
          <n-text depth="3" style="font-size:12px">注册获取密钥：<a href="https://agnes-ai.com" target="_blank">agnes-ai.com</a></n-text>
        </template>
      </n-card>

      <!-- Mimo -->
      <n-card size="medium" :bordered="true" class="provider-card">
        <template #header>
          <div class="provider-header">
            <div class="provider-brand" style="color: #f59e0b">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="4" fill="#fff"/></svg>
            </div>
            <span class="provider-name">Mimo</span>
            <n-tag :bordered="false" size="small" :type="mimoStatus === 'connected' ? 'success' : 'default'">
              {{ mimoStatus === 'connected' ? '已连接' : mimoStatus === 'checking' ? '检测中…' : '未连接' }}
            </n-tag>
          </div>
        </template>
        <n-input
          v-model:value="mimoKey"
          type="password"
          show-password-on="click"
          placeholder="tp-... 输入 Mimo API 密钥"
          size="large"
          clearable
          @blur="checkMimo"
        />
        <template #footer>
          <n-text depth="3" style="font-size:12px">注册获取密钥：<a href="https://token-plan-cn.xiaomimimo.com" target="_blank">小米 Mimo Token Plan</a></n-text>
        </template>
      </n-card>

      <!-- DeepSeek -->
      <n-card size="medium" :bordered="true" class="provider-card">
        <template #header>
          <div class="provider-header">
            <div class="provider-brand" style="color: #10b981">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><rect x="3" y="3" width="18" height="18" rx="3"/><path d="M8 8h8M8 12h8M8 16h5" stroke="#fff" stroke-width="1.5" fill="none"/></svg>
            </div>
            <span class="provider-name">DeepSeek</span>
            <n-tag :bordered="false" size="small" :type="deepseekLoaded ? 'success' : 'default'">
              {{ deepseekLoaded ? '已配置' : deepseekLoading ? '检测中…' : '未配置' }}
            </n-tag>
          </div>
        </template>
        <n-input
          v-model:value="deepseekKey"
          type="password"
          show-password-on="click"
          placeholder="sk-... 输入 DeepSeek API 密钥"
          size="large"
          clearable
          @blur="checkDeepseek"
        />
        <template #footer>
          <n-text depth="3" style="font-size:12px">注册获取密钥：<a href="https://platform.deepseek.com/api_keys" target="_blank">platform.deepseek.com</a></n-text>
        </template>
      </n-card>
    </n-space>

    <div class="action-bar">
      <n-button type="primary" size="large" :loading="saving" @click="saveAll" block>
        保存并接入全部模型
      </n-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { NSpace, NCard, NInput, NButton, NTag, NText, useMessage } from 'naive-ui'
import { llmControlApi, type LLMControlPanelData, type LLMProfile } from '@/api/llmControl'

const message = useMessage()
const saving = ref(false)

// ── 三个密钥 ──
const agnesKey = ref('')
const mimoKey = ref('')
const deepseekKey = ref('')

const agnesStatus = ref<'checking' | 'connected' | 'idle'>('idle')
const mimoStatus = ref<'checking' | 'connected' | 'idle'>('idle')
const deepseekLoading = ref(false)
const deepseekLoaded = ref(false)

// ── 快速连通性检查 ──
async function quickPing(url: string, key: string): Promise<boolean> {
  try {
    const r = await fetch(`${url}/models`, {
      headers: { Authorization: `Bearer ${key}` },
      signal: AbortSignal.timeout(5000),
    })
    return r.ok
  } catch {
    return false
  }
}

async function checkAgnes() {
  if (!agnesKey.value) return
  agnesStatus.value = 'checking'
  agnesStatus.value = (await quickPing('https://apihub.agnes-ai.com/v1', agnesKey.value)) ? 'connected' : 'idle'
}

async function checkMimo() {
  if (!mimoKey.value) return
  mimoStatus.value = 'checking'
  mimoStatus.value = (await quickPing('https://token-plan-cn.xiaomimimo.com/anthropic', mimoKey.value)) ? 'connected' : 'idle'
}

async function checkDeepseek() {
  if (!deepseekKey.value) {
    deepseekLoaded.value = true  // already have from DB
    return
  }
  deepseekLoading.value = true
  deepseekLoaded.value = (await quickPing('https://api.deepseek.com/v1', deepseekKey.value))
  deepseekLoading.value = false
}

// ── 构建 Profile ──
function makeProfile(id: string, name: string, key: string, baseUrl: string, model: string, protocol: string = 'openai'): LLMProfile {
  return {
    id, name, protocol: protocol as any,
    base_url: baseUrl, api_key: key, model,
    temperature: 0.8, max_tokens: 16384, timeout_seconds: 300,
    extra_headers: {}, extra_query: {}, extra_body: {}, notes: '',
    preset_key: 'custom-openai-compatible', use_legacy_chat_completions: false,
  }
}

const PROVIDERS = [
  { id: 'agnes-main', name: 'Agnes AI', keyRef: () => agnesKey.value, url: 'https://apihub.agnes-ai.com/v1', model: 'agnes-2.0-flash', protocol: 'openai' },
  { id: 'mimo-main', name: 'Mimo', keyRef: () => mimoKey.value, url: 'https://token-plan-cn.xiaomimimo.com/anthropic', model: 'mimo-v2.5-pro', protocol: 'anthropic' },
  { id: 'deepseek-main', name: 'DeepSeek', keyRef: () => deepseekKey.value, url: 'https://api.deepseek.com/v1', model: 'deepseek-v4-pro', protocol: 'openai' },
]

async function saveAll() {
  saving.value = true
  try {
    const data: LLMControlPanelData = await llmControlApi.getPanel()
    const profiles: LLMProfile[] = []

    for (const p of PROVIDERS) {
      const k = p.keyRef()
      if (!k) continue
      profiles.push(makeProfile(p.id, p.name, k, p.url, p.model, p.protocol as any))
    }

    if (!profiles.length) {
      message.warning('请至少填入一个 API 密钥')
      saving.value = false
      return
    }

    // 保留不在三选一里的其他 profiles
    const existing = data.config.profiles
    const mergedProfiles = [...existing.filter(ep => !PROVIDERS.some(p => p.id === ep.id))]

    for (const np of profiles) {
      const idx = mergedProfiles.findIndex(mp => mp.id === np.id)
      if (idx >= 0) mergedProfiles[idx] = np
      else mergedProfiles.push(np)
    }

    const newConfig = {
      ...data.config,
      version: 1,
      endpoint_mode: 'unified' as const,
      active_profile_id: profiles[0].id,
      profiles: mergedProfiles,
    }

    await llmControlApi.saveConfig(newConfig)
    message.success(`${profiles.length} 个模型已接入，即刻开始创作`)

    // 刷新页面状态
    agnesStatus.value = 'connected'
    mimoStatus.value = 'connected'
    deepseekLoaded.value = true
  } catch {
    message.error('保存失败，请检查网络后重试')
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  try {
    const data: LLMControlPanelData = await llmControlApi.getPanel()
    for (const p of data.config.profiles) {
      if (p.id === 'agnes-main') agnesKey.value = p.api_key
      if (p.id === 'mimo-main') mimoKey.value = p.api_key
      if (p.id === 'deepseek-main') deepseekKey.value = p.api_key
    }
    // 如果 DB 里已有 key，自动标记
    if (deepseekKey.value) { deepseekLoaded.value = true }
    if (agnesKey.value) checkAgnes()
    if (mimoKey.value) checkMimo()
  } catch { /* 首次使用 */ }
})
</script>

<style scoped>
.api-quick-setup {
  max-width: 540px;
  padding-bottom: 8px;
}

.api-hero {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 24px;
}

.api-hero-icon {
  font-size: 28px;
  line-height: 1;
}

.api-hero-title {
  margin: 0 0 4px;
  font-size: 16px;
  font-weight: 600;
}

.api-hero-desc {
  margin: 0;
  font-size: 13px;
  color: var(--text-color-muted, #94a3b8);
  line-height: 1.5;
}

.provider-card {
  transition: box-shadow 0.2s ease;
}
.provider-card:hover {
  box-shadow: 0 2px 12px rgba(0,0,0,0.06);
}

.provider-header {
  display: flex;
  align-items: center;
  gap: 10px;
}

.provider-brand {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 8px;
  background: var(--action-color-secondary, #f1f5f9);
}

.provider-name {
  font-weight: 600;
  font-size: 15px;
  flex: 1;
}

.action-bar {
  margin-top: 24px;
}
</style>
