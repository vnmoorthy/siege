import clsx from 'clsx'
import { AlertTriangle, Bot, ChevronDown, ChevronRight, ExternalLink, Loader2, Monitor, Play, RefreshCw, RotateCcw, Save, Search, Square, Swords, Trash2, Wrench } from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import { Chip } from '../components/Chip'
import { ConnChip } from '../components/ConnChip'
import { CountdownRing } from '../components/CountdownRing'
import { GateBadge } from '../components/GateBadge'
import { Panel } from '../components/Panel'
import { StageStepper } from '../components/StageStepper'
import { useToast } from '../components/toastContext'
import { useSiege } from '../hooks/useSiege'
import { int, pct, shortDate } from '../lib/format'
import { href } from '../lib/mockFlag'
import type { DefenderRun, GateVersion, GateVersionSummary, Settings, State, Trace } from '../types'

// ---------------------------------------------------------------------------
// small primitives
// ---------------------------------------------------------------------------

function Button({ children, tone = 'neutral', busy, className, ...rest }: { children: ReactNode; tone?: 'neutral' | 'red' | 'green' | 'blue' | 'amber'; busy?: boolean } & React.ButtonHTMLAttributes<HTMLButtonElement>) {
  const tones = {
    neutral: 'border-white/10 bg-white/[0.05] text-fg hover:bg-white/[0.09]',
    red: 'border-breach/50 bg-breach/15 text-breach hover:bg-breach/25',
    green: 'border-allow/50 bg-allow/15 text-allow hover:bg-allow/25',
    blue: 'border-blue/50 bg-blue/15 text-blue hover:bg-blue/25',
    amber: 'border-block/50 bg-block/15 text-block hover:bg-block/25',
  }
  return (
    <button {...rest} disabled={rest.disabled || busy} className={clsx('inline-flex h-9 items-center justify-center gap-1.5 rounded-md border px-3 text-xs font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-40', tones[tone], className)}>
      {busy ? <Loader2 size={13} className="animate-spin" /> : null}
      {children}
    </button>
  )
}

function Field({ label, children, hint }: { label: string; children: ReactNode; hint?: string }) {
  return (
    <label className="block">
      <span className="text-[11px] font-medium text-fg-2">{label}</span>
      <div className="mt-1">{children}</div>
      {hint && <span className="mt-0.5 block text-[10px] text-fg-3">{hint}</span>}
    </label>
  )
}

const inputCls = 'num h-9 w-full rounded-md border border-white/10 bg-black/30 px-2.5 text-sm outline-none focus:border-blue/60 disabled:opacity-50'

function useAsync() {
  const toast = useToast()
  const [busy, setBusy] = useState<string | null>(null)
  const run = useCallback(
    async <T,>(key: string, fn: () => Promise<T>, okMessage?: string | ((r: T) => string)): Promise<T | undefined> => {
      setBusy(key)
      try {
        const r = await fn()
        if (okMessage) toast.success(typeof okMessage === 'function' ? okMessage(r) : okMessage)
        return r
      } catch (e) {
        toast.error(e instanceof Error ? e.message : String(e))
        return undefined
      } finally {
        setBusy(null)
      }
    },
    [toast],
  )
  return { busy, run }
}

function JsonBlock({ value, className }: { value: unknown; className?: string }) {
  return <pre className={clsx('scroll-thin max-h-72 overflow-auto rounded-md bg-black/40 p-2.5 text-[11px] leading-snug text-fg-2', className)}>{JSON.stringify(value, null, 2)}</pre>
}

// ---------------------------------------------------------------------------
// cards
// ---------------------------------------------------------------------------

function RoundCard({ state, refresh }: { state: State; refresh: () => Promise<void> }) {
  const { busy, run } = useAsync()
  const r = state.round
  const live = r?.status === 'live'
  const lastRound = state.series.length ? state.series[state.series.length - 1].round : null
  const defending = state.defender !== null && state.defender.ended_at === null && state.defender.stage !== 'idle'
  const everRan = r !== null || lastRound !== null
  return (
    <Panel title="Round" right={live ? <Chip tone="red" size="xs" dot pulse>LIVE</Chip> : defending ? <Chip tone="blue" size="xs" dot pulse>defending</Chip> : everRan ? <Chip size="xs">between rounds</Chip> : <Chip size="xs">none</Chip>}>
      <div className="flex items-center gap-4">
        <CountdownRing secondsLeft={state.current_round.seconds_left} total={r?.seconds ?? state.settings.round_seconds} size={64} live={live} />
        <div className="flex-1">
          <div className="num text-3xl font-bold leading-none">{r ? `R${r.number}` : lastRound !== null ? `R${lastRound}` : '—'}</div>
          <div className="num mt-1 text-xs text-fg-2">
            {int(state.current_round.attacks)} attacks · <span className="text-breach">{int(state.current_round.breaches)} breaches</span> · {pct(state.current_round.breach_rate)} · benign {pct(state.current_round.benign_allow_rate)}
          </div>
          {r && <div className="num mt-0.5 text-[10px] text-fg-3">gate v{r.gate_version_start}{r.gate_version_end !== null ? ` → v${r.gate_version_end}` : ''} · started {shortDate(r.started_at)}</div>}
        </div>
      </div>
      <div className="mt-4 flex gap-2">
        <Button tone="green" disabled={live || defending} title={defending ? 'Wait for the defender to finish' : undefined} busy={busy === 'start'} onClick={() => void run('start', () => api.admin.roundStart(), (x) => `Round ${x.number} started`).then(() => refresh())}>
          <Play size={13} /> Start round
        </Button>
        <Button tone="amber" disabled={!live} busy={busy === 'end'} onClick={() => void run('end', () => api.admin.roundEnd(), (x) => `Round ${x.number} ended${state.settings.auto_defend ? ' — defender running' : ''}`).then(() => refresh())}>
          <Square size={13} /> End round
        </Button>
      </div>
      {!r && !everRan && <p className="mt-3 text-xs text-fg-3">No round has run yet. Start one to open the chat for attackers.</p>}
      {!r && everRan && <p className="mt-3 text-xs text-fg-3">{defending ? 'Between rounds — the defender is patching the gate. The next round can start when it finishes.' : 'Between rounds. Start the next round when you are ready.'}</p>}
    </Panel>
  )
}

function SettingsCard({ settings, refresh }: { settings: Settings; refresh: () => Promise<void> }) {
  const { busy, run } = useAsync()
  const [edits, setEdits] = useState<Partial<Settings>>({})
  const form: Settings = { ...settings, ...edits }
  const dirty = (Object.keys(edits) as (keyof Settings)[]).some((k) => edits[k] !== settings[k])
  const set = <K extends keyof Settings>(k: K, v: Settings[K]) => setEdits((e) => ({ ...e, [k]: v }))
  const submit = async (e: FormEvent) => {
    e.preventDefault()
    const patch: Partial<Settings> = {}
    for (const k of Object.keys(form) as (keyof Settings)[]) if (form[k] !== settings[k]) (patch as Record<string, unknown>)[k] = form[k]
    if (Object.keys(patch).length === 0) {
      setEdits({})
      return
    }
    const saved = await run('settings', () => api.admin.settings(patch), 'Settings saved')
    if (saved) {
      setEdits({})
      await refresh()
    }
  }
  return (
    <Panel title="Settings" right={dirty ? <Chip tone="amber" size="xs">unsaved</Chip> : null}>
      <form onSubmit={submit} className="grid grid-cols-2 gap-3">
        <Field label="Round seconds">
          <input type="number" min={15} max={900} className={inputCls} value={form.round_seconds} onChange={(e) => set('round_seconds', Number(e.target.value))} />
        </Field>
        <Field label="Benign floor" hint="ship only if benign allow ≥ floor">
          <input type="number" min={0.5} max={1} step={0.01} className={inputCls} value={form.benign_floor} onChange={(e) => set('benign_floor', Number(e.target.value))} />
        </Field>
        <Field label="Max attempts">
          <input type="number" min={1} max={5} className={inputCls} value={form.max_attempts} onChange={(e) => set('max_attempts', Number(e.target.value))} />
        </Field>
        <Field label="Variants per breach">
          <input type="number" min={0} max={10} className={inputCls} value={form.variants_per_breach} onChange={(e) => set('variants_per_breach', Number(e.target.value))} />
        </Field>
        <label className="col-span-2 flex items-center justify-between rounded-md border border-white/10 bg-black/20 px-3 py-2">
          <span>
            <span className="block text-xs font-medium">Auto-defend</span>
            <span className="block text-[10px] text-fg-3">Run the defender automatically when a round ends</span>
          </span>
          <button
            type="button"
            role="switch"
            aria-checked={form.auto_defend}
            onClick={() => set('auto_defend', !form.auto_defend)}
            className={clsx('relative h-6 w-11 rounded-full transition-colors', form.auto_defend ? 'bg-allow' : 'bg-white/15')}
          >
            <span className={clsx('absolute top-0.5 h-5 w-5 rounded-full bg-white transition-all', form.auto_defend ? 'left-[22px]' : 'left-0.5')} />
          </button>
        </label>
        <div className="col-span-2 flex justify-end gap-2">
          <Button type="button" disabled={!dirty} onClick={() => setEdits({})}>
            Revert
          </Button>
          <Button type="submit" tone="blue" disabled={!dirty} busy={busy === 'settings'}>
            <Save size={13} /> Save
          </Button>
        </div>
      </form>
    </Panel>
  )
}

function DefenderCard({ state, refresh }: { state: State; refresh: () => Promise<void> }) {
  const { busy, run } = useAsync()
  const [runs, setRuns] = useState<DefenderRun[]>([])
  const logRef = useRef<HTMLDivElement>(null)
  const current = state.defender
  const running = current !== null && current.ended_at === null && current.stage !== 'idle'
  const loadRuns = useCallback(() => api.defenderRuns().then((r) => setRuns(r.runs)).catch(() => {}), [])
  useEffect(() => {
    void loadRuns()
  }, [loadRuns, current?.id, current?.stage])
  useEffect(() => {
    const el = logRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [current?.log.length])
  return (
    <Panel
      title="Defender"
      right={
        <>
          {current && (
            <Chip size="xs" tone={current.stage === 'shipped' ? 'green' : current.stage === 'rejected' || current.stage === 'failed' ? 'red' : running ? 'blue' : 'neutral'} dot pulse={running}>
              {current.stage}
            </Chip>
          )}
          <Button tone="blue" busy={busy === 'run'} disabled={running || state.round?.status === 'live'} title={state.round?.status === 'live' ? 'End the round first' : 'Run the defender on new breaches now'} onClick={() => void run('run', () => api.admin.defenderRun(), (x) => `Defender run ${x.id} started on ${x.breaches_considered} breaches`).then(() => refresh())}>
            <Wrench size={13} /> Run now
          </Button>
        </>
      }
    >
      <StageStepper stage={current?.stage} compact />
      {current ? (
        <div className="mt-4 grid gap-3 lg:grid-cols-[1fr_1.2fr]">
          <div className="space-y-2 text-xs">
            <div className="num grid grid-cols-3 gap-2">
              <div className="rounded-md bg-white/[0.03] px-2.5 py-1.5">
                <div className="text-[10px] text-fg-3">breaches</div>
                <div className="text-sm font-semibold text-breach">{current.breaches_considered}</div>
              </div>
              <div className="rounded-md bg-white/[0.03] px-2.5 py-1.5">
                <div className="text-[10px] text-fg-3">variants</div>
                <div className="text-sm font-semibold">{current.variants_generated}</div>
              </div>
              <div className="rounded-md bg-white/[0.03] px-2.5 py-1.5">
                <div className="text-[10px] text-fg-3">shipped</div>
                <div className={clsx('text-sm font-semibold', current.shipped_version ? 'text-allow' : 'text-fg-3')}>{current.shipped_version ? `v${current.shipped_version}` : '—'}</div>
              </div>
            </div>
            {current.attempts.length > 0 && (
              <table className="num w-full text-[11px]">
                <thead className="text-left text-fg-3">
                  <tr>
                    <th className="pb-1 pr-3 font-medium">#</th>
                    <th className="pb-1 pr-3 font-medium">catch</th>
                    <th className="pb-1 pr-3 font-medium">benign</th>
                    <th className="pb-1 pr-3 font-medium">n</th>
                    <th className="pb-1 font-medium">verdict</th>
                  </tr>
                </thead>
                <tbody>
                  {current.attempts.map((a) => (
                    <tr key={a.n} className="border-t border-white/[0.05] align-top">
                      <td className="py-1 pr-3 text-fg-2">{a.n}</td>
                      <td className="whitespace-nowrap py-1 pr-3 text-blue">{pct(a.eval.catch_rate)} <span className="text-fg-3">← {pct(a.eval.prev_catch_rate)}</span></td>
                      <td className={clsx('py-1 pr-3', a.eval.benign_allow_rate >= state.settings.benign_floor ? 'text-allow' : 'text-breach')}>{pct(a.eval.benign_allow_rate)}</td>
                      <td className="whitespace-nowrap py-1 pr-3 text-fg-3">{a.eval.n_attacks}/{a.eval.n_benign}</td>
                      <td className={clsx('py-1 font-sans', a.eval.passed ? 'text-allow' : 'text-breach')}>
                        {a.verdict}
                        {a.eval.weave_url && (
                          <a href={a.eval.weave_url} target="_blank" rel="noreferrer" className="ml-1 inline-flex items-center text-fg-3 hover:text-fg" title="Open Weave evaluation">
                            <ExternalLink size={10} />
                          </a>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
            <div className="num text-[10px] text-fg-3">
              run {current.id} · round {current.round} · started {shortDate(current.started_at)}{current.ended_at ? ` · ended ${shortDate(current.ended_at)}` : ''}
            </div>
          </div>
          <div ref={logRef} className="scroll-thin num max-h-56 min-h-[120px] overflow-auto rounded-md bg-black/40 p-2.5 text-[11px] leading-relaxed text-fg-2">
            {current.log.length === 0 ? <span className="text-fg-3">log is empty</span> : current.log.map((l, i) => (
              <div key={i} className={clsx(i === current.log.length - 1 && running && 'text-fg')}>
                <span className="text-fg-3">{String(i + 1).padStart(2, '0')}</span> {l}
              </div>
            ))}
            {running && <div className="animate-pulse text-blue">▍</div>}
          </div>
        </div>
      ) : (
        <p className="mt-4 text-xs text-fg-3">No defender run yet. It runs automatically after a round with breaches (auto-defend), or press Run now between rounds.</p>
      )}
      {runs.length > 1 && (
        <details className="mt-3 text-xs">
          <summary className="cursor-pointer text-fg-3 hover:text-fg">Previous runs ({runs.length - 1})</summary>
          <ul className="num mt-2 space-y-1">
            {runs.filter((r) => r.id !== current?.id).slice(0, 8).map((r) => (
              <li key={r.id} className="flex items-center gap-2 text-[11px]">
                <span className="text-fg-3">R{r.round}</span>
                <Chip size="xs" tone={r.stage === 'shipped' ? 'green' : r.stage === 'rejected' ? 'red' : 'neutral'}>{r.stage}</Chip>
                <span className="text-fg-2">{r.breaches_considered} breaches · {r.attempts.length} attempts{r.shipped_version ? ` · v${r.shipped_version}` : ''}</span>
                <span className="ml-auto text-fg-3">{shortDate(r.started_at)}</span>
              </li>
            ))}
          </ul>
        </details>
      )}
    </Panel>
  )
}

function SimulateCard({ refresh }: { refresh: () => Promise<void> }) {
  const { busy, run } = useAsync()
  const [count, setCount] = useState(12)
  const [seconds, setSeconds] = useState(180)
  const [active, setActive] = useState(false)
  return (
    <Panel title="Simulate attackers" right={active ? <Chip tone="blue" size="xs" dot pulse>running</Chip> : null}>
      <p className="mb-3 text-xs text-fg-3">Synthetic attackers use the red-team corpus and are labeled as bots on the leaderboard.</p>
      <div className="grid grid-cols-2 gap-3">
        <Field label="Count">
          <input type="number" min={1} max={200} className={inputCls} value={count} onChange={(e) => setCount(Number(e.target.value))} />
        </Field>
        <Field label="Seconds">
          <input type="number" min={5} max={3600} className={inputCls} value={seconds} onChange={(e) => setSeconds(Number(e.target.value))} />
        </Field>
      </div>
      <div className="mt-3 flex gap-2">
        <Button tone="blue" busy={busy === 'sim'} onClick={() => void run('sim', () => api.admin.simulate(count, seconds), `Simulating ${count} attackers for ${seconds}s`).then((r) => { if (r) setActive(true); return refresh() })}>
          <Bot size={13} /> Start
        </Button>
        <Button busy={busy === 'stop'} onClick={() => void run('stop', () => api.admin.simulateStop(), 'Simulation stopped').then((r) => { if (r) setActive(false); return refresh() })}>
          <Square size={13} /> Stop
        </Button>
      </div>
    </Panel>
  )
}

function DangerCard({ versions, current, refresh }: { versions: GateVersionSummary[]; current: number; refresh: () => Promise<void> }) {
  const { busy, run } = useAsync()
  const [confirm, setConfirm] = useState(false)
  const [picked, setPicked] = useState<number | null>(null)
  const target = picked ?? current
  const selectable = versions.filter((v) => v.status !== 'rejected')
  return (
    <Panel title="Gate rollback · reset">
      <Field label="Active gate version" hint="Rejected candidates cannot be activated.">
        <div className="flex gap-2">
          <select className={clsx(inputCls, 'flex-1')} value={target} onChange={(e) => setPicked(Number(e.target.value))}>
            {selectable.map((v) => (
              <option key={v.version} value={v.version}>
                v{v.version} · {v.status}{v.catch_rate !== null ? ` · catch ${pct(v.catch_rate)}` : ''}{v.version === current ? ' (active)' : ''}
              </option>
            ))}
          </select>
          <Button tone="amber" disabled={target === current} busy={busy === 'rb'} onClick={() => void run('rb', () => api.admin.rollback(target), (v) => `Gate rolled back to v${v.version}`).then(() => refresh())}>
            <RotateCcw size={13} /> Rollback
          </Button>
        </div>
      </Field>
      <div className="mt-4 rounded-md border border-breach/30 bg-breach/[0.04] p-3">
        <div className="flex items-center gap-1.5 text-xs font-semibold text-breach">
          <AlertTriangle size={13} /> Reset the siege
        </div>
        <p className="mt-1 text-[11px] text-fg-3">Wipes attacks, breaches, rounds and every gate version above v1. Keeps the store and personas.</p>
        <div className="mt-2 flex gap-2">
          {!confirm ? (
            <Button tone="red" onClick={() => setConfirm(true)}>
              <Trash2 size={13} /> Reset…
            </Button>
          ) : (
            <>
              <Button tone="red" busy={busy === 'reset'} onClick={() => void run('reset', () => api.admin.reset(), 'Siege reset').then(() => { setConfirm(false); return refresh() })}>
                <Trash2 size={13} /> Yes, wipe everything
              </Button>
              <Button onClick={() => setConfirm(false)}>Cancel</Button>
            </>
          )}
        </div>
      </div>
    </Panel>
  )
}

function ProvidersCard({ state }: { state: State }) {
  const p = state.providers
  const rows = [
    { role: 'Agent', provider: p.agent.provider, model: p.agent.model, live: p.agent.live },
    { role: 'Gate', provider: p.gate.provider, model: p.gate.model, live: p.gate.live },
    { role: 'Defender', provider: p.defender.provider, model: p.defender.model, live: p.defender.live },
    { role: 'Red team', provider: p.redteam.provider, model: p.redteam.model, live: p.redteam.live },
    { role: 'Weave', provider: 'wandb', model: p.weave.project, live: p.weave.live, url: p.weave.url },
    { role: 'Sandbox', provider: p.sandbox.provider, model: p.sandbox.provider === 'wandb' ? 'W&B sandbox' : 'local subprocess', live: p.sandbox.live },
  ]
  return (
    <Panel title="Providers" right={<Chip tone={state.mode === 'live' ? 'green' : 'amber'} size="xs" dot>{state.mode === 'live' ? 'LIVE MODE' : 'MOCK MODE'}</Chip>} flush>
      <table className="w-full text-xs">
        <thead className="text-left text-[10px] uppercase tracking-wider text-fg-3">
          <tr>
            <th className="px-4 py-2 font-medium">Role</th>
            <th className="py-2 font-medium">Provider</th>
            <th className="py-2 font-medium">Model</th>
            <th className="px-4 py-2 text-right font-medium">Status</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.role} className="border-t border-white/[0.05]">
              <td className="px-4 py-2 font-medium">{r.role}</td>
              <td className="num py-2 text-fg-2">{r.provider}</td>
              <td className="num py-2 text-fg-2">
                {r.model}
                {r.url && (
                  <a href={r.url} target="_blank" rel="noreferrer" className="ml-1 inline-flex items-center text-fg-3 hover:text-fg">
                    <ExternalLink size={10} />
                  </a>
                )}
              </td>
              <td className="px-4 py-2 text-right">
                <Chip tone={r.live ? 'green' : 'amber'} size="xs" dot>
                  {r.live ? 'live' : 'fallback'}
                </Chip>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </Panel>
  )
}

function GateBrowser({ versions, active, reload }: { versions: GateVersionSummary[]; active: number; reload: () => void }) {
  const [selected, setSelected] = useState<number | null>(null)
  const [detail, setDetail] = useState<GateVersion | null>(null)
  const toast = useToast()
  const sel = selected ?? active
  const loading = detail === null || detail.version !== sel
  useEffect(() => {
    let alive = true
    api
      .gateVersion(sel)
      .then((v) => alive && setDetail(v))
      .catch((e: unknown) => {
        if (!alive) return
        setDetail(null)
        toast.error(`Gate v${sel}: ${e instanceof Error ? e.message : String(e)}`)
      })
    return () => {
      alive = false
    }
  }, [sel, toast, versions.length])
  return (
    <Panel
      title="Gate versions"
      right={
        <>
          <span className="num text-fg-3">{versions.length} versions</span>
          <Button className="h-7" onClick={reload}>
            <RefreshCw size={12} />
          </Button>
        </>
      }
      flush
      bodyClassName="grid min-h-[420px] grid-cols-1 md:grid-cols-[260px_1fr]"
    >
      <ul className="scroll-thin max-h-[560px] overflow-y-auto border-b border-white/[0.06] md:border-b-0 md:border-r">
        {versions.length === 0 && <li className="px-4 py-3 text-xs text-fg-3">No versions.</li>}
        {[...versions].sort((a, b) => b.version - a.version).map((v) => (
          <li key={v.version}>
            <button type="button" onClick={() => setSelected(v.version)} className={clsx('flex w-full flex-col gap-1 border-b border-white/[0.05] px-4 py-2.5 text-left hover:bg-white/[0.03]', sel === v.version && 'bg-blue/[0.08]')}>
              <span className="flex items-center gap-2">
                <span className="num text-sm font-bold">v{v.version}</span>
                <Chip size="xs" tone={v.status === 'shipped' ? 'green' : v.status === 'rejected' ? 'red' : 'neutral'}>{v.status}</Chip>
                {v.version === active && <Chip size="xs" tone="blue">active</Chip>}
                <span className="num ml-auto text-[10px] text-fg-3">{shortDate(v.created_at)}</span>
              </span>
              <span className="num text-[10px] text-fg-3">
                catch {pct(v.catch_rate)} · benign {pct(v.benign_allow_rate)} · {v.n_rules} rules · {v.n_examples} ex{v.has_prefilter ? ' · prefilter' : ''}
              </span>
            </button>
          </li>
        ))}
      </ul>
      <div className="scroll-thin max-h-[560px] overflow-y-auto p-4">
        {!detail ? (
          <div className="text-xs text-fg-3"><Loader2 size={12} className="mr-1 inline animate-spin" /> Loading v{sel}…</div>
        ) : loading ? (
          <div className="text-xs text-fg-3"><Loader2 size={12} className="mr-1 inline animate-spin" /> Loading v{sel}…</div>
        ) : (
          <div className="space-y-4 text-xs">
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <GateBadge version={detail.version} size="sm" />
                <Chip size="xs" tone={detail.status === 'shipped' ? 'green' : detail.status === 'rejected' ? 'red' : 'neutral'}>{detail.status}</Chip>
                {detail.parent_version !== null && <span className="num text-fg-3">parent v{detail.parent_version}</span>}
                <span className="num ml-auto text-fg-3">{shortDate(detail.created_at)}</span>
              </div>
              <p className="mt-2 text-fg-2">{detail.changelog}</p>
            </div>
            {detail.eval && (
              <div className="rounded-md border border-white/[0.06] bg-black/20 p-3">
                <div className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-fg-3">Eval</div>
                <div className="num grid grid-cols-2 gap-2 sm:grid-cols-4">
                  <div><div className="text-[10px] text-fg-3">catch rate</div><div className="text-base font-semibold text-blue">{pct(detail.eval.catch_rate, 1)} <span className="text-[10px] text-fg-3">← {pct(detail.eval.prev_catch_rate, 1)}</span></div></div>
                  <div><div className="text-[10px] text-fg-3">benign allow</div><div className="text-base font-semibold text-allow">{pct(detail.eval.benign_allow_rate, 1)}</div></div>
                  <div><div className="text-[10px] text-fg-3">attacks / benign</div><div className="text-base font-semibold">{detail.eval.n_attacks} / {detail.eval.n_benign}</div></div>
                  <div><div className="text-[10px] text-fg-3">verdict</div><div className={clsx('text-base font-semibold', detail.eval.passed ? 'text-allow' : 'text-breach')}>{detail.eval.passed ? 'pass' : 'reject'}</div></div>
                </div>
                {detail.eval.weave_url && (
                  <a href={detail.eval.weave_url} target="_blank" rel="noreferrer" className="mt-2 inline-flex items-center gap-1 text-[11px] text-blue hover:underline">
                    <ExternalLink size={11} /> Weave evaluation
                  </a>
                )}
                {detail.eval.failures.length > 0 && (
                  <ul className="mt-2 space-y-1">
                    {detail.eval.failures.map((f, i) => (
                      <li key={i} className="flex gap-2 text-[11px]">
                        <Chip size="xs" tone={f.kind === 'missed_attack' ? 'red' : 'violet'}>{f.kind === 'missed_attack' ? 'missed' : 'false block'}</Chip>
                        <span className="num text-fg-3">{f.tool}</span>
                        <span className="text-fg-2">{f.message}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}
            <div>
              <div className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-fg-3">Rules ({detail.rules.length})</div>
              <ol className="space-y-1">
                {detail.rules.map((r, i) => {
                  const added = detail.diff_from_parent.added_rules.includes(r)
                  return (
                    <li key={i} className={clsx('flex gap-2 rounded px-2 py-1', added ? 'bg-allow/[0.07]' : 'bg-white/[0.02]')}>
                      <span className={clsx('num shrink-0', added ? 'text-allow' : 'text-fg-3')}>{added ? '+' : i + 1}</span>
                      <span className="text-fg-2">{r}</span>
                    </li>
                  )
                })}
                {detail.diff_from_parent.removed_rules.map((r) => (
                  <li key={`rm-${r}`} className="flex gap-2 rounded bg-breach/[0.07] px-2 py-1">
                    <span className="num shrink-0 text-breach">−</span>
                    <span className="text-fg-3 line-through">{r}</span>
                  </li>
                ))}
              </ol>
            </div>
            <div>
              <div className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-fg-3">Criteria</div>
              <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1">
                {Object.entries(detail.criteria).map(([k, v]) => (
                  <div key={k} className="contents">
                    <dt className="num text-fg-3">{k}</dt>
                    <dd className="text-fg-2">{v}</dd>
                  </div>
                ))}
              </dl>
            </div>
            <div>
              <div className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-fg-3">Examples ({detail.examples.length}, +{detail.diff_from_parent.added_examples} new)</div>
              <div className="overflow-x-auto">
                <table className="w-full min-w-[520px] text-[11px]">
                  <thead className="text-left text-fg-3">
                    <tr><th className="py-1 pr-2 font-medium">message</th><th className="py-1 pr-2 font-medium">tool</th><th className="py-1 pr-2 font-medium">decision</th><th className="py-1 font-medium">why</th></tr>
                  </thead>
                  <tbody>
                    {detail.examples.map((ex, i) => (
                      <tr key={i} className="border-t border-white/[0.05] align-top">
                        <td className="py-1 pr-2 text-fg-2">{ex.message}</td>
                        <td className="num py-1 pr-2 text-fg-3">{ex.tool}</td>
                        <td className="py-1 pr-2"><span className={clsx('num font-semibold', ex.decision === 'allow' ? 'text-allow' : ex.decision === 'block' ? 'text-block' : 'text-blue')}>{ex.decision}</span></td>
                        <td className="py-1 text-fg-3">{ex.why}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
            <div>
              <div className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-fg-3">Prefilter {detail.has_prefilter ? '(python, sandboxed)' : ''}</div>
              {detail.prefilter_code ? (
                <pre className="scroll-thin max-h-80 overflow-auto rounded-md bg-black/50 p-3 text-[11px] leading-relaxed text-fg-2">{detail.prefilter_code}</pre>
              ) : (
                <div className="text-fg-3">No prefilter in this version.</div>
              )}
            </div>
          </div>
        )}
      </div>
    </Panel>
  )
}

function TraceViewer({ attacks }: { attacks: number }) {
  const [traces, setTraces] = useState<Trace[]>([])
  const [filter, setFilter] = useState('')
  const [applied, setApplied] = useState('')
  const [manual, setManual] = useState(0)
  const [open, setOpen] = useState<Set<string>>(new Set())
  const [loaded, setLoaded] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const key = `${applied}|${attacks}|${manual}`
  const loading = loaded !== key
  useEffect(() => {
    let alive = true
    api
      .traces({ limit: 100, attack_id: applied || undefined })
      .then((r) => {
        if (!alive) return
        setTraces(r.traces)
        setError(null)
      })
      .catch((e: unknown) => alive && setError(e instanceof Error ? e.message : String(e)))
      .finally(() => alive && setLoaded(key))
    return () => {
      alive = false
    }
  }, [key, applied])
  const load = () => setManual((m) => m + 1)
  const toggle = (id: string) =>
    setOpen((s) => {
      const n = new Set(s)
      if (n.has(id)) n.delete(id)
      else n.add(id)
      return n
    })
  const byParent = useMemo(() => {
    const m = new Map<string | null, Trace[]>()
    for (const t of traces) {
      const arr = m.get(t.parent_id) ?? []
      arr.push(t)
      m.set(t.parent_id, arr)
    }
    return m
  }, [traces])
  const roots = useMemo(() => traces.filter((t) => t.parent_id === null || !traces.some((x) => x.id === t.parent_id)), [traces])
  const renderRow = (t: Trace, depth: number): ReactNode => {
    const kids = byParent.get(t.id) ?? []
    const isOpen = open.has(t.id)
    return (
      <div key={t.id}>
        <button type="button" onClick={() => toggle(t.id)} className="grid w-full grid-cols-[16px_1fr_auto_auto_auto] items-center gap-2 border-t border-white/[0.05] px-4 py-1.5 text-left text-[11px] hover:bg-white/[0.03]" style={{ paddingLeft: 16 + depth * 16 }}>
          <span className="text-fg-3">{isOpen ? <ChevronDown size={12} /> : <ChevronRight size={12} />}</span>
          <span className="num truncate font-medium text-fg">{t.name}</span>
          <span className="num truncate text-fg-3">{t.turn_id ?? '—'}</span>
          <span className="num w-16 text-right text-fg-2">{t.duration_ms}ms</span>
          <span className="num w-20 text-right text-fg-3">{shortDate(t.started_at).split(' ').pop()}</span>
        </button>
        {isOpen && (
          <div className="grid gap-2 bg-black/20 px-4 py-2 md:grid-cols-2" style={{ paddingLeft: 32 + depth * 16 }}>
            <div>
              <div className="mb-1 text-[10px] uppercase tracking-wider text-fg-3">inputs</div>
              <JsonBlock value={t.inputs} />
            </div>
            <div>
              <div className="mb-1 flex items-center gap-2 text-[10px] uppercase tracking-wider text-fg-3">
                output
                {t.weave_url && (
                  <a href={t.weave_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 normal-case tracking-normal text-blue hover:underline">
                    <ExternalLink size={10} /> weave
                  </a>
                )}
              </div>
              <JsonBlock value={t.output} />
            </div>
          </div>
        )}
        {kids.map((k) => renderRow(k, depth + 1))}
      </div>
    )
  }
  return (
    <Panel
      title="Traces"
      right={
        <form
          onSubmit={(e) => {
            e.preventDefault()
            setApplied(filter.trim())
          }}
          className="flex items-center gap-2"
        >
          <div className="relative">
            <Search size={12} className="absolute left-2 top-1/2 -translate-y-1/2 text-fg-3" />
            <input value={filter} onChange={(e) => setFilter(e.target.value)} placeholder="attack_id / attacker id" className={clsx(inputCls, 'h-7 w-52 pl-7 text-[11px]')} />
          </div>
          <Button type="submit" className="h-7">Filter</Button>
          <Button type="button" className="h-7" busy={loading} onClick={load}>
            <RefreshCw size={12} />
          </Button>
        </form>
      }
      flush
    >
      <div className="grid grid-cols-[16px_1fr_auto_auto_auto] gap-2 px-4 py-1.5 text-[10px] uppercase tracking-wider text-fg-3">
        <span />
        <span>name</span>
        <span>turn</span>
        <span className="w-16 text-right">duration</span>
        <span className="w-20 text-right">at</span>
      </div>
      <div className="scroll-thin max-h-[520px] overflow-y-auto">
        {error ? (
          <div className="px-4 py-3 text-xs text-breach">{error}</div>
        ) : roots.length === 0 ? (
          <div className="px-4 py-3 text-xs text-fg-3">{loading ? 'Loading traces…' : applied ? `No traces for "${applied}".` : 'No traces yet — they appear as soon as the agent handles a message.'}</div>
        ) : (
          roots.map((t) => renderRow(t, 0))
        )}
      </div>
    </Panel>
  )
}

// ---------------------------------------------------------------------------
// page
// ---------------------------------------------------------------------------

export default function Admin() {
  const { state, transport, error, refresh } = useSiege()
  const [versions, setVersions] = useState<GateVersionSummary[]>([])
  const loadVersions = useCallback(() => api.gateVersions().then((r) => setVersions(r.versions)).catch(() => {}), [])
  useEffect(() => {
    void loadVersions()
  }, [loadVersions, state?.gate_version, state?.defender?.stage])

  return (
    <div className="bg-grid min-h-full">
      <header className="sticky top-0 z-30 border-b border-white/[0.06] bg-ink/85 backdrop-blur">
        <div className="mx-auto flex max-w-[1400px] items-center gap-4 px-4 py-2.5">
          <Link to={href('/')} className="flex items-center gap-1.5" title="War Room">
            <Swords size={16} className="text-breach" />
            <span className="text-sm font-black tracking-[0.25em]">SIEGE</span>
          </Link>
          <span className="text-[11px] font-semibold uppercase tracking-[0.2em] text-fg-3">Control</span>
          {state && <GateBadge version={state.gate_version} size="sm" />}
          <div className="ml-auto flex items-center gap-2 text-[11px]">
            <ConnChip transport={transport} error={error} />
            <Link to={href('/')} className="inline-flex items-center gap-1 rounded-md border border-white/10 px-2 py-1 text-fg-2 hover:text-fg">
              <Monitor size={12} /> War Room
            </Link>
            <Link to={href('/attack')} className="inline-flex items-center gap-1 rounded-md border border-white/10 px-2 py-1 text-fg-2 hover:text-fg">
              <Swords size={12} /> Attack
            </Link>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-[1400px] space-y-4 p-4">
        {!state ? (
          <div className="glass p-6 text-sm text-fg-2">
            {error ? (
              <>
                Can’t reach the backend: <span className="text-breach">{error}</span>. Retrying… or use <Link to="/admin?mock=1" className="text-blue">mock mode</Link>.
              </>
            ) : (
              <>
                <Loader2 size={14} className="mr-2 inline animate-spin" /> Loading state…
              </>
            )}
          </div>
        ) : (
          <>
            <div className="grid gap-4 lg:grid-cols-12">
              <div className="lg:col-span-4">
                <RoundCard state={state} refresh={refresh} />
              </div>
              <div className="lg:col-span-8">
                <DefenderCard state={state} refresh={refresh} />
              </div>
              <div className="lg:col-span-4">
                <SettingsCard settings={state.settings} refresh={refresh} />
              </div>
              <div className="flex flex-col gap-4 lg:col-span-4">
                <SimulateCard refresh={refresh} />
                <DangerCard versions={versions} current={state.gate_version} refresh={async () => { await refresh(); await loadVersions() }} />
              </div>
              <div className="lg:col-span-4">
                <ProvidersCard state={state} />
              </div>
            </div>
            <GateBrowser versions={versions} active={state.gate_version} reload={() => void loadVersions()} />
            <TraceViewer attacks={state.totals.attacks} />
          </>
        )}
      </main>
    </div>
  )
}
