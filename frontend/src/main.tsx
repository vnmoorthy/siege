import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { isMockActive } from './lib/mockFlag'

if (isMockActive()) {
  // Lazy so the simulator never ships in the critical path of a real deployment.
  const fresh = new URLSearchParams(window.location.search).get('mock') === 'fresh'
  const { installMock } = await import('./mock/mockServer')
  installMock({ fresh })
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
