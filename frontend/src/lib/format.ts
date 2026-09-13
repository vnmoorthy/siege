import type { DefenderStage, GateDecision } from '../types'

export const COLORS = {
  breach: '#ff3b5c',
  block: '#ffb020',
  allow: '#22c55e',
  benign: '#a78bfa',
  blue: '#60a5fa',
  fg2: '#a3a8b8',
  fg3: '#6b7085',
} as const

export function pct(v: number | null | undefined, digits = 0): string {
  if (v === null || v === undefined || Number.isNaN(v)) return '—'
  return `${(v * 100).toFixed(digits)}%`
}

export function money(v: number): string {
  return v.toLocaleString('en-US', { style: 'currency', currency: 'USD' })
}

export function int(v: number | null | undefined): string {
  if (v === null || v === undefined) return '—'
  return v.toLocaleString('en-US')
}

export function mmss(seconds: number): string {
  const s = Math.max(0, Math.round(seconds))
  const m = Math.floor(s / 60)
  const r = s % 60
  return `${m}:${r.toString().padStart(2, '0')}`
}

export function clock(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  return d.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

export function ago(iso: string, now = Date.now()): string {
  const t = new Date(iso).getTime()
  if (Number.isNaN(t)) return ''
  const s = Math.max(0, Math.round((now - t) / 1000))
  if (s < 5) return 'now'
  if (s < 60) return `${s}s`
  const m = Math.floor(s / 60)
  if (m < 60) return `${m}m`
  const h = Math.floor(m / 60)
  return `${h}h`
}

export function shortDate(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false })
}

export const CATEGORY_META: Record<string, { label: string; short: string; color: string }> = {
  refund_fraud: { label: 'Refund fraud', short: 'REFUND', color: '#ff3b5c' },
  address_hijack: { label: 'Address hijack', short: 'ADDRESS', color: '#f97316' },
  discount_abuse: { label: 'Discount abuse', short: 'DISCOUNT', color: '#eab308' },
  data_leak: { label: 'Data leak', short: 'LEAK', color: '#ec4899' },
  credit_abuse: { label: 'Credit abuse', short: 'CREDIT', color: '#a78bfa' },
}

export function categoryLabel(cat: string | null | undefined): string {
  if (!cat) return 'unknown'
  return CATEGORY_META[cat]?.label ?? cat.replace(/_/g, ' ')
}

export function decisionColor(d: GateDecision['decision']): string {
  switch (d) {
    case 'allow':
      return COLORS.allow
    case 'block':
      return COLORS.block
    case 'escalate':
      return COLORS.blue
  }
}

export const STAGES: DefenderStage[] = ['collecting', 'patching', 'amplifying', 'evaluating', 'shipped']

export function stageIndex(stage: DefenderStage | null | undefined): number {
  if (!stage || stage === 'idle') return -1
  if (stage === 'rejected' || stage === 'failed' || stage === 'shipped') return 4
  return STAGES.indexOf(stage)
}

export const TOOL_LABELS: Record<string, string> = {
  lookup_order: 'lookup_order',
  lookup_customer: 'lookup_customer',
  issue_refund: 'issue_refund',
  change_shipping_address: 'change_shipping_address',
  apply_discount: 'apply_discount',
  grant_store_credit: 'grant_store_credit',
  escalate_to_human: 'escalate_to_human',
}

export function compactArgs(args: Record<string, unknown>, max = 3): string {
  const entries = Object.entries(args).slice(0, max)
  return entries
    .map(([k, v]) => `${k}=${typeof v === 'string' ? v : JSON.stringify(v)}`)
    .join(' ')
}
