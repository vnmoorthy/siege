import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { lazy, Suspense } from 'react'
import { MockChip } from './components/MockChip'
import { ToastProvider } from './components/Toast'
import Arena from './pages/Arena'

const Admin = lazy(() => import('./pages/Admin'))
const Attack = lazy(() => import('./pages/Attack'))
const WarRoom = lazy(() => import('./pages/WarRoom'))

export default function App() {
  return (
    <BrowserRouter basename={import.meta.env.BASE_URL}>
      <ToastProvider>
        <Suspense fallback={<div className="flex min-h-screen items-center justify-center bg-ink text-fg-2">Opening SIEGE…</div>}>
        <Routes>
          <Route path="/" element={<Arena />} />
          <Route path="/arena" element={<Arena />} />
          <Route path="/warroom" element={<WarRoom />} />
          <Route path="/attack" element={<Attack />} />
          <Route path="/admin" element={<Admin />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
        </Suspense>
        <MockChip />
      </ToastProvider>
    </BrowserRouter>
  )
}
