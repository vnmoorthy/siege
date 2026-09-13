import clsx from 'clsx'
import type { ReactNode } from 'react'

export type Tone = 'neutral' | 'red' | 'amber' | 'green' | 'violet' | 'blue'

const TONES: Record<Tone, string> = {
  neutral: 'border-white/10 bg-white/[0.04] text-fg-2',
  red: 'border-breach/40 bg-breach/10 text-breach',
  amber: 'border-block/40 bg-block/10 text-block',
  green: 'border-allow/40 bg-allow/10 text-allow',
  violet: 'border-benign/40 bg-benign/10 text-benign',
  blue: 'border-blue/40 bg-blue/10 text-blue',
}

const DOTS: Record<Tone, string> = {
  neutral: 'bg-fg-3',
  red: 'bg-breach',
  amber: 'bg-block',
  green: 'bg-allow',
  violet: 'bg-benign',
  blue: 'bg-blue',
}

type Props = {
  tone?: Tone
  dot?: boolean
  pulse?: boolean
  mono?: boolean
  size?: 'xs' | 'sm'
  className?: string
  title?: string
  children: ReactNode
}

export function Chip({ tone = 'neutral', dot, pulse, mono, size = 'sm', className, title, children }: Props) {
  return (
    <span
      title={title}
      className={clsx(
        'inline-flex items-center gap-1.5 whitespace-nowrap rounded-full border font-medium',
        size === 'xs' ? 'h-5 px-2 text-[10px]' : 'h-6 px-2.5 text-[11px]',
        mono && 'num',
        TONES[tone],
        className,
      )}
    >
      {dot && (
        <span className="relative flex h-1.5 w-1.5">
          {pulse && <span className={clsx('absolute inline-flex h-full w-full animate-ping rounded-full opacity-60', DOTS[tone])} />}
          <span className={clsx('relative inline-flex h-1.5 w-1.5 rounded-full', DOTS[tone])} />
        </span>
      )}
      {children}
    </span>
  )
}
