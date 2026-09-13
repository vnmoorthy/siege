import { useCallback, useEffect, useRef, useState } from 'react'
import { api, openSocket } from '../api'
import type { Event, State, WsMessage } from '../types'

export const MAX_EVENTS = 200
const POLL_MS = 2000
const BACKOFF_MIN_MS = 1000
const BACKOFF_MAX_MS = 15000

export type Transport = 'ws' | 'poll' | 'connecting'

export type Siege = {
  state: State | null
  events: Event[]
  connected: boolean
  transport: Transport
  error: string | null
  /** Force an immediate refetch of state + feed (used after admin actions). */
  refresh: () => Promise<void>
}

function mergeEvents(prev: Event[], incoming: Event[]): Event[] {
  if (incoming.length === 0) return prev
  const seen = new Set(prev.map((e) => e.id))
  const fresh = incoming.filter((e) => !seen.has(e.id))
  if (fresh.length === 0) return prev
  // newest first
  fresh.sort((a, b) => (a.at < b.at ? 1 : a.at > b.at ? -1 : 0))
  return [...fresh, ...prev].slice(0, MAX_EVENTS)
}

/**
 * Live connection to SIEGE. Keeps the latest State and a rolling list of
 * Events (newest first, max 200). Uses the /ws socket when available,
 * reconnects with exponential backoff, and polls /api/state + /api/feed
 * every 2s while the socket is down.
 */
export function useSiege(): Siege {
  const [state, setState] = useState<State | null>(null)
  const [events, setEvents] = useState<Event[]>([])
  const [connected, setConnected] = useState(false)
  const [transport, setTransport] = useState<Transport>('connecting')
  const [error, setError] = useState<string | null>(null)

  const alive = useRef(true)
  const pollTimer = useRef<number | null>(null)
  const reconnectTimer = useRef<number | null>(null)
  const backoff = useRef(BACKOFF_MIN_MS)
  const socketRef = useRef<{ close: () => void } | null>(null)
  const wsUp = useRef(false)

  const refresh = useCallback(async () => {
    try {
      const [s, f] = await Promise.all([api.state(), api.feed(50)])
      if (!alive.current) return
      setState(s)
      setEvents((prev) => mergeEvents(prev, f.events))
      setError(null)
    } catch (e) {
      if (!alive.current) return
      setError(e instanceof Error ? e.message : String(e))
    }
  }, [])

  useEffect(() => {
    alive.current = true

    const stopPolling = () => {
      if (pollTimer.current !== null) {
        window.clearInterval(pollTimer.current)
        pollTimer.current = null
      }
    }
    const startPolling = () => {
      if (pollTimer.current !== null) return
      setTransport('poll')
      void refresh()
      pollTimer.current = window.setInterval(() => {
        if (!wsUp.current) void refresh()
      }, POLL_MS)
    }

    const scheduleReconnect = () => {
      if (!alive.current || reconnectTimer.current !== null) return
      const delay = backoff.current
      backoff.current = Math.min(BACKOFF_MAX_MS, Math.round(backoff.current * 1.8))
      reconnectTimer.current = window.setTimeout(() => {
        reconnectTimer.current = null
        connect()
      }, delay)
    }

    const connect = () => {
      if (!alive.current) return
      socketRef.current?.close()
      socketRef.current = openSocket({
        onOpen: () => {
          if (!alive.current) return
          wsUp.current = true
          backoff.current = BACKOFF_MIN_MS
          setConnected(true)
          setTransport('ws')
          setError(null)
          stopPolling()
          // Sync once on (re)connect so we never show stale data.
          void refresh()
        },
        onMessage: (msg: WsMessage) => {
          if (!alive.current) return
          if (msg.type === 'state') {
            setState(msg.state)
          } else {
            setEvents((prev) => mergeEvents(prev, [msg]))
          }
        },
        onClose: () => {
          if (!alive.current) return
          wsUp.current = false
          setConnected(false)
          startPolling()
          scheduleReconnect()
        },
      })
    }

    // First paint: fetch immediately, then open the socket.
    Promise.all([api.state(), api.feed(50)])
      .then(([s, f]) => {
        if (!alive.current) return
        setState(s)
        setEvents((prev) => mergeEvents(prev, f.events))
        setError(null)
      })
      .catch((e: unknown) => alive.current && setError(e instanceof Error ? e.message : String(e)))
    connect()

    return () => {
      alive.current = false
      wsUp.current = false
      stopPolling()
      if (reconnectTimer.current !== null) {
        window.clearTimeout(reconnectTimer.current)
        reconnectTimer.current = null
      }
      socketRef.current?.close()
      socketRef.current = null
    }
  }, [refresh])

  return { state, events, connected, transport, error, refresh }
}
