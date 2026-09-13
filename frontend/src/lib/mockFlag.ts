const KEY = 'siege_mock'

/** Mock mode is on when the URL has ?mock=1 (or ?mock=fresh for an empty simulator), VITE_MOCK=1, or it was enabled earlier this tab. */
export function isMockActive(): boolean {
  if (typeof window === 'undefined') return false
  const params = new URLSearchParams(window.location.search)
  const q = params.get('mock')
  if (q === '1' || q === 'true' || q === 'fresh') {
    try {
      sessionStorage.setItem(KEY, '1')
    } catch {
      // storage unavailable
    }
    return true
  }
  if (q === '0' || q === 'false') {
    try {
      sessionStorage.removeItem(KEY)
    } catch {
      // storage unavailable
    }
    return false
  }
  if (import.meta.env.VITE_MOCK === '1') return true
  try {
    return sessionStorage.getItem(KEY) === '1'
  } catch {
    return false
  }
}

/** Build an in-app href that preserves ?mock=1 so client-side navigation stays in mock mode. */
export function href(path: string): string {
  const mode = isMockActive() ? '1' : '0'
  return path.includes('?') ? `${path}&mock=${mode}` : `${path}?mock=${mode}`
}

/** A returning phone must explicitly leave its earlier browser simulation. */
export function joinHref(url: string): string {
  const target = new URL(url, window.location.origin)
  target.searchParams.set('mock', isMockActive() ? '1' : '0')
  return target.href
}
