import type { History } from '../api/client'

function timeAgo(iso?: string): string {
  if (!iso) return ''
  const d = new Date(iso)
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

export function ListeningDashboard({ history }: { history: History }) {
  return (
    <section className="card dashboard">
      <h2>Your listening</h2>

      <h3>Top artists · last 4 weeks</h3>
      <ul className="chips">
        {history.top_artists.map((a) => (
          <li key={a.id} className="chip" title={a.genres.join(', ')}>
            {a.name}
          </li>
        ))}
      </ul>

      <h3>Recently played</h3>
      <ol className="track-list">
        {history.recent.map((t) => (
          <li key={`${t.id}-${t.played_at}`}>
            {t.image ? <img src={t.image} alt="" /> : <div className="art-placeholder" />}
            <div className="track-meta">
              <span className="track-title" title={t.name}>
                {t.name}
              </span>
              <span className="muted small">{t.artists.join(', ')}</span>
            </div>
            <span className="muted small track-date">{timeAgo(t.played_at)}</span>
          </li>
        ))}
      </ol>
    </section>
  )
}
