/**
 * SSE (Server-Sent Events) 流解析工具
 *
 * 统一 fetch → ReadableStream → TextDecoder → 帧分割 → JSON 解析 的管线，
 * 消除 config.ts / workflow.ts / planning.ts 中的三份重复实现。
 *
 * 兼容标准 SSE（LF）和部分运行栈的 CRLF 换行。
 */

// ---------------------------------------------------------------------------
// 低层解析：帧分割 + data: 行提取
// ---------------------------------------------------------------------------

/** SSE 帧分隔：兼容 `\n\n`（标准）和 `\r\n\r\n`（CRLF） */
export function takeNextSseBlock(buffer: string): { block: string; rest: string } | null {
  const lfIdx = buffer.indexOf('\n\n')
  const crlfIdx = buffer.indexOf('\r\n\r\n')
  let sep = -1
  let sepLen = 2
  if (lfIdx !== -1 && (crlfIdx === -1 || lfIdx <= crlfIdx)) {
    sep = lfIdx
    sepLen = 2
  } else if (crlfIdx !== -1) {
    sep = crlfIdx
    sepLen = 4
  }
  if (sep < 0) return null
  return {
    block: buffer.slice(0, sep),
    rest: buffer.slice(sep + sepLen),
  }
}

/** 解析单个 SSE 帧：提取 event 类型和合并后的 data 字符串（支持多行 data） */
export function parseSseEventBlock(block: string): { eventType: string; dataStr: string } {
  let eventType = 'message'
  const dataLines: string[] = []
  for (const line of block.split(/\r?\n/)) {
    if (line.startsWith('event:')) {
      eventType = line.startsWith('event: ') ? line.slice(7).trim() : line.slice(6).trim()
    } else if (line.startsWith('data:')) {
      dataLines.push(line.startsWith('data: ') ? line.slice(6) : line.slice(5).replace(/^\s/, ''))
    }
  }
  return { eventType, dataStr: dataLines.join('\n') }
}

/** 从单行 `data: {...}` 提取 JSON，解析失败返回 null */
export function parseSseDataLine(line: string): unknown | null {
  if (!line.startsWith('data: ')) return null
  try {
    return JSON.parse(line.slice(6)) as unknown
  } catch {
    return null
  }
}

// ---------------------------------------------------------------------------
// 高层消费：fetch → 流式读取 → 逐帧回调
// ---------------------------------------------------------------------------

export interface SseConsumerOptions {
  /** 请求 URL（需已解析为完整地址） */
  url: string
  /** fetch 请求配置（method / headers / body / signal 等） */
  requestInit?: RequestInit
  /**
   * 每解析出一个完整 SSE 帧时回调。
   * 对于标准 `data: {json}` 格式，parsed 已是 JSON.parse 结果；
   * 对于多行 data 或自定义 event，可通过 eventType / dataStr 处理。
   */
  onFrame: (frame: { eventType: string; dataStr: string; parsed: unknown | null }) => void
  /** 流正常结束 */
  onDone?: () => void
  /** 流异常（非 AbortError） */
  onError?: (error: Error) => void
  /** fetch 响应就绪 */
  onConnected?: () => void
}

/**
 * 通用 SSE 消费器 — 替代三处重复的 fetch → reader → decoder → 帧分割 管线。
 *
 * 返回 AbortController，调用 abort() 可提前终止流。
 *
 * @example
 * ```ts
 * const ctrl = consumeSseStream({
 *   url: resolveHttpUrl('/api/v1/autopilot/xxx/chapter-stream'),
 *   onFrame({ parsed }) {
 *     if (parsed && typeof parsed === 'object') {
 *       const o = parsed as Record<string, unknown>
 *       // dispatch by o.type ...
 *     }
 *   },
 *   onError(err) { console.error(err) },
 * })
 * ```
 */
export function consumeSseStream(opts: SseConsumerOptions): AbortController {
  const ctrl = new AbortController()

  void (async () => {
    try {
      const { signal: _unused, ...init } = (opts.requestInit ?? {})
      const res = await fetch(opts.url, {
        signal: _unused ?? ctrl.signal,
        headers: {
          'Accept': 'text/event-stream',
          'Cache-Control': 'no-cache',
          ...init.headers,
        },
        ...init,
      })

      if (!res.ok || !res.body) {
        opts.onError?.(new Error(`HTTP ${res.status}`))
        return
      }

      opts.onConnected?.()

      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      const flushBlocks = (buf: string): string => {
        let result = buf
        let hit: { block: string; rest: string } | null
        while ((hit = takeNextSseBlock(result)) !== null) {
          result = hit.rest
          const { eventType, dataStr } = parseSseEventBlock(hit.block)
          if (!dataStr) continue
          let parsed: unknown | null = null
          try {
            parsed = JSON.parse(dataStr)
          } catch {
            /* 保留 dataStr 供调用方处理 */
          }
          opts.onFrame({ eventType, dataStr, parsed })
        }
        return result
      }

      while (true) {
        const { done, value } = await reader.read()
        if (value) buffer += decoder.decode(value, { stream: true })
        buffer = flushBlocks(buffer)
        if (done) {
          buffer += decoder.decode()
          buffer = flushBlocks(buffer)
          break
        }
      }

      if (!ctrl.signal.aborted) {
        opts.onDone?.()
      }
    } catch (e) {
      if (e instanceof Error && e.name === 'AbortError') return
      opts.onError?.(e instanceof Error ? e : new Error('SSE stream error'))
    }
  })()

  return ctrl
}
