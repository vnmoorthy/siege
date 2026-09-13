import { useState } from 'react'

/** A static preview cannot share activity between phones. Open the shared host. */
export function LiveCrowdLink() {
  const [address, setAddress] = useState('')
  const [error, setError] = useState('')
  return <details className="border-b border-block/30 bg-block/10 px-3 py-2 text-xs text-block">
    <summary className="cursor-pointer font-semibold">Simulation · connect the live crowd ↗</summary>
    <p className="my-2 leading-relaxed">This activity stays in this browser. Open the live arena, then have everyone scan its QR code.</p>
    <form className="flex flex-wrap gap-2" onSubmit={event => {
      event.preventDefault()
      try {
        const target = new URL(address.trim())
        if (!['http:', 'https:'].includes(target.protocol) || target.username || target.password || target.hostname.endsWith('.github.io')) throw new Error()
        target.pathname = `${target.pathname.replace(/\/(attack|warroom|arena)\/?$/, '').replace(/\/$/, '')}/warroom`
        target.search = '?mock=0'
        target.hash = ''
        window.location.assign(target.href)
      } catch {
        setError('Enter the shared live arena URL, including http:// or https://.')
      }
    }}>
      <label className="flex min-w-0 flex-1 flex-col gap-1">Live arena URL
        <input type="url" required value={address} onChange={event => { setAddress(event.target.value); setError('') }} placeholder="https://your-live-arena.example" className="min-w-0 rounded border border-block/30 bg-ink px-2 py-2 text-fg" />
      </label>
      <button className="self-end rounded border border-block/50 px-3 py-2 font-semibold" type="submit">Open live arena</button>
      {error && <p role="alert" className="w-full">{error}</p>}
    </form>
  </details>
}
