import { apiClient } from './config'

export interface ForeshadowingHealth {
  total: number
  planted: number
  resolved: number
  abandoned: number
  overdue: number
  upcoming_window: number
  t0_count: number
  deferred_count: number
}

export interface DebtHealth {
  total: number
  active: number
  overdue: number
  resolved: number
  abandoned: number
  by_type: Record<string, number>
}

export interface TensionPoint {
  chapter: number
  composite: number
  plot: number
  emotional: number
  pacing: number
}

export interface PropHealth {
  total: number
  by_state: Record<string, number>
  stale_count: number
}

export interface VoiceDriftHealth {
  latest_score: number
  alert: boolean
  trend: string
}

export interface NarrativeHealthResponse {
  foreshadowing: ForeshadowingHealth
  narrative_debts: DebtHealth
  tension_curve: TensionPoint[]
  props: PropHealth
  voice_drift: VoiceDriftHealth
  health_score: number
}

export const narrativeHealthApi = {
  getHealth: (novelId: string) =>
    apiClient.get<NarrativeHealthResponse>(`/novels/${novelId}/narrative-health`),
}
