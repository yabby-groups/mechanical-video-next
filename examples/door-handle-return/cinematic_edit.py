"""Compose the matched comparison and the full measured Neil diagnostic edit."""
import argparse
from array import array
import math
import random
import wave
import json
from pathlib import Path
import shutil
import subprocess

from mechanical_video_next import joint_timeline as joint
from mechanical_video_next.audio_acceptance import verify_mix
from mechanical_video_next.director import preview_evidence
from scripts.common import ROOT, filehash, writejson

import importlib.util

spec = importlib.util.spec_from_file_location('door_handle_compose', Path(__file__).with_name('compose.py'))
compose = importlib.util.module_from_spec(spec)
spec.loader.exec_module(compose)

TASK = ROOT / 'output/tasks/door-handle-return-20261121'
OLD = TASK / 'restored-3d/revised'


def ffmpeg(*args, cwd=None):
    subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', *map(str, args)], cwd=cwd, check=True)


def encode_core(out):
    clock = json.loads((out / 'core-clock.json').read_text())
    count = len(clock['source_frames'])
    if filehash(out / 'scene.blend') != clock['scene_sha256']:
        raise ValueError('Cinematic blend differs from the core render clock')
    baseline = out / 'old-frames'
    baseline.mkdir(exist_ok=True)
    for number, source in enumerate(clock['source_frames'], 1):
        shutil.copyfile(OLD / 'frames' / f'frame-{source:04d}.jpg', baseline / f'{number:04d}.jpg')
    old = out / 'old-workbench.mp4'
    new = out / 'door-handle-cinematic-reveal.mp4'
    ab = out / 'side-by-side.mp4'
    silent = out / 'mechanical-review-silent.mp4'
    codec = ('-an', '-c:v', 'libx264', '-preset', 'fast', '-crf', 15,
             '-pix_fmt', 'yuv420p', '-movflags', '+faststart')
    for folder, movie in ((baseline, old), (out / 'core-frames', new)):
        ffmpeg('-framerate', 30, '-start_number', 1, '-i', folder / '%04d.jpg',
               '-frames:v', count, *codec, movie)
    ffmpeg('-i', old, '-i', new, '-filter_complex',
           '[0:v]scale=960:540[a];[1:v]scale=960:540[b];[a][b]hstack=inputs=2',
           *codec, ab)
    ffmpeg('-i', new, '-vf', 'trim=start_frame=175,setpts=PTS-STARTPTS', *codec, silent)
    reports = {}
    for movie in (old, new, ab, silent):
        expected = count - 175 if movie == silent else count
        joint.validate_rendered_film(movie, {'frame_count': expected}, require_audio=False)
        ffmpeg('-xerror', '-i', movie, '-f', 'null', '-')
        reports[movie.name] = {**joint.binding(movie), 'frames': expected}
    writejson(out / 'technical.json', {
        'matched_30fps_output': True, 'original_workbench_picture': joint.binding(OLD / 'door-handle-return-preview.mp4'),
        'baseline_blend': joint.binding(OLD / 'door-handle-return.blend'),
        'cinematic_blend': joint.binding(out / 'scene.blend'), 'mapping': joint.binding(out / 'core-clock.json'),
        'outputs': reports, 'continuous_visual_review': 'UNKNOWN',
    })


def replace_picture_window(out):
    first, last = 556, 794
    patch = out / 'native-picture.mp4'
    unpatched = out.parent / 'animatic/native-picture.mp4'
    if patch.with_name('chunk-result.json').is_file():
        joint.validate_rendered_film(patch, {'frame_count': last - first}, require_audio=False)
    picture = out / 'native-picture-complete.mp4'
    ffmpeg('-i', unpatched, '-i', patch, '-filter_complex',
           f'[0:v]split[before][after];[before]trim=end_frame={first},setpts=PTS-STARTPTS[a];'
           f'[after]trim=start_frame={last},setpts=PTS-STARTPTS[c];'
           '[a][1:v][c]concat=n=3:v=1:a=0[outv]', '-map', '[outv]',
           '-c:v', 'libx264', '-crf', 16, '-pix_fmt', 'yuv420p', picture)
    writejson(out / 'picture-splice.json', {
        'scene': joint.binding(out / 'scene.blend'),
        'inputs': [joint.binding(unpatched), joint.binding(patch)],
        'patch_frames_half_open': [first, last], 'output': joint.binding(picture),
    })
    return picture


def write_wav(path, samples):
    with wave.open(str(path), 'wb') as stream:
        stream.setparams((1, 2, joint.SAMPLE_RATE, 0, 'NONE', 'not compressed'))
        stream.writeframes(samples.tobytes())


def build_effects(out, plan):
    rate = joint.SAMPLE_RATE
    total = plan['frame_count'] * joint.SAMPLES_PER_FRAME
    foley = array('h', [0]) * total
    randomizer = random.Random(7900978)
    cues = [
        (.79, .14, 650, 560, 'handle press'),
        (3.14, .11, 1450, 850, 'handle home stop'),
        (6.28, .18, 470, 490, 'illustrative spindle extraction'),
        (7.34, .19, 820, 520, 'illustrative cover release'),
        (20.51, .26, 475, 420, 'illustrated spring loading'),
        (24.38, .23, 640, 480, 'illustrated spring release'),
        (29.39, .11, 1420, 690, 'home stop'),
        (37.49, .10, 1510, 750, 'installed handle home stop'),
    ]
    for start, length, frequency, amplitude, _ in cues:
        offset = round(start * rate)
        for sample in range(round(length * rate)):
            t = sample / rate
            envelope = min(t / .004, 1) * math.exp(-5 * t / length)
            ring = math.sin(math.tau * frequency * t) + .37 * math.sin(math.tau * frequency * 1.73 * t)
            foley[offset + sample] += round(amplitude * envelope * (ring + .22 * randomizer.uniform(-1, 1)))
    source = out / 'mechanical-foley.wav'
    write_wav(source, foley)
    narration = OLD / 'neil.wav'
    with wave.open(str(narration), 'rb') as stream:
        voice = array('h')
        voice.frombytes(stream.readframes(total))
    master = out / 'neil-and-foley.wav'
    write_wav(master, array('h', (speech + effect for speech, effect in zip(voice, foley, strict=True))))
    proof = out / 'foley-source.json'
    writejson(proof, {'method': 'Original procedural foley authored for this workprint',
                      'cues': cues, 'license': 'CC0-1.0', 'source_program': joint.binding(__file__),
                      'scope': 'Illustrative sound design. No field recordings or external sound assets.'})
    mix = {'master': joint.binding(master), 'stems': [{
        'kind': 'sfx', 'source': joint.binding(source), 'start_sample': 0,
        'end_sample': total, 'source_start_sample': 0, 'gain_db': 0,
        'source_type': 'GENERATED', 'license_status': 'VERIFIED', 'usage_restrictions': [],
        'credit': '君哥拆机器 · 原创拟音',
        'license': {'name': 'CC0-1.0', 'holder': '君哥拆机器', 'status': 'VERIFIED',
                    'editing_and_distribution': True, 'commercial_use': True,
                    'proof': {**joint.binding(proof), 'position': 'method and license'}}}]}
    verify_mix(mix, narration, total)
    writejson(out / 'audio-mix.json', mix)
    return master


def encode_full(out, *, revised=False):
    edit = json.loads((Path(__file__).with_name('edit.json')).read_text())
    plan = compose.plan_for(edit)
    measured_path = OLD / 'measured-neil.json'
    measured = joint.receipt(plan, joint.binding(measured_path))
    captions = compose.HEADER.replace('Heiti SC,25', 'Heiti SC,23')
    captions += compose.cue(.15, 3.15, 'Title', edit['title'])
    for start, end, label in [
        (5.3, 10.9, '说明性拆解'), (11.1, 14.25, '方轴与拨片'),
        (19.1, 22.8, '压缩｜弹簧储能'), (24.65, 27.35, '回弹｜推回拨片')
    ]:
        captions += compose.cue(start, end, 'Label', label)
    for row in measured['speech']:
        captions += compose.cue(row['start_sample'] / joint.SAMPLE_RATE,
                                row['end_sample'] / joint.SAMPLE_RATE, 'Sub', row['subtitle'])
    (out / 'captions.ass').write_text(captions)
    picture = replace_picture_window(out) if revised else out / 'native-picture.mp4'
    playback = build_effects(out, plan) if revised else OLD / 'neil.wav'
    film = out / 'door-handle-animatic.mp4'
    ffmpeg('-i', picture, '-i', playback, '-vf', 'subtitles=captions.ass',
           '-map', '0:v:0', '-map', '1:a:0', '-c:v', 'libx264', '-crf', 18, '-preset', 'fast',
           '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '160k', '-movflags', '+faststart',
           film, cwd=out)
    core = ['explode', 'load', 'release']
    scene = joint.binding(out / 'scene.blend')
    writejson(out / 'preview-blueprint.json', {
        'title': edit['title'], 'timeline': plan, 'measured_timeline': joint.binding(measured_path),
        'core_3d': [{'shot_id': shot_id, 'scene_id': shot_id, 'source': scene} for shot_id in core],
    })
    writejson(out / 'technical.json', {
        'picture': joint.validate_rendered_film(film, plan, require_audio=True),
        'audio': joint.validate_rendered_audio(film, plan, measured, playback=playback, mix=revised),
        'preview': preview_evidence(film, plan, core),
        'native_picture': joint.binding(picture), 'scene': scene,
        'captions': joint.binding(out / 'captions.ass'), 'neil': joint.binding(OLD / 'neil.wav'),
    })


def bind_actions(out):
    edit = json.loads((Path(__file__).with_name('edit.json')).read_text())
    plan = compose.plan_for(edit)
    measured = joint.receipt(plan, joint.binding(OLD / 'measured-neil.json'))
    voices = {row['text']: row for row in measured['speech']}
    scene = joint.binding(out / 'scene.blend')
    evidence = {
        **joint.binding(OLD.parent / 'sources/US7900978.pdf'),
        'position': 'Figs. 1–5 and detailed description of the lost-motion drivers',
    }
    plan[joint.INTEGRITY] = 1
    for event_id, knowledge, start, end in [
        ('installed-press-and-return', 'handle-return', 22, 96),
        ('exposed-press-and-return', 'spring-return', 469, 888),
        ('installed-return-replay', 'handle-return', 1019, 1126),
    ]:
        plan['actions'].append(dict(
            id=event_id, source=scene, evidence=evidence, knowledge_id=knowledge,
            start_frame=start, end_frame=end, source_start_frame=start, source_end_frame=end,
            start_state='Horizontal lever and open coil pitch',
            end_state='Horizontal lever and restored coil pitch',
            intermediate_state='One driver moves, with the opposite end against its stationary seat',
            input='Press and then release the installed lever', direction='Downward rotation followed by return',
            transmission='Square spindle turns the active driver, which displaces one compression spring seat',
            contact='Modeled spring-end-to-seat geometry. The spindle aperture includes illustrative clearance.',
            curve='Continuous native authored 30 fps action, sampled without temporal rescaling',
            constraints=['Opposite driver stationary', 'Spindle and active driver co-rotate',
                         'Compression spring shape weights follow the native driver state'],
        ))
    for shot in plan['shots']:
        start, stop = shot['start_frame'], shot['end_frame']
        shot['source_start_frame'] = start
        shot['action_views'] = {event['id']: max(event['start_frame'], start)
                                for event in plan['actions']
                                if start < event['end_frame'] and stop > event['start_frame']}
    exact_speech = out / 'action-bound-neil.wav'
    receipt = joint.measure(plan, lambda words: (joint.bound(voices[words]['audio']), voices[words]['cache']),
                            exact_speech)
    if filehash(exact_speech) != filehash(OLD / 'neil.wav'):
        raise ValueError('Action binding unexpectedly changed Neil')
    receipt_path = out / 'action-bound-measured.json'
    writejson(receipt_path, receipt)
    joint.receipt(plan, joint.binding(receipt_path))
    evidence = joint.binding(out.parent / 'mechanical-verification.json')
    writejson(out / 'action-bound-blueprint.json', {
        'status': 'DRAFT_UNAPPROVED',
        'media': joint.binding(out / 'door-handle-animatic.mp4'),
        'mechanical_object': '门把手回正机构',
        'core_question': '为什么按下门把手后，松手它能够自动回到水平位置？',
        'timeline': plan, 'measured_timeline': joint.binding(receipt_path),
        'evaluated_motion': evidence, 'native_scene': scene,
    })


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['core', 'full', 'bind-actions'])
    parser.add_argument('out', type=Path)
    parser.add_argument('--revised', action='store_true')
    args = parser.parse_args()
    if args.mode == 'core':
        encode_core(args.out.resolve())
    elif args.mode == 'full':
        encode_full(args.out.resolve(), revised=args.revised)
    else:
        bind_actions(args.out.resolve())
