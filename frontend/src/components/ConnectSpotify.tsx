import type { Status } from '../api/client'

export function ConnectSpotify({ status }: { status: Status }) {
  return (
    <section className="card connect">
      <h2>Connect your Spotify</h2>
      <p className="muted">
        The agent reads your recent plays, top artists and liked songs. That data is cached
        locally and refreshed once a day, so Spotify's API is hit as rarely as possible.
      </p>
      {status.spotify_configured ? (
        <a className="btn primary" href="/auth/login">
          Connect Spotify
        </a>
      ) : (
        <p className="notice">
          Set <code>SPOTIFY_CLIENT_ID</code> and <code>SPOTIFY_CLIENT_SECRET</code> in{' '}
          <code>backend/.env</code>, or run with <code>DEMO_MODE=true</code> to try the sample
          dataset.
        </p>
      )}
    </section>
  )
}
