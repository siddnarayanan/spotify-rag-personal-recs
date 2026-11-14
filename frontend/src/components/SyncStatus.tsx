import { useState } from 'react'
import { api, type Status } from '../api/client'

function relative(iso: string): string {
  const mins = Math.round((Date.now() - new Date(iso).getTime()) / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins} min ago`
  const hrs = Math.round(mins / 60)
  return hrs < 24 ? `${hrs} h ago` : `${Math.round(hrs / 24)} d ago`
}

export function SyncStatus({ status, onSynced }: { status: Status; onSynced: () => void }) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const sync = async () => {
    setBusy(true)
    setError(null)
    try {
      await api.sync()
      onSynced()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="sync-status">
      {status.demo_mode ? (
        <span className="badge">Demo data</span>
      ) : (
        <>
          <span className="muted small">
            {status.last_sync ? `Synced ${relative(status.last_sync)}` : 'Not synced yet'}
          </span>
          {status.authenticated && (
            <button className="btn ghost small" onClick={sync} disabled={busy}>
              {busy ? 'Syncing…' : 'Sync now'}
            </button>
          )}
        </>
      )}
      {error && <span className="error small">{error}</span>}
    </div>
  )
}
