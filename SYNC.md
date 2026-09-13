# SYNC (humans + agents working in this folder)

Last updated by Claude: see git log. An auto-commit loop commits and pushes this folder every 2 minutes (`scripts/autocommit.sh`). Do not force-push.

## State (verified)
- Backend (`backend/app`): live loop works end to end. Agent gpt-oss-20b (W&B Inference), gate TypeSafe System One, defender DeepSeek V4 Pro, red team Nemotron 3 Ultra, Weave traces + Evaluations, W&B sandbox for prefilter validation. `cd backend && python -m pytest` = 11 passed. Server: `uvicorn app.main:app --port 8000` (currently running on :8000, serving frontend/dist).
- Frontend (`frontend`): `/` war room, `/attack`, `/admin` all working against the live backend. A three.js battlefield layer (`src/components/SiegeField.tsx`) is being added by a Claude agent RIGHT NOW: do not edit `frontend/src` until it lands (watch git log for "SiegeField").
- Notebook: `notebooks/siege_lab.py`, forked on molab with an RTX Pro 6000 (Blackwell): https://molab.marimo.io/notebooks/nb_JJREjE7meQ5T3n2SkNFCoL
- Repo: https://github.com/vnmoorthy/siege (public). Deck: `docs/deck/SIEGE.pptx` (rebuild: `cd docs/deck && node build_deck.js`). Storyboard: `docs/PRESENTATION.md`.

## Ownership right now
| Area | Owner | Files |
|---|---|---|
| Blender cinematic loop v1 | Claude agent (running) | `blender/siege_scene.py`, outputs `frontend/public/media/siege_loop.*`, `siege_poster.jpg`, `siege_hero.png`, `docs/media/*` |
| Blender improvements | GPT-6 Astra | `blender/siege_scene_astra.py` and any new files under `blender/`; when your render is better, write outputs with the SAME filenames into `frontend/public/media/` and `docs/media/` (they are consumed by the join screen, the deck title, and the README). Brief: `blender/ASTRA_HANDOFF.md` |
| three.js war room layer | Claude agent (running) | `frontend/src/components/SiegeField.tsx`, `frontend/src/pages/WarRoom.tsx` |
| Everything else | Claude | backend, docs, deck, README, notebook |

## Next (Claude)
1. Land SiegeField, rebuild frontend, deploy mock-mode war room to GitHub Pages (`scripts/deploy_pages.sh`).
2. Rebuild deck with Blender hero + molab link; final storyboard pass.
3. Final live run + reset for the demo.
