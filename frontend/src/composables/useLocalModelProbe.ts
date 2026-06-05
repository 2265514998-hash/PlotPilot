import { pickPrimaryLlmService, useLocalModelStore } from '@/stores/localModelStore'

export type { ModelServiceItem } from '@/stores/localModelStore'
export { pickPrimaryLlmService, useLocalModelStore }

/** 兼容旧引用，等同于 useLocalModelStore */
export function useLocalModelProbe() {
  return useLocalModelStore()
}
