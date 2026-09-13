# SIEGE procedural cinematic

`siege_scene_astra.py` is a self-contained Blender 5.2 scene generator. It is
separate from Claude's `siege_scene.py` so both collaborators' work is retained.
It creates its own geometry, materials, camera, lights and animation; it does
not read credentials, use external assets, download dependencies or need an
add-on.

The checkpoint has a machined titanium perimeter, emerald indexed emitters,
three counter-rotating helical lattices and an etched inspection membrane.
The protected agent is a faceted ceramic core inside an orbital cage. Three
attack waves contain 16, 11 and 5 projectiles. Blocked attacks split into nine
decelerating amber fragments; three attacks reach the core with red light
pulses. Five violet satellites mark the two intervening defender revisions.

The six-second timeline is analytically periodic. Frames 1 and 181 describe
the same pose; export frames 1–180 at 30 fps to avoid a duplicated terminal
frame. All random layout uses a fixed seed. Render frame 181 separately and
compare it to frame 1 when changing choreography.

Run from the `siege` directory:

```sh
/Applications/Blender.app/Contents/MacOS/Blender -b -P blender/siege_scene_astra.py -- --out blender/astra_frames --res 1280 720 --start 1 --end 180 --samples 24
python blender/encode_astra.py --frames blender/astra_frames
```

For the large still:

```sh
/Applications/Blender.app/Contents/MacOS/Blender -b -P blender/siege_scene_astra.py -- --out blender/astra_hero --res 3200 1800 --start 28 --end 28 --samples 48 --save-blend
```

Optional `--title` adds a dimensional SIEGE wordmark. The source is necessary
to regenerate animation: frame handlers run in Python and are deliberately
not hidden inside an auto-running text block in the saved `.blend` file.

On this Mac the default sandbox prevents Blender's Metal device discovery,
causing a startup crash before Python runs. Rendering requires the same
host GPU access as normal Blender use. Blender's first EEVEE render also
compiles Metal shader specializations; this cold startup cost is separate
from steady-state frame render times. Frame timing is printed as
`ASTRA_FRAME` and summarized as `ASTRA_DONE`.

`encode_astra.py` checks for missing frames, writes H.264 MP4 with fast-start
and yuv420p, VP9 WebM and JPEG poster, then mirrors them to both `docs/media/`
and `frontend/public/media/`. It writes the final codec/dimension/duration
metadata and sizes to `docs/media/siege_render_manifest.json`.
