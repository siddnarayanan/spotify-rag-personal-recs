import type { Recommendation } from '../api/client'

export function RecommendationCard({ rec }: { rec: Recommendation }) {
  return (
    <article className="rec-card">
      {rec.image_url ? (
        <img className="rec-art" src={rec.image_url} alt={`${rec.album ?? rec.title} cover`} />
      ) : (
        <div className="rec-art art-placeholder" aria-hidden />
      )}
      <div className="rec-body">
        <header>
          <h4>{rec.title}</h4>
          <span className="muted">
            {rec.artist}
            {rec.album ? ` · ${rec.album}` : ''}
          </span>
        </header>
        <span className={`tag ${rec.novelty}`}>
          {rec.novelty === 'new_artist' ? 'New artist' : 'Deep cut'}
        </span>
        <p>{rec.reason}</p>
        {rec.evidence.length > 0 && (
          <p className="evidence small">
            <span className="muted">Because you listened to </span>
            {rec.evidence.join(', ')}
          </p>
        )}
        {rec.spotify_url && (
          <a className="btn ghost small" href={rec.spotify_url} target="_blank" rel="noreferrer">
            {rec.verified ? 'Open in Spotify' : 'Search on Spotify'}
          </a>
        )}
      </div>
    </article>
  )
}
