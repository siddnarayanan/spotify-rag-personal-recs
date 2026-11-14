import { useRef, useState } from 'react'
import { describeTool, streamSSE, type ToolStatus } from '../api/client'

interface Message {
  role: 'user' | 'assistant'
  text: string
  tools: string[]
}

export function ChatPanel() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [running, setRunning] = useState(false)
  const threadId = useRef(crypto.randomUUID())

  const patchLast = (fn: (m: Message) => Message) =>
    setMessages((ms) => [...ms.slice(0, -1), fn(ms[ms.length - 1])])

  const send = async () => {
    const text = input.trim()
    if (!text || running) return
    setInput('')
    setRunning(true)
    setMessages((ms) => [
      ...ms,
      { role: 'user', text, tools: [] },
      { role: 'assistant', text: '', tools: [] },
    ])
    try {
      await streamSSE('/api/chat', { message: text, thread_id: threadId.current }, (ev, data) => {
        if (ev === 'token') patchLast((m) => ({ ...m, text: m.text + (data as { text: string }).text }))
        else if (ev === 'status')
          patchLast((m) => ({ ...m, tools: [...m.tools, describeTool(data as ToolStatus)] }))
        else if (ev === 'error')
          patchLast((m) => ({ ...m, text: `⚠️ ${(data as { message: string }).message}` }))
      })
    } catch (e) {
      patchLast((m) => ({ ...m, text: `⚠️ ${(e as Error).message}` }))
    } finally {
      setRunning(false)
    }
  }

  return (
    <section className="card chat">
      <h2>Ask about your taste</h2>
      <div className="messages">
        {messages.length === 0 && (
          <p className="muted small">
            Try “What have I been into this week?” or “Give me something like Frank Ocean but
            more upbeat”.
          </p>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`msg ${m.role}`}>
            {m.tools.length > 0 && (
              <ul className="tool-trace small muted">
                {m.tools.map((t, j) => (
                  <li key={j}>{t}</li>
                ))}
              </ul>
            )}
            <p>{m.text || (running && i === messages.length - 1 ? '…' : '')}</p>
          </div>
        ))}
      </div>
      <form
        className="row"
        onSubmit={(e) => {
          e.preventDefault()
          void send()
        }}
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask a follow-up…"
          maxLength={2000}
        />
        <button className="btn primary" type="submit" disabled={running || !input.trim()}>
          Send
        </button>
      </form>
    </section>
  )
}
