import { createContext, useContext } from 'react'

export type ToastTone = 'info' | 'success' | 'error'

export type ToastApi = {
  push: (message: string, tone?: ToastTone) => void
  error: (message: string) => void
  success: (message: string) => void
}

export const ToastContext = createContext<ToastApi | null>(null)

export function useToast(): ToastApi {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be used inside <ToastProvider>')
  return ctx
}
