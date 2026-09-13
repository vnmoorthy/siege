import type { Event } from '../types'

export const MAX_EVENTS = 200

// Python timestamps may include microseconds that Date.parse truncates.
const fraction = (at: string) =>
  Number((at.match(/T\d{2}:\d{2}:\d{2}\.(\d+)/)?.[1] ?? '').padEnd(9, '0').slice(0, 9))

/** Reconcile live and catch-up events without moving old history above new data. */
export function mergeEvents(prev: Event[], incoming: readonly Event[]): Event[] {
  const unique = new Map<string, Event>()
  // Events are immutable; retain the existing object when history repeats it.
  for (const event of [...prev, ...incoming]) {
    if (!unique.has(event.id)) unique.set(event.id, event)
  }
  const merged = [...unique.values()]
    .sort((a, b) => {
      const aTime = Date.parse(a.at)
      const bTime = Date.parse(b.at)
      const timeOrder = (Number.isNaN(bTime) ? -Infinity : bTime)
        - (Number.isNaN(aTime) ? -Infinity : aTime)
      if (timeOrder && !Number.isNaN(timeOrder)) return timeOrder
      if (Number.isFinite(aTime) && Number.isFinite(bTime)) {
        const fractionOrder = fraction(b.at) - fraction(a.at)
        if (fractionOrder) return fractionOrder
      }
      // Stable across reconnect/batch arrival order when timestamps tie.
      return a.id < b.id ? -1 : a.id > b.id ? 1 : 0
    })
    .slice(0, MAX_EVENTS)
  return merged.length === prev.length && merged.every((event, i) => event === prev[i])
    ? prev
    : merged
}
