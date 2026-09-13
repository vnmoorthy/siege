import clsx from 'clsx'
import { motion } from 'framer-motion'
import { Check, X } from 'lucide-react'
import type { DefenderStage } from '../types'
import { STAGES, stageIndex } from '../lib/format'

type Props = {
  stage: DefenderStage | null | undefined
  className?: string
  compact?: boolean
}

const LABELS: Record<string, string> = {
  collecting: 'Collect',
  patching: 'Patch',
  amplifying: 'Amplify',
  evaluating: 'Evaluate',
  shipped: 'Ship',
}

export function StageStepper({ stage, className, compact }: Props) {
  const idx = stageIndex(stage)
  const terminal = stage === 'shipped' || stage === 'rejected' || stage === 'failed'
  const failed = stage === 'rejected' || stage === 'failed'
  const running = !terminal && idx >= 0
  return (
    <ol className={clsx('flex w-full items-center', className)}>
      {STAGES.map((s, i) => {
        const done = terminal ? true : i < idx
        const active = !terminal && i === idx
        const isLast = i === STAGES.length - 1
        const lastFailed = isLast && failed
        const lastShipped = isLast && stage === 'shipped'
        const color = lastFailed ? '#ff3b5c' : done || active ? (lastShipped ? '#22c55e' : '#60a5fa') : 'rgba(255,255,255,0.18)'
        return (
          <li key={s} className={clsx('flex items-center', !isLast && 'flex-1')}>
            <div className="flex flex-col items-center gap-1">
              <motion.div
                layout
                className={clsx('relative flex items-center justify-center rounded-full border-2', compact ? 'h-5 w-5' : 'h-7 w-7')}
                style={{ borderColor: color, background: done || lastFailed ? color : 'transparent', color: done || lastFailed ? '#07080c' : color }}
                animate={active ? { scale: [1, 1.12, 1] } : { scale: 1 }}
                transition={active ? { repeat: Infinity, duration: 1.4, ease: 'easeInOut' } : { duration: 0.2 }}
              >
                {lastFailed ? <X size={compact ? 10 : 14} strokeWidth={3} /> : done ? <Check size={compact ? 10 : 14} strokeWidth={3} /> : active ? <span className="h-2 w-2 rounded-full" style={{ background: color }} /> : <span className="num text-[10px]">{i + 1}</span>}
              </motion.div>
              <span className={clsx('text-[10px] font-medium uppercase tracking-wider', active || done ? 'text-fg' : 'text-fg-3', lastFailed && 'text-breach')}>
                {lastFailed ? (stage === 'failed' ? 'Failed' : 'Rejected') : LABELS[s]}
              </span>
            </div>
            {!isLast && (
              <div className="relative mx-2 mb-4 h-[2px] flex-1 overflow-hidden rounded bg-white/[0.08]">
                <motion.div
                  className="absolute inset-y-0 left-0"
                  style={{ background: failed && i === STAGES.length - 2 ? '#ff3b5c' : '#60a5fa' }}
                  initial={false}
                  animate={{ width: done ? '100%' : active ? '55%' : '0%' }}
                  transition={{ duration: 0.6, ease: 'easeOut' }}
                />
                {active && running && (
                  <motion.div
                    className="absolute inset-y-0 w-1/3 bg-gradient-to-r from-transparent via-blue/80 to-transparent"
                    animate={{ x: ['-100%', '300%'] }}
                    transition={{ repeat: Infinity, duration: 1.6, ease: 'linear' }}
                  />
                )}
              </div>
            )}
          </li>
        )
      })}
    </ol>
  )
}
