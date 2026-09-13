# SIEGE visuals: handoff brief for GPT-6 Astra (Blender 5.2 LTS, headless)

You are taking over the cinematic visuals for SIEGE. Everything below is verified against the repo; do not invent files.

## What SIEGE is (30 seconds)
200 people attack a live customer-support agent from their phones. Every tool call the agent wants to make passes a glowing typed **gate** (TypeSafe System One: allow / block / escalate with probabilities). Most attacks **shatter on the gate** (amber). A few **breach** through and hit the core (red). Between rounds a **defender** rewrites the gate (violet activity), and the next round fewer get through. Palette: background `#07080c`, gate emerald `#22c55e`, block amber `#ffb020`, breach red `#ff3b5c`, defender violet `#a78bfa`, tracing blue `#60a5fa`. Mood: premium title sequence, restrained, volumetric, never a game.

## What exists
- `blender/siege_scene.py`: procedural scene builder + render CLI (see the header of the file for args; typical: `/Applications/Blender.app/Contents/MacOS/Blender -b -P blender/siege_scene.py -- --out blender/out --res 1280 720 --frames 180`). EEVEE, 30 fps, 6 s seamless loop, glow via compositor glare / EEVEE bloom.
- Outputs (copied to both `frontend/public/media/` and `docs/media/`): `siege_loop.mp4`, `siege_loop.webm`, `siege_poster.jpg` (frame 1), `siege_hero.png` (3200x1800 still).
- Consumers: the attacker join screen background (`frontend/src/pages/Attack.tsx`), the deck title slide (`docs/deck/build_deck.js` reads `docs/media/siege_hero.png` if present), the README hero.
- The live war room already has a real-time three.js layer (`frontend/src/components/SiegeField.tsx`) driven by WebSocket events; the Blender loop is the *cinematic* counterpart used where there is no live data (join screen, slides, social).

## What to improve (in priority order)
1. **Gate as a character.** Give the ring depth: a thin outer halo, an inner lattice (wireframe torus knot or instanced shards) that rotates counter to the ring, and a soft core with subsurface-like glow. It must read as "a checkpoint that thinks".
2. **Attack choreography.** Projectiles should arrive in waves (2 to 3 per loop), with the last wave visibly thinner (the defender learned). Blocked projectiles: a crisp amber impact flare plus 8 to 12 fragments that decelerate and fade. Breaches: a red streak that pierces, a core flash, a brief red chromatic pulse on the whole frame.
3. **Defender moment.** Between waves, 3 to 5 violet satellites orbit the ring, then collapse into it with a violet-to-emerald pulse: that is "gate v(n+1) shipped".
4. **Camera and depth.** Slow dolly-in with a 3-degree orbit, shallow depth of field on the ring, a little fog for parallax, film grain in the compositor, subtle vignette. Keep the loop seamless (frame 180 must match frame 1).
5. **Typography plate.** A second render variant with a 3D "SIEGE" wordmark (extruded, emissive edge) settling into place for the deck title, 1920x1080, 4 s.
6. **Deliverables to overwrite in place** (same filenames, same folders): `siege_loop.mp4` (h264, yuv420p, crf 20, faststart, under 8 MB), `siege_loop.webm`, `siege_poster.jpg`, `siege_hero.png`. Add `siege_title.mp4` for the wordmark plate.

## Constraints
- Headless only (`-b`), no external assets, no add-ons that are not bundled with Blender 5.2.
- Keep per-frame render time under 3 s at 1280x720 on an Apple M3 (EEVEE); verify with a 10-frame test before the full render.
- Encode with `/opt/homebrew/bin/ffmpeg`. Check the poster and hero with an image viewer before declaring done.
- Do not touch anything outside `blender/`, `frontend/public/media/`, `docs/media/`.
