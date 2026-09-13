# SIEGE visual showcase

A standalone, responsive product explainer and media gallery. It does not alter the war room or backend. The same page is copied to `frontend/public/story/index.html` so a normal Vite build includes it.

## Preview

From the repository root:

```bash
python3 -m http.server 8767 --directory docs --bind 127.0.0.1
```

Open `http://127.0.0.1:8767/visual-showcase/`. To target a different app, add `?app=https%3A%2F%2Fyour-demo.example%2F`. App links preserve an explicit `mock` flag. The hosted `/siege/story/index.html` version resolves app links under `/siege/`, and GitHub Pages defaults to `mock=1`. A backend-mounted `/story/index.html` resolves to the same-origin app root.

## Media

The gallery reads assets from `../media/`: `siege_keyart.png`, `siege_social.mp4`, `siege_social_vertical.mp4`, `siege_social.vtt`, and `siege_loop.mp4|webm`. Unavailable film resources leave concept artwork visible and hide unavailable download controls. No media auto-plays. The hero can switch between generated artwork and an animated inline SVG schematic; motion can be paused and respects the system preference for reduced motion.

Every conceptual visual and illustrative trace is labeled. The page reports no live metrics. The 90% figure is the default evaluation requirement, not a measured run result.

## Checks performed

Desktop (1440px) and mobile (390px) browser checks passed with no horizontal overflow or JavaScript errors. App links preserved mock mode, the learning-loop controls updated correctly, and reduced-motion controls worked. Source-level checks cover GitHub Pages base paths, local mounting, app overrides, and explicit mock disabling. Keep the two HTML copies synchronized when editing.

`notebooks/siege_render_studio.py` is a separate opt-in GPU preview companion. It has passed Python compilation and `marimo check`; no GPU job was launched as part of validation.
