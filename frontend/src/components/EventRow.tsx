import clsx from 'clsx'
import { AlertTriangle, ArrowUpRight, Bot, Flag, Gavel, Rocket, ShieldBan, ShieldOff, UserPlus, Wrench, XOctagon } from 'lucide-react'
import type { Event } from '../types'
import { categoryLabel, clock } from '../lib/format'

type Props = {
  event: Event
  compact?: boolean
  className?: string
}

const META: Record<Event['type'], { color: string; bg: string; icon: typeof Flag; label: string }> = {
  breach: { color: '#ff3b5c', bg: 'rgba(255,59,92,0.10)', icon: AlertTriangle, label: 'BREACH' },
  block: { color: '#ffb020', bg: 'rgba(255,176,32,0.08)', icon: ShieldBan, label: 'BLOCKED' },
  benign_block: { color: '#a78bfa', bg: 'rgba(167,139,250,0.08)', icon: ShieldOff, label: 'FALSE BLOCK' },
  attack: { color: '#a3a8b8', bg: 'transparent', icon: Flag, label: 'ATTACK' },
  join: { color: '#6b7085', bg: 'transparent', icon: UserPlus, label: 'JOIN' },
  round_start: { color: '#60a5fa', bg: 'rgba(96,165,250,0.08)', icon: Rocket, label: 'ROUND' },
  round_end: { color: '#60a5fa', bg: 'rgba(96,165,250,0.08)', icon: Gavel, label: 'ROUND' },
  defender_stage: { color: '#60a5fa', bg: 'transparent', icon: Wrench, label: 'DEFENDER' },
  gate_shipped: { color: '#22c55e', bg: 'rgba(34,197,94,0.10)', icon: ArrowUpRight, label: 'SHIPPED' },
  gate_rejected: { color: '#ff3b5c', bg: 'rgba(255,59,92,0.08)', icon: XOctagon, label: 'REJECTED' },
}

export function EventRow({ event, compact, className }: Props) {
  const m = META[event.type] ?? META.attack
  const Icon = m.icon
  const category = typeof event.data?.category === 'string' ? (event.data.category as string) : null
  const points = typeof event.data?.points === 'number' ? (event.data.points as number) : null
  const first = event.data?.first_of_round === true
  const synthetic = event.data?.synthetic === true
  const isBreach = event.type === 'breach'
  const isBlock = event.type === 'block'
  const muted = event.type === 'join' || event.type === 'attack'
  const phase = event.data?.phase
  const label = event.type === 'attack' && phase === 'submitted' ? 'SUBMITTED' : event.type === 'attack' && phase === 'completed' ? 'REPLY' : m.label
  const message = typeof event.data?.message === 'string' ? event.data.message : null
  const reply = typeof event.data?.reply === 'string' ? event.data.reply : null
  return (
    <div
      className={clsx(
        'flex items-start gap-2.5 border-b border-white/[0.05] px-3',
        compact ? 'py-1.5' : 'py-2',
        isBreach && 'animate-flash-red',
        isBlock && 'animate-flash-amber',
        muted && 'opacity-70',
        className,
      )}
      style={{ background: isBreach || isBlock ? undefined : m.bg, borderLeft: `2px solid ${m.color}` }}
    >
      <span className="mt-[2px] shrink-0" style={{ color: m.color }}>
        <Icon size={13} strokeWidth={2.5} />
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="num text-[10px] font-bold tracking-wider" style={{ color: m.color }}>
            {label}
          </span>
          {category && (
            <span className="rounded px-1.5 text-[10px] font-semibold uppercase tracking-wide" style={{ background: `${m.color}22`, color: m.color }}>
              {categoryLabel(category)}
            </span>
          )}
          {points !== null && isBreach && (
            <span className="num text-[11px] font-bold text-breach">
              +{points}
              {first && <span className="ml-1 rounded bg-breach px-1 text-[9px] text-white">×2 FIRST</span>}
            </span>
          )}
          {synthetic && (
            <span className="inline-flex items-center gap-1 text-[10px] text-fg-3">
              <Bot size={10} /> bot
            </span>
          )}
          <span className="num ml-auto shrink-0 text-[10px] text-fg-3">{clock(event.at)}</span>
        </div>
        <div className={clsx('break-words text-fg-2', compact ? 'truncate text-[11px]' : 'line-clamp-2 text-xs', isBreach && 'text-fg')} title={event.text}>
          {event.text}
        </div>
        {(message || reply) && !compact && <details className="mt-1 text-[11px] text-fg-3">
          <summary className="cursor-pointer">View {reply ? 'conversation' : 'message'}</summary>
          {message && <p className="mt-1 whitespace-pre-wrap break-words text-fg-2"><strong>{event.attacker?.nickname ?? 'Player'}:</strong> {message}</p>}
          {reply && <p className="mt-1 whitespace-pre-wrap break-words text-fg-2"><strong>Agent:</strong> {reply}</p>}
        </details>}
      </div>
    </div>
  )
}
