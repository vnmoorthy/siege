/*
 * SiegeField — the living battlefield rendered behind the war room panels.
 *
 * A full-viewport three.js canvas (fixed, z-index 0, pointer-events none).
 * Everything is additive-blended point sprites / glow sprites on the page's
 * near-black ground, driven by real data from useSiege:
 *
 *   - THE GATE: an emerald ring at the centre whose brightness and thickness
 *     follow the active gate's catch rate. A version change fires shockwaves
 *     and a short "GATE vN" HTML overlay.
 *   - ATTACKS: every new attack/block/benign_block/breach event launches a
 *     projectile from the viewport edge toward the gate. Blocks shatter on the
 *     ring, breaches punch through to the core (red flash + vignette),
 *     allowed attacks dissolve softly.
 *   - AMBIENT: slow-drifting dust, a far star field and a faint grid with
 *     mouse parallax; the dust tints redder as the live round's breach rate
 *     climbs.
 *   - DEFENDER: violet satellites orbit the gate while the defender works;
 *     they collapse into the ring on ship and disperse on reject.
 *
 * The engine is plain TypeScript (FieldEngine). React only forwards state
 * deltas and new event ids; the animation loop never touches React state.
 */

import { AnimatePresence, motion } from 'framer-motion'
import { useEffect, useRef, useState } from 'react'
import * as THREE from 'three'
import type { DefenderStage, Event, State } from '../types'

// Legacy (WYSIWYG) colour pipeline: hex in == hex out. Every material here is
// additive on a near-black clear colour, so no sRGB round trip is wanted.
THREE.ColorManagement.enabled = false

// ---------------------------------------------------------------------------
// constants
// ---------------------------------------------------------------------------

const BG = 0x07080c
const FOV = 45
/** Visible half-height of the z=0 plane in world units (width follows aspect). */
const HALF_H = 50
const CAM_Z = HALF_H / Math.tan((FOV * Math.PI) / 360)
const GATE_R = 11
const MAX_PROJECTILES = 60
const POOL_CAP = 6000
const AMBIENT_N = 640
const STARS_N = 420
const MAX_DPR = 1.5
/** History guard: events stamped this long before mount are never animated. */
const STALE_MS = 5000

const COL = {
  emerald: new THREE.Color('#22c55e'),
  amber: new THREE.Color('#ffb020'),
  violet: new THREE.Color('#a78bfa'),
  red: new THREE.Color('#ff3b5c'),
  blue: new THREE.Color('#60a5fa'),
  white: new THREE.Color('#ffffff'),
  ambient: new THREE.Color('#5d6d94'),
  star: new THREE.Color('#9fb0d6'),
  grid: new THREE.Color('#5b6b8f'),
}

type Kind = 'attack' | 'block' | 'benign_block' | 'breach'
const TRAIL: Record<Kind, THREE.Color> = { attack: COL.blue, block: COL.amber, benign_block: COL.violet, breach: COL.red }
const HEAD: Record<Kind, THREE.Color> = {
  attack: COL.white.clone().lerp(COL.blue, 0.35),
  block: COL.white.clone().lerp(COL.amber, 0.35),
  benign_block: COL.white.clone().lerp(COL.violet, 0.35),
  breach: COL.white.clone().lerp(COL.red, 0.4),
}

const rand = (a: number, b: number) => a + Math.random() * (b - a)
const clamp01 = (v: number) => (v < 0 ? 0 : v > 1 ? 1 : v)
const easeOutCubic = (k: number) => 1 - Math.pow(1 - k, 3)

// ---------------------------------------------------------------------------
// textures + shaders
// ---------------------------------------------------------------------------

function glowTexture(stops: ReadonlyArray<readonly [number, number]>): THREE.CanvasTexture {
  const size = 64
  const canvas = document.createElement('canvas')
  canvas.width = size
  canvas.height = size
  const ctx = canvas.getContext('2d')
  if (ctx) {
    const g = ctx.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2)
    for (const [offset, alpha] of stops) g.addColorStop(offset, `rgba(255,255,255,${alpha})`)
    ctx.fillStyle = g
    ctx.fillRect(0, 0, size, size)
  }
  const tex = new THREE.CanvasTexture(canvas)
  tex.minFilter = THREE.LinearFilter
  tex.magFilter = THREE.LinearFilter
  tex.generateMipmaps = false
  return tex
}

const VERT = /* glsl */ `
attribute float aSize;
attribute float aAlpha;
attribute vec3 aColor;
uniform float uScale;
uniform float uSize;
varying float vAlpha;
varying vec3 vColor;
void main() {
  vColor = aColor;
  vAlpha = aAlpha;
  vec4 mv = modelViewMatrix * vec4(position, 1.0);
  gl_PointSize = aSize * uSize * (uScale / -mv.z);
  gl_Position = projectionMatrix * mv;
}`

const FRAG = /* glsl */ `
uniform sampler2D uTex;
uniform vec3 uColor;
uniform float uAlpha;
varying float vAlpha;
varying vec3 vColor;
void main() {
  float a = texture2D(uTex, gl_PointCoord).a;
  gl_FragColor = vec4(vColor * uColor, a * vAlpha * uAlpha);
}`

/** Additive point-sprite material. aSize is a world-space diameter at z=0. */
function pointMaterial(tex: THREE.Texture, size = 1): THREE.ShaderMaterial {
  return new THREE.ShaderMaterial({
    uniforms: {
      uTex: { value: tex },
      uScale: { value: 1000 },
      uSize: { value: size },
      uColor: { value: new THREE.Color(1, 1, 1) },
      uAlpha: { value: 1 },
    },
    vertexShader: VERT,
    fragmentShader: FRAG,
    transparent: true,
    depthWrite: false,
    depthTest: false,
    blending: THREE.AdditiveBlending,
  })
}

function dynAttr(n: number, itemSize: number): THREE.BufferAttribute {
  return new THREE.BufferAttribute(new Float32Array(n * itemSize), itemSize).setUsage(THREE.DynamicDrawUsage)
}

// ---------------------------------------------------------------------------
// particle pool — every transient spark, trail and fragment in one draw call
// ---------------------------------------------------------------------------

class Pool {
  readonly points: THREE.Points
  readonly material: THREE.ShaderMaterial
  private readonly cap: number
  private readonly z: number
  private n = 0
  private readonly geometry: THREE.BufferGeometry
  private readonly pos: THREE.BufferAttribute
  private readonly col: THREE.BufferAttribute
  private readonly siz: THREE.BufferAttribute
  private readonly alp: THREE.BufferAttribute
  private readonly posArr: Float32Array
  private readonly colArr: Float32Array
  private readonly sizArr: Float32Array
  private readonly alpArr: Float32Array
  private readonly px: Float32Array
  private readonly py: Float32Array
  private readonly vx: Float32Array
  private readonly vy: Float32Array
  private readonly age: Float32Array
  private readonly life: Float32Array
  private readonly s0: Float32Array
  private readonly s1: Float32Array
  private readonly cr: Float32Array
  private readonly cg: Float32Array
  private readonly cb: Float32Array
  private readonly a0: Float32Array
  private readonly drag: Float32Array

  constructor(cap: number, tex: THREE.Texture, z: number) {
    this.cap = cap
    this.z = z
    const geometry = new THREE.BufferGeometry()
    this.pos = dynAttr(cap, 3)
    this.col = dynAttr(cap, 3)
    this.siz = dynAttr(cap, 1)
    this.alp = dynAttr(cap, 1)
    this.posArr = this.pos.array as Float32Array
    this.colArr = this.col.array as Float32Array
    this.sizArr = this.siz.array as Float32Array
    this.alpArr = this.alp.array as Float32Array
    geometry.setAttribute('position', this.pos)
    geometry.setAttribute('aColor', this.col)
    geometry.setAttribute('aSize', this.siz)
    geometry.setAttribute('aAlpha', this.alp)
    geometry.setDrawRange(0, 0)
    this.geometry = geometry
    this.material = pointMaterial(tex, 1)
    this.points = new THREE.Points(geometry, this.material)
    this.points.frustumCulled = false
    this.points.renderOrder = 4
    const f = () => new Float32Array(cap)
    this.px = f()
    this.py = f()
    this.vx = f()
    this.vy = f()
    this.age = f()
    this.life = f()
    this.s0 = f()
    this.s1 = f()
    this.cr = f()
    this.cg = f()
    this.cb = f()
    this.a0 = f()
    this.drag = f()
  }

  get count(): number {
    return this.n
  }

  spawn(x: number, y: number, vx: number, vy: number, life: number, s0: number, s1: number, color: THREE.Color, alpha: number, drag: number): void {
    if (this.n >= this.cap) return
    const i = this.n++
    this.px[i] = x
    this.py[i] = y
    this.vx[i] = vx
    this.vy[i] = vy
    this.age[i] = 0
    this.life[i] = life
    this.s0[i] = s0
    this.s1[i] = s1
    this.cr[i] = color.r
    this.cg[i] = color.g
    this.cb[i] = color.b
    this.a0[i] = alpha
    this.drag[i] = drag
  }

  private removeAt(i: number): void {
    const j = --this.n
    if (i === j) return
    this.px[i] = this.px[j]
    this.py[i] = this.py[j]
    this.vx[i] = this.vx[j]
    this.vy[i] = this.vy[j]
    this.age[i] = this.age[j]
    this.life[i] = this.life[j]
    this.s0[i] = this.s0[j]
    this.s1[i] = this.s1[j]
    this.cr[i] = this.cr[j]
    this.cg[i] = this.cg[j]
    this.cb[i] = this.cb[j]
    this.a0[i] = this.a0[j]
    this.drag[i] = this.drag[j]
  }

  update(dt: number): void {
    const { px, py, vx, vy, age, life, s0, s1, cr, cg, cb, a0, drag, posArr, colArr, sizArr, alpArr, z } = this
    let i = 0
    while (i < this.n) {
      const a = age[i] + dt
      const l = life[i]
      if (a >= l) {
        this.removeAt(i)
        continue
      }
      age[i] = a
      const d = drag[i] * dt
      const damp = d >= 1 ? 0 : 1 - d
      vx[i] *= damp
      vy[i] *= damp
      const x = (px[i] += vx[i] * dt)
      const y = (py[i] += vy[i] * dt)
      const k = a / l
      const j = i * 3
      posArr[j] = x
      posArr[j + 1] = y
      posArr[j + 2] = z
      colArr[j] = cr[i]
      colArr[j + 1] = cg[i]
      colArr[j + 2] = cb[i]
      sizArr[i] = s0[i] + (s1[i] - s0[i]) * k
      alpArr[i] = a0[i] * (1 - k * k)
      i++
    }
    this.geometry.setDrawRange(0, this.n)
    if (this.n > 0) {
      for (const attr of [this.pos, this.col]) {
        attr.clearUpdateRanges()
        attr.addUpdateRange(0, this.n * 3)
        attr.needsUpdate = true
      }
      for (const attr of [this.siz, this.alp]) {
        attr.clearUpdateRanges()
        attr.addUpdateRange(0, this.n)
        attr.needsUpdate = true
      }
    }
  }

  dispose(): void {
    this.geometry.dispose()
    this.material.dispose()
  }
}

// ---------------------------------------------------------------------------
// flash sprites (big soft glows — sprites have no GPU point-size cap)
// ---------------------------------------------------------------------------

type Flash = { sprite: THREE.Sprite; mat: THREE.SpriteMaterial; age: number; life: number; sc0: number; sc1: number; op: number; active: boolean }

class FlashPool {
  private readonly items: Flash[] = []
  private next = 0

  constructor(n: number, tex: THREE.Texture, scene: THREE.Scene, z: number) {
    for (let i = 0; i < n; i++) {
      const mat = new THREE.SpriteMaterial({ map: tex, transparent: true, opacity: 0, blending: THREE.AdditiveBlending, depthWrite: false, depthTest: false })
      const sprite = new THREE.Sprite(mat)
      sprite.visible = false
      sprite.position.z = z
      sprite.renderOrder = 5
      scene.add(sprite)
      this.items.push({ sprite, mat, age: 0, life: 1, sc0: 1, sc1: 1, op: 1, active: false })
    }
  }

  spawn(x: number, y: number, color: THREE.Color, sc0: number, sc1: number, op: number, life: number): void {
    const f = this.items[this.next]
    this.next = (this.next + 1) % this.items.length
    f.active = true
    f.age = 0
    f.life = life
    f.sc0 = sc0
    f.sc1 = sc1
    f.op = op
    f.sprite.position.x = x
    f.sprite.position.y = y
    f.sprite.scale.set(sc0, sc0, 1)
    f.sprite.visible = true
    f.mat.color.copy(color)
    f.mat.opacity = op
  }

  update(dt: number): void {
    for (const f of this.items) {
      if (!f.active) continue
      f.age += dt
      const k = f.age / f.life
      if (k >= 1) {
        f.active = false
        f.sprite.visible = false
        continue
      }
      const sc = f.sc0 + (f.sc1 - f.sc0) * easeOutCubic(k)
      f.sprite.scale.set(sc, sc, 1)
      f.mat.opacity = f.op * (1 - k) * (1 - k)
    }
  }

  dispose(): void {
    for (const f of this.items) {
      f.mat.dispose()
      f.sprite.removeFromParent()
    }
  }
}

// ---------------------------------------------------------------------------
// shockwave rings
// ---------------------------------------------------------------------------

type Wave = { mesh: THREE.Mesh; mat: THREE.MeshBasicMaterial; c0: THREE.Color; c1: THREE.Color; age: number; life: number; r0: number; r1: number; op: number; active: boolean }

class WavePool {
  private readonly items: Wave[] = []
  private readonly geometry: THREE.RingGeometry
  private next = 0

  constructor(n: number, scene: THREE.Scene, z: number) {
    this.geometry = new THREE.RingGeometry(0.965, 1.0, 160)
    for (let i = 0; i < n; i++) {
      const mat = new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0, blending: THREE.AdditiveBlending, depthWrite: false, depthTest: false, side: THREE.DoubleSide })
      const mesh = new THREE.Mesh(this.geometry, mat)
      mesh.visible = false
      mesh.position.z = z
      mesh.renderOrder = 6
      scene.add(mesh)
      this.items.push({ mesh, mat, c0: new THREE.Color(), c1: new THREE.Color(), age: 0, life: 1, r0: 1, r1: 2, op: 1, active: false })
    }
  }

  spawn(x: number, y: number, c0: THREE.Color, c1: THREE.Color, r0: number, r1: number, life: number, op: number): void {
    const w = this.items[this.next]
    this.next = (this.next + 1) % this.items.length
    w.active = true
    w.age = 0
    w.life = life
    w.r0 = r0
    w.r1 = r1
    w.op = op
    w.c0.copy(c0)
    w.c1.copy(c1)
    w.mesh.position.x = x
    w.mesh.position.y = y
    w.mesh.scale.set(r0, r0, 1)
    w.mesh.visible = true
    w.mat.color.copy(c0)
    w.mat.opacity = op
  }

  update(dt: number): void {
    for (const w of this.items) {
      if (!w.active) continue
      w.age += dt
      const k = w.age / w.life
      if (k >= 1) {
        w.active = false
        w.mesh.visible = false
        continue
      }
      const r = w.r0 + (w.r1 - w.r0) * easeOutCubic(k)
      w.mesh.scale.set(r, r, 1)
      w.mat.color.lerpColors(w.c0, w.c1, k)
      w.mat.opacity = w.op * (1 - k)
    }
  }

  dispose(): void {
    for (const w of this.items) {
      w.mat.dispose()
      w.mesh.removeFromParent()
    }
    this.geometry.dispose()
  }
}

// ---------------------------------------------------------------------------
// ambient dust — persistent drifting motes, tinted by the live breach rate
// ---------------------------------------------------------------------------

class Ambient {
  readonly points: THREE.Points
  readonly material: THREE.ShaderMaterial
  private readonly n: number
  private readonly geometry: THREE.BufferGeometry
  private readonly pos: THREE.BufferAttribute
  private readonly alp: THREE.BufferAttribute
  private readonly posArr: Float32Array
  private readonly alpArr: Float32Array
  private readonly vx: Float32Array
  private readonly vy: Float32Array
  private readonly baseA: Float32Array
  private readonly freq: Float32Array
  private readonly phase: Float32Array
  private halfW = HALF_H * 1.25 * 1.8
  private readonly halfH = HALF_H * 1.25

  constructor(n: number, tex: THREE.Texture) {
    this.n = n
    const geometry = new THREE.BufferGeometry()
    this.pos = dynAttr(n, 3)
    this.alp = dynAttr(n, 1)
    const col = new THREE.BufferAttribute(new Float32Array(n * 3).fill(1), 3)
    const siz = new THREE.BufferAttribute(new Float32Array(n), 1)
    this.posArr = this.pos.array as Float32Array
    this.alpArr = this.alp.array as Float32Array
    this.vx = new Float32Array(n)
    this.vy = new Float32Array(n)
    this.baseA = new Float32Array(n)
    this.freq = new Float32Array(n)
    this.phase = new Float32Array(n)
    const sizArr = siz.array as Float32Array
    for (let i = 0; i < n; i++) {
      const j = i * 3
      this.posArr[j] = rand(-this.halfW, this.halfW)
      this.posArr[j + 1] = rand(-this.halfH, this.halfH)
      this.posArr[j + 2] = rand(-22, 6)
      this.vx[i] = 0.5 + rand(-0.9, 0.9)
      this.vy[i] = rand(-0.9, 0.9)
      this.baseA[i] = rand(0.12, 0.45)
      this.freq[i] = rand(0.4, 1.6)
      this.phase[i] = rand(0, Math.PI * 2)
      sizArr[i] = rand(0.25, 0.8)
      this.alpArr[i] = this.baseA[i]
    }
    geometry.setAttribute('position', this.pos)
    geometry.setAttribute('aColor', col)
    geometry.setAttribute('aSize', siz)
    geometry.setAttribute('aAlpha', this.alp)
    this.geometry = geometry
    this.material = pointMaterial(tex, 1)
    this.material.uniforms.uColor.value.copy(COL.ambient)
    this.points = new THREE.Points(geometry, this.material)
    this.points.frustumCulled = false
    this.points.renderOrder = 1
  }

  setAspect(aspect: number): void {
    this.halfW = this.halfH * aspect + 6
  }

  update(dt: number, time: number): void {
    const { posArr, alpArr, vx, vy, baseA, freq, phase, halfW, halfH } = this
    for (let i = 0; i < this.n; i++) {
      const j = i * 3
      let x = posArr[j] + vx[i] * dt
      let y = posArr[j + 1] + vy[i] * dt
      if (x > halfW) x = -halfW
      else if (x < -halfW) x = halfW
      if (y > halfH) y = -halfH
      else if (y < -halfH) y = halfH
      posArr[j] = x
      posArr[j + 1] = y
      alpArr[i] = baseA[i] * (0.72 + 0.28 * Math.sin(time * freq[i] + phase[i]))
    }
    this.pos.needsUpdate = true
    this.alp.needsUpdate = true
  }

  dispose(): void {
    this.geometry.dispose()
    this.material.dispose()
  }
}

// ---------------------------------------------------------------------------
// engine
// ---------------------------------------------------------------------------

type Projectile = {
  kind: Kind
  x0: number
  y0: number
  cx: number
  cy: number
  x1: number
  y1: number
  t: number
  dur: number
  lx: number
  ly: number
  crossed: boolean
}

type Sat = { ang: number; speed: number; r: number; rT: number; squish: number; tilt: number; lx: number; ly: number }
type OrbitMode = 'off' | 'active' | 'collapsing' | 'dispersing' | 'fading'

class FieldEngine {
  onGateFlash: ((version: number) => void) | null = null

  private readonly renderer: THREE.WebGLRenderer
  private readonly scene = new THREE.Scene()
  private readonly camera: THREE.PerspectiveCamera
  private readonly texGlow: THREE.CanvasTexture
  private readonly texSoft: THREE.CanvasTexture
  private readonly pointMats: THREE.ShaderMaterial[] = []
  private readonly pool: Pool
  private readonly flashes: FlashPool
  private readonly waves: WavePool
  private readonly ambient: Ambient
  private readonly stars: THREE.Points
  private readonly grid: THREE.GridHelper
  private readonly ringLine: THREE.Mesh
  private readonly ringLineMat: THREE.MeshBasicMaterial
  private readonly beads: THREE.Points
  private readonly beadsMat: THREE.ShaderMaterial
  private readonly halo: THREE.Points
  private readonly haloMat: THREE.ShaderMaterial
  private readonly haloPos: THREE.BufferAttribute
  private readonly haloAng: Float32Array
  private readonly haloOff: Float32Array
  private haloBuilt = -1
  private readonly core: THREE.Sprite
  private readonly coreMat: THREE.SpriteMaterial
  private readonly coreDot: THREE.Sprite
  private readonly coreDotMat: THREE.SpriteMaterial
  private readonly vignetteEl: HTMLElement | null

  private readonly projectiles: Projectile[] = []
  private readonly orbit: { mode: OrbitMode; sats: Sat[]; alpha: number; t: number } = { mode: 'off', sats: [], alpha: 0, t: 0 }
  private readonly timers: { at: number; fn: () => void }[] = []

  private aspect = 16 / 9
  private halfW = HALF_H * (16 / 9)
  private readonly mouseT = { x: 0, y: 0 }
  private catchTarget = 0.3
  private brightness = 0
  private thickness = 1
  private breachTintT = 0
  private breachTint = 0
  private hitRed = 0
  private flare = 0
  private coreFlash = 0
  private vignette = 0
  private vignetteShown = -1

  private time = 0
  private last = 0
  private raf = 0
  private running = false
  private disposed = false
  private w = 1
  private h = 1
  // adaptive quality: average frame time over 3 s windows; two slow windows in a
  // row step the pixel ratio down (never back up, so it cannot oscillate)
  private perfAcc = 0
  private perfN = 0
  private perfSlow = 0

  private readonly tmpColor = new THREE.Color()
  private readonly tmpColor2 = new THREE.Color()

  constructor(canvas: HTMLCanvasElement, vignetteEl: HTMLElement | null) {
    this.vignetteEl = vignetteEl
    this.renderer = new THREE.WebGLRenderer({ canvas, antialias: false, alpha: false, powerPreference: 'high-performance', stencil: false })
    this.renderer.outputColorSpace = THREE.LinearSRGBColorSpace
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, MAX_DPR))
    this.renderer.setClearColor(BG, 1)

    this.camera = new THREE.PerspectiveCamera(FOV, 16 / 9, 1, 400)
    this.camera.position.set(0, 0, CAM_Z)
    this.camera.lookAt(0, 0, 0)

    this.texGlow = glowTexture([
      [0, 1],
      [0.18, 0.75],
      [0.42, 0.22],
      [0.7, 0.05],
      [1, 0],
    ])
    this.texSoft = glowTexture([
      [0, 0.6],
      [0.35, 0.22],
      [0.7, 0.05],
      [1, 0],
    ])

    // --- far layers: grid + stars (parallax with the camera) ---
    this.grid = new THREE.GridHelper(300, 60, COL.grid, COL.grid)
    this.grid.rotation.x = Math.PI / 2
    this.grid.position.z = -34
    const gridMat = this.grid.material as THREE.Material
    gridMat.transparent = true
    gridMat.opacity = 0.07
    gridMat.depthWrite = false
    this.grid.renderOrder = -2
    this.scene.add(this.grid)

    this.stars = this.buildStars()
    this.scene.add(this.stars)

    // --- ambient dust ---
    this.ambient = new Ambient(AMBIENT_N, this.texSoft)
    this.pointMats.push(this.ambient.material)
    this.scene.add(this.ambient.points)

    // --- the gate ---
    this.ringLineMat = new THREE.MeshBasicMaterial({ color: COL.emerald, transparent: true, opacity: 0, blending: THREE.AdditiveBlending, depthWrite: false, depthTest: false, side: THREE.DoubleSide })
    this.ringLine = new THREE.Mesh(new THREE.RingGeometry(GATE_R - 0.12, GATE_R + 0.12, 180), this.ringLineMat)
    this.ringLine.renderOrder = 2
    this.scene.add(this.ringLine)

    const beads = this.buildBeads()
    this.beads = beads.points
    this.beadsMat = beads.material
    this.scene.add(this.beads)

    const halo = this.buildHalo()
    this.halo = halo.points
    this.haloMat = halo.material
    this.haloPos = halo.pos
    this.haloAng = halo.ang
    this.haloOff = halo.off
    this.scene.add(this.halo)

    this.coreMat = new THREE.SpriteMaterial({ map: this.texSoft, color: COL.emerald, transparent: true, opacity: 0, blending: THREE.AdditiveBlending, depthWrite: false, depthTest: false })
    this.core = new THREE.Sprite(this.coreMat)
    this.core.scale.set(GATE_R * 2.2, GATE_R * 2.2, 1)
    this.core.renderOrder = 1
    this.scene.add(this.core)

    this.coreDotMat = new THREE.SpriteMaterial({ map: this.texGlow, color: COL.emerald, transparent: true, opacity: 0, blending: THREE.AdditiveBlending, depthWrite: false, depthTest: false })
    this.coreDot = new THREE.Sprite(this.coreDotMat)
    this.coreDot.scale.set(2.4, 2.4, 1)
    this.coreDot.renderOrder = 3
    this.scene.add(this.coreDot)

    // --- transient layers ---
    this.pool = new Pool(POOL_CAP, this.texGlow, 0)
    this.pointMats.push(this.pool.material)
    this.scene.add(this.pool.points)
    this.flashes = new FlashPool(28, this.texSoft, this.scene, 0.1)
    this.waves = new WavePool(10, this.scene, 0.2)

    window.addEventListener('mousemove', this.onMouse, { passive: true })
    document.addEventListener('visibilitychange', this.onVisibility)
    canvas.addEventListener('webglcontextlost', this.onContextLost, false)
    canvas.addEventListener('webglcontextrestored', this.onContextRestored, false)
  }

  // ------------------------------------------------------------- builders

  private buildStars(): THREE.Points {
    const n = STARS_N
    const geometry = new THREE.BufferGeometry()
    const pos = new Float32Array(n * 3)
    const col = new Float32Array(n * 3)
    const siz = new Float32Array(n)
    const alp = new Float32Array(n)
    for (let i = 0; i < n; i++) {
      const j = i * 3
      pos[j] = rand(-210, 210)
      pos[j + 1] = rand(-120, 120)
      pos[j + 2] = rand(-80, -46)
      const warm = Math.random() < 0.18
      col[j] = warm ? 1 : COL.star.r
      col[j + 1] = warm ? 0.92 : COL.star.g
      col[j + 2] = warm ? 0.8 : COL.star.b
      siz[i] = rand(0.35, 1.1)
      alp[i] = rand(0.15, 0.7)
    }
    geometry.setAttribute('position', new THREE.BufferAttribute(pos, 3))
    geometry.setAttribute('aColor', new THREE.BufferAttribute(col, 3))
    geometry.setAttribute('aSize', new THREE.BufferAttribute(siz, 1))
    geometry.setAttribute('aAlpha', new THREE.BufferAttribute(alp, 1))
    const material = pointMaterial(this.texGlow, 1)
    this.pointMats.push(material)
    const points = new THREE.Points(geometry, material)
    points.frustumCulled = false
    points.renderOrder = -1
    return points
  }

  private buildBeads(): { points: THREE.Points; material: THREE.ShaderMaterial } {
    const n = 220
    const geometry = new THREE.BufferGeometry()
    const pos = new Float32Array(n * 3)
    const col = new Float32Array(n * 3).fill(1)
    const siz = new Float32Array(n)
    const alp = new Float32Array(n)
    for (let i = 0; i < n; i++) {
      const a = (i / n) * Math.PI * 2
      const j = i * 3
      pos[j] = Math.cos(a) * GATE_R
      pos[j + 1] = Math.sin(a) * GATE_R
      pos[j + 2] = 0
      // uneven bead sizes so the slow rotation is visible
      const wave = Math.pow(Math.abs(Math.sin(i * 0.61)), 3)
      siz[i] = 0.55 + 1.35 * wave
      alp[i] = 0.35 + 0.65 * wave
    }
    geometry.setAttribute('position', new THREE.BufferAttribute(pos, 3))
    geometry.setAttribute('aColor', new THREE.BufferAttribute(col, 3))
    geometry.setAttribute('aSize', new THREE.BufferAttribute(siz, 1))
    geometry.setAttribute('aAlpha', new THREE.BufferAttribute(alp, 1))
    const material = pointMaterial(this.texGlow, 1)
    this.pointMats.push(material)
    const points = new THREE.Points(geometry, material)
    points.frustumCulled = false
    points.renderOrder = 3
    return { points, material }
  }

  private buildHalo(): { points: THREE.Points; material: THREE.ShaderMaterial; pos: THREE.BufferAttribute; ang: Float32Array; off: Float32Array } {
    const n = 640
    const geometry = new THREE.BufferGeometry()
    const pos = dynAttr(n, 3)
    const col = new Float32Array(n * 3).fill(1)
    const siz = new Float32Array(n)
    const alp = new Float32Array(n)
    const ang = new Float32Array(n)
    const off = new Float32Array(n)
    for (let i = 0; i < n; i++) {
      ang[i] = rand(0, Math.PI * 2)
      // bell-shaped radial offset in [-1, 1]
      off[i] = (Math.random() + Math.random() + Math.random() - 1.5) / 1.5
      siz[i] = rand(1.2, 2.8)
      alp[i] = rand(0.1, 0.32)
    }
    geometry.setAttribute('position', pos)
    geometry.setAttribute('aColor', new THREE.BufferAttribute(col, 3))
    geometry.setAttribute('aSize', new THREE.BufferAttribute(siz, 1))
    geometry.setAttribute('aAlpha', new THREE.BufferAttribute(alp, 1))
    const material = pointMaterial(this.texSoft, 1)
    this.pointMats.push(material)
    const points = new THREE.Points(geometry, material)
    points.frustumCulled = false
    points.renderOrder = 2
    return { points, material, pos, ang, off }
  }

  private rebuildHalo(thickness: number): void {
    const arr = this.haloPos.array as Float32Array
    const n = this.haloAng.length
    for (let i = 0; i < n; i++) {
      const r = GATE_R + this.haloOff[i] * thickness
      const j = i * 3
      arr[j] = Math.cos(this.haloAng[i]) * r
      arr[j + 1] = Math.sin(this.haloAng[i]) * r
      arr[j + 2] = 0
    }
    this.haloPos.needsUpdate = true
    this.haloBuilt = thickness
  }

  // ------------------------------------------------------------- lifecycle

  private readonly onMouse = (e: MouseEvent): void => {
    const w = window.innerWidth || 1
    const h = window.innerHeight || 1
    this.mouseT.x = (e.clientX / w) * 2 - 1
    this.mouseT.y = -((e.clientY / h) * 2 - 1)
  }

  private readonly onVisibility = (): void => {
    if (document.hidden) this.stop()
    else this.start()
  }

  private readonly onContextLost = (e: globalThis.Event): void => {
    e.preventDefault()
    this.stop()
  }

  private readonly onContextRestored = (): void => {
    this.haloBuilt = -1
    this.start()
  }

  resize(w: number, h: number): void {
    if (this.disposed || w < 2 || h < 2) return
    this.w = w
    this.h = h
    this.renderer.setSize(w, h, false)
    this.aspect = w / h
    this.halfW = HALF_H * this.aspect
    this.camera.aspect = this.aspect
    this.camera.updateProjectionMatrix()
    this.ambient.setAspect(this.aspect)
    const scale = (this.renderer.getPixelRatio() * h) / (2 * Math.tan((FOV * Math.PI) / 360))
    for (const m of this.pointMats) m.uniforms.uScale.value = scale
  }

  start(): void {
    if (this.running || this.disposed || document.hidden) return
    this.running = true
    this.last = performance.now()
    this.raf = requestAnimationFrame(this.frame)
  }

  stop(): void {
    if (!this.running) return
    this.running = false
    cancelAnimationFrame(this.raf)
  }

  dispose(): void {
    if (this.disposed) return
    this.disposed = true
    this.stop()
    window.removeEventListener('mousemove', this.onMouse)
    document.removeEventListener('visibilitychange', this.onVisibility)
    const canvas = this.renderer.domElement
    canvas.removeEventListener('webglcontextlost', this.onContextLost)
    canvas.removeEventListener('webglcontextrestored', this.onContextRestored)
    this.pool.dispose()
    this.flashes.dispose()
    this.waves.dispose()
    this.ambient.dispose()
    this.stars.geometry.dispose()
    ;(this.stars.material as THREE.Material).dispose()
    this.grid.geometry.dispose()
    ;(this.grid.material as THREE.Material).dispose()
    this.ringLine.geometry.dispose()
    this.ringLineMat.dispose()
    this.beads.geometry.dispose()
    this.beadsMat.dispose()
    this.halo.geometry.dispose()
    this.haloMat.dispose()
    this.coreMat.dispose()
    this.coreDotMat.dispose()
    this.texGlow.dispose()
    this.texSoft.dispose()
    this.scene.clear()
    this.renderer.dispose()
  }

  // ------------------------------------------------------------- inputs

  setCatchRate(v: number): void {
    this.catchTarget = clamp01(v)
  }

  setBreachRate(v: number): void {
    this.breachTintT = clamp01(v)
  }

  onEvent(e: Event): void {
    if (this.disposed) return
    if (e.type === 'attack' || e.type === 'block' || e.type === 'benign_block' || e.type === 'breach') {
      this.spawnProjectile(e.type)
    } else if (e.type === 'join') {
      // a new attacker at the edge of the field: a small blue twinkle
      const [x, y] = this.edgePoint(-2)
      for (let i = 0; i < 7; i++) this.pool.spawn(x, y, rand(-3, 3), rand(-3, 3), rand(0.5, 0.9), 1.1, 0.1, COL.blue, 0.7, 1.5)
      this.flashes.spawn(x, y, COL.blue, 2, 6, 0.45, 0.5)
    }
  }

  pulseGate(version: number): void {
    if (this.disposed) return
    this.flare += 1.4
    this.waves.spawn(0, 0, COL.emerald, COL.emerald, GATE_R, GATE_R * 4.4, 1.6, 0.85)
    this.later(0.16, () => this.waves.spawn(0, 0, COL.white, COL.emerald, GATE_R, GATE_R * 3.3, 1.25, 0.6))
    this.later(0.34, () => this.waves.spawn(0, 0, COL.emerald, COL.emerald, GATE_R, GATE_R * 2.4, 1.0, 0.45))
    for (let i = 0; i < 48; i++) {
      const a = rand(0, Math.PI * 2)
      const sp = rand(9, 26)
      this.pool.spawn(Math.cos(a) * GATE_R, Math.sin(a) * GATE_R, Math.cos(a) * sp, Math.sin(a) * sp, rand(0.7, 1.3), rand(0.8, 1.4), 0.1, i % 3 === 0 ? COL.white : COL.emerald, 0.95, 2.0)
    }
    this.flashes.spawn(0, 0, COL.emerald, GATE_R * 1.5, GATE_R * 3.2, 0.55, 0.9)
    this.onGateFlash?.(version)
  }

  setDefenderStage(stage: DefenderStage | null): void {
    const o = this.orbit
    const active = stage === 'patching' || stage === 'amplifying' || stage === 'evaluating'
    if (active) {
      const want = stage === 'patching' ? 3 : stage === 'amplifying' ? 4 : 5
      if (o.mode !== 'active') {
        o.mode = 'active'
        o.t = 0
        if (o.sats.length === 0) o.alpha = 0
      }
      while (o.sats.length < want) o.sats.push(this.makeSat(o.sats.length, want))
      while (o.sats.length > want) o.sats.pop()
      for (const s of o.sats) s.rT = GATE_R * rand(1.75, 2.2)
      return
    }
    const live = o.mode === 'active' || o.mode === 'fading'
    if (stage === 'shipped') {
      if (live) {
        o.mode = 'collapsing'
        o.t = 0
      }
      return
    }
    if (stage === 'rejected' || stage === 'failed') {
      if (live) {
        o.mode = 'dispersing'
        o.t = 0
      }
      return
    }
    if (o.mode === 'active') {
      o.mode = 'fading'
      o.t = 0
    }
  }

  private makeSat(i: number, n: number): Sat {
    const r = GATE_R * rand(2.8, 3.6)
    const s: Sat = {
      ang: (i / n) * Math.PI * 2 + rand(-0.3, 0.3),
      speed: rand(0.9, 1.35),
      r,
      rT: GATE_R * rand(1.75, 2.2),
      squish: rand(0.8, 1),
      tilt: rand(0, Math.PI),
      lx: 0,
      ly: 0,
    }
    const [x, y] = this.satPos(s)
    s.lx = x
    s.ly = y
    return s
  }

  private satPos(s: Sat): [number, number] {
    const ex = Math.cos(s.ang) * s.r
    const ey = Math.sin(s.ang) * s.r * s.squish
    const c = Math.cos(s.tilt)
    const sn = Math.sin(s.tilt)
    return [ex * c - ey * sn, ex * sn + ey * c]
  }

  // ------------------------------------------------------------- helpers

  private later(delay: number, fn: () => void): void {
    this.timers.push({ at: this.time + delay, fn })
  }

  /** Random point on the viewport edge (z=0 plane), `margin` units outside it. */
  private edgePoint(margin: number): [number, number] {
    const W = this.halfW + margin
    const H = HALF_H + margin
    const side = Math.floor(Math.random() * 4)
    if (side === 0) return [rand(-W, W), H]
    if (side === 1) return [rand(-W, W), -H]
    if (side === 2) return [-W, rand(-H, H)]
    return [W, rand(-H, H)]
  }

  private spawnProjectile(kind: Kind): void {
    if (this.projectiles.length >= MAX_PROJECTILES) this.projectiles.shift()
    const [x0, y0] = this.edgePoint(4)
    const len = Math.hypot(x0, y0) || 1
    const ux = -x0 / len
    const uy = -y0 / len
    const endR = kind === 'breach' ? GATE_R * 0.1 : GATE_R
    const x1 = -ux * endR
    const y1 = -uy * endR
    const bend = len * rand(-0.28, 0.28)
    const cx = (x0 + x1) / 2 - uy * bend
    const cy = (y0 + y1) / 2 + ux * bend
    this.projectiles.push({ kind, x0, y0, cx, cy, x1, y1, t: 0, dur: rand(1.05, 1.35), lx: x0, ly: y0, crossed: false })
  }

  /** Emit trail motes along the segment (lx,ly)->(x,y), spaced `gap` units. */
  private trail(p: { lx: number; ly: number }, x: number, y: number, gap: number, color: THREE.Color, alpha: number, size: number, life: number): void {
    const dx = x - p.lx
    const dy = y - p.ly
    const dist = Math.hypot(dx, dy)
    const steps = Math.min(10, Math.floor(dist / gap))
    if (steps <= 0) return
    for (let s = 1; s <= steps; s++) {
      const f = s / steps
      this.pool.spawn(p.lx + dx * f, p.ly + dy * f, rand(-1.2, 1.2), rand(-1.2, 1.2), life * rand(0.8, 1.2), size, 0.12, color, alpha, 3)
    }
    p.lx = x
    p.ly = y
  }

  private arrive(p: Projectile): void {
    const x = p.x1
    const y = p.y1
    const len = Math.hypot(x, y) || 1
    const nx = x / len
    const ny = y / len
    switch (p.kind) {
      case 'block':
      case 'benign_block': {
        const col = p.kind === 'block' ? COL.amber : COL.violet
        const n = 12 + Math.floor(Math.random() * 9)
        for (let i = 0; i < n; i++) {
          const sp = rand(7, 23)
          const a = rand(-1.15, 1.15)
          const c = Math.cos(a)
          const s = Math.sin(a)
          this.pool.spawn(x, y, (nx * c - ny * s) * sp, (nx * s + ny * c) * sp, rand(0.45, 0.9), rand(0.7, 1.25), 0.1, i % 5 === 0 ? COL.white : col, 0.95, 2.2)
        }
        this.flashes.spawn(x, y, col, 3.5, 9, 0.85, 0.35)
        this.flare += 0.22
        break
      }
      case 'attack': {
        for (let i = 0; i < 9; i++) {
          this.pool.spawn(x, y, rand(-4, 4) + nx * 2, rand(-4, 4) + ny * 2, rand(0.6, 1.1), 1.3, 0.05, i % 2 === 0 ? COL.blue : COL.white, 0.5, 1.6)
        }
        this.flashes.spawn(x, y, COL.blue, 2.5, 6, 0.45, 0.45)
        break
      }
      case 'breach': {
        for (let i = 0; i < 36; i++) {
          const a = rand(0, Math.PI * 2)
          const sp = rand(9, 30)
          this.pool.spawn(x, y, Math.cos(a) * sp, Math.sin(a) * sp, rand(0.55, 1.0), rand(0.7, 1.3), 0.1, i % 4 === 0 ? COL.white : COL.red, 1, 2.3)
        }
        this.flashes.spawn(0, 0, COL.red, 6, 24, 0.95, 0.55)
        this.waves.spawn(0, 0, COL.red, COL.red, GATE_R * 0.4, GATE_R * 1.9, 0.6, 0.8)
        this.coreFlash = 1
        this.vignette = 1
        this.hitRed = 1
        break
      }
    }
  }

  // ------------------------------------------------------------- per-frame

  private readonly frame = (now: number): void => {
    if (!this.running) return
    this.raf = requestAnimationFrame(this.frame)
    const raw = Math.max(0, (now - this.last) / 1000)
    const dt = Math.min(0.05, raw)
    this.last = now
    this.time += dt
    this.update(dt)
    this.renderer.render(this.scene, this.camera)
    this.perfAcc += Math.min(0.25, raw)
    this.perfN++
    if (this.perfAcc >= 3) {
      const avg = this.perfAcc / this.perfN
      this.perfAcc = 0
      this.perfN = 0
      if (avg > 1 / 42) {
        const dpr = this.renderer.getPixelRatio()
        if (++this.perfSlow >= 2 && dpr > 1) {
          this.perfSlow = 0
          this.renderer.setPixelRatio(Math.max(1, dpr - 0.25))
          this.resize(this.w, this.h)
        }
      } else {
        this.perfSlow = 0
      }
    }
  }

  private update(dt: number): void {
    // scheduled effects (paused with the loop)
    if (this.timers.length > 0) {
      for (let i = this.timers.length - 1; i >= 0; i--) {
        if (this.timers[i].at <= this.time) {
          const t = this.timers[i]
          this.timers.splice(i, 1)
          t.fn()
        }
      }
    }

    // projectiles
    for (let i = this.projectiles.length - 1; i >= 0; i--) {
      const p = this.projectiles[i]
      p.t += dt / p.dur
      if (p.t >= 1) {
        this.projectiles.splice(i, 1)
        this.arrive(p)
        continue
      }
      const te = Math.pow(p.t, 1.45)
      const u = 1 - te
      const x = u * u * p.x0 + 2 * u * te * p.cx + te * te * p.x1
      const y = u * u * p.y0 + 2 * u * te * p.cy + te * te * p.y1
      if (p.kind === 'breach' && !p.crossed && x * x + y * y < GATE_R * GATE_R) {
        p.crossed = true
        this.hitRed = Math.min(1, this.hitRed + 0.35)
        for (let s = 0; s < 6; s++) this.pool.spawn(x, y, rand(-6, 6), rand(-6, 6), rand(0.3, 0.6), 0.9, 0.1, COL.red, 0.9, 2)
      }
      this.trail(p, x, y, 0.45, TRAIL[p.kind], 0.6, 0.95, 0.38)
      this.pool.spawn(x, y, 0, 0, 0.07, 2.3, 1.9, HEAD[p.kind], 1, 0)
    }

    this.updateOrbit(dt)

    this.pool.update(dt)
    this.flashes.update(dt)
    this.waves.update(dt)
    this.ambient.update(dt, this.time)

    // gate
    const ease = Math.min(1, dt * 2)
    this.brightness += (0.45 + 0.55 * this.catchTarget - this.brightness) * ease
    this.thickness += (0.5 + 3.2 * this.catchTarget - this.thickness) * ease
    if (Math.abs(this.thickness - this.haloBuilt) > 0.02) this.rebuildHalo(this.thickness)
    this.hitRed = Math.max(0, this.hitRed - dt * 2.2)
    this.flare = Math.max(0, this.flare - dt * 2.4)
    this.coreFlash = Math.max(0, this.coreFlash - dt * 1.7)
    this.vignette = Math.max(0, this.vignette - dt * 1.1)

    const b = this.brightness * (1 + this.flare * 0.8)
    const ringColor = this.tmpColor.copy(COL.emerald).lerp(COL.red, Math.min(1, this.hitRed * 0.85)).lerp(COL.white, Math.min(0.5, this.flare * 0.3))
    this.ringLineMat.color.copy(ringColor)
    this.ringLineMat.opacity = Math.min(1, 0.55 * b)
    this.beadsMat.uniforms.uColor.value.copy(ringColor)
    this.beadsMat.uniforms.uAlpha.value = Math.min(1, 0.95 * b)
    this.beadsMat.uniforms.uSize.value = 0.8 + 0.4 * this.brightness
    this.haloMat.uniforms.uColor.value.copy(ringColor)
    this.haloMat.uniforms.uAlpha.value = Math.min(1, 0.75 * b)
    this.beads.rotation.z += dt * 0.14
    this.halo.rotation.z -= dt * 0.05

    const breathe = 0.5 + 0.5 * Math.sin(this.time * 1.1)
    const coreColor = this.tmpColor2.copy(COL.emerald).lerp(COL.red, this.coreFlash)
    this.coreMat.color.copy(coreColor)
    const coreScale = GATE_R * 2.2 * (1 + this.coreFlash * 0.9 + breathe * 0.05)
    this.core.scale.set(coreScale, coreScale, 1)
    this.coreMat.opacity = Math.min(1, 0.16 * b + 0.05 * breathe * b + 0.75 * this.coreFlash)
    this.coreDotMat.color.copy(coreColor)
    const dotScale = 2.4 * (1 + this.coreFlash * 1.6 + breathe * 0.1)
    this.coreDot.scale.set(dotScale, dotScale, 1)
    this.coreDotMat.opacity = Math.min(1, 0.65 * b + 0.35 * this.coreFlash)

    // ambient tint follows the live breach rate (subtle)
    this.breachTint += (this.breachTintT - this.breachTint) * Math.min(1, dt * 1.5)
    this.ambient.material.uniforms.uColor.value.copy(COL.ambient).lerp(COL.red, this.breachTint * 0.55)

    // vignette DOM overlay
    if (this.vignetteEl && Math.abs(this.vignette - this.vignetteShown) > 0.004) {
      this.vignetteShown = this.vignette
      this.vignetteEl.style.opacity = (this.vignette * this.vignette).toFixed(3)
    }

    // parallax
    const cam = this.camera.position
    const k = Math.min(1, dt * 3)
    cam.x += (this.mouseT.x * 2.4 - cam.x) * k
    cam.y += (this.mouseT.y * 1.7 - cam.y) * k
    this.camera.lookAt(0, 0, 0)
  }

  private updateOrbit(dt: number): void {
    const o = this.orbit
    if (o.mode === 'off') return
    o.t += dt
    let spd = 1
    let dispersal = 0
    switch (o.mode) {
      case 'active':
        o.alpha = Math.min(1, o.alpha + dt / 0.7)
        break
      case 'fading':
        o.alpha = Math.max(0, o.alpha - dt / 0.6)
        if (o.alpha <= 0) {
          o.mode = 'off'
          o.sats = []
          return
        }
        break
      case 'collapsing': {
        const k = clamp01(o.t / 0.7)
        spd = 1 + 2.5 * k
        o.alpha = Math.min(1, o.alpha + dt)
        if (k >= 1) {
          // the patch lands: violet -> emerald pulse, ring flares
          this.waves.spawn(0, 0, COL.violet, COL.emerald, GATE_R, GATE_R * 2.9, 1.1, 0.9)
          this.later(0.12, () => this.waves.spawn(0, 0, COL.violet, COL.emerald, GATE_R, GATE_R * 2.0, 0.8, 0.6))
          for (let i = 0; i < 34; i++) {
            const a = rand(0, Math.PI * 2)
            const sp = rand(6, 16)
            const c = i % 2 === 0 ? COL.violet : COL.emerald
            this.pool.spawn(Math.cos(a) * GATE_R, Math.sin(a) * GATE_R, Math.cos(a) * sp, Math.sin(a) * sp, rand(0.6, 1.0), rand(0.7, 1.2), 0.1, c, 0.9, 2)
          }
          this.flashes.spawn(0, 0, COL.violet, GATE_R * 1.4, GATE_R * 2.6, 0.5, 0.7)
          this.flare += 1.0
          o.mode = 'off'
          o.sats = []
          return
        }
        break
      }
      case 'dispersing': {
        const k = clamp01(o.t / 0.8)
        o.alpha = 1 - k
        dispersal = 26
        if (k >= 1) {
          o.mode = 'off'
          o.sats = []
          return
        }
        break
      }
    }
    for (const s of o.sats) {
      s.ang += s.speed * spd * dt
      if (o.mode === 'collapsing') s.r += (GATE_R - s.r) * Math.min(1, dt * 5)
      else if (o.mode === 'dispersing') s.r += dispersal * dt
      else s.r += (s.rT - s.r) * Math.min(1, dt * 2.2)
      const [x, y] = this.satPos(s)
      this.trail(s, x, y, 0.5, COL.violet, 0.45 * o.alpha, 0.8, 0.5)
      this.pool.spawn(x, y, 0, 0, 0.07, 1.8, 1.5, HEAD.benign_block, o.alpha, 0)
    }
  }
}

// ---------------------------------------------------------------------------
// React
// ---------------------------------------------------------------------------

type Props = { state: State; events: Event[] }

/** The on/off toggle lives in src/hooks/useFieldEnabled.ts; WarRoom mounts this only when on. */
export function SiegeField({ state, events }: Props) {
  const wrapRef = useRef<HTMLDivElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const vignetteRef = useRef<HTMLDivElement>(null)
  const engineRef = useRef<FieldEngine | null>(null)
  const [flash, setFlash] = useState<{ key: number; version: number } | null>(null)
  const processed = useRef<Set<string>>(new Set())
  const primed = useRef(false)
  const mountedAt = useRef(0)
  const prevVersion = useRef<number | null>(null)

  const catchRate = state.series.findLast((s) => s.catch_rate !== null)?.catch_rate ?? 0.3
  const breachRate = state.round?.status === 'live' ? state.current_round.breach_rate : 0
  const stage = state.defender?.stage ?? null
  const runId = state.defender?.id ?? null

  // engine lifecycle. Declared first: on mount the state effects below run right
  // after this one in the same commit, so they push the initial values.
  useEffect(() => {
    mountedAt.current = Date.now()
    const canvas = canvasRef.current
    const wrap = wrapRef.current
    if (!canvas || !wrap) return
    let engine: FieldEngine
    try {
      engine = new FieldEngine(canvas, vignetteRef.current)
    } catch {
      // no WebGL: the page simply keeps its static ground
      return
    }
    engineRef.current = engine
    engine.onGateFlash = (version) => setFlash({ key: Date.now(), version })
    const ro = new ResizeObserver(() => engine.resize(wrap.clientWidth, wrap.clientHeight))
    ro.observe(wrap)
    engine.resize(wrap.clientWidth, wrap.clientHeight)
    engine.start()
    return () => {
      ro.disconnect()
      engine.dispose()
      if (engineRef.current === engine) engineRef.current = null
    }
  }, [])

  useEffect(() => {
    engineRef.current?.setCatchRate(catchRate)
  }, [catchRate])

  useEffect(() => {
    engineRef.current?.setBreachRate(breachRate)
  }, [breachRate])

  useEffect(() => {
    engineRef.current?.setDefenderStage(stage)
  }, [stage, runId])

  useEffect(() => {
    const v = state.gate_version
    if (prevVersion.current !== null && v !== prevVersion.current) engineRef.current?.pulseGate(v)
    prevVersion.current = v
  }, [state.gate_version])

  // events: process each id once; never replay the history present at mount
  useEffect(() => {
    const seen = processed.current
    if (!primed.current) {
      primed.current = true
      for (const e of events) seen.add(e.id)
      return
    }
    const fresh: Event[] = []
    for (const e of events) {
      if (seen.has(e.id)) continue
      seen.add(e.id)
      fresh.push(e)
    }
    const engine = engineRef.current
    if (engine && fresh.length > 0) {
      // the hook keeps newest first; animate in arrival order
      for (let i = fresh.length - 1; i >= 0; i--) {
        const e = fresh[i]
        const at = Date.parse(e.at)
        if (!Number.isNaN(at) && at < mountedAt.current - STALE_MS) continue
        engine.onEvent(e)
      }
    }
    if (seen.size > 2000) processed.current = new Set(events.map((e) => e.id))
  }, [events])

  return (
    <>
      <div ref={wrapRef} aria-hidden className="pointer-events-none fixed inset-0 z-0">
        <canvas ref={canvasRef} className="block h-full w-full" />
      </div>
      <div
        ref={vignetteRef}
        aria-hidden
        className="pointer-events-none fixed inset-0 z-20"
        style={{ opacity: 0, willChange: 'opacity', background: 'radial-gradient(ellipse at center, rgba(255,59,92,0) 50%, rgba(255,59,92,0.22) 76%, rgba(255,59,92,0.6) 100%)' }}
      />
      {/* The full-screen container stays static; only the small text block animates
          (a blur filter on a viewport-sized layer would cost a full-frame pass). */}
      <div aria-hidden className="pointer-events-none fixed inset-0 z-20 flex items-center justify-center">
        <AnimatePresence>
          {flash && (
            <motion.div
              key={flash.key}
              className="flex flex-col items-center"
              initial={{ opacity: 0, scale: 0.6, filter: 'blur(14px)' }}
              animate={{ opacity: [0, 1, 1, 0], scale: [0.6, 1, 1.04, 1.2], filter: ['blur(14px)', 'blur(0px)', 'blur(0px)', 'blur(8px)'] }}
              exit={{ opacity: 0 }}
              transition={{ duration: 2.4, times: [0, 0.14, 0.72, 1], ease: 'easeOut' }}
              onAnimationComplete={() => setFlash((f) => (f && f.key === flash.key ? null : f))}
            >
              <div className="num text-[72px] font-black leading-none tracking-[0.35em] text-allow" style={{ textShadow: '0 0 24px rgba(34,197,94,0.85), 0 0 72px rgba(34,197,94,0.45)' }}>
                GATE v{flash.version}
              </div>
              <div className="mt-3 text-[12px] font-semibold uppercase tracking-[0.5em] text-allow/80">new policy live</div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </>
  )
}
