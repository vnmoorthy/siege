import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import ts from 'typescript'
import { MAX_EVENTS, mergeEvents } from '../src/lib/events.ts'

const event = (id, at = '2026-09-13T12:00:00Z') => ({ id, at, type: 'attack', round: 1, text: id })

test('reconnect history stays behind newer live events and batches deduplicate', () => {
  const live = event('live', '2026-09-13T12:03:00Z')
  const old = event('old', '2026-09-13T12:01:00Z')
  const older = event('older', '2026-09-13T12:00:00Z')
  const result = mergeEvents([live, old, old], [older, older, { ...live }])
  assert.deepEqual(result.map((e) => e.id), ['live', 'old', 'older'])
  assert.equal(result[0], live)
})

test('ordering compares timestamps across UTC offsets', () => {
  const earlier = event('earlier', '2026-09-13T13:00:00+02:00')
  const later = event('later', '2026-09-13T12:00:00Z')
  assert.deepEqual(mergeEvents([earlier], [later]).map((e) => e.id), ['later', 'earlier'])
})

test('equal timestamps have deterministic ordering across batch boundaries', () => {
  assert.deepEqual(mergeEvents([event('z')], [event('a')]), mergeEvents([event('a')], [event('z')]))
})

test('chronology retains backend microsecond precision within one millisecond', () => {
  const earlier = event('a', '2026-09-13T12:00:00.123001+00:00')
  const later = event('z', '2026-09-13T12:00:00.123999Z')
  assert.deepEqual(mergeEvents([earlier], [later]).map((e) => e.id), ['z', 'a'])
})

test('cap is applied after global sorting so catch-up cannot evict newest live events', () => {
  const batch = Array.from({ length: 250 }, (_, i) => event(String(i), new Date(i * 1000).toISOString()))
  const live = event('live', new Date(999_000).toISOString())
  const result = mergeEvents([live], batch)
  assert.equal(result.length, MAX_EVENTS)
  assert.equal(result[0], live)
  assert.equal(result.at(-1).id, '51')
})

test('duplicate-only refresh preserves identity and never mutates input', () => {
  const previous = Object.freeze([event('a')])
  const incoming = Object.freeze([{ ...previous[0] }, { ...previous[0] }])
  assert.equal(mergeEvents(previous, incoming), previous)
  assert.equal(incoming.length, 2)
})

test('malformed timestamps fall behind dated events without breaking sort', () => {
  assert.deepEqual(mergeEvents([event('bad', 'invalid')], [event('good')]).map((e) => e.id), ['good', 'bad'])
})

// Execute the real hook with controlled React primitives and transport callbacks.
// No DOM or third-party test framework is needed for its connection lifecycle.
function mountHook({ failInitial = false } = {}) {
  const state = []
  const intervals = new Map()
  const timeouts = new Map()
  const calls = []
  let effect, handlers, cleanup, timerId = 0, closed = false, fetchCount = 0
  const oldWindow = globalThis.window
  globalThis.window = {
    setInterval: (fn) => { intervals.set(++timerId, fn); return timerId },
    clearInterval: (id) => intervals.delete(id),
    setTimeout: (fn) => { timeouts.set(++timerId, fn); return timerId },
    clearTimeout: (id) => timeouts.delete(id),
  }
  const react = {
    useState: (initial) => {
      const index = state.length
      state.push(initial)
      return [initial, (next) => { state[index] = typeof next === 'function' ? next(state[index]) : next }]
    },
    useRef: (current) => ({ current }),
    useCallback: (fn) => fn,
    useEffect: (fn) => { effect = fn },
  }
  const api = {
    state: async () => {
      calls.push('state')
      if (failInitial && fetchCount++ === 0) throw new Error('temporarily offline')
      return { gate_version: 1 }
    },
    feed: async (limit) => { calls.push(`feed:${limit}`); return { events: [event('history')] } },
  }
  const socket = {
    api,
    openSocket: (callbacks) => {
      calls.push('socket')
      handlers = callbacks
      return { close: () => { closed = true } }
    },
  }
  const source = readFileSync(new URL('../src/hooks/useSiege.ts', import.meta.url), 'utf8')
  const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2023 } }).outputText
  const module = { exports: {} }
  const requireMock = (name) => {
    if (name === 'react') return react
    if (name === '../api') return socket
    if (name === '../lib/events') return { MAX_EVENTS, mergeEvents }
    throw new Error(`Unexpected import ${name}`)
  }
  new Function('require', 'exports', 'module', compiled)(requireMock, module.exports, module)
  module.exports.useSiege()
  cleanup = effect()
  return {
    state, intervals, timeouts, calls, handlers,
    tick: () => [...intervals.values()].forEach((fn) => fn()),
    unmount: () => { cleanup(); globalThis.window = oldWindow; assert.equal(closed, true) },
  }
}

const flush = () => new Promise((resolve) => setImmediate(resolve))

test('polling starts before a stalled handshake and retries a failed first paint', async () => {
  const hook = mountHook({ failInitial: true })
  try {
    assert.deepEqual(hook.calls.slice(0, 3), ['state', 'feed:200', 'socket'])
    assert.equal(hook.intervals.size, 1)
    await flush()
    assert.match(hook.state[4], /temporarily offline/)
    hook.tick()
    await flush()
    assert.equal(hook.state[0].gate_version, 1)
    assert.equal(hook.state[4], null)
    assert.equal(hook.state[3], 'poll')
  } finally { hook.unmount() }
})

test('socket open stops polling, catch-up preserves live ordering, close resumes polling', async () => {
  const hook = mountHook()
  try {
    await flush()
    hook.handlers.onMessage(event('live', '2026-09-13T12:03:00Z'))
    hook.handlers.onOpen()
    assert.equal(hook.intervals.size, 0)
    await flush()
    assert.deepEqual(hook.state[1].map((e) => e.id), ['live', 'history'])
    assert.equal(hook.state[2], true)
    assert.equal(hook.state[3], 'ws')
    hook.handlers.onClose()
    assert.equal(hook.intervals.size, 1)
    assert.equal(hook.timeouts.size, 1)
    assert.equal(hook.state[2], false)
  } finally { hook.unmount() }
  assert.equal(hook.intervals.size, 0)
  assert.equal(hook.timeouts.size, 0)
})
