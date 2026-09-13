import clsx from 'clsx'
import { AnimatePresence, motion } from 'framer-motion'
import { ShieldCheck } from 'lucide-react'

type Props = { version: number; size?: 'sm' | 'lg'; className?: string }

/** Gate version badge — flips and glows when the version changes. */
export function GateBadge({ version, size = 'lg', className }: Props) {
  return (
    <div className={clsx('relative inline-flex items-center gap-2 overflow-hidden rounded-lg border border-allow/30 bg-allow/[0.06] text-allow', size === 'lg' ? 'h-11 px-3' : 'h-7 px-2', className)}>
      <ShieldCheck size={size === 'lg' ? 18 : 13} strokeWidth={2.5} />
      <span className={clsx('font-medium uppercase tracking-[0.14em] text-allow/80', size === 'lg' ? 'text-[10px]' : 'text-[9px]')}>gate</span>
      <span className={clsx('relative inline-block overflow-hidden', size === 'lg' ? 'h-6 min-w-[3ch]' : 'h-4 min-w-[2.5ch]')}>
        <AnimatePresence initial={false} mode="popLayout">
          <motion.span
            key={version}
            initial={{ y: '100%', opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: '-100%', opacity: 0 }}
            transition={{ type: 'spring', stiffness: 420, damping: 30 }}
            className={clsx('num absolute inset-0 flex items-center font-bold leading-none', size === 'lg' ? 'text-xl' : 'text-sm')}
          >
            v{version}
          </motion.span>
        </AnimatePresence>
      </span>
      <AnimatePresence>
        <motion.span
          key={`glow-${version}`}
          initial={{ opacity: 0.8 }}
          animate={{ opacity: 0 }}
          transition={{ duration: 1.6, ease: 'easeOut' }}
          className="pointer-events-none absolute inset-0 rounded-lg bg-allow/30"
        />
      </AnimatePresence>
    </div>
  )
}
