// 轻量 API 封装：同源 /api，Cookie 会话；前端不接触任何密钥（全局铁律 4）
export async function api<T = any>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`/api${path}`, {
    credentials: 'same-origin',
    headers: options.body instanceof FormData ? undefined : { 'Content-Type': 'application/json' },
    ...options,
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error((data as any).error || `请求失败 ${res.status}`)
  return data as T
}

export interface SseHandlers {
  onStatus?: (s: { status: string; message: string }) => void
  onDelta?: (text: string) => void
  onError?: (msg: string) => void
  onDone?: () => void
}

// POST /api/chat 的 SSE 流式消费：兼容后端透传的 OpenAI 分片 + 自定义 status/error 事件
export async function chatStream(
  body: { agent: string; messages: { role: string; content: string }[] },
  h: SseHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch('/api/chat', {
    method: 'POST',
    credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ...body, stream: true }),
    signal,
  })
  if (!res.ok || !res.body) {
    const d = await res.json().catch(() => ({}))
    h.onError?.((d as any).error || `请求失败 ${res.status}`)
    h.onDone?.()
    return
  }
  const reader = res.body.getReader()
  const dec = new TextDecoder()
  let buf = ''
  try {
    for (;;) {
      const { done, value } = await reader.read()
      if (done) break
      buf += dec.decode(value, { stream: true })
      let i: number
      while ((i = buf.indexOf('\n\n')) >= 0) {
        const block = buf.slice(0, i)
        buf = buf.slice(i + 2)
        let ev = ''
        const dataLines: string[] = []
        for (const line of block.split('\n')) {
          if (line.startsWith('event:')) ev = line.slice(6).trim()
          else if (line.startsWith('data:')) dataLines.push(line.slice(5).trim())
        }
        if (!dataLines.length) continue
        const data = dataLines.join('\n')
        if (ev === 'status') { try { h.onStatus?.(JSON.parse(data)) } catch { /* ignore */ } continue }
        if (ev === 'error') { try { h.onError?.(JSON.parse(data).error) } catch { h.onError?.(data) } continue }
        if (data === '[DONE]') { h.onDone?.(); return }
        try {
          const j = JSON.parse(data)
          const delta = j?.choices?.[0]?.delta?.content
          if (delta) h.onDelta?.(delta)
        } catch { /* 忽略非 JSON 分片 */ }
      }
    }
  } catch (e: any) {
    if (e?.name !== 'AbortError') h.onError?.(e?.message || '流式读取中断')
  }
  h.onDone?.()
}
