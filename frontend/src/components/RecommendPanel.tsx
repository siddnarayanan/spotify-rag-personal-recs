import { useRef, useState } from 'react'
import { describeTool, streamSSE, type Recommendation, type ToolStatus } from '../api/client'
import { RecommendationCard } from './RecommendationCard'

export function RecommendPanel() {
  const [prompt, setPrompt] = useState('')
  const [steps, setSteps] = useState<string[]>([])
  const [summary, setSummary] = useState<string | null>(null)
  const [recs, setRecs] = useState<Recommendation[]>([])
  const [error, setError] = useState<string | null>(null)
  const [running, setRunning] = useState(false)
  const abort = useRef<AbortController | null>(null)

  const run = async () => {
    abort.current?.abort()
    const ctrl = new AbortController()
    abort.current = ctrl
    setRunning(true)
    setSteps([])
    setSummary(null)
    setRecs([])
    setError(null)
    try {
      await streamSSE(
        '/api/recommend',
        { prompt: prompt.trim() || null, count: 8 },
        (event, data) => {
          if (event === 'status') setSteps((s) => [...s, describeTool(data as ToolStatus)])
          else if (event === 'summary') setSummary((data as { summary: string }).summary)
          else if (event === 'recommendation') setRecs((r) => [...r, data as Recommendation])
          else if (event === 'error') setError((data as { message: string }).message)
        },
        ctrl.signal,
      )
    } catch (e) {
      if ((e as Error).name !== 'AbortError') setError((e as Error).message)
    } finally {
      setRunning(false)
    }
  }

  return (
    <section className="card">
      <h2>Recommendations</h2>
      <form
        className="row"
        onSubmit={(e) => {
          e.preventDefault()
          void run()
        }}
      >
        <input
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder="Optional: a mood or vibe, e.g. “rainy-day focus”"
          maxLength={500}
        />
        <button className="btn primary" type="submit" disabled={running}>
          {running ? 'Thinking…' : 'Get recommendations'}
        </button>
      </form>

      {steps.length > 0 && (
        <ol className={`steps ${running ? 'live' : ''}`} aria-live="polite">
          {steps.map((s, i) => (
            <li key={i}>{s}</li>
          ))}
        </ol>
      )}
      {error && <p className="error">{error}</p>}
      {summary && <p className="summary">{summary}</p>}
      <div className="rec-grid">
        {recs.map((r) => (
          <RecommendationCard key={`${r.title}-${r.artist}`} rec={r} />
        ))}
      </div>
    </section>
  )
}
