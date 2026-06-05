import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { useMessage } from 'naive-ui'
import { localWorkspaceApi, type LocalModelProbeResponse } from '@/api/localWorkspace'

export interface ModelServiceItem {
  id: string
  label: string
  kind: string
  reachable: boolean
  detail?: string
  models_preview?: string[]
  suggested_model?: string
  suggested_base_url?: string
  manage_url?: string
}

const AUTO_CONNECT_KEY = 'plotpilot_auto_connect_local_llm'
const PROBE_CACHE_KEY = 'plotpilot_local_llm_probe_cache'
const PROBE_CACHE_TTL_MS = 45_000
const SERVICE_PRIORITY = ['ollama', 'lm_studio', 'localai'] as const
const LOCAL_FALLBACK_TARGETS = [
  { serviceId: 'ollama', baseUrl: 'http://127.0.0.1:11434/v1' },
  { serviceId: 'ollama', baseUrl: 'http://localhost:11434/v1' },
  { serviceId: 'lm_studio', baseUrl: 'http://127.0.0.1:1234/v1' },
] as const
let sessionAutoConnectDone = false
/** 本会话内 /local/connect-llm 已确认 404，避免并行回退重复打接口并触发 incident 导出 */
let sessionLocalConnectApiMissing = false
let connectDirectInFlight: Promise<boolean> | null = null

function formatConnectError(e: unknown): string {
  const err = e as {
    response?: { status?: number; data?: { detail?: string | { msg?: string }[] } }
    message?: string
  }
  const d = err.response?.data?.detail
  if (typeof d === 'string' && d.trim()) return d.trim()
  if (Array.isArray(d)) {
    return d
      .map((x) =>
        typeof x === 'object' && x && 'msg' in x
          ? String((x as { msg?: string }).msg)
          : JSON.stringify(x),
      )
      .join('; ')
  }
  if (err.message) return err.message
  return '连接失败'
}

function readAutoConnectPref(): boolean {
  try {
    return localStorage.getItem(AUTO_CONNECT_KEY) !== '0'
  } catch {
    return true
  }
}

function writeProbeCache(services: ModelServiceItem[], summary: LocalModelProbeResponse['summary']) {
  try {
    localStorage.setItem(
      PROBE_CACHE_KEY,
      JSON.stringify({ at: Date.now(), services, summary }),
    )
  } catch {
    /* ignore */
  }
}

function readProbeCache(): { services: ModelServiceItem[]; summary: LocalModelProbeResponse['summary'] } | null {
  try {
    const raw = localStorage.getItem(PROBE_CACHE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw) as {
      at?: number
      services?: ModelServiceItem[]
      summary?: LocalModelProbeResponse['summary']
    }
    if (!parsed.at || Date.now() - parsed.at > PROBE_CACHE_TTL_MS) return null
    if (!Array.isArray(parsed.services)) return null
    return { services: parsed.services, summary: parsed.summary ?? ({} as LocalModelProbeResponse['summary']) }
  } catch {
    return null
  }
}

export function resolveAutoModelForService(service: ModelServiceItem): string {
  const suggested = (service.suggested_model || '').trim()
  if (suggested) return suggested
  return (service.models_preview?.[0] || '').trim()
}

export function pickPrimaryLlmService(services: ModelServiceItem[]): ModelServiceItem | null {
  const reachable = services.filter((s) => s.kind === 'llm' && s.reachable && s.suggested_base_url)
  if (!reachable.length) return null
  for (const id of SERVICE_PRIORITY) {
    const hit = reachable.find((s) => s.id === id)
    if (hit) return hit
  }
  return reachable[0]
}

export const useLocalModelStore = defineStore('localModel', () => {
  const modelProbing = ref(false)
  const modelProbeSummary = ref('')
  const modelProbeOk = ref(false)
  const modelServices = ref<ModelServiceItem[]>([])
  const embeddingInfo = ref<LocalModelProbeResponse['embedding'] | null>(null)
  const selectedModels = ref<Record<string, string>>({})
  const autoConnectOnDetect = ref(readAutoConnectPref())
  const lastConnectedLabel = ref<string | null>(null)
  const connectingId = ref<string | null>(null)

  const reachableLlms = computed(() =>
    modelServices.value.filter((s) => s.kind === 'llm' && s.reachable && s.suggested_base_url),
  )

  const primaryReachable = computed(() => pickPrimaryLlmService(modelServices.value))

  const hasReachableLocalLlm = computed(() => reachableLlms.value.length > 0)

  function setAutoConnect(enabled: boolean) {
    autoConnectOnDetect.value = enabled
    try {
      localStorage.setItem(AUTO_CONNECT_KEY, enabled ? '1' : '0')
    } catch {
      /* ignore */
    }
  }

  function openServicePage(service: ModelServiceItem) {
    const message = useMessage()
    const url = service.manage_url || service.suggested_base_url
    if (!url) {
      message.info('暂无该服务的管理地址')
      return
    }
    window.open(url, '_blank', 'noopener,noreferrer')
  }

  function notifyLlmConfigChanged() {
    if (typeof window !== 'undefined') {
      window.dispatchEvent(new CustomEvent('plotpilot-llm-config-changed'))
    }
  }

  function markLocalConnectApiMissing(quiet: boolean) {
    sessionLocalConnectApiMissing = true
    modelProbeSummary.value =
      '后端缺少 /local/connect-llm：请停止旧 uvicorn 后重新启动（开发环境端口 8010），再刷新页面'
    if (!quiet) {
      useMessage().error(modelProbeSummary.value)
    }
  }

  async function connectLocalLlm(
    service: ModelServiceItem,
    quiet = false,
    options?: { baseUrl?: string; model?: string },
  ): Promise<boolean> {
    const message = useMessage()
    if (sessionLocalConnectApiMissing) {
      return false
    }
    if (service.kind !== 'llm') {
      if (!quiet) message.info('该条目为后端 API，无需连接')
      return false
    }
    const model = (
      options?.model ||
      selectedModels.value[service.id] ||
      resolveAutoModelForService(service) ||
      ''
    ).trim()
    const baseUrl = (options?.baseUrl || '').trim()
    if (!service.reachable && !baseUrl) {
      if (!quiet) {
        message.warning(
          `${service.label} 当前不可达。请用下方「手动填写地址」连接，或先重新探测。`,
        )
      }
      return false
    }
    if (!model && !quiet) {
      message.warning(
        '未检测到可用模型名。Ollama 请执行 ollama pull；LM Studio 请先在软件内加载模型。',
      )
    }
    connectingId.value = service.id
    try {
      const data = await localWorkspaceApi.connectLlm(
        service.id,
        model || undefined,
        baseUrl || undefined,
        { silent: quiet },
      )
      notifyLlmConfigChanged()

      if (data.runtime?.using_mock) {
        if (!quiet) {
          message.warning(
            data.runtime.reason ||
              '配置已写入数据库，但 PlotPilot 仍判定为 Mock。请在 AI 控制台检查 Base URL、模型名与 API Key。',
          )
        }
        return false
      }

      lastConnectedLabel.value = data.label || service.label

      if (data.runtime?.verified === false && !quiet) {
        message.warning(
          `已写入配置（${data.model}），试跑未通过：${data.runtime.verify_error || '未知错误'}，生成时若失败请检查模型名。`,
        )
      }

      if (!quiet && data.runtime?.verified !== false) {
        const preview = data.runtime?.verify_preview
          ? ` · 试跑：${data.runtime.verify_preview}`
          : ''
        message.success(
          `已连接 ${data.label || service.label} · 模型 ${data.model}${preview}`,
        )
      }
      return true
    } catch (e: unknown) {
      const err = e as { response?: { status?: number } }
      if (err.response?.status === 404) {
        markLocalConnectApiMissing(quiet)
      } else if (!quiet) {
        message.error(formatConnectError(e))
      }
      return false
    } finally {
      connectingId.value = null
    }
  }

  async function connectPrimary(quiet = false): Promise<boolean> {
    const message = useMessage()
    const primary = primaryReachable.value
    if (!primary) {
      if (!quiet) message.warning('未检测到可用的本机 LLM，请先启动 Ollama 或 LM Studio')
      return false
    }
    return connectLocalLlm(primary, quiet)
  }

  async function runModelProbe(options?: { autoApply?: boolean; quiet?: boolean }) {
    const message = useMessage()
    modelProbing.value = true
    if (!options?.quiet) {
      modelProbeSummary.value = ''
    }
    try {
      const data = await localWorkspaceApi.modelProbe({ silent: options?.quiet })
      modelServices.value = data.services || []
      embeddingInfo.value = data.embedding
      writeProbeCache(modelServices.value, data.summary)

      const nextSel: Record<string, string> = { ...selectedModels.value }
      for (const s of modelServices.value) {
        if (s.kind !== 'llm') continue
        const auto = resolveAutoModelForService(s)
        if (auto && !nextSel[s.id]) {
          nextSel[s.id] = auto
        }
      }
      selectedModels.value = nextSel

      const s = data.summary
      const parts: string[] = []
      if (s.local_llm_runtime) parts.push('检测到本机 LLM，可直接启用')
      else parts.push('未检测到本机 LLM（请先启动 Ollama 或 LM Studio）')
      if (s.local_embedding_ready) parts.push('本地嵌入就绪')
      else parts.push('本地嵌入未就绪')
      modelProbeOk.value = !!s.local_llm_runtime
      modelProbeSummary.value = parts.join(' · ')

      const shouldAuto =
        (options?.autoApply ?? autoConnectOnDetect.value) && reachableLlms.value.length > 0
      if (shouldAuto && primaryReachable.value) {
        const ok = await connectPrimary(true)
        if (!ok) {
          const hint = ' · 自动连接未成功'
          modelProbeSummary.value = modelProbeSummary.value.includes('自动连接')
            ? modelProbeSummary.value
            : `${modelProbeSummary.value}${hint}`
        }
      }
    } catch (e: unknown) {
      const err = e as { response?: { status?: number } }
      if (err.response?.status === 404) {
        modelProbeSummary.value = '后端未加载 /local 接口，请重启 uvicorn 后重试'
      } else {
        modelProbeSummary.value = formatConnectError(e)
      }
      modelProbeOk.value = false
    } finally {
      modelProbing.value = false
    }
  }

  function applyProbeServices(
    services: ModelServiceItem[],
    summary?: LocalModelProbeResponse['summary'],
  ) {
    modelServices.value = services
    if (summary) {
      writeProbeCache(services, summary)
      modelProbeOk.value = !!summary.local_llm_runtime
    }
    const nextSel: Record<string, string> = { ...selectedModels.value }
    for (const s of services) {
      if (s.kind !== 'llm') continue
      const auto = resolveAutoModelForService(s)
      if (auto && !nextSel[s.id]) {
        nextSel[s.id] = auto
      }
    }
    selectedModels.value = nextSel
  }

  /** 启动时自动探测并连接本机 LLM（默认开启，每会话一次） */
  async function runAutoConnect(options?: { quiet?: boolean; force?: boolean }) {
    if (!autoConnectOnDetect.value && !options?.force) return false
    if (sessionAutoConnectDone && !options?.force) return false
    sessionAutoConnectDone = true

    const quiet = options?.quiet ?? true
    modelProbing.value = true
    try {
      const data = await localWorkspaceApi.autoConnectLlm()
      if (data.services?.length) {
        applyProbeServices(data.services, data.summary)
      }

      if (data.connected) {
        if (data.skipped) {
          lastConnectedLabel.value = data.label || lastConnectedLabel.value
          modelProbeSummary.value = data.label
            ? `已使用本地模型：${data.label}${data.model ? ` · ${data.model}` : ''}`
            : '已配置本地模型'
          modelProbeOk.value = true
        } else if (data.label && data.model) {
          lastConnectedLabel.value = data.label
          modelProbeSummary.value = `已自动连接 ${data.label} · ${data.model}`
          modelProbeOk.value = true
          notifyLlmConfigChanged()
          if (!quiet && data.runtime?.verified !== false) {
            useMessage().success(`已自动连接 ${data.label} · ${data.model}`)
          }
        }
        return true
      }

      if (data.summary) {
        const s = data.summary
        modelProbeOk.value = !!s.local_llm_runtime
        modelProbeSummary.value = [
          s.local_llm_runtime ? '检测到本机 LLM' : '未检测到本机 LLM',
          data.reason || '自动连接未成功',
        ].join(' · ')
      } else {
        modelProbeSummary.value = data.reason || '自动连接未成功'
      }

      return false
    } catch (e: unknown) {
      const err = e as { response?: { status?: number } }
      if (err.response?.status === 404) {
        markLocalConnectApiMissing(quiet)
      }
      return false
    } finally {
      modelProbing.value = false
    }
  }

  /** 一键直连本地 AI：自动接口 → 探测 → 默认地址回退（全局单飞，避免并行 404 刷屏） */
  async function connectLocalDirect(options?: {
    quiet?: boolean
    force?: boolean
  }): Promise<boolean> {
    if (sessionLocalConnectApiMissing) {
      return false
    }
    if (connectDirectInFlight) {
      return connectDirectInFlight
    }

    const quiet = options?.quiet ?? false
    const message = useMessage()
    const force = options?.force ?? true

    connectDirectInFlight = (async () => {
      modelProbing.value = true
      try {
        if (autoConnectOnDetect.value || force) {
          const viaApi = await runAutoConnect({ quiet: true, force })
          if (viaApi) {
            if (!quiet) {
              message.success(
                lastConnectedLabel.value
                  ? `已连接 ${lastConnectedLabel.value}`
                  : '已连接本地 AI',
              )
            }
            return true
          }
          if (sessionLocalConnectApiMissing) {
            return false
          }
        }

        await runModelProbe({ autoApply: !sessionLocalConnectApiMissing, quiet: true })
        if (sessionLocalConnectApiMissing) {
          return false
        }
        if (primaryReachable.value) {
          const ok = await connectPrimary(true)
          if (ok) {
            if (!quiet) message.success(`已连接 ${lastConnectedLabel.value || '本地 AI'}`)
            return true
          }
          if (sessionLocalConnectApiMissing) {
            return false
          }
        }

        for (const fb of LOCAL_FALLBACK_TARGETS) {
          if (sessionLocalConnectApiMissing) break
          const ok = await connectManual(fb.serviceId, fb.baseUrl, '', true)
          if (ok) {
            modelProbeSummary.value = `已连接 ${fb.baseUrl}`
            modelProbeOk.value = true
            notifyLlmConfigChanged()
            if (!quiet) message.success('已连接本地 AI 模型')
            return true
          }
        }

        if (sessionLocalConnectApiMissing) {
          return false
        }

        modelProbeSummary.value =
          '未能连接本机 AI：请启动 Ollama（ollama pull 模型）或 LM Studio 并加载模型'
        modelProbeOk.value = false
        if (!quiet) {
          message.warning(
            '未能连接本地 AI。请确认 Ollama 在运行且已拉取模型（ollama list 可见）。',
          )
        }
        return false
      } finally {
        modelProbing.value = false
        connectDirectInFlight = null
      }
    })()

    return connectDirectInFlight
  }

  function hydrateFromCache() {
    const cached = readProbeCache()
    if (!cached) return false
    modelServices.value = cached.services
    modelProbeOk.value = !!cached.summary?.local_llm_runtime
    modelProbeSummary.value = modelProbeOk.value
      ? '已缓存探测结果：检测到本机 LLM'
      : '已缓存探测结果：暂无本机 LLM'
    return true
  }

  function setSelectedModel(serviceId: string, model: string) {
    selectedModels.value = { ...selectedModels.value, [serviceId]: model }
  }

  async function connectManual(
    serviceId: string,
    baseUrl: string,
    model: string,
    quiet = false,
  ): Promise<boolean> {
    const stub: ModelServiceItem = {
      id: serviceId,
      label: serviceId,
      kind: 'llm',
      reachable: true,
      suggested_base_url: baseUrl,
    }
    return connectLocalLlm(stub, quiet, { baseUrl, model })
  }

  return {
    modelProbing,
    modelProbeSummary,
    modelProbeOk,
    modelServices,
    embeddingInfo,
    selectedModels,
    autoConnectOnDetect,
    lastConnectedLabel,
    connectingId,
    reachableLlms,
    primaryReachable,
    hasReachableLocalLlm,
    setAutoConnect,
    setSelectedModel,
    openServicePage,
    connectLocalLlm,
    connectPrimary,
    connectManual,
    connectLocalDirect,
    runAutoConnect,
    runModelProbe,
    hydrateFromCache,
  }
})
