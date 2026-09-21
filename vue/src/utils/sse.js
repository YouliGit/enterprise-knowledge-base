// SSRFetch：POST + Authorization + 解析 SSE 事件流（EventSource 不支持 POST，故自实现）
// 事件类型（后端 /chat/ask）：start / agent_start / step / token / refs / trace / done / error
export async function sseFetch(url, body, { token, onEvent, onDone, onError, signal } = {}) {
  let resp
  try {
    resp = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: token ? `Bearer ${token}` : '',
        Accept: 'text/event-stream',
      },
      body: JSON.stringify(body),
      signal,
    })
  } catch (e) {
    onError && onError(e)
    return
  }
  if (!resp.ok) {
    let msg = `HTTP ${resp.status}`
    try {
      const j = await resp.json()
      msg = j.msg || msg
    } catch (_) {
      /* ignore */
    }
    onError && onError(new Error(msg))
    return
  }
  if (!resp.body) {
    onError && onError(new Error('当前浏览器不支持流式读取'))
    return
  }

  const reader = resp.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''

  const parseLines = (chunk) => {
    buffer += chunk
    let idx
    while ((idx = buffer.indexOf('\n\n')) >= 0) {
      const raw = buffer.slice(0, idx)
      buffer = buffer.slice(idx + 2)
      let payload = null
      for (const line of raw.split('\n')) {
        const t = line.trim()
        if (t.startsWith('data:')) {
          try {
            payload = JSON.parse(t.slice(5).trim())
          } catch (_) {
            payload = null
          }
        }
      }
      if (payload) {
        if (payload.type === 'done') {
          onDone && onDone(payload)
        } else if (payload.type === 'error') {
          onError && onError(new Error(payload.message || '流式错误'))
        } else {
          onEvent && onEvent(payload)
        }
      }
    }
  }

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      parseLines(decoder.decode(value, { stream: true }))
    }
    parseLines(decoder.decode()) // 尾部
  } catch (e) {
    if (e.name !== 'AbortError') {
      onError && onError(e)
    }
  }
}