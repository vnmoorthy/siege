import clsx from 'clsx'
import type { CSSProperties, ReactNode } from 'react'

type Props = {
  title?: ReactNode
  right?: ReactNode
  children: ReactNode
  className?: string
  style?: CSSProperties
  bodyClassName?: string
  /** remove body padding (for lists that manage their own) */
  flush?: boolean
}

export function Panel({ title, right, children, className, style, bodyClassName, flush }: Props) {
  return (
    <section className={clsx('glass flex min-h-0 flex-col overflow-hidden', className)} style={style}>
      {(title || right) && (
        <header className="flex shrink-0 items-center justify-between gap-3 border-b border-line px-4 py-2.5">
          {title ? <h2 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-fg-2">{title}</h2> : <span />}
          {right && <div className="flex items-center gap-2 text-xs text-fg-2">{right}</div>}
        </header>
      )}
      <div className={clsx('min-h-0 flex-1', flush ? '' : 'p-4', bodyClassName)}>{children}</div>
    </section>
  )
}
