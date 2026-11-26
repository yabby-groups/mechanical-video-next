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
from mechanical_video_next.production_contract import (
    FORMAL_DURATION_FIELD, FORMAL_DURATION_VERSION, validate_formal_duration,
)
from mechanical_video_next.remotion_build import render
from mechanical_video_next.workflow import lock
from scripts.common import ROOT, digest, filehash, probe, run, writejson
from scripts.narration import effective_profile, load_env, srt_time, synthesize_shot

FPS = 30


def narration_blocks(episode, edit):
    return (episode / edit.get('narration', 'narration.txt')).read_text(
        encoding='utf-8').strip().split('\n\n')


def measure_narration(episode, edit, *, limit=None):
    blocks = narration_blocks(episode, edit)
    profile = effective_profile({'narration_profile': 'config/narration-neil.json'})
    speech = []
    for block, shot in list(zip(blocks, edit['shots'], strict=True))[:limit]:
        lines = block.splitlines()
        if not lines or any(not line.strip() for line in lines):
            raise ValueError('Each shot needs narration with one subtitle per line')
        audio, cues, _, _ = synthesize_shot({'narration': lines}, profile)
        if not cues or not math.isfinite(shot['tail']) or shot['tail'] < 0:
            raise ValueError('Each narrated shot needs a nonnegative tail')
        needed = math.ceil((cues[-1]['end'] + shot['tail']) * FPS)
        frames = shot.get('frames', needed)
        if type(frames) is not int or frames < needed:
            raise ValueError('Narration and its tail extend beyond the shot')
        speech.append((audio, cues, frames))
    return speech


def load_directed_narration(episode, edit, work):
    reference = joint.binding(episode / edit['directed_timeline'])
    plan = joint.validate(json.loads(joint.bound(reference).read_text())['plan'])
    timeline = joint.receipt(plan, reference, directed=True)
    narration = narration_blocks(episode, edit)
    if len(narration) != len(edit['shots']) or len(narration) != len(plan['shots']):
        raise ValueError('Directed timeline must have one picture interval per episode shot')
    speech, placed = [], []
    cues = joint.cues(timeline)
    with wave.open(str(joint.bound(timeline['narration_audio'])), 'rb') as master:
        for index, (block, shot) in enumerate(zip(narration, plan['shots'], strict=True)):
            first, last = shot['start_frame'], shot['end_frame']
            frames = edit['shots'][index].get('frames', last - first)
            if type(frames) is not int or frames != last - first:
                raise ValueError(f'Edit frames differ from the directed timeline in shot {index + 1}')
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


def picture_sources(episode, speech, work, *, shots=None, preview_step=None):
    counts = [frames for _, _, frames in speech]
    shots = [{} for _ in counts] if shots is None else shots
    paths = []
    for index, (count, cut) in enumerate(zip(counts, shots, strict=True)):
        reference = cut.get('picture')
        if reference and (not reference.get('fallback_to_scene') or (episode / reference['path']).is_file()):
            paths.append(recut_picture(episode, reference, count, work))
            continue
        scene = episode / cut.get('scene', 'scene.py')
        shot = cut.get('scene_shot', index)
        if type(shot) is not int or shot < 0:
            raise ValueError('scene_shot must be a nonnegative integer')
        key = {'scene': filehash(scene), 'shot': shot, 'frames': count, 'fps': FPS}
        if cut.get('scene_inputs'):
            key['scene_inputs'] = {name: filehash(episode / name) for name in cut['scene_inputs']}
        filename = f'shot-{shot}.mp4'
        path = work / digest(key) / filename
        draft_step = None
        if preview_step is not None and not path.is_file():
            draft_step = cut.get('preview_step', preview_step)
            if type(draft_step) is not int or draft_step < 1:
                raise ValueError('preview_step must be a positive integer')
            path = work / digest(dict(key, preview_step=draft_step)) / filename
        paths.append(path)
        if path.is_file():
            continue
        with lock(ROOT / 'work/production.lock', wait=True):
            if path.is_file():
                continue
            picture = path.parent
            picture.mkdir(exist_ok=True)
            frames = picture / f'shot-{shot}'
            timing = picture / 'timing.json'
            scene_counts = counts + [0] * max(0, shot + 1 - len(counts))
            scene_counts[shot] = count
            writejson(timing, scene_counts)
            command = ['--python-exit-code', '7', '--python', str(scene), '--',
                       '--timing', str(timing), '--directory', str(picture), '--shot', str(shot)]
            if draft_step is not None:
                command.append('--preview')
            step = draft_step or 1
            if not all((frames / f'{frame:05}.jpg').is_file() for frame in range(0, count, step)):
                run_blender(command, name=f'episode-{shot}',
                            directory=picture / f'blender-{shot}-{uuid4().hex}', timeout=1800)
            encode_shot(frames, count, path, preview_step=draft_step)
    return paths


def recut_picture(episode, reference, count, work):
    """Use an at-speed interval of an existing original 3D render."""
    if type(count) is not int or count < 1:
        raise ValueError('Picture requires a positive frame count')
    source = (episode / reference['path']).resolve()
    if filehash(source) != reference['sha256']:
        raise ValueError(f'Original 3D render hash differs: {source}')
    start = reference.get('start_frame', 0)
    if type(start) is not int or start < 0:
        raise ValueError('Picture start_frame must be a nonnegative integer')
    video = next((row for row in probe(source)['streams'] if row['codec_type'] == 'video'), {})
    available = int(video['nb_frames']) if str(video.get('nb_frames', '')).isdigit() else 0
    if ((video.get('width'), video.get('height'), video.get('avg_frame_rate')) != (1920, 1080, '30/1')
            or start + count > available):
        raise ValueError(f'Recut requires a complete 1080p30 frame interval: {source}')
    if start == 0 and count == available:
        return source
    key = digest({'picture_sha256': reference['sha256'], 'start_frame': start, 'frames': count})
    target = work / key / 'recut.mp4'
    if target.is_file():
        return target
    target.parent.mkdir(exist_ok=True)
    with TemporaryDirectory(dir=target.parent) as staging:
        candidate = Path(staging) / target.name
        run(['ffmpeg', '-v', 'error', '-xerror', '-i', source, '-map', '0:v:0',
             '-vf', f'trim=start_frame={start}:end_frame={start + count},setpts=PTS-STARTPTS',
             '-an', '-c:v', 'libx264', '-preset', 'fast', '-crf', 16, '-pix_fmt', 'yuv420p', candidate])
        if int(probe(candidate)['streams'][0]['nb_frames']) != count or filehash(source) != reference['sha256']:
            raise ValueError(f'Recut is incomplete or its source changed: {source}')
        candidate.replace(target)
    return target


def encode_shot(frames, count, output, *, preview_step=None):
    candidate = output.with_suffix('.tmp.mp4')
    source = ['-framerate', FPS, '-i', frames / '%05d.jpg']
    if preview_step is not None:
        expected = [f'{frame:05}.jpg' for frame in range(0, count, preview_step)]
        if sorted(path.name for path in frames.glob('*.jpg')) != expected:
            raise ValueError(f'Preview requires regular frame samples every {preview_step} frames: {frames}')
        source = ['-framerate', f'{FPS}/{preview_step}', '-pattern_type', 'glob', '-i',
                  frames / '*.jpg', '-vf',
                  f'scale=trunc(iw/2)*2:trunc(ih/2)*2,fps={FPS},tpad=stop_mode=clone:stop={count}']
    run(['ffmpeg', '-v', 'error', '-xerror', '-y', *source,
         '-frames:v', count, '-c:v', 'libx264', '-preset', 'fast', '-crf', 16,
         '-pix_fmt', 'yuv420p', '-movflags', '+faststart', candidate])
    picture = probe(candidate)['streams'][0]
    if ((picture['r_frame_rate'], int(picture['nb_frames'])) != ('30/1', count)
            or (preview_step is None and (picture['width'], picture['height']) != (1920, 1080))):
        raise ValueError(f'Incomplete picture sequence: {frames}')
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


def compose_ffmpeg(props, output, log, *, preview):
    """Compose authored picture, speech and timed text without browser capture."""
    from PIL import Image, ImageDraw

    from . import text_layout

    width, height = (960, 540) if preview else (1920, 1080)
    style = text_layout.scaled_style(width, height)
    items = [dict(cue, layer='subtitle') for cue in props['cues']] + props['annotations']
    items = [dict(item, box=style[item['layer']]['safe_box']) for item in items]
    errors = text_layout.validate_layout(items, width=width, height=height)
    if errors:
        raise ValueError(f'Invalid text layout: {errors}')

    command = ['ffmpeg', '-v', 'error', '-xerror', '-y']
    filters = []
    shots = props['shots']
    size = (f'scale={width}:{height}:force_original_aspect_ratio=decrease,'
            f'pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=0x223139')
    for index, shot in enumerate(shots):
        frames = round(shot['seconds'] * FPS)
        samples = frames * joint.SAMPLES_PER_FRAME
        command += ['-i', ROOT / 'remotion/public' / shot['media'],
                    '-i', ROOT / 'remotion/public' / shot['audio']]
        filters += [f'[{2 * index}:v]{size},setsar=1,trim=end_frame={frames},setpts=PTS-STARTPTS[v{index}]',
                    f'[{2 * index + 1}:a]aresample=48000,aformat=channel_layouts=stereo,'
                    f'apad,atrim=end_sample={samples},asetpts=PTS-STARTPTS[a{index}]']
    segments = ''.join(f'[v{index}][a{index}]' for index in range(len(shots)))
    filters.append(f'{segments}concat=n={len(shots)}:v=1:a=1[v0o][voice]')

    with TemporaryDirectory(prefix='mvn-episode-text-') as folder:
        stroke = round(style['stroke_width'])
        for index, item in enumerate(items):
            font = text_layout.measured_font(style[item['layer']]['font_size'], style)
            x0, y0, x1, y1 = font.getbbox(item['text'], stroke_width=stroke)
            label = Image.new('RGBA', (x1 - x0, y1 - y0))
            ImageDraw.Draw(label).text((-x0, -y0), item['text'], font=font, fill=style['fill'],
                                       stroke_width=stroke, stroke_fill=style['stroke'])
            path = Path(folder) / f'{index}.png'
            label.save(path)
            command += ['-i', path]
            left, top, right, bottom = map(round, item['box'])
            x = (left + right - label.width) // 2 if item['layer'] == 'subtitle' else left
            y = (top + bottom - label.height) // 2
            start, end = (math.ceil(item[key] * FPS - 1e-10) for key in ('start', 'end'))
            filters.append(f"[v{index}o][{2 * len(shots) + index}:v]overlay={x}:{y}:"
                           f"enable='between(n,{start},{end - 1})'[v{index + 1}o]")
        run([*command, '-filter_complex_threads', '2', '-filter_complex', ';'.join(filters),
             '-map', f'[v{len(items)}o]', '-map', '[voice]', '-c:v', 'libx264', '-preset', 'fast',
             '-crf', '23' if preview else '17', '-threads', '4', '-pix_fmt', 'yuv420p',
             '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', output], log)


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


def assemble(episode, edit, pictures, speech, work, *, preview_shots=None, duration_policy=None):
    public = ROOT / 'remotion/public/cache'
    public.mkdir(exist_ok=True, parents=True)
    with TemporaryDirectory(prefix='episode-', dir=public) as folder:
        directory = Path(folder)
        props, clicks = edit_props(edit, pictures, speech, directory, f'cache/{directory.name}')
        props_path = work / 'edit-props.json'
        writejson(props_path, props)
        composition = edit.get('composition', 'remotion')
        if composition not in ('ffmpeg', 'remotion'):
            raise ValueError(f'Unknown episode composition: {composition}')
        intermediate = work / f'{composition}.mp4'
        if composition == 'ffmpeg':
            compose_ffmpeg(props, intermediate, work / 'ffmpeg.log', preview=preview_shots is not None)
            video = next(stream for stream in probe(intermediate)['streams'] if stream['codec_type'] == 'video')
            if int(video['nb_frames']) != props['frameCount']:
                raise ValueError('FFmpeg picture frames differ from the authored timeline')
        else:
            render(props_path, intermediate, work / 'remotion.log', visual=True,
                   preview=preview_shots is not None)
        track = work / 'mix.m4a'
        mix(intermediate, ROOT / edit['bgm'], props['duration'], clicks, track)
        output = ROOT / 'output' / episode.name / edit['output']
        if preview_shots is not None:
            output = output.with_stem(f'{output.stem}-preview-{preview_shots}')
        output.parent.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(prefix='.export-', dir=output.parent) as staging:
            candidate = Path(staging) / output.name
            mux_picture(intermediate, track, candidate, encoded=True)
            if duration_policy is not None and preview_shots is None:
                video = next(stream for stream in probe(candidate)['streams']
                             if stream['codec_type'] == 'video')
                if int(video['nb_frames']) != props['frameCount']:
                    raise ValueError('Exported picture frames differ from the authored timeline')
                validate_formal_duration(duration_policy, float(video['duration']))
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


def produce(episode, *, work_dir=None, env_file=None, edit_file=None, preview_shots=None,
            allow_short=False):
    episode = Path(episode).resolve()
    edit = json.loads((episode / (edit_file or 'edit.json')).read_text(encoding='utf-8'))
    if Path(edit['output']).name != edit['output'] or not edit['output'].endswith('.mp4'):
        raise ValueError('Episode output must be an MP4 filename')
    load_env(env_file)
    if preview_shots is not None and not 1 <= preview_shots <= len(edit['shots']):
        raise ValueError('preview_shots must select a nonempty prefix of the episode')
    duration_policy = {} if allow_short else {FORMAL_DURATION_FIELD: FORMAL_DURATION_VERSION}

    def render_into(work):
        assembly = work / 'preview' if preview_shots is not None else work
        assembly.mkdir(exist_ok=True)
        speech = (load_directed_narration(episode, edit, assembly) if 'directed_timeline' in edit
                  else measure_narration(episode, edit, limit=preview_shots))[:preview_shots]
        if preview_shots is None:
            validate_formal_duration(duration_policy, sum(frames for _, _, frames in speech) / FPS)
        selected = dict(edit, shots=edit['shots'][:preview_shots])
        step = edit.get('preview_step', 5) if preview_shots is not None else None
        writejson(assembly / 'timing.json', [frames for _, _, frames in speech])
        pictures = picture_sources(episode, speech, work, shots=selected['shots'], preview_step=step)
        return assemble(episode, selected, pictures, speech, assembly, preview_shots=preview_shots,
                        duration_policy=duration_policy)

    if work_dir is None:
        with TemporaryDirectory(prefix='mvn-episode-') as temporary:
            return render_into(Path(temporary))
    work_dir = Path(work_dir).resolve()
    work_dir.mkdir(exist_ok=True, parents=True)
    with lock(work_dir / '.episode.lock', wait=True):
        return render_into(work_dir)
