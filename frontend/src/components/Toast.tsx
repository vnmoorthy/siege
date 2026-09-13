import clsx from 'clsx'
import { AnimatePresence, motion } from 'framer-motion'
import { AlertCircle, CheckCircle2, Info, X } from 'lucide-react'
import { useCallback, useMemo, useRef, useState, type ReactNode } from 'react'
import { ToastContext, type ToastApi, type ToastTone } from './toastContext'

type ToastItem = { id: number; tone: ToastTone; message: string }

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([])
  const nextId = useRef(1)
  const push = useCallback((message: string, tone: ToastTone = 'info') => {
    const id = nextId.current++
    setItems((xs) => [...xs.slice(-3), { id, tone, message }])
    window.setTimeout(() => setItems((xs) => xs.filter((x) => x.id !== id)), tone === 'error' ? 6000 : 3500)
  }, [])
  const api = useMemo<ToastApi>(() => ({ push, error: (m) => push(m, 'error'), success: (m) => push(m, 'success') }), [push])
  return (
    <ToastContext.Provider value={api}>
      {children}
      <div className="pointer-events-none fixed inset-x-0 bottom-4 z-[100] flex flex-col items-center gap-2 px-4">
        <AnimatePresence initial={false}>
          {items.map((t) => (
            <motion.div
              key={t.id}
              layout
              initial={{ opacity: 0, y: 16, scale: 0.96 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 8, scale: 0.98 }}
              transition={{ duration: 0.2 }}
              className={clsx(
                'pointer-events-auto flex max-w-md items-start gap-2 rounded-lg border px-3 py-2 text-xs shadow-xl backdrop-blur',
                t.tone === 'error' && 'border-breach/40 bg-[#1a0b10]/95 text-fg',
                t.tone === 'success' && 'border-allow/40 bg-[#07130c]/95 text-fg',
                t.tone === 'info' && 'border-white/10 bg-ink-3/95 text-fg',
              )}
              role="status"
            >
              <span className="mt-[1px] shrink-0">
                {t.tone === 'error' ? <AlertCircle size={14} className="text-breach" /> : t.tone === 'success' ? <CheckCircle2 size={14} className="text-allow" /> : <Info size={14} className="text-blue" />}
              </span>
              <span className="min-w-0 flex-1 break-words">{t.message}</span>
              <button type="button" aria-label="Dismiss" onClick={() => setItems((xs) => xs.filter((x) => x.id !== t.id))} className="shrink-0 text-fg-3 hover:text-fg">
                <X size={12} />
              </button>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </ToastContext.Provider>
  )
}
