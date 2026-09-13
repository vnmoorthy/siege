import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { MockChip } from './components/MockChip'
import { ToastProvider } from './components/Toast'
import Admin from './pages/Admin'
import Attack from './pages/Attack'
import WarRoom from './pages/WarRoom'
import Arena from './pages/Arena'

export default function App() {
  return (
    <BrowserRouter basename={import.meta.env.BASE_URL}>
      <ToastProvider>
        <Routes>
          <Route path="/" element={<Arena />} />
          <Route path="/arena" element={<Arena />} />
          <Route path="/warroom" element={<WarRoom />} />
          <Route path="/attack" element={<Attack />} />
          <Route path="/admin" element={<Admin />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
        <MockChip />
      </ToastProvider>
    </BrowserRouter>
  )
}
