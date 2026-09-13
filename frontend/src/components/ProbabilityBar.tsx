import clsx from 'clsx'
import { decisionColor } from '../lib/format'

const ORDER = ['allow', 'block', 'escalate'] as const

type Props = {
  probabilities: Record<string, number>
  decision?: string
  className?: string
  /** show the numeric labels under the bar */
  labels?: boolean
}

export function ProbabilityBar({ probabilities, decision, className, labels = true }: Props) {
  const keys = [...ORDER.filter((k) => k in probabilities), ...Object.keys(probabilities).filter((k) => !(ORDER as readonly string[]).includes(k))]
  const total = keys.reduce((s, k) => s + (probabilities[k] ?? 0), 0) || 1
  return (
    <div className={clsx('min-w-0', className)}>
      <div className="flex h-1.5 w-full overflow-hidden rounded-full bg-white/[0.06]">
        {keys.map((k) => {
          const v = (probabilities[k] ?? 0) / total
          const color = k === 'allow' || k === 'block' || k === 'escalate' ? decisionColor(k) : '#6b7085'
          return (
            <div
              key={k}
              className="h-full transition-[width] duration-500"
              style={{ width: `${Math.max(0, v * 100)}%`, background: color, opacity: decision && decision !== k ? 0.45 : 1 }}
              title={`${k} ${(v * 100).toFixed(0)}%`}
            />
          )
        })}
      </div>
      {labels && (
        <div className="num mt-1 flex gap-2 text-[10px] leading-none text-fg-3">
          {keys.map((k) => (
            <span key={k} className={clsx(decision === k && 'text-fg')}>
              {k} {((probabilities[k] ?? 0) * 100).toFixed(0)}%
            </span>
          ))}
        </div>
      )}
    </div>
  )
}
