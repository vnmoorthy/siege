import { Radio, RefreshCw } from 'lucide-react'
import type { Transport } from '../hooks/useSiege'
import { Chip } from './Chip'

export function ConnChip({ transport, error }: { transport: Transport; error: string | null }) {
  if (transport === 'ws') {
    return (
      <Chip tone="green" size="xs" dot pulse title="WebSocket connected">
        <Radio size={10} /> live
      </Chip>
    )
  }
  if (transport === 'poll') {
    return (
      <Chip tone="amber" size="xs" dot title={error ? `Polling (${error})` : 'Socket down — polling every 2s'}>
        <RefreshCw size={10} className="animate-spin [animation-duration:3s]" /> polling
      </Chip>
    )
  }
  return (
    <Chip tone="neutral" size="xs" dot title="Connecting">
      connecting
    </Chip>
  )
}
