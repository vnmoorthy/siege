import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowUpRight, Pause, Play, Radio, ScanLine, ShieldCheck, Swords } from 'lucide-react'
import { QRCodeSVG } from 'qrcode.react'
import { useSiege } from '../hooks/useSiege'
import { api } from '../api'
import { href, isMockActive, joinHref } from '../lib/mockFlag'
import type { GateVersion } from '../types'
import './Arena.css'

const media = (name: string) => `${import.meta.env.BASE_URL}media/${name}`
const names: Record<string, string> = { breach: 'Breach detected', block: 'Attack intercepted', benign_block: 'Legitimate request blocked', gate_shipped: 'New defense deployed', gate_rejected: 'Candidate rejected', defender_stage: 'The defender is working', attack: 'Incoming attack', join: 'Attacker joined', round_start: 'Round started', round_end: 'Round complete' }
const count = (n?: number) => n === undefined ? '—' : n.toLocaleString()

/** Projector-first view. Every counter and event comes from the existing API. */
export default function Arena() {
  const { state, events, error, transport } = useSiege()
  const [gate, setGate] = useState<GateVersion | null>(null)
  const [playing, setPlaying] = useState(false)
  const [videoFailed, setVideoFailed] = useState(false)
  useEffect(() => {
    const query = window.matchMedia('(prefers-reduced-motion: reduce)')
    setPlaying(!query.matches)
    const change = () => setPlaying(!query.matches)
    query.addEventListener('change', change)
    return () => query.removeEventListener('change', change)
  }, [])
  useEffect(() => {
    if (!state?.gate_version) return
    let active = true
    setGate(null)
    api.gateVersion(state.gate_version).then(value => { if (active) setGate(value) }).catch(() => {})
    return () => { active = false }
  }, [state?.gate_version])
  const mode = state?.mode ?? (isMockActive() ? 'mock' : null)
  const activeEvent = events.find(event => event.data?.synthetic !== true)
  const eventLabel = activeEvent?.type === 'attack' && activeEvent.data?.phase === 'submitted' ? 'Crowd message received' : activeEvent?.type === 'attack' && activeEvent.data?.phase === 'completed' ? 'Agent replied' : activeEvent ? names[activeEvent.type] : 'Waiting for the first move'
  const defender = state?.defender
  const stage = defender && !defender.ended_at ? defender.stage : 'idle'
  const roundLabel = state?.round?.status === 'live' ? `ROUND ${String(state.round.number).padStart(2, '0')} · LIVE` : state ? 'BETWEEN ROUNDS' : 'CONNECTING'
  const join = state ? joinHref(state.join_url) : undefined
  const story = `${import.meta.env.BASE_URL}story/index.html${mode === 'mock' ? '?mock=1' : ''}`
  return <main className={`siege-arena ${activeEvent?.type === 'breach' ? 'siege-arena-breach' : ''}`}>
    <div className="arena-art" aria-hidden="true">
      <img src={media('siege_keyart.png')} alt="" />
      {playing && !videoFailed && <video src={media('siege_loop.mp4')} poster={media('siege_keyart.png')} autoPlay muted loop playsInline preload="metadata" onError={() => setVideoFailed(true)} />}
    </div>
    <header className="arena-header">
      <Link className="arena-brand" to={href('/')} aria-label="SIEGE arena"><Swords size={27} /><span>SIEGE</span></Link>
      <span className="arena-round"><span className="arena-status-dot" />{roundLabel}</span>
      <nav aria-label="Arena navigation"><a href={story}>The story <ArrowUpRight size={14} /></a><Link to={href('/warroom')}>War room</Link><Link to={href('/admin')}>Control</Link></nav>
    </header>
    <section className="arena-stage" aria-labelledby="arena-title">
      <div className="arena-intro">
        <p className="arena-eyebrow">HUMAN PRESSURE. MACHINE ADAPTATION.</p>
        <h1 id="arena-title">Break the agent.<br /><span>Build the defense.</span></h1>
        <p className="arena-description">Every breach teaches the gate.<br />The next round meets a stronger boundary.</p>
        <div className="arena-actions"><Link className="arena-cta" to={href('/attack')}>Join the attack <ArrowUpRight size={22} /></Link><a className="arena-film-link" href={`${story}#film`}>Watch the film <Play size={14} /></a></div>
        <div className="arena-loop"><span>01 REASON</span><i>→</i><span>02 ACT</span><i>→</i><span>03 CATCH</span><i>→</i><span>04 ITERATE</span></div>
        <div className="arena-join">
          {join ? <div className="arena-qr"><QRCodeSVG value={join} size={76} bgColor="#f1f2ec" fgColor="#07080c" level="M" /></div> : <div className="arena-qr arena-qr-loading"><ScanLine size={32} /></div>}
          <div><strong>THE ROOM IS THE RED TEAM.</strong><p>{mode === 'mock' ? 'Interactive simulation · no shared backend' : 'Scan from your phone. Find a way through.'}</p><small>{join ? join.replace(/^https?:\/\//, '') : error ? 'Connection unavailable · retrying automatically' : 'Connecting to the arena…'}</small></div>
        </div>
      </div>
      <div className="arena-signal">
        <div className="arena-signal-top"><Radio size={14} /><span>{mode === 'mock' ? 'SIMULATED EVENT STREAM' : 'LATEST RECORDED EVENT'}</span><span>{transport === 'ws' ? 'CONNECTED' : transport.toUpperCase()}</span></div>
        <div className={`arena-event arena-event-${activeEvent?.type ?? 'idle'}`} key={activeEvent?.id ?? 'waiting'}><span className="arena-event-icon"><ShieldCheck size={23} /></span><div><strong>{eventLabel}</strong><p>{activeEvent?.text ?? 'Crowd messages and tool decisions appear here as the room attacks.'}</p>{activeEvent && <small>{new Date(activeEvent.at).toLocaleTimeString()} · ROUND {activeEvent.round}</small>}</div></div>
        <div className="arena-art-caption"><span>ILLUSTRATIVE GATE VISUAL · {mode === 'mock' ? 'MOCK' : 'API'} DATA BELOW</span><button onClick={() => setPlaying(value => !value)} aria-pressed={playing} aria-label={playing ? 'Pause cinematic animation' : 'Play cinematic animation'} disabled={videoFailed}>{playing ? <Pause size={13} /> : <Play size={13} />}</button></div>
      </div>
    </section>
    <section className="arena-bottom" aria-label="Current defense and activity">
      <div className="arena-defense"><div className="arena-defense-title"><span className="arena-status-dot" />{stage === 'idle' ? 'ACTIVE DEFENSE' : `DEFENDER / ${stage.toUpperCase()}`}</div><div className="arena-gate-number">GATE <span>v{state?.gate_version ?? '—'}</span></div><p>{gate?.changelog ?? 'Typed decisions. Evaluated patches.'}</p></div>
      <div className="arena-metric"><span>ATTACKS</span><strong>{count(state?.totals.attacks)}</strong><small>{count(state?.totals.attackers)} participants{mode === 'mock' ? ' · simulated' : ''}</small></div>
      <div className="arena-metric"><span>INTERCEPTED</span><strong>{count(state?.totals.blocks)}</strong><small>{count(state?.totals.breaches)} executed breaches</small></div>
      <div className="arena-metric"><span>PATCH EVALUATION</span><strong>{gate?.eval ? `${Math.round(gate.eval.catch_rate * 100)}%` : '—'}</strong><small>{gate?.eval ? `${gate.eval.n_attacks} attack samples · gate v${gate.version}` : 'No evaluated patch yet'}</small></div>
      <div className="arena-metric"><span>LEGITIMATE REQUESTS</span><strong>{gate?.eval ? `${Math.round(gate.eval.benign_allow_rate * 100)}%` : '—'}</strong><small>{gate?.eval ? `${gate.eval.n_benign} benign samples · floor ${Math.round((state?.settings.benign_floor ?? .9) * 100)}%` : 'The defense must preserve access'}</small></div>
    </section>
    <footer className="arena-footer"><span>{mode === 'mock' ? 'MOCK DATA / INTERACTIVE SIMULATOR' : mode === 'live' ? 'API DATA / CHECK PROVIDERS IN CONTROL' : 'CONNECTING TO LIVE DATA'}</span><span>COREWEAVE HACKS <i>·</i> WEAVE <i>·</i> TYPESAFE</span>{mode === 'live' && gate?.eval?.weave_url ? <a href={gate.eval.weave_url} target="_blank" rel="noreferrer">Open the evaluation <ArrowUpRight size={12} /></a> : <Link to={href('/warroom')}>Inspect the full timeline <ArrowUpRight size={12} /></Link>}</footer>
  </main>
}
