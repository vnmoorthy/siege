import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { MockChip } from './components/MockChip'
import { ToastProvider } from './components/Toast'
import Admin from './pages/Admin'
import Attack from './pages/Attack'
import WarRoom from './pages/WarRoom'

export default function App() {
  return (
    <BrowserRouter>
      <ToastProvider>
        <Routes>
          <Route path="/" element={<WarRoom />} />
          <Route path="/attack" element={<Attack />} />
          <Route path="/admin" element={<Admin />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
        <MockChip />
      </ToastProvider>
    </BrowserRouter>
  )
}
