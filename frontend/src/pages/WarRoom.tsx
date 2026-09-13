import clsx from 'clsx'
import { AnimatePresence, motion } from 'framer-motion'
import { ArrowDown, ArrowUp, Bot, Crown, Minus, Orbit, Smartphone, Swords } from 'lucide-react'
import { QRCodeSVG } from 'qrcode.react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { Area, CartesianGrid, ComposedChart, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api } from '../api'
import { Chip } from '../components/Chip'
import { ConnChip } from '../components/ConnChip'
import { CountdownRing } from '../components/CountdownRing'
import { EventRow } from '../components/EventRow'
import { GateBadge } from '../components/GateBadge'
import { Panel } from '../components/Panel'
import { ProviderChips } from '../components/ProviderChips'
import { SiegeField, useFieldEnabled } from '../components/SiegeField'
import { StageStepper } from '../components/StageStepper'
import { Stat } from '../components/Stat'
import { useSiege } from '../hooks/useSiege'
import { COLORS, categoryLabel, int, pct } from '../lib/format'
import { href } from '../lib/mockFlag'
import type { GateVersion, LeaderRow, State } from '../types'

// ---------------------------------------------------------------------------
// local helpers
// ---------------------------------------------------------------------------

/**
 * Interpolates seconds_left between server pushes so the ring ticks every second.
 * RoundClock is keyed by round number, so within a round the server value only
 * ever decreases and min(display, server) is always the honest value.
 */
function useSecondsLeft(serverValue: number, live: boolean): number {
  const [display, setDisplay] = useState(serverValue)
  useEffect(() => {
    if (!live) return
    const anchorAt = Date.now()
    const t = window.setInterval(() => setDisplay(Math.max(0, Math.ceil(serverValue - (Date.now() - anchorAt) / 1000))), 250)
    return () => window.clearInterval(t)
  }, [serverValue, live])
  if (!live) return 0
  return Math.min(display, serverValue)
}

function RoundClock({ state }: { state: State }) {
  const round = state.round
  const live = round?.status === 'live'
  const secondsLeft = useSecondsLeft(state.current_round.seconds_left, live)
  const shown = round?.number ?? (state.series.length ? state.series[state.series.length - 1].round : null)
  return (
    <div className="flex items-center gap-4">
      <CountdownRing secondsLeft={secondsLeft} total={round?.seconds ?? state.settings.round_seconds} size={72} stroke={6} live={live} />
      <div>
        <div className="text-[11px] font-medium uppercase tracking-[0.18em] text-fg-3">Round</div>
        <div className="num text-[34px] font-bold leading-none">{shown !== null ? shown.toString().padStart(2, '0') : '—'}</div>
        <div className="mt-1">
          {live ? (
            <Chip tone="red" size="xs" dot pulse>
              LIVE
            </Chip>
          ) : state.defender && !state.defender.ended_at ? (
            <Chip tone="blue" size="xs" dot pulse>
              DEFENDING
            </Chip>
          ) : shown !== null ? (
            <Chip tone="neutral" size="xs" dot>
              BETWEEN ROUNDS
            </Chip>
          ) : (
            <Chip tone="neutral" size="xs">
              NOT STARTED
            </Chip>
          )}
        </div>
      </div>
    </div>
  )
}

function useLeaderboard(breachCount: number, attackerCount: number): { rows: LeaderRow[]; movement: Map<string, number> } {
  const [rows, setRows] = useState<LeaderRow[]>([])
  const prevRanks = useRef<Map<string, number>>(new Map())
  const [movement, setMovement] = useState<Map<string, number>>(new Map())
  const apply = useCallback((r: { rows: LeaderRow[] }) => {
    const top = r.rows.slice(0, 10)
    const mv = new Map<string, number>()
    for (const row of top) {
      const prev = prevRanks.current.get(row.attacker_id)
      if (prev !== undefined && prev !== row.rank) mv.set(row.attacker_id, prev - row.rank)
    }
    const next = new Map<string, number>()
    for (const row of r.rows) next.set(row.attacker_id, row.rank)
    prevRanks.current = next
    setRows(top)
    setMovement((old) => {
      // keep the previous arrow for rows that did not move this fetch so it does not flicker
      const merged = new Map(old)
      for (const [k, v] of mv) merged.set(k, v)
      for (const k of [...merged.keys()]) if (!top.some((t) => t.attacker_id === k)) merged.delete(k)
      return merged
    })
  }, [])
  // leaderboard is non-critical; state + feed still render if it fails
  useEffect(() => {
    let alive = true
    api.leaderboard().then((r) => alive && apply(r)).catch(() => {})
    return () => {
      alive = false
    }
  }, [apply, breachCount, attackerCount])
  useEffect(() => {
    const t = window.setInterval(() => api.leaderboard().then(apply).catch(() => {}), 3000)
    return () => window.clearInterval(t)
  }, [apply])
  return { rows, movement }
}

function useGateVersion(version: number | undefined): GateVersion | null {
  const [gv, setGv] = useState<GateVersion | null>(null)
  useEffect(() => {
    if (!version) return
    let alive = true
    api
      .gateVersion(version)
      .then((v) => alive && setGv(v))
      .catch(() => alive && setGv(null))
    return () => {
      alive = false
    }
  }, [version])
  return gv
}

// ---------------------------------------------------------------------------
// chart
// ---------------------------------------------------------------------------

type Point = { round: number; breach: number | null; benign: number | null; catch: number | null; gate_version: number; label: string }

function ChartTooltip({ active, payload }: { active?: boolean; payload?: ReadonlyArray<{ payload?: Point }> }) {
  const p = active && payload && payload.length > 0 ? payload[0].payload : undefined
  if (!p) return null
  return (
    <div className="glass num px-3 py-2 text-[11px]">
      <div className="mb-1 text-fg-2">
        Round {p.round} · gate v{p.gate_version}
      </div>
      <div className="flex flex-col gap-0.5">
        <span style={{ color: COLORS.breach }}>breach rate {pct(p.breach, 1)}</span>
        <span style={{ color: COLORS.allow }}>benign allow {pct(p.benign, 1)}</span>
        <span style={{ color: COLORS.blue }}>catch rate {pct(p.catch, 1)}</span>
      </div>
    </div>
  )
}

function RoundsChart({ series }: { series: State['series'] }) {
  const data = useMemo<Point[]>(
    () =>
      series.map((s) => ({
        round: s.round,
        breach: s.breach_rate * 100,
        benign: s.benign_allow_rate * 100,
        catch: s.catch_rate === null ? null : s.catch_rate * 100,
        gate_version: s.gate_version,
        label: `R${s.round}`,
      })),
    [series],
  )
  const versionChanges = useMemo(() => {
    const out: { round: number; version: number }[] = []
    for (let i = 1; i < series.length; i++) {
      if (series[i].gate_version !== series[i - 1].gate_version) out.push({ round: series[i].round, version: series[i].gate_version })
    }
    return out
  }, [series])

  if (data.length === 0) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 text-center">
        <Swords size={28} className="text-fg-3" />
        <div className="text-sm font-medium text-fg-2">No rounds yet</div>
        <div className="max-w-xs text-xs text-fg-3">
          Start a round from <Link to={href('/admin')} className="text-blue underline-offset-2 hover:underline">Control</Link>. Each finished round adds a point: breach rate should fall as the gate learns.
        </div>
      </div>
    )
  }
  const single = data.length === 1
  return (
    <ResponsiveContainer width="100%" height="100%">
      <ComposedChart data={data} margin={{ top: 18, right: 16, bottom: 4, left: -12 }}>
        <defs>
          <linearGradient id="breachFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={COLORS.breach} stopOpacity={0.28} />
            <stop offset="100%" stopColor={COLORS.breach} stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid stroke="rgba(255,255,255,0.06)" vertical={false} />
        <XAxis dataKey="label" tick={{ fill: COLORS.fg3, fontSize: 11, fontFamily: 'var(--font-mono)' }} axisLine={{ stroke: 'rgba(255,255,255,0.08)' }} tickLine={false} />
        <YAxis domain={[0, 100]} ticks={[0, 25, 50, 75, 100]} tickFormatter={(v: number) => `${v}%`} tick={{ fill: COLORS.fg3, fontSize: 11, fontFamily: 'var(--font-mono)' }} axisLine={false} tickLine={false} width={48} />
        <Tooltip content={<ChartTooltip />} cursor={{ stroke: 'rgba(255,255,255,0.15)' }} />
        {versionChanges.map((vc) => (
          <ReferenceLine
            key={vc.round}
            x={`R${vc.round}`}
            stroke={COLORS.allow}
            strokeDasharray="3 4"
            strokeOpacity={0.7}
            label={{ value: `v${vc.version}`, position: 'top', fill: COLORS.allow, fontSize: 11, fontFamily: 'var(--font-mono)', fontWeight: 700 }}
          />
        ))}
        <ReferenceLine y={90} stroke={COLORS.allow} strokeOpacity={0.25} strokeDasharray="2 6" />
        <Area type="monotone" dataKey="breach" stroke="none" fill="url(#breachFill)" isAnimationActive={false} />
        <Line type="monotone" dataKey="benign" name="benign allow" stroke={COLORS.allow} strokeWidth={2.5} dot={{ r: single ? 5 : 3.5, fill: COLORS.allow, strokeWidth: 0 }} activeDot={{ r: 5 }} isAnimationActive={false} />
        <Line type="monotone" dataKey="catch" name="catch rate" stroke={COLORS.blue} strokeWidth={2} strokeDasharray="6 4" dot={{ r: single ? 5 : 3, fill: COLORS.blue, strokeWidth: 0 }} activeDot={{ r: 5 }} connectNulls isAnimationActive={false} />
        <Line type="monotone" dataKey="breach" name="breach rate" stroke={COLORS.breach} strokeWidth={3} dot={{ r: single ? 6 : 4, fill: COLORS.breach, strokeWidth: 0 }} activeDot={{ r: 6 }} isAnimationActive={false} />
      </ComposedChart>
    </ResponsiveContainer>
  )
}

// ---------------------------------------------------------------------------
// defender panel
// ---------------------------------------------------------------------------

function DefenderPanel({ state, gate }: { state: State; gate: GateVersion | null }) {
  const run = state.defender
  const latest = run?.attempts[run.attempts.length - 1]
  const lastLog = run?.log[run.log.length - 1]
  const idle = !run || run.stage === 'idle'
  return (
    <Panel
      title="Defender loop"
      right={
        run ? (
          <>
            <span className="num text-fg-3">round {run.round}</span>
            <Chip size="xs" tone={run.stage === 'shipped' ? 'green' : run.stage === 'rejected' || run.stage === 'failed' ? 'red' : run.ended_at ? 'neutral' : 'blue'} dot pulse={!run.ended_at}>
              {run.stage}
            </Chip>
          </>
        ) : null
      }
      className="h-full"
      bodyClassName="grid min-h-0 grid-cols-[1.15fr_1fr] gap-4"
    >
      <div className="flex min-h-0 flex-col gap-3">
        <StageStepper stage={run?.stage} />
        {idle ? (
          <div className="flex flex-1 items-center justify-center text-center text-xs text-fg-3">
            {state.round?.status === 'live' ? 'Collecting breach traces this round. The defender runs when the round ends.' : 'Defender idle. It runs when a round ends with new breaches.'}
          </div>
        ) : (
          <>
            <div className="num grid grid-cols-3 gap-2 text-[11px]">
              <div className="rounded-md bg-white/[0.03] px-2.5 py-1.5">
                <div className="text-fg-3">breaches</div>
                <div className="text-base font-semibold text-breach">{run.breaches_considered}</div>
              </div>
              <div className="rounded-md bg-white/[0.03] px-2.5 py-1.5">
                <div className="text-fg-3">variants</div>
                <div className="text-base font-semibold text-fg">{run.variants_generated}</div>
              </div>
              <div className="rounded-md bg-white/[0.03] px-2.5 py-1.5">
                <div className="text-fg-3">shipped</div>
                <div className={clsx('text-base font-semibold', run.shipped_version ? 'text-allow' : 'text-fg-3')}>{run.shipped_version ? `v${run.shipped_version}` : '—'}</div>
              </div>
            </div>
            <div className="min-h-0 flex-1 overflow-hidden">
              {run.attempts.length > 0 ? (
                <table className="num w-full text-[11px]">
                  <thead className="text-left text-fg-3">
                    <tr>
                      <th className="pb-1 pr-3 font-medium">attempt</th>
                      <th className="pb-1 pr-3 font-medium">catch</th>
                      <th className="pb-1 pr-3 font-medium">benign</th>
                      <th className="pb-1 font-medium">verdict</th>
                    </tr>
                  </thead>
                  <tbody>
                    {run.attempts.map((a) => (
                      <tr key={a.n} className="border-t border-white/[0.05]">
                        <td className="py-1 pr-3 text-fg-2">#{a.n}</td>
                        <td className="whitespace-nowrap py-1 pr-3">
                          <span className="text-blue">{pct(a.eval.catch_rate)}</span>
                          <span className="text-fg-3"> ← {pct(a.eval.prev_catch_rate)}</span>
                        </td>
                        <td className={clsx('py-1 pr-3', a.eval.benign_allow_rate >= state.settings.benign_floor ? 'text-allow' : 'text-breach')}>{pct(a.eval.benign_allow_rate)}</td>
                        <td className={clsx('py-1 font-sans', a.eval.passed ? 'text-allow' : 'text-breach')}>{a.eval.passed ? 'pass' : 'reject'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <div className="text-xs text-fg-3">{latest ? '' : 'No eval yet.'}</div>
              )}
            </div>
            {lastLog && (
              <AnimatePresence mode="wait" initial={false}>
                <motion.div key={lastLog} initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className="num truncate rounded-md bg-black/30 px-2.5 py-1.5 text-[11px] text-fg-2" title={lastLog}>
                  <span className="text-blue">›</span> {lastLog}
                </motion.div>
              </AnimatePresence>
            )}
          </>
        )}
      </div>
      <div className="flex min-h-0 flex-col gap-2 border-l border-white/[0.06] pl-4">
        <div className="flex items-center justify-between">
          <span className="text-[11px] font-semibold uppercase tracking-[0.14em] text-fg-3">Gate v{state.gate_version} changelog</span>
          {gate && (
            <span className="num text-[10px] text-fg-3">
              {gate.n_rules} rules · {gate.n_examples} examples{gate.has_prefilter ? ' · prefilter' : ''}
            </span>
          )}
        </div>
        {gate ? (
          <div className="scroll-thin min-h-0 flex-1 overflow-auto">
            <p className="text-xs leading-snug text-fg-2">{gate.changelog}</p>
            {gate.diff_from_parent.added_rules.length === 0 && gate.diff_from_parent.removed_rules.length === 0 && gate.diff_from_parent.added_examples === 0 ? (
              <div className="mt-2 text-[11px] text-fg-3">{gate.status === 'seed' ? 'Seed policy — no parent to diff against.' : 'No rule changes from parent.'}</div>
            ) : (
              <div className="num mt-2 space-y-1 text-[11px] leading-snug">
                {gate.diff_from_parent.added_rules.map((r) => (
                  <div key={r} className="flex gap-1.5 rounded bg-allow/[0.07] px-2 py-1 text-allow">
                    <span className="shrink-0 font-bold">+</span>
                    <span className="font-sans text-fg-2">{r}</span>
                  </div>
                ))}
                {gate.diff_from_parent.removed_rules.map((r) => (
                  <div key={r} className="flex gap-1.5 rounded bg-breach/[0.07] px-2 py-1 text-breach">
                    <span className="shrink-0 font-bold">−</span>
                    <span className="font-sans text-fg-2 line-through">{r}</span>
                  </div>
                ))}
                {gate.diff_from_parent.added_examples > 0 && (
                  <div className="flex gap-1.5 rounded bg-blue/[0.07] px-2 py-1 text-blue">
                    <span className="shrink-0 font-bold">+</span>
                    <span className="font-sans text-fg-2">{gate.diff_from_parent.added_examples} adversarial examples</span>
                  </div>
                )}
              </div>
            )}
          </div>
        ) : (
          <div className="text-xs text-fg-3">Loading gate v{state.gate_version}…</div>
        )}
      </div>
    </Panel>
  )
}

// ---------------------------------------------------------------------------
// leaderboard
// ---------------------------------------------------------------------------

function Leaderboard({ rows, movement }: { rows: LeaderRow[]; movement: Map<string, number> }) {
  if (rows.length === 0) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 px-4 text-center">
        <Smartphone size={24} className="text-fg-3" />
        <div className="text-sm font-medium text-fg-2">No attackers yet</div>
        <div className="text-xs text-fg-3">Scan the QR code to join the siege.</div>
      </div>
    )
  }
  return (
    <ol className="flex flex-col">
      {rows.map((r) => {
        const mv = movement.get(r.attacker_id) ?? 0
        return (
          <motion.li
            key={r.attacker_id}
            layout
            transition={{ type: 'spring', stiffness: 400, damping: 34 }}
            className={clsx('flex items-center gap-3 border-b border-white/[0.05] px-3 py-[7px]', r.rank === 1 && 'bg-block/[0.05]')}
          >
            <span className={clsx('num w-6 text-right text-sm font-bold', r.rank === 1 ? 'text-block' : r.rank <= 3 ? 'text-fg' : 'text-fg-3')}>{r.rank}</span>
            <span className="w-3 shrink-0">
              {mv > 0 ? <ArrowUp size={12} className="text-allow" /> : mv < 0 ? <ArrowDown size={12} className="text-breach" /> : <Minus size={10} className="text-fg-3/40" />}
            </span>
            <span className="flex min-w-0 flex-1 items-center gap-1.5">
              {r.rank === 1 && <Crown size={12} className="shrink-0 text-block" />}
              <span className="truncate text-sm font-medium">{r.nickname}</span>
              {r.synthetic && <Bot size={11} className="shrink-0 text-fg-3" aria-label="synthetic attacker" />}
            </span>
            <span className="hidden items-center gap-1 xl:flex">
              {r.categories.slice(0, 5).map((c) => (
                <span key={c} className="h-1.5 w-1.5 rounded-full" style={{ background: COLORS.breach, opacity: 0.85 }} title={categoryLabel(c)} />
              ))}
            </span>
            <span className="num w-8 text-right text-[11px] text-fg-3" title="breaches">
              {r.breaches}
            </span>
            <span className="num w-14 text-right text-sm font-semibold text-fg">{int(r.score)}</span>
          </motion.li>
        )
      })}
    </ol>
  )
}

// ---------------------------------------------------------------------------
// page
// ---------------------------------------------------------------------------

export default function WarRoom() {
  const { state, events, transport, error } = useSiege()
  const { rows, movement } = useLeaderboard(state?.totals.breaches ?? 0, state?.totals.attackers ?? 0)
  const gate = useGateVersion(state?.gate_version)
  const [fieldOn, toggleField] = useFieldEnabled()

  const feed = useMemo(() => events.slice(0, 60), [events])
  const round = state?.round ?? null
  const prevRound = useMemo(() => {
    if (!state) return null
    const finished = state.series.filter((s) => !round || s.round !== round.number)
    return finished.length ? finished[finished.length - 1] : null
  }, [state, round])
  const catchRate = gate?.catch_rate ?? state?.series.findLast((s) => s.gate_version === state.gate_version && s.catch_rate !== null)?.catch_rate ?? null
  const breachDelta = prevRound && state ? state.current_round.breach_rate - prevRound.breach_rate : null

  if (!state) {
    return (
      <div className="bg-grid flex h-screen w-screen flex-col items-center justify-center gap-3 text-center">
        <div className="text-2xl font-black tracking-[0.3em] text-fg">SIEGE</div>
        {error ? (
          <div className="max-w-md text-sm text-fg-2">
            Can’t reach the backend at <code className="text-fg">/api</code>: {error}
            <div className="mt-2 text-xs text-fg-3">
              Retrying every 2s. Or open <Link to="/?mock=1" className="text-blue">/?mock=1</Link> for the in-browser simulator.
            </div>
          </div>
        ) : (
          <div className="text-sm text-fg-3">Connecting…</div>
        )}
      </div>
    )
  }

  return (
    <div className={clsx('flex h-screen w-screen flex-col gap-4 overflow-hidden p-4', fieldOn ? 'relative' : 'bg-grid')}>
      {/* Living battlefield behind the panels (fixed, z-0, pointer-events none) */}
      {fieldOn && <SiegeField state={state} events={events} />}

      {/* Header */}
      <header className="glass relative z-10 flex h-24 shrink-0 items-center gap-6 px-5">
        <div className="flex items-center gap-4">
          <div>
            <div className="flex items-center gap-2">
              <Swords size={22} className="text-breach" />
              <span className="text-[28px] font-black leading-none tracking-[0.28em] text-fg">SIEGE</span>
            </div>
            <div className="mt-1 text-[11px] uppercase tracking-[0.18em] text-fg-3">the room vs one agent</div>
          </div>
        </div>
        <div className="h-12 w-px bg-white/[0.08]" />
        <RoundClock key={round?.number ?? 'none'} state={state} />
        <div className="h-12 w-px bg-white/[0.08]" />
        <GateBadge version={state.gate_version} />
        <div className="flex min-w-0 flex-1 flex-col gap-1.5">
          <ProviderChips providers={state.providers} mode={state.mode} />
          <div className="flex items-center gap-2 text-[11px] text-fg-3">
            <ConnChip transport={transport} error={error} />
            <span className="num">
              {state.providers.agent.model} · gate {state.providers.gate.provider} · defender {state.providers.defender.model}
            </span>
            <button
              type="button"
              onClick={toggleField}
              aria-pressed={fieldOn}
              aria-label={fieldOn ? 'Battlefield on. Click to hide the field.' : 'Battlefield off. Click to show the field.'}
              title={fieldOn ? 'field on — click to hide' : 'field off — click to show'}
              className={clsx('ml-auto inline-flex items-center gap-1 rounded px-1.5 py-0.5 transition-colors', fieldOn ? 'text-allow hover:text-fg' : 'text-fg-3 hover:text-fg')}
            >
              <Orbit size={12} />
              <span className="num">field {fieldOn ? 'on' : 'off'}</span>
            </button>
            <Link to={href('/admin')} className="text-fg-3 underline-offset-2 hover:text-fg hover:underline">
              control
            </Link>
          </div>
        </div>
        <div className="flex items-center gap-3 rounded-lg border border-white/[0.08] bg-white p-1.5">
          <QRCodeSVG value={state.join_url} size={72} bgColor="#ffffff" fgColor="#07080c" level="M" />
        </div>
        <div className="w-44">
          <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-fg">Join the siege</div>
          <div className="num mt-1 break-all text-[11px] leading-snug text-fg-2">{state.join_url.replace(/^https?:\/\//, '')}</div>
          <div className="num mt-1 text-[11px] text-fg-3">
            {state.totals.online} online · {state.totals.attackers} joined
          </div>
        </div>
      </header>

      {/* Body */}
      <div className="relative z-10 grid min-h-0 flex-1 grid-cols-[1fr_440px] gap-4">
        <div className="flex min-h-0 flex-col gap-4">
          <div className="grid shrink-0 grid-cols-6 gap-4">
            <Stat label="Attacks" value={int(state.totals.attacks)} sub={<span className="num">{int(state.current_round.attacks)} this round</span>} />
            <Stat label="Breaches" value={int(state.totals.breaches)} accent={COLORS.breach} sub={<span className="num">{int(state.current_round.breaches)} this round</span>} />
            <Stat
              label="Breach rate · round"
              value={pct(state.current_round.breach_rate)}
              accent={COLORS.breach}
              sub={
                breachDelta === null ? (
                  <span className="text-fg-3">no previous round</span>
                ) : (
                  <span className={clsx('num', breachDelta <= 0 ? 'text-allow' : 'text-breach')}>
                    {breachDelta <= 0 ? '▼' : '▲'} {pct(Math.abs(breachDelta), 1)} vs R{prevRound?.round}
                  </span>
                )
              }
            />
            <Stat label="Benign allow" value={pct(state.current_round.benign_allow_rate)} accent={COLORS.allow} sub={<span className="num text-fg-3">floor {pct(state.settings.benign_floor)}</span>} />
            <Stat label={`Catch rate · v${state.gate_version}`} value={pct(catchRate)} accent={COLORS.blue} sub={<span className="num text-fg-3">{gate?.status === 'seed' ? 'seed policy' : gate ? `benign ${pct(gate.benign_allow_rate)}` : 'eval pending'}</span>} />
            <Stat label="Attackers online" value={int(state.totals.online)} sub={<span className="num">{int(state.totals.attackers)} total</span>} />
          </div>
          <Panel
            title="Breach rate per round"
            right={
              <div className="num flex items-center gap-3 text-[11px]">
                <span className="flex items-center gap-1.5">
                  <span className="h-[3px] w-4 rounded" style={{ background: COLORS.breach }} /> breach rate
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="h-[3px] w-4 rounded" style={{ background: COLORS.allow }} /> benign allow
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="h-[3px] w-4 rounded border-t-2 border-dashed" style={{ borderColor: COLORS.blue, background: 'transparent' }} /> catch rate
                </span>
                <span className="flex items-center gap-1.5 text-allow">┆ gate shipped</span>
              </div>
            }
            className="min-h-0 flex-1"
            bodyClassName="p-2"
          >
            <RoundsChart series={state.series} />
          </Panel>
          <div className="shrink-0" style={{ height: 'clamp(236px, 28vh, 300px)' }}>
            <DefenderPanel state={state} gate={gate} />
          </div>
        </div>

        <div className="flex min-h-0 flex-col gap-4">
          <Panel
            title="Live feed"
            right={
              <span className="num text-fg-3">
                {state.totals.blocks} blocked · {state.totals.benign_blocks} false blocks
              </span>
            }
            className="min-h-0 flex-1"
            flush
            bodyClassName="scroll-thin overflow-y-auto overflow-x-hidden"
          >
            {feed.length === 0 ? (
              <div className="flex h-full flex-col items-center justify-center gap-1 px-4 text-center">
                <div className="text-sm font-medium text-fg-2">Quiet for now</div>
                <div className="text-xs text-fg-3">Attacks, blocks and breaches stream here as they happen.</div>
              </div>
            ) : (
              <AnimatePresence initial={false}>
                {feed.map((e) => (
                  <motion.div
                    key={e.id}
                    layout="position"
                    initial={{ opacity: 0, x: 32, height: 0 }}
                    animate={{ opacity: 1, x: 0, height: 'auto' }}
                    exit={{ opacity: 0, height: 0 }}
                    transition={{ duration: 0.28, ease: 'easeOut' }}
                    className="overflow-hidden"
                  >
                    <EventRow event={e} />
                  </motion.div>
                ))}
              </AnimatePresence>
            )}
          </Panel>
          <Panel title="Leaderboard" right={<span className="num text-fg-3">top 10 · ⬤ = category breached</span>} className="shrink-0" style={{ height: 'clamp(300px, 40vh, 430px)' }} flush bodyClassName="scroll-thin overflow-y-auto">
            <Leaderboard rows={rows} movement={movement} />
          </Panel>
        </div>
      </div>
    </div>
  )
}
