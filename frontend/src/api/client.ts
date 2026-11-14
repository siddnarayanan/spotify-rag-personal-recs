// Typed client for the FastAPI backend. Vite proxies /api and /auth to :8000.

export interface Track {
  id: string
  name: string
  artists: string[]
  album: string | null
  release_year: string | null
  url: string | null
  image: string | null
  played_at?: string
}

export interface Artist {
  id: string
  name: string
  genres: string[]
  url: string | null
  image: string | null
}

export interface Status {
  demo_mode: boolean
  spotify_configured: boolean
  authenticated: boolean
  llm_configured: boolean
  last_sync: string | null
  next_sync: string | null
  counts: { history?: number; saved_tracks?: number; playlists?: number }
}

export interface History {
  recent: Track[]
  top_artists: Artist[]
  top_tracks: Track[]
}

export interface Recommendation {
  title: string
  artist: string
  album: string | null
  reason: string
  evidence: string[]
  novelty: 'new_artist' | 'familiar_artist'
  spotify_url: string | null
  image_url: string | null
  verified: boolean
}

export interface ToolStatus {
  tool: string
  args: Record<string, unknown>
}

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail ?? `${res.status} ${res.statusText}`)
  }
  return res.json() as Promise<T>
}

export const api = {
  status: () => fetch('/api/status').then((r) => json<Status>(r)),
  history: (limit = 30) => fetch(`/api/history?limit=${limit}`).then((r) => json<History>(r)),
  sync: () => fetch('/api/sync', { method: 'POST' }).then((r) => json<{ ok: boolean }>(r)),
}

export type SSEHandler = (event: string, data: unknown) => void

/**
 * POST a JSON body and consume a Server-Sent-Events response.
 * (The browser EventSource API only supports GET, so we parse the stream manually.)
 */
export async function streamSSE(
  path: string,
  body: unknown,
  onEvent: SSEHandler,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
    body: JSON.stringify(body),
    signal,
  })
  if (!res.ok || !res.body) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail ?? `${res.status} ${res.statusText}`)
  }

  const reader = res.body.pipeThrough(new TextDecoderStream()).getReader()
  let buffer = ''
  for (;;) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += value
    const frames = buffer.split(/\r?\n\r?\n/)
    buffer = frames.pop() ?? ''
    for (const frame of frames) {
      let event = 'message'
      const data: string[] = []
      for (const line of frame.split(/\r?\n/)) {
        if (line.startsWith('event:')) event = line.slice(6).trim()
        else if (line.startsWith('data:')) data.push(line.slice(5).trimStart())
      }
      if (data.length) onEvent(event, JSON.parse(data.join('\n')))
    }
  }
}

/** Human-readable label for an agent tool call, shown while the agent works. */
export function describeTool({ tool, args }: ToolStatus): string {
  switch (tool) {
    case 'search_listening_history':
      return `Searching your history for “${String(args.query ?? '')}”`
    case 'get_listening_stats':
      return 'Reading your listening stats'
    case 'check_already_known': {
      const n = Array.isArray(args.candidates) ? args.candidates.length : 0
      return `Filtering out ${n} candidate${n === 1 ? '' : 's'} you might already know`
    }
    case 'lookup_spotify_track':
      return `Checking Spotify for “${String(args.title ?? '')}” by ${String(args.artist ?? '')}`
    case 'verify':
      return 'Attaching Spotify links'
    default:
      return tool
  }
}
