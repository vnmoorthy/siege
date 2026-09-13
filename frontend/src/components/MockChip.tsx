import { FlaskConical } from 'lucide-react'
import { isMockActive } from '../lib/mockFlag'

/** Small fixed chip shown whenever the in-browser simulator is driving the UI. */
export function MockChip() {
  if (!isMockActive()) return null
  return (
    <div className="pointer-events-none fixed right-3 top-[54px] z-[90] inline-flex sm:bottom-3 sm:left-3 sm:right-auto sm:top-auto items-center gap-1.5 rounded-full border border-block/50 bg-[#1a1408]/90 px-2.5 py-1 text-[10px] font-bold uppercase tracking-[0.14em] text-block shadow-lg backdrop-blur">
      <FlaskConical size={11} strokeWidth={2.5} />
      Mock data
    </div>
  )
}
