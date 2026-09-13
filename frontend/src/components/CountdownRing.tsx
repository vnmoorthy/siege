import clsx from 'clsx'
import { mmss } from '../lib/format'

type Props = {
  secondsLeft: number
  total: number
  size?: number
  stroke?: number
  live?: boolean
  className?: string
}

export function CountdownRing({ secondsLeft, total, size = 64, stroke = 5, live = true, className }: Props) {
  const r = (size - stroke) / 2
  const c = 2 * Math.PI * r
  const frac = total > 0 ? Math.max(0, Math.min(1, secondsLeft / total)) : 0
  const urgent = live && secondsLeft <= 10
  const color = !live ? '#6b7085' : urgent ? '#ff3b5c' : frac < 0.33 ? '#ffb020' : '#60a5fa'
  return (
    <div className={clsx('relative shrink-0', className)} style={{ width: size, height: size }} aria-label={`${secondsLeft} seconds left`}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth={stroke} />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke={color}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={c}
          strokeDashoffset={c * (1 - frac)}
          style={{ transition: 'stroke-dashoffset 0.9s linear, stroke 0.4s ease' }}
        />
      </svg>
      <div className={clsx('num absolute inset-0 flex items-center justify-center font-semibold', size >= 60 ? 'text-sm' : 'text-[11px]', urgent && 'text-breach')}>
        {live ? mmss(secondsLeft) : '—'}
      </div>
    </div>
  )
}
