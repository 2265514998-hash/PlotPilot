import { ref, onUnmounted, type Ref } from 'vue'

export interface AICompletionState {
  suggestion: Ref<string>
  loading: Ref<boolean>
  request: (context: string) => void
  accept: () => string
  dismiss: () => void
}

export function useAICompletion(): AICompletionState {
  const suggestion = ref('')
  const loading = ref(false)
  let controller: AbortController | null = null
  let debounceTimer: ReturnType<typeof setTimeout> | null = null

  function request(context: string) {
    if (debounceTimer) clearTimeout(debounceTimer)
    if (controller) controller.abort()

    suggestion.value = ''

    debounceTimer = setTimeout(async () => {
      if (!context.trim()) return
      loading.value = true
      controller = new AbortController()

      try {
        const res = await fetch('/api/v1/ai/completion', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ context, max_tokens: 80 }),
          signal: controller.signal,
        })

        if (!res.ok || !res.body) { loading.value = false; return }

        const reader = res.body.getReader()
        const decoder = new TextDecoder()
        let buffer = ''

        while (true) {
          const { done, value } = await reader.read()
          if (done) break
          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split('\n')
          buffer = lines.pop() || ''
          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const data = JSON.parse(line.slice(6))
                if (data.text) suggestion.value += data.text
              } catch { /* skip malformed */ }
            }
          }
        }
      } catch (e) {
        if ((e as Error).name !== 'AbortError') {
          console.warn('[AICompletion]', e)
        }
      } finally {
        loading.value = false
      }
    }, 1500)
  }

  function accept(): string {
    const text = suggestion.value
    suggestion.value = ''
    if (debounceTimer) clearTimeout(debounceTimer)
    return text
  }

  function dismiss() {
    suggestion.value = ''
    if (debounceTimer) clearTimeout(debounceTimer)
    if (controller) controller.abort()
  }

  onUnmounted(() => {
    if (debounceTimer) clearTimeout(debounceTimer)
    if (controller) controller.abort()
  })

  return { suggestion, loading, request, accept, dismiss }
}
