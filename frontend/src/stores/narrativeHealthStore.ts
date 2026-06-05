import { defineStore } from 'pinia'
import { ref } from 'vue'
import { narrativeHealthApi, type NarrativeHealthResponse } from '../api/narrativeHealth'

export const useNarrativeHealthStore = defineStore('narrativeHealth', () => {
  const data = ref<NarrativeHealthResponse | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function loadHealth(novelId: string, force = false) {
    if (!force && data.value !== null) return data.value
    loading.value = true
    error.value = null
    try {
      data.value = await narrativeHealthApi.getHealth(novelId)
      return data.value
    } catch (err) {
      error.value = err instanceof Error ? err.message : '加载叙事健康数据失败'
      throw err
    } finally {
      loading.value = false
    }
  }

  function clear() {
    data.value = null
    error.value = null
  }

  return { data, loading, error, loadHealth, clear }
})
