"""Render an authored episode with Blender, measured narration, Remotion and FFmpeg."""

import json
import math
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
from uuid import uuid4
import wave

from mechanical_video_next import joint_timeline as joint
from mechanical_video_next.blender_runtime import run_blender
from mechanical_video_next.director_audio import mux_picture
from mechanical_video_next.remotion_build import render
from mechanical_video_next.workflow import lock
from scripts.common import ROOT, digest, filehash, probe, run, writejson
from scripts.narration import effective_profile, load_env, srt_time, synthesize_shot

FPS = 30


def measure_narration(episode, edit):
    blocks = (episode / 'narration.txt').read_text(encoding='utf-8').strip().split('\n\n')
    profile = effective_profile({'narration_profile': 'config/narration-neil.json'})
    speech = []
    for block, shot in zip(blocks, edit['shots'], strict=True):
        lines = block.splitlines()
        if not lines or any(not line.strip() for line in lines):
            raise ValueError('Each shot needs narration with one subtitle per line')
        audio, cues, _, _ = synthesize_shot({'narration': lines}, profile)
        if not cues or not math.isfinite(shot['tail']) or shot['tail'] < 0:
            raise ValueError('Each narrated shot needs a nonnegative tail')
        frames = math.ceil((cues[-1]['end'] + shot['tail']) * FPS)
        if frames <= 0 or cues[-1]['end'] > frames / FPS:
            raise ValueError('Narration extends beyond the shot')
        speech.append((audio, cues, frames))
    return speech


def load_directed_narration(episode, edit, work):
    reference = joint.binding(episode / edit['directed_timeline'])
    plan = joint.validate(json.loads(joint.bound(reference).read_text())['plan'])
    timeline = joint.receipt(plan, reference, directed=True)
    narration = (episode / 'narration.txt').read_text(encoding='utf-8').strip().split('\n\n')
    if len(narration) != len(edit['shots']) or len(narration) != len(plan['shots']):
        raise ValueError('Directed timeline must have one picture interval per episode shot')
    speech, placed = [], []
    cues = joint.cues(timeline)
    with wave.open(str(joint.bound(timeline['narration_audio'])), 'rb') as master:
        for index, (block, shot) in enumerate(zip(narration, plan['shots'], strict=True)):
            first, last = shot['start_frame'], shot['end_frame']
            start, end = first * joint.SAMPLES_PER_FRAME, last * joint.SAMPLES_PER_FRAME
            rows = [(row, cue) for row, cue in zip(timeline['speech'], cues, strict=True)
                    if start <= row['start_sample'] < end]
            if [row['text'] for row, _ in rows] != block.splitlines():
                raise ValueError(f'Directed speech differs from episode script in shot {index + 1}')
            placed.extend(row['id'] for row, _ in rows)
            relative = [dict(cue, start=cue['start'] - first / FPS, end=cue['end'] - first / FPS)
                        for _, cue in rows]
            path = work / f'directed-shot-{index}.wav'
            master.setpos(start)
            with wave.open(str(path), 'wb') as audio:
                audio.setparams(master.getparams())
                audio.writeframes(master.readframes(end - start))
            speech.append((path, relative, last - first))
    if placed != [row['id'] for row in timeline['speech']]:
        raise ValueError('Directed speech is outside the episode picture track')
    return speech


def picture_sources(episode, speech, work):
    scene = episode / 'scene.py'
    counts = [frames for _, _, frames in speech]
    timing = work / 'timing.json'
    writejson(timing, counts)
    scene_hash = filehash(scene)
    paths = [work / digest({'scene': scene_hash, 'shot': i, 'frames': count, 'fps': FPS}) / f'shot-{i}.mp4'
             for i, count in enumerate(counts)]
    missing = [i for i, path in enumerate(paths) if not path.is_file()]
    if missing:
        with lock(ROOT / 'work/production.lock', wait=True):
            for i in missing:
                if paths[i].is_file():
                    continue
                picture = paths[i].parent
                picture.mkdir(exist_ok=True)
                frames = picture / f'shot-{i}'
                run_blender(['--python-exit-code', '7', '--python', str(scene), '--',
                             '--timing', str(timing), '--directory', str(picture), '--shot', str(i)],
                            name=f'episode-{i}', directory=picture / f'blender-{i}-{uuid4().hex}',
                            timeout=1800)
                encode_shot(frames, counts[i], paths[i])
    return paths


def encode_shot(frames, count, output):
    candidate = output.with_suffix('.tmp.mp4')
    run(['ffmpeg', '-v', 'error', '-xerror', '-y', '-framerate', FPS, '-i', frames / '%05d.jpg',
         '-frames:v', count, '-c:v', 'libx264', '-preset', 'fast', '-crf', 16,
         '-pix_fmt', 'yuv420p', '-movflags', '+faststart', candidate])
    picture = probe(candidate)['streams'][0]
    if (picture['width'], picture['height'], picture['r_frame_rate'], int(picture['nb_frames'])) != (
            1920, 1080, '30/1', count):
        raise ValueError(f'Incomplete 1080p shot: {frames}')
    candidate.replace(output)
    shutil.rmtree(frames)


def subtitle_cues(words, breaks):
    for index, cue in enumerate(words):
        text = cue['text']
        start = cue['start']
        for end, prefix in breaks.get(str(index), []):
            if not prefix or not text.startswith(prefix) or not start < end < cue['end']:
                raise ValueError(f'Invalid subtitle break in {cue["text"]}')
            yield dict(cue, start=start, end=end, text=prefix)
            start = end
            text = text[len(prefix):]
        if not text:
            raise ValueError(f'Subtitle break leaves no text in {cue["text"]}')
        yield dict(cue, start=start, text=text)


def edit_props(edit, pictures, speech, public, asset_prefix):
    shots, cues, labels, clicks = [], [], [], []
    cursor = 0
    for i, (shot, media, (audio, words, frames)) in enumerate(zip(edit['shots'], pictures, speech, strict=True)):
        shutil.copyfile(media, public / f'{i}.mp4')
        audio_name = f'{i}{Path(audio).suffix}'
        shutil.copyfile(audio, public / audio_name)
        shots.append({'id': f'shot-{i}', 'seconds': frames / FPS,
                      'media': f'{asset_prefix}/{i}.mp4', 'audio': f'{asset_prefix}/{audio_name}'})
        start = cursor / FPS
        cues.extend(dict(cue, start=cue['start'] + start, end=cue['end'] + start)
                    for cue in subtitle_cues(words, shot.get('subtitle_breaks', {})))
        labels.extend({'layer': 'part', 'start': start + first, 'end': start + last, 'text': text}
                      for first, last, text in shot.get('labels', ()))
        clicks.extend(start + seconds for seconds in shot.get('clicks', ()))
        cursor += frames
    return {'title': edit['title'], 'width': 1920, 'height': 1080, 'fps': FPS,
            'duration': cursor / FPS, 'frameCount': cursor, 'shots': shots, 'cues': cues,
            'annotations': labels}, clicks


def mix(picture, bgm, duration, clicks, destination):
    # Quiet mechanical transients are synthesized for the authored contact frames.
    transient = 'aevalsrc=0.14*sin(2*PI*1530*t)*exp(-85*t):s=48000:d=0.075'
    args = ['ffmpeg', '-v', 'error', '-xerror', '-y', '-i', picture,
            '-stream_loop', '-1', '-i', bgm]
    filters = [
        '[0:a]aformat=sample_rates=48000:channel_layouts=stereo[voice]',
        f'[1:a]atrim=duration={duration},aformat=sample_rates=48000:channel_layouts=stereo,'
        f'loudnorm=I=-28:TP=-4:LRA=8,aresample=48000,afade=d=0.45,'
        f'afade=t=out:st={duration - 0.8}:d=0.8[music]',
    ]
    buses = ['[voice]', '[music]']
    for i, time in enumerate(clicks, start=2):
        args.extend(['-f', 'lavfi', '-i', transient])
        filters.append(f'[{i}:a]aformat=channel_layouts=stereo,adelay={round(time * 1000)}:all=1[c{i}]')
        buses.append(f'[c{i}]')
    filters.append(''.join(buses) + f'amix=inputs={len(buses)}:normalize=0,'
                   'alimiter=limit=0.85:level=false:latency=true[out]')
    run([*args, '-filter_complex', ';'.join(filters), '-map', '[out]', '-t', duration,
         '-ar', 48000, '-c:a', 'aac', '-b:a', '192k', destination])


def assemble(episode, edit, pictures, speech, work):
    public = ROOT / 'remotion/public/cache'
    public.mkdir(exist_ok=True, parents=True)
    with TemporaryDirectory(prefix='episode-', dir=public) as folder:
        directory = Path(folder)
        props, clicks = edit_props(edit, pictures, speech, directory, f'cache/{directory.name}')
        props_path = work / 'edit-props.json'
        writejson(props_path, props)
        intermediate = work / 'remotion.mp4'
        render(props_path, intermediate, work / 'remotion.log', visual=True)
        track = work / 'mix.m4a'
        mix(intermediate, ROOT / edit['bgm'], props['duration'], clicks, track)
        output = ROOT / 'output' / episode.name / edit['output']
        output.parent.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(prefix='.export-', dir=output.parent) as staging:
            candidate = Path(staging) / output.name
            mux_picture(intermediate, track, candidate, encoded=True)
            run(['ffmpeg', '-v', 'error', '-xerror', '-i', candidate, '-map', '0:v:0',
                 '-map', '0:a:0', '-f', 'null', '-'])
            srt = candidate.with_suffix('.srt')
            srt.write_text('\n'.join(
                f'{i}\n{srt_time(cue["start"])} --> {srt_time(cue["end"])}\n{cue["text"]}\n'
                for i, cue in enumerate(props['cues'], start=1)), encoding='utf-8')
            with lock(ROOT / 'work/episode-locks' / digest(str(output)), wait=True):
                srt.replace(output.with_suffix('.srt'))
                candidate.replace(output)
    return output


def produce(episode, *, work_dir=None, env_file=None):
    episode = Path(episode).resolve()
    edit = json.loads((episode / 'edit.json').read_text(encoding='utf-8'))
    if Path(edit['output']).name != edit['output'] or not edit['output'].endswith('.mp4'):
        raise ValueError('Episode output must be an MP4 filename')
    load_env(env_file)

    def render_into(work):
        speech = (load_directed_narration(episode, edit, work) if 'directed_timeline' in edit
                  else measure_narration(episode, edit))
        pictures = picture_sources(episode, speech, work)
        return assemble(episode, edit, pictures, speech, work)

    if work_dir is None:
        with TemporaryDirectory(prefix='mvn-episode-') as temporary:
            return render_into(Path(temporary))
    work_dir = Path(work_dir).resolve()
    work_dir.mkdir(exist_ok=True, parents=True)
    with lock(work_dir / '.episode.lock', wait=True):
        return render_into(work_dir)
