import clsx from 'clsx'
import { AlertTriangle, ArrowUpRight, Ban, Check, Filter } from 'lucide-react'
import { useState } from 'react'
import type { ToolCall } from '../types'
import { categoryLabel, decisionColor } from '../lib/format'
import { ProbabilityBar } from './ProbabilityBar'

type Props = {
  call: ToolCall
  points?: number
  className?: string
}

function DecisionIcon({ decision }: { decision: ToolCall['gate']['decision'] }) {
  if (decision === 'allow') return <Check size={12} strokeWidth={3} />
  if (decision === 'block') return <Ban size={12} strokeWidth={2.5} />
  return <ArrowUpRight size={12} strokeWidth={2.5} />
}

export function ToolCallChip({ call, points, className }: Props) {
  const [open, setOpen] = useState(false)
  const color = decisionColor(call.gate.decision)
  const args = Object.entries(call.args)
  return (
    <div
      className={clsx(
        'rounded-lg border bg-ink-3/70 text-xs',
        call.breach ? 'border-breach/50 shadow-[0_0_0_1px_rgba(255,59,92,0.15),0_0_24px_-8px_rgba(255,59,92,0.6)]' : call.benign_block ? 'border-benign/40' : 'border-white/10',
        className,
      )}
    >
      <button type="button" onClick={() => setOpen((o) => !o)} className="flex w-full items-start gap-2 px-2.5 py-2 text-left">
        <span className="mt-[1px] flex h-4 w-4 shrink-0 items-center justify-center rounded" style={{ background: `${color}22`, color }}>
          <DecisionIcon decision={call.gate.decision} />
        </span>
        <span className="min-w-0 flex-1">
          <span className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <span className="num font-semibold text-fg">{call.name}</span>
            <span className="num rounded px-1.5 py-[1px] text-[10px] font-semibold uppercase tracking-wide" style={{ background: `${color}1f`, color }}>
              {call.gate.decision}
            </span>
            {call.gate.prefilter_hit && (
              <span className="inline-flex items-center gap-1 rounded bg-white/[0.06] px-1.5 py-[1px] text-[10px] text-fg-2" title={call.gate.prefilter_reason ?? 'prefilter'}>
                <Filter size={10} /> prefilter
              </span>
            )}
            {call.breach && (
              <span className="inline-flex items-center gap-1 rounded bg-breach px-1.5 py-[1px] text-[10px] font-bold uppercase tracking-wide text-white">
                <AlertTriangle size={10} strokeWidth={3} /> Breach{call.category ? ` · ${categoryLabel(call.category)}` : ''}
                {points ? <span className="num">+{points}</span> : null}
              </span>
            )}
            {call.benign_block && (
              <span className="rounded bg-benign/20 px-1.5 py-[1px] text-[10px] font-semibold uppercase tracking-wide text-benign">false block</span>
            )}
          </span>
          <span className="num mt-1 block truncate text-[11px] text-fg-3">
            {args.length === 0 ? '()' : args.map(([k, v]) => `${k}=${typeof v === 'string' ? v : JSON.stringify(v)}`).join('  ')}
          </span>
          <ProbabilityBar probabilities={call.gate.probabilities} decision={call.gate.decision} className="mt-1.5" labels={open} />
        </span>
      </button>
      {open && (
        <div className="space-y-1.5 border-t border-white/[0.06] px-2.5 py-2 text-[11px] text-fg-2">
          <div>
            <span className="text-fg-3">oracle </span>
            <span className={call.oracle.allowed ? 'text-allow' : 'text-breach'}>{call.oracle.allowed ? 'allowed' : 'forbidden'}</span>
            <span className="text-fg-3"> · </span>
            {call.oracle.reason}
          </div>
          <div className="num text-fg-3">
            gate v{call.gate.gate_version} · {call.gate.provider} · conf {(call.gate.confidence * 100).toFixed(0)}% · {call.gate.latency_ms}ms
            {call.gate.prefilter_hit && call.gate.prefilter_reason ? ` · prefilter: ${call.gate.prefilter_reason}` : ''}
          </div>
          <div className="num text-fg-3">
            {call.executed ? 'executed' : 'not executed'} · {call.result}
          </div>
          {args.length > 0 && (
            <pre className="scroll-thin max-h-32 overflow-auto rounded bg-black/40 p-2 text-[10px] leading-snug text-fg-2">{JSON.stringify(call.args, null, 2)}</pre>
          )}
        </div>
      )}
    </div>
  )
}
