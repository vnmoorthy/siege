import type { ProviderStatus, State } from '../types'
import { Chip } from './Chip'

type Props = { providers: ProviderStatus | null | undefined; mode?: State['mode']; size?: 'xs' | 'sm'; compact?: boolean }

/** Live vs fallback chips per provider. Honest: a degraded provider turns amber. */
export function ProviderChips({ providers, mode, size = 'xs', compact }: Props) {
  if (!providers) return null
  const rows: { key: string; label: string; live: boolean; detail: string }[] = [
    { key: 'agent', label: 'agent', live: providers.agent.live, detail: `${providers.agent.provider} · ${providers.agent.model}` },
    { key: 'gate', label: 'gate', live: providers.gate.live, detail: `${providers.gate.provider} · ${providers.gate.model}` },
    { key: 'defender', label: 'defender', live: providers.defender.live, detail: `${providers.defender.provider} · ${providers.defender.model}` },
    { key: 'redteam', label: 'red team', live: providers.redteam.live, detail: `${providers.redteam.provider} · ${providers.redteam.model}` },
    { key: 'weave', label: 'weave', live: providers.weave.live, detail: providers.weave.project },
    { key: 'sandbox', label: 'sandbox', live: providers.sandbox.live, detail: providers.sandbox.provider },
  ]
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {mode && (
        <Chip tone={mode === 'live' ? 'green' : 'amber'} size={size} dot pulse={mode === 'live'} title={mode === 'live' ? 'Backend running with real providers' : 'Backend in mock mode'}>
          {mode === 'live' ? 'LIVE' : 'MOCK MODE'}
        </Chip>
      )}
      {rows.map((r) => (
        <Chip key={r.key} tone={mode === 'mock' ? 'amber' : r.live ? 'green' : 'amber'} size={size} dot title={`${r.label}: ${r.detail} — ${mode === 'mock' ? 'simulated' : r.live ? 'live' : 'fallback'}`}>
          {r.label}
          {!compact && <span className="text-fg-3">{mode === 'mock' ? 'simulated' : r.live ? 'live' : 'fallback'}</span>}
        </Chip>
      ))}
    </div>
  )
}
