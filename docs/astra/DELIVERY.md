# SIEGE visual delivery

Completed September 13, 2026. This package complements the existing Claude Code build in the shared repository.

## Product

- `/` and `/arena`: cinematic arena with the existing live API/event stream, real evaluation sample counts, QR participation, and explicit mock labels when simulated.
- `/warroom`: existing telemetry dashboard and Claude's event-driven Three.js field.
- `/attack`: cinematic nickname entry; original session, persona, chat and tool-call behavior preserved.
- `/story/index.html`: product story, interactive loop explanation, media players and downloads.
- Pages subpath routing and mock QR destinations respect `/siege/`.
- Telemetry, administration and attack screens load on demand so the arena does not load the Three.js/chart bundle at startup.

## Media

All primary media is in both `docs/media/` and `frontend/public/media/`.

| Asset | Deliverable |
| --- | --- |
| `siege_brand_hero.png` | Finished branded cover, integrated in README |
| `siege_keyart.png` | Generated cinematic gate art used in the app and story |
| `siege_loop.mp4` | Blender loop, 6 seconds, 960×540, H.264, 30 delivery fps |
| `siege_loop.webm` | Matching VP9 loop |
| `siege_poster.jpg` | Actual Blender still |
| `siege_social.mp4` | 30-second landscape film, 1920×1080, 900 frames, H.264/AAC |
| `siege_social_vertical.mp4` | 30-second portrait film, 1080×1920, 900 frames, H.264/AAC |
| `siege_social.srt` / `.vtt` | Captions |
| `siege_social_landscape_poster.jpg` / `siege_social_portrait_poster.jpg` | Film posters |

The films use original synthesized ambient sound and are labeled illustrative. They explain the loop, not a claimed live performance run. The Blender loop has 90 rendered poses, duplicated to 180 delivery frames; a smoother interpolated alternative is retained in `docs/media`. No claim of 30 unique rendered poses per second is made.

Actual UI evidence of the executed $100 credit breach is in `docs/astra/evidence/recorded-2026-09-13/phone-recorded-credit-breach-430x932.png`. Its manifest records the capture and limitations. Measured eval denominators and exact Weave links are in `docs/DEMO_READINESS.md`.

## Verification

- TypeScript/Vite production builds passed; final build follows the last link-only fixes.
- Desktop 1440×1000 and mobile 390×844: no horizontal overflow, correct mock labels and navigation, 48px join controls, no JavaScript exceptions.
- Both films decoded to exactly 900 frames and 30.000 seconds with stereo AAC audio.
- Story keyboard/interactive controls, mobile layout, mock-preserving URLs and reduced motion checked.
- Generated image prompts and tool provenance are in `KEY_ART_PROMPT.md`; Blender source and render manifest preserve reproducibility.

## GPU

`notebooks/siege_render_studio.py` is a separate marimo GPU render notebook with a pinned, hash-verified public scene generator. It starts with a single bounded Cycles GPU preview, reports device names and does not silently fall back to CPU. Compilation and `marimo check` passed. No cloud GPU job was launched by Astra.

## Publishing status

Claude's independent workflow published the arena and story on GitHub Pages. At verification, the live site had the artwork but the new video files were not uploaded. Astra's separately prepared Pages publication was blocked by automatic approval review pending explicit approval. The complete final files are available locally and in the main repository via the existing vnmoorthy commit/push workflow; do not describe the videos as already live on Pages until their URLs return 200.

All commit authors are vnmoorthy. Two older commits contain Claude co-author trailers; history was not rewritten during concurrent work.
