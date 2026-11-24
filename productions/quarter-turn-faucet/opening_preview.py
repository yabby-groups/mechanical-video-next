"""Rebuild the faucet's A/B/C opening workprints without rendering the full film."""

import argparse
import json
from pathlib import Path
from shutil import copyfile

from mechanical_video_next import joint_timeline as joint, pacing
from mechanical_video_next.blender_runtime import run_blender
from mechanical_video_next.workflow import lock
from scripts.common import ROOT, digest, run, writejson

EPISODE = Path(__file__).resolve().parent
BASELINE_SHA = 'ef42007f8a0a2a09c2b1263acdb9fd9132f19ed6c1aae4c655b63d8bd9d7dce7'
CODEC = ['-c:v', 'libx264', '-crf', '17', '-pix_fmt', 'yuv420p', '-c:a', 'aac',
         '-b:a', '192k', '-movflags', '+faststart']


def encode(inputs, filters, mapping, target, duration):
    run(['ffmpeg', '-y', '-v', 'error', '-xerror', *inputs, '-filter_complex', filters,
         *mapping, '-t', str(duration), *CODEC, target])
    run(['ffmpeg', '-v', 'error', '-xerror', '-i', target, '-map', '0:v:0',
         '-map', '0:a:0', '-f', 'null', '-'])
    return joint.binding(target)


def caption(text, position, size, font, timing=''):
    return (f"drawtext=fontfile='{font}':text='{text}':{position}:fontsize={size}:"
            f"fontcolor=white:box=1:boxcolor=0x142321@0.86:boxborderw=8{timing}")


def layout(version, font):
    if version == 'B':
        exterior = '[0:v]scale=540:304,pad=540:540:0:118:color=0x142321[left]'
        ports = '[1:v]crop=420:540[right]'
        labels = [caption('左侧把手', 'x=22:y=30', 27, font),
                  caption('陶瓷阀芯', 'x=560:y=20', 27, font)]
        composite = f'{exterior};{ports};[left][right]hstack'
    else:
        labels = [caption('水龙头阀芯', 'x=26:y=29', 27, font),
                  caption('蓝色为通水面积', 'x=26:y=236', 22, font)]
        composite = '[0:v]scale=250:-2[inset];[1:v][inset]overlay=x=22:y=79'
    labels.append(caption('转这么一点，水就停了。', 'x=(w-tw)/2:y=491', 28, font,
                          ":enable='gte(t,0.150)'"))
    return composite + ',' + ','.join(labels)


def render_views(work):
    scene = EPISODE / 'opening_scene.py'
    with lock(ROOT / 'work/production.lock', wait=True):
        for view in ('exterior', 'ports'):
            folder = work / view
            if not (folder / 'states.json').is_file() or any(
                    not (folder / f'{frame:05}.jpg').is_file() for frame in range(60)):
                run_blender(['--python-exit-code', '7', '--python', scene, '--', folder, view],
                            name=f'faucet-opening-{view}', timeout=900)
    states = (work / 'ports/states.json').read_bytes()
    if states != (work / 'exterior/states.json').read_bytes():
        raise ValueError('Exterior and port animation must share the same clock')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--font', type=Path, default=Path('/System/Library/Fonts/STHeiti Medium.ttc'))
    args = parser.parse_args()

    original = pacing.opening_analysis(args.source, expected_sha=BASELINE_SHA)
    video = f"0:{original['picture_stream']}"
    audio = f"0:{original['audio_stream']}"
    source_refs = [joint.binding(EPISODE / name)
                   for name in ('scene.py', 'opening_scene.py', 'opening_preview.py')]
    work = args.work.resolve() / digest([item['sha256'] for item in source_refs[:2]])[:16]
    render_views(work)
    args.output.mkdir(parents=True, exist_ok=True)
    copyfile(work / 'ports/states.json', args.output / 'opening-states.json')
    results = {'source': original['media'], 'scene_sources': source_refs,
               'native_states': joint.binding(args.output / 'opening-states.json'), 'files': {}}
    for seconds in (2, 5):
        key = f'A-{seconds}s'
        results['files'][key] = encode(
            ['-i', args.source], f'[{video}]null[v]', ['-map', '[v]', '-map', audio],
            args.output / f'{key}.mp4', seconds)
    for version in ('B', 'C'):
        plates = ['-framerate', '30', '-i', work / 'exterior/%05d.jpg',
                  '-framerate', '30', '-i', work / 'ports/%05d.jpg', '-i', args.source]
        candidate = layout(version, args.font.resolve())
        for seconds in (2, 5):
            key = f'{version}-{seconds}s'
            picture = candidate + ',setsar=1,format=yuv420p[head]'
            if seconds == 5:
                picture += (f";[2:{original['picture_stream']}]trim=start=2:end=5,"
                            'setpts=PTS-STARTPTS,scale=960:540,setsar=1[tail];'
                            '[head][tail]concat=n=2:v=1:a=0[v]')
            results['files'][key] = encode(
                plates, picture, ['-map', '[v]' if seconds == 5 else '[head]',
                                  '-map', f"2:{original['audio_stream']}"],
                args.output / f'{key}.mp4', seconds)
        key = f'A-vs-{version}-5s'
        results['files'][key] = encode(
            ['-i', args.output / 'A-5s.mp4', '-i', args.output / f'{version}-5s.mp4'],
            f'[0:v]scale=960:540,setsar=1[left];[left][1:v]hstack[v]',
            ['-map', '[v]', '-map', '0:a:0'], args.output / f'{key}.mp4', 5)
    joint.bound(original['media'])
    for ref in source_refs:
        joint.bound(ref)
    writejson(args.output / 'comparison.json', results)


if __name__ == '__main__':
    main()
