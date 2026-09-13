import clsx from 'clsx'
import { motion } from 'framer-motion'
import type { ReactNode } from 'react'

type Props = {
  label: string
  value: string
  sub?: ReactNode
  /** accent color for the value (hex) */
  accent?: string
  size?: 'md' | 'lg'
  className?: string
}

export function Stat({ label, value, sub, accent, size = 'md', className }: Props) {
  return (
    <div className={clsx('glass flex flex-col justify-between gap-1 px-4 py-3', className)}>
      <div className="text-[11px] font-medium uppercase tracking-[0.14em] text-fg-3">{label}</div>
      <motion.div
        key={value}
        initial={{ opacity: 0.4, y: 4 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.25 }}
        className={clsx('num font-semibold leading-none', size === 'lg' ? 'text-[40px]' : 'text-[30px]')}
        style={accent ? { color: accent } : undefined}
      >
        {value}
      </motion.div>
      {sub !== undefined && <div className="text-xs text-fg-2">{sub}</div>}
    </div>
  )
}
