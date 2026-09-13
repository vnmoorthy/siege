import type {
  Attacker,
  Bounty,
  Breach,
  ChatResult,
  DefenderRun,
  Event,
  GateVersion,
  GateVersionSummary,
  LeaderRow,
  ProviderStatus,
  Round,
  Settings,
  State,
  Trace,
  Turn,
  WsMessage,
} from './types'

export const API_BASE = '/api'

// ---------------------------------------------------------------------------
// Transport layer. Real mode goes through fetch; mock mode (src/mock) swaps
// both the request transport and the socket factory so every page can run
// without a backend.
// ---------------------------------------------------------------------------

export type HttpMethod = 'GET' | 'POST'
export type Transport = (method: HttpMethod, path: string, body?: unknown) => Promise<unknown>

export type SocketHandlers = {
  onOpen: () => void
  onMessage: (msg: WsMessage) => void
  onClose: () => void
}
export type SocketHandle = { close: () => void }
export type SocketFactory = (handlers: SocketHandlers) => SocketHandle

export class ApiError extends Error {
  status: number
  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

async function readErrorMessage(res: Response): Promise<string> {
  const text = await res.text().catch(() => '')
  if (!text) return `${res.status} ${res.statusText}`.trim()
  try {
    const json = JSON.parse(text) as { detail?: unknown; error?: unknown; message?: unknown }
    const detail = json.detail ?? json.error ?? json.message
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) {
      // FastAPI validation errors
      return detail
        .map((d) => (typeof d === 'object' && d && 'msg' in d ? String((d as { msg: unknown }).msg) : JSON.stringify(d)))
        .join('; ')
    }
    if (detail != null) return JSON.stringify(detail)
  } catch {
    // not JSON
  }
  return text.slice(0, 300)
}

const fetchTransport: Transport = async (method, path, body) => {
  let res: Response
  try {
    res = await fetch(API_BASE + path, {
      method,
      headers: body !== undefined ? { 'Content-Type': 'application/json' } : undefined,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    })
  } catch (e) {
    throw new ApiError(e instanceof Error ? `Network error: ${e.message}` : 'Network error', 0)
  }
  if (!res.ok) throw new ApiError(await readErrorMessage(res), res.status)
  if (res.status === 204) return null
  const text = await res.text()
  return text ? JSON.parse(text) : null
}

export function wsUrl(): string {
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${proto}//${window.location.host}/ws`
}

const browserSocketFactory: SocketFactory = ({ onOpen, onMessage, onClose }) => {
  const ws = new WebSocket(wsUrl())
  let closed = false
  ws.onopen = () => onOpen()
  ws.onmessage = (ev) => {
    try {
      const parsed = JSON.parse(String(ev.data)) as WsMessage
      if (parsed && typeof parsed === 'object' && 'type' in parsed) onMessage(parsed)
    } catch {
      // ignore malformed frames
    }
  }
  ws.onerror = () => {
    // onclose follows an error; nothing else to do here
  }
  ws.onclose = () => {
    if (!closed) onClose()
  }
  return {
    close: () => {
      closed = true
      try {
        ws.close()
      } catch {
        // already closed
      }
    },
  }
}

let transport: Transport = fetchTransport
let socketFactory: SocketFactory = browserSocketFactory

export function setTransport(t: Transport | null): void {
  transport = t ?? fetchTransport
}
export function setSocketFactory(f: SocketFactory | null): void {
  socketFactory = f ?? browserSocketFactory
}
export function openSocket(handlers: SocketHandlers): SocketHandle {
  return socketFactory(handlers)
}

function get<T>(path: string): Promise<T> {
  return transport('GET', path) as Promise<T>
}
function post<T>(path: string, body?: unknown): Promise<T> {
  return transport('POST', path, body ?? {}) as Promise<T>
}

function qs(params: Record<string, string | number | undefined | null>): string {
  const entries = Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== '')
  if (entries.length === 0) return ''
  const sp = new URLSearchParams()
  for (const [k, v] of entries) sp.set(k, String(v))
  return `?${sp.toString()}`
}

// ---------------------------------------------------------------------------
// Typed client — one method per route in SPEC.md
// ---------------------------------------------------------------------------

export const api = {
  // Attacker
  join: (nickname: string) => post<Attacker>('/join', { nickname }),
  attacker: (id: string) => get<Attacker>(`/attackers/${encodeURIComponent(id)}`),
  chat: (attacker_id: string, message: string) => post<ChatResult>('/chat', { attacker_id, message }),
  history: (id: string) => get<{ turns: Turn[] }>(`/attackers/${encodeURIComponent(id)}/history`),
  bounties: () => get<{ bounties: Bounty[] }>('/bounties'),

  // War room / state
  state: () => get<State>('/state'),
  feed: (limit = 50) => get<{ events: Event[] }>(`/feed${qs({ limit })}`),
  leaderboard: () => get<{ rows: LeaderRow[] }>('/leaderboard'),
  rounds: () => get<{ rounds: Round[] }>('/rounds'),
  gateVersions: () => get<{ versions: GateVersionSummary[] }>('/gate/versions'),
  gateVersion: (v: number) => get<GateVersion>(`/gate/versions/${v}`),
  breaches: (limit = 100) => get<{ breaches: Breach[] }>(`/breaches${qs({ limit })}`),
  traces: (opts: { limit?: number; attack_id?: string } = {}) =>
    get<{ traces: Trace[] }>(`/traces${qs({ limit: opts.limit ?? 100, attack_id: opts.attack_id })}`),
  defenderRuns: () => get<{ runs: DefenderRun[] }>('/defender/runs'),
  providers: () => get<ProviderStatus>('/providers'),

  // Admin
  admin: {
    roundStart: () => post<Round>('/admin/round/start'),
    roundEnd: () => post<Round>('/admin/round/end'),
    defenderRun: () => post<DefenderRun>('/admin/defender/run'),
    settings: (patch: Partial<Settings>) => post<Settings>('/admin/settings', patch),
    simulate: (count: number, seconds: number) => post<{ started: true }>('/admin/simulate', { count, seconds }),
    simulateStop: () => post<{ stopped: true }>('/admin/simulate/stop'),
    reset: () => post<{ ok: true }>('/admin/reset'),
    rollback: (version: number) => post<GateVersionSummary>('/admin/gate/rollback', { version }),
  },
}

export type Api = typeof api
