"""Encode the procedural SIEGE frames to browser-ready videos and a poster.

Usage: python blender/encode_astra.py --frames blender/astra_frames
Only Python's standard library and an installed ffmpeg/ffprobe are required.
"""
import argparse
import json
from pathlib import Path
import shutil
import subprocess

parser = argparse.ArgumentParser()
parser.add_argument('--frames', type=Path, required=True)
parser.add_argument('--fps', type=int, default=30)
parser.add_argument('--output-fps', type=int, default=0, help='Duplicate poses to a delivery frame rate without expensive interpolation.')
parser.add_argument('--ffmpeg', default='/opt/homebrew/bin/ffmpeg')
parser.add_argument('--name', default='siege_loop')
parser.add_argument('--poster-frame', type=int, default=28)
parser.add_argument('--interpolate-fps', type=int, default=0, help='Optical-flow interpolate a lower-rate loop to this delivery frame rate.')
parser.add_argument('--expected-frames', type=int, default=0, help='Fail if an in-progress or stale render has the wrong number of frames.')
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
dest = root / 'docs' / 'media'
public = root / 'frontend' / 'public' / 'media'
dest.mkdir(parents=True, exist_ok=True)
public.mkdir(parents=True, exist_ok=True)
frames = sorted(args.frames.glob('frame_*.png'))
if not frames:
    raise SystemExit(f'No rendered frames found: {args.frames}')
if args.expected_frames and len(frames) != args.expected_frames:
    raise SystemExit(f'Expected {args.expected_frames} frames, found {len(frames)}; render is incomplete or the output directory is stale.')
indices = [int(p.stem.split('_')[-1]) for p in frames]
if indices != list(range(indices[0], indices[-1] + 1)):
    raise SystemExit('Frame sequence has gaps; refusing to silently shorten video.')

def run(*cmd):
    subprocess.run([str(x) for x in cmd], check=True)

common = [args.ffmpeg, '-hide_banner', '-loglevel', 'error', '-y', '-framerate', str(args.fps),
          '-start_number', str(indices[0]), '-i', str(args.frames / 'frame_%04d.png')]
if args.interpolate_fps:
    # Feed wrapped poses for optical-flow lookahead; bound output explicitly.
    common = [args.ffmpeg, '-hide_banner', '-loglevel', 'error', '-y', '-stream_loop', '-1',
              '-framerate', str(args.fps), '-start_number', str(indices[0]), '-i',
              str(args.frames / 'frame_%04d.png'), '-vf',
              f'minterpolate=fps={args.interpolate_fps}:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1',
              '-frames:v', str(round(len(frames) / args.fps * args.interpolate_fps))]
elif args.output_fps:
    common += ['-vf', f'fps={args.output_fps}']
mp4 = dest / f'{args.name}.mp4'
webm = dest / f'{args.name}.webm'
mp4_partial = dest / f'.partial_{args.name}.mp4'
webm_partial = dest / f'.partial_{args.name}.webm'
run(*common, '-c:v', 'libx264', '-preset', 'medium', '-crf', '20', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', '-an', mp4_partial)
mp4_partial.replace(mp4)
shutil.copy2(mp4, public / mp4.name)
print(f'MP4_READY {mp4}', flush=True)
run(args.ffmpeg, '-hide_banner', '-loglevel', 'error', '-y', '-i', mp4,
    '-c:v', 'libvpx-vp9', '-b:v', '0', '-crf', '34', '-row-mt', '1',
    '-cpu-used', '8', '-pix_fmt', 'yuv420p', '-an', webm_partial)
webm_partial.replace(webm)
poster = dest / 'siege_poster.jpg'
poster_input = args.frames / f'frame_{args.poster_frame:04d}.png'
if not poster_input.exists():
    poster_input = frames[0]
run(args.ffmpeg, '-hide_banner', '-loglevel', 'error', '-y', '-i', poster_input, '-frames:v', '1', '-q:v', '2', poster)
for path in [mp4, webm, poster]:
    shutil.copy2(path, public / path.name)
probe = subprocess.run(['/opt/homebrew/bin/ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(mp4)], capture_output=True, text=True, check=True)
metadata = json.loads(probe.stdout)
metadata['source_frames'] = len(frames)
metadata['source_fps'] = args.fps
metadata['delivery_fps'] = args.interpolate_fps or args.output_fps or args.fps
metadata['optical_flow_fps'] = args.interpolate_fps or None
metadata['files'] = {p.name: p.stat().st_size for p in [mp4, webm, poster]}
(dest / 'siege_render_manifest.json').write_text(json.dumps(metadata, indent=2) + '\n')
print(json.dumps(metadata['files'], indent=2))
