"""Build original 30-second SIEGE product films; never touch the running app.

Run from siege: .venv/bin/python docs/astra/build_film.py [--portrait]
Requires captured typography layers, siege_keyart.png and optionally siege_loop.mp4.
If the Blender loop is unavailable, the film uses moving key art throughout.
"""
from __future__ import annotations
import argparse
import array
import math
from pathlib import Path
import random
import subprocess
import wave

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
WORK = HERE / 'render'
MEDIA = ROOT / 'docs' / 'media'
FFMPEG = '/opt/homebrew/bin/ffmpeg'
DURATIONS = [5, 5, 7, 7, 6]

def run(args):
    subprocess.run([FFMPEG, '-hide_banner', '-loglevel', 'warning', '-y', *args], check=True)

def soundtrack():
    """Original synthesized ambient bed, impulses and repair chimes; no samples."""
    sample_rate = 48000
    rng = random.Random(2026)
    data = array.array('h')
    cuts = (0, 5, 10, 17, 24)
    for n in range(30 * sample_rate):
        t = n / sample_rate
        fade = min(1, t / 1.5, (30-t)/2.0)
        drone = (math.sin(2*math.pi*55*t)*.055 + math.sin(2*math.pi*82.4069*t)*.025 + math.sin(2*math.pi*110.06*t)*.018)
        drone *= (.72 + .28*math.sin(t*.57))
        impact = 0.0
        for start in cuts:
            dt=t-start
            if 0 <= dt < 1.5:
                impact += .17*math.exp(-dt*5)*math.sin(2*math.pi*(67*dt-16*dt*dt))
                impact += (rng.random()-.5)*.04*math.exp(-dt*18)
        chime=0.0
        for start in (10.12, 10.52, 10.92, 17.12, 17.52, 24.12, 24.52, 24.92):
            dt=t-start
            if 0 <= dt < 2.6:
                freq = 440 if start < 17 else (554.365 if start < 24 else 659.255)
                chime += .021*math.exp(-dt*2.5)*(1-math.exp(-dt*60))*math.sin(2*math.pi*freq*dt)
        value=(drone+impact+chime)*fade
        stereo=.012*math.sin(2*math.pi*110*t + .5*math.sin(t*.7))*fade
        data.append(int(max(-1,min(1,value+stereo))*32767))
        data.append(int(max(-1,min(1,value-stereo))*32767))
    dest=WORK/'soundtrack.wav'
    with wave.open(str(dest),'wb') as f:
        f.setnchannels(2);f.setsampwidth(2);f.setframerate(sample_rate);f.writeframes(data.tobytes())
    return dest

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--portrait',action='store_true');args=parser.parse_args()
    name='portrait' if args.portrait else 'landscape'
    width,height=(1080,1920) if args.portrait else (1920,1080)
    WORK.mkdir(parents=True,exist_ok=True);MEDIA.mkdir(parents=True,exist_ok=True)
    loop=MEDIA/'siege_loop.mp4';art=MEDIA/'siege_keyart.png'
    outputs=[]
    for i,duration in enumerate(DURATIONS):
        use_loop=i in (1,2,3) and loop.exists()
        media_args=['-stream_loop','-1','-i',str(loop)] if use_loop else ['-loop','1','-framerate','30','-i',str(art)]
        media_args+=['-loop','1','-framerate','30','-i',str(WORK/f'{name}-{i}.png')]
        if args.portrait:
            base="[0:v]scale=1080:608:force_original_aspect_ratio=increase,crop=1080:608,setsar=1,fps=30,pad=1080:1920:0:755:color=0x07080c[base]"
        elif use_loop:
            base='[0:v]scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,setsar=1,fps=30[base]'
        else:
            base="[0:v]scale=2400:-1,zoompan=z='min(zoom+0.00010,1.08)':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d=1:s=1920x1080:fps=30,setsar=1[base]"
        filters=base+f';[1:v]format=rgba[title];[base][title]overlay=0:0:shortest=1,fade=t=in:st=0:d=0.35,fade=t=out:st={duration-.25}:d=0.25,format=yuv420p[v]'
        out=WORK/f'{name}-scene-{i}.mp4'
        run([*media_args,'-filter_complex_threads','2','-filter_complex',filters,'-map','[v]','-t',str(duration),'-c:v','libx264','-preset','fast','-crf','19','-threads','4','-an',str(out)])
        outputs.append(out);print(f'Rendered {name} scene {i+1}/5',flush=True)
    concat=WORK/f'{name}-concat.txt';concat.write_text(''.join(f"file '{p.name}'\n" for p in outputs))
    audio=soundtrack()
    final=MEDIA/('siege_social_vertical.mp4' if args.portrait else 'siege_social.mp4')
    run(['-f','concat','-safe','0','-i',str(concat),'-i',str(audio),'-map','0:v:0','-map','1:a:0','-c:v','copy','-c:a','aac','-b:a','192k','-af','loudnorm=I=-18:TP=-2:LRA=9','-t','30','-movflags','+faststart',str(final)])
    run(['-ss','1','-i',str(final),'-frames:v','1',str(MEDIA/f'siege_social_{name}_poster.jpg')])
    print(f'Completed {final}',flush=True)

if __name__ == '__main__': main()
