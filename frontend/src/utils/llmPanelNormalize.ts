import type {
  LLMControlConfig,
  LLMControlPanelData,
  LLMProfile,
  LLMPreset,
  LLMRuntimeSummary,
} from '@/api/llmControl'

function defaultRuntimeSummary(): LLMRuntimeSummary {
  return {
    source: 'mock',
    active_profile_id: null,
    active_profile_name: null,
    protocol: null,
    model: null,
    base_url: null,
    using_mock: true,
    reason: '尚未加载或未返回运行时摘要',
  }
}

/** 兼容代理/网关包装的 panel 响应，与 LLMControlPanel 一致。 */
export function normalizePanelData(raw: unknown): LLMControlPanelData {
  let root: Record<string, unknown> =
    raw && typeof raw === 'object' ? { ...(raw as Record<string, unknown>) } : {}

  const wrapped = root.data
  if (
    wrapped &&
    typeof wrapped === 'object' &&
    'config' in (wrapped as object) &&
    !('config' in root)
  ) {
    root = { ...(wrapped as Record<string, unknown>) }
  }

  const cfgIn = root.config
  const cfgObj =
    cfgIn && typeof cfgIn === 'object'
      ? (cfgIn as Record<string, unknown>)
      : { version: 1, active_profile_id: null, profiles: [] }

  let profiles: LLMProfile[] = Array.isArray(cfgObj.profiles)
    ? (cfgObj.profiles as LLMProfile[]).filter(
        (p) => p && typeof p === 'object' && typeof p.id === 'string',
      )
    : []

  if (!profiles.length) {
    profiles = [
      {
        id: 'openai-compatible-default',
        name: 'OpenAI 兼容 / 国产通用',
        preset_key: 'custom-openai-compatible',
        protocol: 'openai',
        base_url: '',
        api_key: '',
        model: '',
        temperature: 0.7,
        max_tokens: 4096,
        timeout_seconds: 300,
        extra_headers: {},
        extra_query: {},
        extra_body: {},
        notes: '',
        use_legacy_chat_completions: false,
      },
    ]
  }

  const config: LLMControlConfig = {
    version: typeof cfgObj.version === 'number' ? cfgObj.version : 1,
    active_profile_id:
      typeof cfgObj.active_profile_id === 'string'
        ? cfgObj.active_profile_id
        : profiles[0]?.id ?? null,
    endpoint_mode:
      cfgObj.endpoint_mode === 'independent' ? 'independent' : 'unified',
    profiles,
  }

  const presets: LLMPreset[] = Array.isArray(root.presets)
    ? (root.presets as LLMPreset[])
    : []

  const rtIn = root.runtime
  const runtime: LLMRuntimeSummary =
    rtIn && typeof rtIn === 'object'
      ? { ...defaultRuntimeSummary(), ...(rtIn as Partial<LLMRuntimeSummary>) }
      : defaultRuntimeSummary()

  return { config, presets, runtime }
}
