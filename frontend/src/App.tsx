import { useCallback, useEffect, useState } from 'react'
import { api, type History, type Status } from './api/client'
import { ChatPanel } from './components/ChatPanel'
import { ConnectSpotify } from './components/ConnectSpotify'
import { ListeningDashboard } from './components/ListeningDashboard'
import { RecommendPanel } from './components/RecommendPanel'
import { SyncStatus } from './components/SyncStatus'

export default function App() {
  const [status, setStatus] = useState<Status | null>(null)
  const [history, setHistory] = useState<History | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      const s = await api.status()
      setStatus(s)
      if (s.authenticated) setHistory(await api.history())
      setError(null)
    } catch (e) {
      setError(`Can't reach the backend (${(e as Error).message}). Is it running on :8000?`)
    }
  }, [])

  useEffect(() => {
    void load()
    // Right after connecting Spotify the first sync runs in the background, so poll briefly.
    if (new URLSearchParams(location.search).has('connected')) {
      window.history.replaceState(null, '', '/')
      const id = setInterval(() => void load(), 4000)
      setTimeout(() => clearInterval(id), 60000)
      return () => clearInterval(id)
    }
  }, [load])

  return (
    <div className="app">
      <header className="topbar">
        <div>
          <h1>Spotify RAG Recommender</h1>
          <p className="muted small">
            LangChain agent · retrieval over your cached listening history
          </p>
        </div>
        {status && <SyncStatus status={status} onSynced={load} />}
      </header>

      {error && <p className="error">{error}</p>}
      {status && !status.llm_configured && (
        <p className="notice">
          <code>ANTHROPIC_API_KEY</code> is not set, so recommendations and chat are disabled.
        </p>
      )}

      {status && !status.authenticated && <ConnectSpotify status={status} />}

      {status?.authenticated && (
        <main className="layout">
          <div className="col-main">
            <RecommendPanel />
            <ChatPanel />
          </div>
          <aside className="col-side">
            {history ? (
              <ListeningDashboard history={history} />
            ) : (
              <p className="muted">Loading history…</p>
            )}
          </aside>
        </main>
      )}
    </div>
  )
}
