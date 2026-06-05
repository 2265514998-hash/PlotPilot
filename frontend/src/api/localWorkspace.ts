import type { AxiosRequestConfig } from 'axios'
import { apiClient } from './config'

type SilentRequestConfig = AxiosRequestConfig & { silentGlobalFeedback?: boolean }

export interface ChapterPreviewItem {
  number: number
  title: string
  path: string
  words: number
}

export interface ScanCandidate {
  kind: string
  path: string
  title_guess: string
  chapter_files: number
  total_words_estimate: number
  confidence: number
  chapter_preview: ChapterPreviewItem[]
  extra: Record<string, unknown>
}

export interface LocalScanResponse {
  scan_id: string
  roots: string[]
  candidates: ScanCandidate[]
  warnings: string[]
}

export interface LocalConnectResponse {
  novel_id: string
  title: string
  imported_chapters: number
  total_words: number
  skipped_files: string[]
  warnings: string[]
  next_actions: string[]
}

export interface HealthProbeItem {
  host: string
  port: number
  reachable: boolean
  base_url: string
  detail: string
}

export interface LocalModelProbeResponse {
  services: Array<{
    id: string
    label: string
    kind: string
    reachable: boolean
    detail: string
    models_preview?: string[]
    suggested_model?: string
    suggested_base_url?: string
    manage_url?: string
  }>
  embedding: {
    mode_env: string
    model_path: string
    suggested_model_path?: string
    model_path_auto_matched?: boolean
    model_path_exists: boolean
    extensions_installed: boolean
    extensions_detail: string
    ready: boolean
  }
  llm_env: {
    ark_api_key_set: boolean
    anthropic_key_set: boolean
  }
  summary: {
    plotpilot_backend: boolean
    local_llm_runtime: boolean
    local_embedding_ready: boolean
    cloud_llm_configured: boolean
  }
}

export const localWorkspaceApi = {
  scan(roots: string[], depth = 4) {
    return apiClient.post<LocalScanResponse>('/local/scan', {
      roots,
      depth,
      detect_plotpilot_db: true,
    })
  },

  connect(sourcePath: string, novelTitle?: string) {
    return apiClient.post<LocalConnectResponse>('/local/connect', {
      mode: 'import_manuscript',
      source_path: sourcePath,
      novel_title: novelTitle || undefined,
    })
  },

  healthProbe(hosts = '127.0.0.1', ports = '8005') {
    return apiClient.get<{ probes: HealthProbeItem[] }>('/local/health-probe', {
      params: { hosts, ports },
    })
  },

  modelProbe(options?: { silent?: boolean }) {
    return apiClient.get<LocalModelProbeResponse>('/local/model-probe', {
      silentGlobalFeedback: options?.silent === true,
    } as SilentRequestConfig)
  },

  autoConnectLlm() {
    return apiClient.post<{
      connected: boolean
      skipped?: boolean
      method?: string
      reason?: string | null
      profile_id?: string | null
      service_id?: string | null
      label?: string | null
      base_url?: string | null
      model?: string | null
      runtime?: {
        using_mock?: boolean
        verified?: boolean
        verify_error?: string | null
      }
      services?: LocalModelProbeResponse['services']
      summary?: LocalModelProbeResponse['summary']
    }>('/local/auto-connect-llm', {}, { silentGlobalFeedback: true } as SilentRequestConfig)
  },

  connectLlm(serviceId: string, model?: string, baseUrl?: string, options?: { silent?: boolean }) {
    return apiClient.post<{
      profile_id: string
      service_id: string
      label?: string
      base_url: string
      model: string
      runtime: {
        using_mock?: boolean
        reason?: string | null
        active_profile_name?: string | null
        model?: string | null
        verified?: boolean
        verify_error?: string | null
        verify_preview?: string | null
      }
    }>(
      '/local/connect-llm',
      {
        service_id: serviceId,
        model: model || undefined,
        base_url: baseUrl || undefined,
      },
      { silentGlobalFeedback: options?.silent === true } as SilentRequestConfig,
    )
  },
}
