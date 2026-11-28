"""Render an authored episode with Blender, measured narration, Remotion and FFmpeg."""

import json
import math
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
from uuid import uuid4
import wave

from mechanical_video_next import joint_timeline as joint
from mechanical_video_next import creative_selection, episode_evidence, pacing, video_review, visual_diagnosis
from mechanical_video_next.audio_acceptance import decode_aac
from mechanical_video_next.blender_runtime import BlenderFailure, blender_executable, run_blender
from mechanical_video_next.director_audio import aac_hash, mux_picture
from mechanical_video_next.production_contract import (
    FORMAL_DURATION_FIELD, FORMAL_DURATION_VERSION, validate_formal_duration,
)
from mechanical_video_next.remotion_build import VISUAL_SOURCES, render
from mechanical_video_next.visual_narrative import validate_graphic
from mechanical_video_next.workflow import lock
from scripts.common import ROOT, digest, filehash, probe, run, writejson
from scripts.narration import effective_profile, load_env, sentence, srt_time, synthesize_shot

FPS = 30
MECHANICS_SCRIPT = ROOT / 'blender/episode_mechanics.py'
FOLEY = {
    'press': (680, 72, .086),
    'mesh': (1850, 115, .066),
    'slide': (420, 48, .102),
    'contact': (980, 88, .085),
    'impact': (570, 67, .105),
    'latch': (1530, 85, .075),
    'release': (1270, 98, .075),
    'return': (840, 68, .091),
    'vibration': (295, 41, .125),
}


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
    with wave.open(str(joint.bound(timeline['narration_audio'])), 'rb') as master:
        for index, (block, shot) in enumerate(zip(narration, plan['shots'], strict=True)):
            first, last = shot['start_frame'], shot['end_frame']
            frames = edit['shots'][index].get('frames', last - first)
            if type(frames) is not int or frames != last - first:
                raise ValueError(f'Edit frames differ from the directed timeline in shot {index + 1}')
            start, end = first * joint.SAMPLES_PER_FRAME, last * joint.SAMPLES_PER_FRAME
            rows = [row for row in timeline['speech'] if start <= row['start_sample'] < end]
            if [row['text'] for row in rows] != block.splitlines() or any(
                    row['end_sample'] > end for row in rows):
                raise ValueError(f'Directed speech differs from episode script in shot {index + 1}')
            placed.extend(row['id'] for row in rows)
            relative = [dict(cue, start=cue['start'] - first / FPS, end=cue['end'] - first / FPS)
                        for cue in joint.cues({'speech': rows})]
            path = work / f'directed-shot-{index}.wav'
            master.setpos(start)
            with wave.open(str(path), 'wb') as audio:
                audio.setparams(master.getparams())
                audio.writeframes(master.readframes(end - start))
            speech.append((path, relative, last - first))
    if placed != [row['id'] for row in timeline['speech']]:
        raise ValueError('Directed speech is outside the episode picture track')
    return speech


def load_joint_edit(episode, edit):
    document = json.loads((episode / edit['timeline']).read_text(encoding='utf-8'))
    plan = joint.validate(document['plan'], source_root=episode)
    if 'directed_timeline' in edit or 'narration' in edit:
        raise ValueError('A joint edit takes its script from the timeline')
    actions = {row['id']: row for row in plan['actions']}
    cuts = []
    for index, (cut, slot) in enumerate(zip(edit['shots'], plan['shots'], strict=True)):
        count = slot['end_frame'] - slot['start_frame']
        offset = slot.get('source_start_frame', 0)
        reference = cut.get('picture')
        graphic = 'graphic' in cut
        source_frames = cut.get('source_frames', count)
        if 'crop' in cut:
            crop = cut['crop']
            if (graphic or not isinstance(crop, list) or len(crop) != 4
                    or any(type(value) not in (int, float) or not 0 <= value <= 1 for value in crop)):
                raise ValueError(f"Invalid picture crop in {slot['id']}")
            x, y, width, height = crop
            if width <= 0 or width != height or x + width > 1 or y + height > 1:
                raise ValueError(f"Picture crop must preserve the output aspect ratio in {slot['id']}")
        if (cut.get('id') != slot['id'] or cut.get('frames', count) != count
                or type(source_frames) is not int
                or (not reference and source_frames < offset + count)
                or (reference and offset != reference.get('start_frame', 0))
                or (reference and reference.get('fallback_to_scene'))
                or (graphic and (offset or 'source_frames' in cut))):
            raise ValueError(f"Picture extent differs from the joint timeline in {slot['id']}")
        if slot.get('action_views') and not graphic:
            if 'mechanics' not in cut:
                raise ValueError(f"Action view needs evaluated mechanics in {slot['id']}")
            if not reference:
                inputs = {(episode / name).resolve() for name in
                          [cut.get('scene', 'scene.py'), *cut.get('scene_inputs', ())]}
                if any(joint.bound(actions[key]['source'], root=episode).resolve() not in inputs
                       for key in slot['action_views']):
                    raise ValueError(f"Action source is absent from the scene inputs in {slot['id']}")
        cuts.append(dict(cut, scene_shot=cut.get('scene_shot', index),
                         source_start_frame=0 if reference else offset))
        if graphic:
            del cuts[-1]['scene_shot']
    if design := document.get('pacing'):
        pacing.validate(plan, design)
    if 'creative' in document:
        creative_selection.episode_direction(document, episode=episode)
    if any('clicks' in cut or 'subtitle_breaks' in cut for cut in cuts):
        raise ValueError('Joint edits place subtitles and mechanical sound on the timeline')
    for cue in document.get('sounds', ()):
        action = actions.get(cue.get('action_id'))
        frame, duration = joint.interval(cue, plan['frame_count'])
        witness = cue.get('witness', {})
        if (not action or not action['start_frame'] <= frame < duration <= action['end_frame']
                or cue.get('kind') not in FOLEY or not isinstance(cue.get('event'), str)
                or not cue['event'].strip() or not video_review.valid_sound_witness(witness)
                or not any(slot['start_frame'] <= frame < slot['end_frame']
                           and action['id'] in slot.get('action_views', {})
                           and 'mechanics' in cut and 'graphic' not in cut
                           for slot, cut in zip(plan['shots'], cuts, strict=True))):
            raise ValueError('Foley must identify a visible mechanical event and its output interval')
    return document, cuts


def measure_joint_narration(episode, edit, plan, output):
    if 'voice_direction' not in edit:
        profile = effective_profile({'narration_profile': 'config/narration-neil.json'})
        return joint.measure(plan, lambda words: sentence(words, profile), output, source_root=episode)

    from .directed_narration import measure
    from .voice_engines import Synthesizer, load_profile

    direction = json.loads((episode / edit['voice_direction']).read_text(encoding='utf-8'))
    profile = load_profile(ROOT / 'config/voice-profile.json')
    # The shot containing a speech entry can change during a picture-only recut.
    for spec, row in zip(plan['narration'], direction['segments'], strict=True):
        row['scene_id'] = next(shot['id'] for shot in plan['shots']
                               if shot['start_frame'] <= spec['start_frame'] < shot['end_frame'])
    with Synthesizer(diagnostics=output.parent / 'voice-diagnostics') as service:
        return measure(plan, direction, profile, service, output, source_root=episode,
                       fallback=profile.get('fallback_engine') == 'neil')


def picture_sources(episode, speech, work, *, counts=None, shots=None, preview_step=None,
                    coverage=None, document=None):
    if counts is None:
        counts = [frames for _, _, frames in speech]
    shots = [{} for _ in counts] if shots is None else shots
    paths = []
    renders = []
    witnesses = []
    for index, (count, cut) in enumerate(zip(counts, shots, strict=True)):
        reviewed = coverage[index] if coverage is not None else None
        witnesses.append(None)
        if 'graphic' in cut:
            paths.append(None)  # Render only after the mechanical preflight.
            continue
        reference = cut.get('picture')
        if reference and (not reference.get('fallback_to_scene') or (episode / reference['path']).is_file()):
            paths.append(None)  # A recut also requires preflight before cache reuse.
            witnesses[-1] = picture_motion((episode / reference['path']).resolve(), current=True)
            continue
        scene = episode / cut.get('scene', 'scene.py')
        shot = cut.get('scene_shot', index)
        if type(shot) is not int or shot < 0:
            raise ValueError('scene_shot must be a nonnegative integer')
        source_count = cut.get('source_frames', count)
        key = {'scene': filehash(scene), 'shot': shot, 'frames': source_count, 'fps': FPS}
        if cut.get('scene_inputs'):
            key['scene_inputs'] = {name: filehash(episode / name) for name in cut['scene_inputs']}
        mechanics = cut.get('mechanics')
        if mechanics is not None:
            executable = blender_executable()
            inputs = [scene, MECHANICS_SCRIPT, episode / mechanics['evidence']]
            inputs.extend(episode / name for name in cut.get('scene_inputs', ()))
            key['mechanics'] = {
                'inputs': {str(path.resolve()): filehash(path) for path in inputs},
                'blender': [str(executable), executable.stat().st_mtime_ns],
            }
        filename = f'shot-{shot}.mp4'
        path = work / digest(key) / filename
        draft_step = None
        if preview_step is not None and not path.is_file():
            draft_step = cut.get('preview_step', preview_step)
            if type(draft_step) is not int or draft_step < 1:
                raise ValueError('preview_step must be a positive integer')
            path = work / digest(dict(key, preview_step=draft_step)) / filename
        paths.append(path)
        if path.is_file() and mechanics is None:
            continue
        picture = path.parent
        picture.mkdir(exist_ok=True)
        timing = picture / 'timing.json'
        if mechanics is None:
            scene_counts = counts + [0] * max(0, shot + 1 - len(counts))
        else:
            scene_counts = [0] * (shot + 1)
        scene_counts[shot] = source_count
        command = ['--timing', str(timing), '--directory', str(picture), '--shot', str(shot)]
        motion = None
        verification = picture
        binding = key
        reviewer = None
        if reviewed and reviewed['kind'] == 'core':
            verifier = episode / episode_evidence.VERIFIER
            requirements = reviewed['relations']
            inputs = key['mechanics']['inputs'] | {
                str(file.resolve()): filehash(file)
                for file in (verifier, episode_evidence.RELATIONS_RUNNER)
            }
            binding = dict(key, mechanics=dict(key['mechanics'], inputs=inputs),
                           independent_relations=requirements)
            verification = picture / f"review-{digest(binding)}"
            verification.mkdir(exist_ok=True)
            reviewer = (verifier, json.dumps(sorted(requirements)))
        if mechanics is not None:
            with lock(ROOT / 'work/production.lock', wait=True):
                writejson(timing, scene_counts)
                try:
                    motion = prepare_motion(scene, command, verification, binding, reviewer=reviewer)
                except ValueError as error:
                    start = sum(counts[:index]) / FPS
                    raise ValueError(f'Edit shot {index + 1} starts at {start:.4f}s. {error}') from error
            witnesses[-1] = motion
        renders.append((path, scene, command, timing, scene_counts, shot, source_count, draft_step,
                        motion, verification, key, reviewer))

    findings, _ = video_review.episode_state_findings(shots, counts, witnesses, episode, coverage=coverage)
    if document is not None:
        findings.extend(video_review.joint_action_findings(document, shots, witnesses, episode))
    block_mechanical_errors(findings, work / 'mechanics-preflight-failure.json',
                            formal=coverage is not None and preview_step is None)
    for index, (cut, count) in enumerate(zip(shots, counts, strict=True)):
        if paths[index] is not None:
            continue
        if 'graphic' in cut:
            paths[index] = render_graphic(cut['graphic'], count, work, preview=preview_step is not None)
        else:
            paths[index] = recut_picture(episode, cut['picture'], count, work)
    for (path, scene, args, timing, scene_counts, shot, count, draft_step, motion,
         verification, key, reviewer) in renders:
        with lock(ROOT / 'work/production.lock', wait=True):
            bound = picture_motion(path, current=True, draft=draft_step is not None) if motion else None
            if path.is_file() and (motion is None or bound == motion):
                continue
            prior = picture_motion(path) if reviewer and draft_step is None else None
            previous_binding = (prior or {}).get('binding', {})
            previous_inputs = previous_binding.get('mechanics', {}).get('inputs', {})
            if (previous_binding and all(previous_binding.get(name) == value
                                         for name, value in key.items() if name != 'mechanics')
                    and previous_binding['mechanics'].get('blender') == key['mechanics']['blender']
                    and all(previous_inputs.get(name) == sha
                            for name, sha in key['mechanics']['inputs'].items())):
                # Reuse an unchanged render only after independent replay and a
                # comparison to its current dynamic witness.
                first, last = motion['preview_range']
                findings = video_review.pixel_findings(
                    path, verification / 'motion-preview.mp4', first, last, 0, f'shot-{shot}')
                if not findings:
                    video_review.write_report(path.with_suffix('.motion.json'), {
                        'picture_sha256': filehash(path), 'motion': motion, 'draft': False, 'preview_step': 1,
                    })
                    continue
            picture = path.parent
            frames = picture / f'shot-{shot}'
            if motion and (frames.exists() or path.exists()):
                # Retry once from the verified scene. Preserve the bad cache and partial evidence.
                quarantine = picture / f'unverified-{uuid4().hex}'
                quarantine.mkdir()
                for item in (frames, path, path.with_suffix('.motion.json')):
                    if item.exists():
                        item.replace(quarantine / item.name)
            if draft_step is not None:
                args = [*args, '--preview']
            step = draft_step or 1
            if not all((frames / f'{frame:05}.jpg').is_file() for frame in range(0, count, step)):
                writejson(timing, scene_counts)
                if motion:
                    run_checked_scene(scene, 'render', verification / 'evaluation.json',
                                      args, picture, timeout=1800, reviewer=reviewer)
                else:
                    run_blender(['--python-exit-code', '7', '--python', scene, '--', *args],
                                name=f'episode-{shot}',
                                directory=picture / f'blender-{shot}-{uuid4().hex}', timeout=1800)
            encode_shot(frames, count, path, preview_step=draft_step)
            if motion and draft_step is None:
                first, last = motion['preview_range']
                findings = video_review.pixel_findings(
                    path, verification / 'motion-preview.mp4', first, last, 0, f'shot-{shot}')
                block_mechanical_errors(findings, picture / 'mechanics-render-failure.json')
            if motion:
                if not motion_inputs_current(motion):
                    raise ValueError(f'Mechanical scene inputs changed during rendering: {scene}')
                video_review.write_report(path.with_suffix('.motion.json'), {
                    'picture_sha256': filehash(path), 'motion': motion, 'draft': draft_step is not None,
                    'preview_step': draft_step or 1,
                })
    return paths


def block_mechanical_errors(findings, path, *, formal=False):
    failures = [row for row in findings if row['status'] == 'FAIL'
                or (formal and row['status'] == 'UNKNOWN' and row.get('scope') == 'mechanical')]
    if failures:
        writejson(path, failures)
        first = failures[0]
        raise ValueError(f"{first['code']} at {first['time_range']}s: {first['evidence']}. See {path}")


def motion_inputs_current(motion):
    inputs = motion['binding'].get('mechanics', {}).get('inputs', {})
    return bool(inputs) and all(Path(path).is_file() and filehash(path) == sha for path, sha in inputs.items())


def picture_motion(path, *, current=False, draft=False, include_record=False):
    receipt = path.with_suffix('.motion.json')
    if not path.is_file() or not receipt.is_file():
        return None
    try:
        record = json.loads(receipt.read_text())
        motion = record['motion']
        if record.get('draft', False) and not draft:
            return None
        if record['picture_sha256'] == filehash(path) and (not current or motion_inputs_current(motion)):
            return record if include_record else motion
    except (OSError, ValueError, KeyError, TypeError):
        return None


def run_checked_scene(scene, phase, receipt, args, picture, *, timeout, reviewer=None):
    failure = receipt.with_suffix(f'.{phase}.failure.json')
    if failure.is_file():
        failure.rename(picture / f'{phase}-failure-{uuid4().hex}.json')
    script = episode_evidence.RELATIONS_RUNNER if reviewer else MECHANICS_SCRIPT
    try:
        run_blender(['--python-exit-code', '7', '--python', script, '--',
                     *(reviewer or ()), scene, phase, receipt, *args],
                    directory=picture / f'blender-{phase}-{uuid4().hex}', timeout=timeout)
    except BlenderFailure as error:
        if failure.is_file():
            raise ValueError(json.loads(failure.read_text())['error'] + f' [{scene}]') from error
        raise


def prepare_motion(scene, args, picture, binding, *, reviewer=None):
    # Stage receipt and dynamic preview together. A partial attempt never becomes a cache hit.
    evaluation = picture / 'evaluation.json'
    preview = picture / 'motion-preview.mp4'
    manifest = picture / 'motion-inputs.json'
    if manifest.is_file() and evaluation.is_file() and preview.is_file():
        try:
            record = json.loads(manifest.read_text())
            if record == {'binding': binding, 'evaluation': filehash(evaluation), 'preview': filehash(preview)}:
                return dict(json.loads(evaluation.read_text()), binding=binding, preview_sha256=record['preview'])
        except (OSError, ValueError):
            pass
    with TemporaryDirectory(prefix='preflight-', dir=picture) as folder:
        stage = Path(folder)
        candidate = stage / evaluation.name
        try:
            run_checked_scene(scene, 'preflight', candidate, args, picture, timeout=300, reviewer=reviewer)
        except ValueError:
            failure = candidate.with_suffix('.preflight.failure.json')
            if failure.is_file():
                failure.replace(picture / f'preflight-failure-{uuid4().hex}.json')
            raise
        motion = json.loads(candidate.read_text())
        run(['ffmpeg', '-v', 'error', '-xerror', '-framerate', FPS,
             '-i', stage / 'motion-preview-frames/%05d.jpg', '-vf', 'scale=trunc(iw/2)*2:trunc(ih/2)*2',
             '-c:v', 'libx264', '-crf', 16, '-pix_fmt', 'yuv420p', stage / preview.name])
        record = {'binding': binding, 'evaluation': filehash(candidate), 'preview': filehash(stage / preview.name)}
        candidate.replace(evaluation)
        (stage / preview.name).replace(preview)
        writejson(manifest, record)
    return dict(motion, binding=binding, preview_sha256=record['preview'])


def render_graphic(graphic, count, work, *, preview):
    """Render an original explanatory graphic into the same picture track as Blender."""
    seconds = count / FPS
    props = {'title': '', 'width': 1920, 'height': 1080, 'fps': FPS, 'duration': seconds,
             'frameCount': count, 'cues': [],
             'shots': [{'id': 'graphic', 'seconds': seconds, 'graphic': graphic}]}
    key = digest({'props': props, 'preview': preview,
                  'sources': {name: filehash(ROOT / name) for name in VISUAL_SOURCES}})
    output = work / key / 'graphic.mp4'
    if not output.is_file():
        output.parent.mkdir(exist_ok=True)
        props_path = output.parent / 'graphic.json'
        writejson(props_path, props)
        with TemporaryDirectory(dir=output.parent) as staging:
            candidate = Path(staging) / output.name
            render(props_path, candidate, output.parent / 'remotion.log', preview=preview, visual=True)
            video = next(row for row in probe(candidate)['streams'] if row['codec_type'] == 'video')
            size = (960, 540) if preview else (1920, 1080)
            if ((video['width'], video['height']) != size or video['r_frame_rate'] != '30/1'
                    or int(video['nb_frames']) != count):
                raise ValueError('Rendered graphic differs from its authored picture interval')
            candidate.replace(output)
    return output


def recut_picture(episode, reference, count, work):
    """Use an at-speed interval of an existing original picture render."""
    if type(count) is not int or count < 1:
        raise ValueError('Picture requires a positive frame count')
    source = (episode / reference['path']).resolve()
    if filehash(source) != reference['sha256']:
        raise ValueError(f'Original picture render hash differs: {source}')
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


def edit_props(edit, pictures, speech, public, asset_prefix, *, measured=None, counts=None):
    shots, cues, labels, clicks = [], [], [], []
    if measured is None:
        counts = [frames for _, _, frames in speech]
    else:
        master = joint.bound(measured['narration_audio'])
        shutil.copyfile(master, public / 'narration.wav')
        duration = sum(counts) / FPS
        cues = [dict(cue, end=min(cue['end'], duration))
                for cue in joint.cues(measured) if cue['start'] < duration]
    cursor = 0
    for i, (shot, media, frames) in enumerate(zip(edit['shots'], pictures, counts, strict=True)):
        shutil.copyfile(media, public / f'{i}.mp4')
        row = {'id': shot.get('id', f'shot-{i}'), 'seconds': frames / FPS, 'media': f'{asset_prefix}/{i}.mp4'}
        start = cursor / FPS
        if measured is None:
            audio, words, _ = speech[i]
            audio_name = f'{i}{Path(audio).suffix}'
            shutil.copyfile(audio, public / audio_name)
            row['audio'] = f'{asset_prefix}/{audio_name}'
            cues.extend(dict(cue, start=cue['start'] + start, end=cue['end'] + start)
                        for cue in subtitle_cues(words, shot.get('subtitle_breaks', {})))
        else:
            row['mediaStartFrame'] = shot['source_start_frame']
            if 'crop' in shot:
                row['crop'] = shot['crop']
        shots.append(row)
        for first, last, text in shot.get('labels', ()):
            if measured is None:
                left, right = start + first, start + last
            else:
                left = (cursor + math.ceil(first * FPS - 1e-6)) / FPS
                right = (cursor + math.ceil(last * FPS - 1e-6)) / FPS
            if left < right:
                labels.append({'layer': 'part', 'start': left, 'end': right, 'text': text})
        clicks.extend(start + seconds for seconds in shot.get('clicks', ()))
        cursor += frames
    props = {'title': edit['title'], 'width': 1920, 'height': 1080, 'fps': FPS,
             'duration': cursor / FPS, 'frameCount': cursor, 'shots': shots, 'cues': cues,
             'annotations': labels}
    if measured is not None:
        props['narrationTrack'] = f'{asset_prefix}/narration.wav'
    return props, clicks


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
    master = props.get('narrationTrack')
    size = (f'scale={width}:{height}:force_original_aspect_ratio=decrease,'
            f'pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=0x223139')
    for index, shot in enumerate(shots):
        frames = round(shot['seconds'] * FPS)
        samples = frames * joint.SAMPLES_PER_FRAME
        source = index if master else 2 * index
        start = shot.get('mediaStartFrame', 0)
        command += ['-i', ROOT / 'remotion/public' / shot['media']]
        crop = video_review.crop_filter(shot.get('crop'))
        filters.append(f'[{source}:v]{crop}{size},setsar=1,trim=start_frame={start}:end_frame={start + frames},'
                       f'setpts=PTS-STARTPTS[v{index}]')
        if not master:
            command += ['-i', ROOT / 'remotion/public' / shot['audio']]
            filters.append(f'[{source + 1}:a]aresample=48000,aformat=channel_layouts=stereo,'
                           f'apad,atrim=end_sample={samples},asetpts=PTS-STARTPTS[a{index}]')
    if master:
        command += ['-i', ROOT / 'remotion/public' / master]
        segments = ''.join(f'[v{index}]' for index in range(len(shots)))
        filters.append(f'{segments}concat=n={len(shots)}:v=1:a=0[v0o]')
        samples = props['frameCount'] * joint.SAMPLES_PER_FRAME
        filters.append(f'[{len(shots)}:a]atrim=end_sample={samples},asetpts=PTS-STARTPTS[voice]')
    else:
        segments = ''.join(f'[v{index}][a{index}]' for index in range(len(shots)))
        filters.append(f'{segments}concat=n={len(shots)}:v=1:a=1[v0o][voice]')
    media_inputs = len(shots) + 1 if master else 2 * len(shots)

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
            filters.append(f"[v{index}o][{media_inputs + index}:v]overlay={x}:{y}:"
                           f"enable='between(n,{start},{end - 1})'[v{index + 1}o]")
        run([*command, '-filter_complex_threads', '2', '-filter_complex', ';'.join(filters),
             '-map', f'[v{len(items)}o]', '-map', '[voice]', '-c:v', 'libx264', '-preset', 'fast',
             '-crf', '23' if preview else '17', '-threads', '4', '-pix_fmt', 'yuv420p',
             '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', output], log)


def mix(picture, bgm, duration, clicks, destination, *, sounds=()):
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
    effects = [(str(round(time * 1000)), transient) for time in clicks]
    for cue in sounds:
        pitch, decay, scale = FOLEY[cue['kind']]
        seconds = (cue['end_frame'] - cue['start_frame']) / FPS
        effect = (f'aevalsrc={scale}*(sin(2*PI*{pitch}*t)+0.3*sin(2*PI*{1.37*pitch}*t))'
                  f'*exp(-{decay}*t):s=48000:d={seconds:.8f}')
        effects.append((f"{cue['start_frame'] * joint.SAMPLES_PER_FRAME}S", effect))
    for i, (delay, effect) in enumerate(effects, start=2):
        args.extend(['-f', 'lavfi', '-i', effect])
        filters.append(f'[{i}:a]aformat=channel_layouts=stereo,adelay={delay}:all=1[c{i}]')
        buses.append(f'[c{i}]')
    filters.append(''.join(buses) + f'amix=inputs={len(buses)}:normalize=0,'
                   'alimiter=limit=0.85:level=false:latency=true[out]')
    run([*args, '-filter_complex', ';'.join(filters), '-map', '[out]', '-t', duration,
         '-ar', 48000, '-c:a', 'aac', '-b:a', '192k', destination])


def review_export(candidate, episode, edit, pictures, speech, props, public, *, preview, coverage=None,
                  measured=None, document=None):
    motions, sources, audio_hashes, diagnostics = [], [], [], []
    for index, (cut, picture) in enumerate(zip(edit['shots'], pictures, strict=True)):
        reference = cut.get('picture')
        recut = bool(reference and (episode / reference['path']).is_file())
        if recut:
            source = (episode / reference['path']).resolve()
            if filehash(source) != reference['sha256']:
                raise ValueError(f'Recut source changed during production: {source}')
            offset = reference.get('start_frame', 0)
            motion_source = source
        else:
            source, offset = public / f'{index}.mp4', cut.get('source_start_frame', 0)
            motion_source = picture
        record = picture_motion(motion_source, current=True, draft=preview, include_record=True)
        motion = record['motion'] if record else None
        step = record.get('preview_step', 1 if not record.get('draft') else None) if record else None
        if record and step is None:
            # Older draft receipts predate the step field. Verify the cache key
            # against the step used by the original preview entry point.
            step = cut.get('preview_step', edit.get('preview_step', 5))
            if motion_source.parent.name != digest(dict(motion['binding'], preview_step=step)):
                step = None
        diagnostics.append(visual_diagnosis.shot_binding(
            cut, motion, episode, direct=not recut and not offset,
            preview_step=step, crop=cut.get('crop')))
        if 'mechanics' in cut and 'graphic' not in cut and motion is None:
            raise ValueError(f'Shot {index}: the rendered picture or evaluated scene inputs changed')
        motions.append(motion)
        sources.append((source, offset, filehash(source)))
        if filehash(picture) != filehash(public / f'{index}.mp4'):
            raise ValueError(f'Picture changed during composition: {picture}')
        if measured is None:
            audio = speech[index][0]
            sha = filehash(public / f'{index}{Path(audio).suffix}')
            if filehash(audio) != sha:
                raise ValueError(f'Narration changed during composition: {audio}')
            audio_hashes.append(sha)
    if measured is not None:
        sha = filehash(joint.bound(measured['narration_audio']))
        if filehash(public / 'narration.wav') != sha:
            raise ValueError('Continuous narration changed during composition')
        audio_hashes.append(sha)
    findings, cuts = video_review.episode_state_findings(
        edit['shots'], [round(row['seconds'] * FPS) for row in props['shots']],
        motions, episode, coverage=coverage)
    if document is not None:
        findings.extend(video_review.joint_action_findings(document, edit['shots'], motions, episode))
    picture_findings, intervals = [], []
    for index, (cut, motion, (source, offset, sha)) in enumerate(zip(cuts, motions, sources, strict=True)):
        authored = edit['shots'][index].get('mechanics', {})
        first, last = cut['start_frame'], cut['end_frame']
        regions = [None, *authored.get('regions', ())]
        crop = edit['shots'][index].get('crop')
        for region in regions:
            source_region = video_review.compose_region(crop, region)
            picture_findings.extend(video_review.pixel_findings(
                candidate, source, first, last, offset, cut['id'], region=region, source_region=source_region))
        if filehash(source) != sha:
            raise ValueError(f'Picture source changed during final review: {source}')
        if motion and not motion_inputs_current(motion):
            raise ValueError(f"Shot {index}: mechanical scene inputs changed during final review")
        intervals.append(dict(cut, picture_sha256=sha, evaluated_motion=motion,
                              compared_regions=regions, **diagnostics[index]))
    return {
        'media': {'filename': candidate.name, 'sha256': filehash(candidate)},
        'edit_sha256': digest(edit), 'composition_props_sha256': digest(props),
        'narration_sha256': filehash(episode / edit.get('timeline', edit.get('narration', 'narration.txt'))),
        'audio_sha256': audio_hashes,
        'intervals': intervals, 'preview': preview,
        'technical_status': video_review.status(findings + picture_findings),
        'decoded_picture_status': video_review.status(picture_findings),
        'continuous_viewing': 'UNKNOWN', 'perceptual_listening': 'UNKNOWN',
        'independent_acceptance': 'UNKNOWN',
        'findings': findings + picture_findings,
    }


def assemble(episode, edit, pictures, speech, work, *, preview_shots=None, duration_policy=None,
             coverage=None, mechanical_plan=None, document=None, measured=None, counts=None):
    public = ROOT / 'remotion/public/cache'
    public.mkdir(exist_ok=True, parents=True)
    with TemporaryDirectory(prefix='episode-', dir=public) as folder:
        directory = Path(folder)
        props, clicks = edit_props(edit, pictures, speech, directory, f'cache/{directory.name}',
                                   measured=measured, counts=counts)
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
        bgm = ROOT / edit['bgm']
        bgm_sha256 = filehash(bgm)
        sounds = [dict(cue, end_frame=min(cue['end_frame'], props['frameCount']))
                  for cue in (document or {}).get('sounds', ()) if cue['start_frame'] < props['frameCount']]
        voice = directory / 'narration.wav' if measured is not None else intermediate
        mix(voice, bgm, props['duration'], clicks, track, sounds=sounds)
        if filehash(bgm) != bgm_sha256:
            raise ValueError(f'BGM changed during composition: {bgm}')
        output = ROOT / 'output' / episode.name / edit['output']
        if preview_shots is not None:
            output = output.with_stem(f'{output.stem}-preview-{preview_shots}')
        output.parent.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(prefix='.export-', dir=output.parent) as staging:
            candidate = Path(staging) / output.name
            mux_picture(intermediate, track, candidate, encoded=True)
            video = joint.validate_rendered_film(candidate, {'frame_count': props['frameCount']})
            if duration_policy is not None and preview_shots is None:
                validate_formal_duration(duration_policy, float(video['duration']))
            audio_sha256 = aac_hash(candidate)
            if audio_sha256 != aac_hash(track):
                raise ValueError('MP4 audio differs from the encoded episode mix')
            review = review_export(candidate, episode, edit, pictures, speech, props, directory,
                                   preview=preview_shots is not None, coverage=coverage, measured=measured,
                                   document=document)
            if document is not None:
                review['timeline'] = {'shots': document['plan']['shots'][:preview_shots],
                                      'actions': [row for row in document['plan']['actions']
                                                  if row['start_frame'] < props['frameCount']],
                                      'speech': props['cues'], 'sounds': sounds}
                review['editing'] = pacing.episode_diagnostics(
                    joint.binding(candidate), document, props['frameCount'], measured, review['intervals'])
                sample_count = props['frameCount'] * joint.SAMPLES_PER_FRAME
                samples, audio = decode_aac(candidate, sample_count)
                playback = [dict(row, end_sample=min(row['end_sample'], sample_count))
                            for row in measured['speech'] if row['start_sample'] < sample_count]
                review['audio_playback'] = dict(audio, sample_peak=max(map(abs, samples)),
                                                narration=playback)
            review['bgm_sha256'] = bgm_sha256
            review['aac_packets_sha256'] = audio_sha256
            review['decoded_frame_count'] = int(video['nb_frames'])
            block_mechanical_errors(review['findings'], work / 'mechanics-export-failure.json',
                                    formal=preview_shots is None and coverage is not None)
            presentation = (mechanical_plan or {}).get('presentation', {}).get(review['media']['sha256'])
            reviewed_shots = [i for i, row in enumerate(coverage or ())
                              if row and row['kind'] in {'core', 'graphic'}]
            presentation_pass = (bool(reviewed_shots) and isinstance(presentation, dict)
                                 and all(isinstance(presentation.get(str(i)), str) and presentation[str(i)].strip()
                                         for i in reviewed_shots))
            qualified = (preview_shots is None and coverage and all(coverage)
                         and presentation_pass)
            review['mechanical_status'] = 'PASS' if qualified else 'UNKNOWN'
            review['mechanical_presentation'] = presentation if presentation_pass else 'UNKNOWN'
            review['mechanical_plan_sha256'] = digest(mechanical_plan) if mechanical_plan else None
            if preview_shots is None and not qualified:
                output = output.with_stem(f'{output.stem}-candidate')
            review['media']['filename'] = output.name
            if document is not None:
                review['editing']['media']['path'] = str(output.resolve())
                if direction := review['editing'].get('direction'):
                    direction['media']['path'] = str(output.resolve())
            receipt = candidate.with_suffix('.mechanics.json')
            writejson(receipt, review)
            srt = candidate.with_suffix('.srt')
            srt.write_text('\n'.join(
                f'{i}\n{srt_time(cue["start"])} --> {srt_time(cue["end"])}\n{cue["text"]}\n'
                for i, cue in enumerate(props['cues'], start=1)), encoding='utf-8')
            with lock(ROOT / 'work/episode-locks' / digest(str(output)), wait=True):
                srt.replace(output.with_suffix('.srt'))
                candidate.replace(output)
                receipt.replace(output.with_suffix('.mechanics.json'))
    return output


def produce(episode, *, work_dir=None, env_file=None, edit_file=None, preview_shots=None,
            allow_short=False):
    episode = Path(episode).resolve()
    edit = json.loads((episode / (edit_file or 'edit.json')).read_text(encoding='utf-8'))
    if Path(edit['output']).name != edit['output'] or not edit['output'].endswith('.mp4'):
        raise ValueError('Episode output must be an MP4 filename')
    document, cuts = load_joint_edit(episode, edit) if 'timeline' in edit else (None, edit['shots'])
    for cut in cuts:
        if 'mechanics' in cut:
            mechanical = cut['mechanics']
            if not isinstance(mechanical, dict) or not isinstance(mechanical.get('evidence'), str):
                raise ValueError('A mechanical check requires a research evidence path')
            if not (episode / mechanical['evidence']).is_file():
                raise ValueError(f"Mechanical evidence is missing: {mechanical['evidence']}")
        if 'graphic' not in cut:
            continue
        if (not isinstance(cut['graphic'], dict) or
                {'picture', 'scene', 'scene_shot', 'scene_inputs'} & cut.keys()):
            raise ValueError('A graphic shot requires one graphic and no separate picture source')
        validate_graphic(cut['graphic'])
    if preview_shots is None and edit['shots'] and all('graphic' in cut for cut in edit['shots']):
        raise ValueError('An episode needs original 3D shots for its mechanical content')
    load_env(env_file)
    if preview_shots is not None and not 1 <= preview_shots <= len(edit['shots']):
        raise ValueError('preview_shots must select a nonempty prefix of the episode')
    duration_policy = {} if allow_short else {FORMAL_DURATION_FIELD: FORMAL_DURATION_VERSION}

    def render_into(work, preview_shots):
        assembly = work / 'preview' if preview_shots is not None else work
        assembly.mkdir(exist_ok=True)
        speech = measured = None
        if document is None:
            speech = (load_directed_narration(episode, edit, assembly) if 'directed_timeline' in edit
                      else measure_narration(episode, edit, limit=preview_shots))[:preview_shots]
            counts = [frames for _, _, frames in speech]
            narration = narration_blocks(episode, edit)[:preview_shots]
        else:
            timeline = document['plan']
            slots = timeline['shots'][:preview_shots]
            counts = [slot['end_frame'] - slot['start_frame'] for slot in slots]
            measured = measure_joint_narration(episode, edit, timeline, assembly / 'narration.wav')
            writejson(assembly / 'narration-timeline.json', measured)
            words = measured['speech']
            narration = ['\n'.join(row['text'] for row in words
                                   if row['start_sample'] < slot['end_frame'] * joint.SAMPLES_PER_FRAME
                                   and row['end_sample'] > slot['start_frame'] * joint.SAMPLES_PER_FRAME)
                         for slot in slots]
        if preview_shots is None:
            validate_formal_duration(duration_policy, sum(counts) / FPS)
        selected = dict(edit, shots=cuts[:preview_shots])
        plan = episode_evidence.load(episode)
        coverage = []
        missing = []
        cursor = 0
        for index, (cut, script, frames) in enumerate(zip(selected['shots'], narration, counts, strict=True)):
            row, reason = episode_evidence.coverage(episode, plan, cut, index, script)
            coverage.append(row)
            if reason:
                missing.append(dict(video_review.finding(
                    'mechanical_coverage_unreviewed', cursor, cursor + frames, reason,
                    shot=f'shot-{index}', status='UNKNOWN'), scope='mechanical'))
            cursor += frames
        block_mechanical_errors(missing, assembly / 'mechanics-preflight-failure.json',
                                formal=preview_shots is None)
        step = edit.get('preview_step', 5) if preview_shots is not None else None
        writejson(assembly / 'timing.json', counts)
        joint_args = {} if document is None else {'counts': counts, 'document': document}
        pictures = picture_sources(episode, speech, work, shots=selected['shots'],
                                   preview_step=step, coverage=coverage, **joint_args)
        return assemble(episode, selected, pictures, speech, assembly, preview_shots=preview_shots,
                        duration_policy=duration_policy, coverage=coverage, mechanical_plan=plan,
                        document=document, measured=measured, counts=counts)

    modern = document is not None and 'creative' in document

    def produce_into(work):
        if not modern or (preview_shots is not None and preview_shots < len(cuts)):
            return render_into(work, preview_shots)

        # Source edits invalidate the whole-preview receipt while unchanged shot and voice caches survive.
        plan = episode_evidence.load(episode)
        paths = {episode / 'mechanics_review.py', ROOT / edit['bgm'],
                 ROOT / 'config/narration-neil.json'}
        if 'voice_direction' in edit:
            paths.update((episode / edit['voice_direction'], ROOT / 'config/voice-profile.json'))
        for shot in cuts:
            if 'mechanics' in shot:
                paths.add(episode / shot['mechanics']['evidence'])
        identity = digest({
            'edit': edit, 'timeline': {key: value for key, value in document.items()
                                      if key not in ('creative', 'pacing')},
            'mechanics': plan.get('shots'),
            'claims': plan.get('claims'),
            'shots': [episode_evidence.shot_signature(episode, shot, index, '')
                      for index, shot in enumerate(cuts)],
            'inputs': {str(path): filehash(path) for path in paths if path.is_file()},
        })
        preview_root = work / 'preview'
        receipt = preview_root / 'audience-analysis.json'
        analysis = json.loads(receipt.read_text()) if receipt.is_file() else {}
        try:
            preview = joint.bound(analysis['media']) if analysis.get('inputs') == identity else None
            if preview is not None:
                joint.bound(analysis['phone_preview']['playback'])
        except (KeyError, TypeError, ValueError):
            preview = None
        if preview is None:
            preview = render_into(work, len(cuts))
            analysis = pacing.producer_preview(preview, preview_root)
            analysis['inputs'] = identity
            writejson(receipt, analysis)
        if preview_shots is not None:
            return preview
        review_file = preview_root / 'audience-review.json'
        if not review_file.is_file():
            print(f'Producer preview ready. Record timed observations in {review_file}')
            return preview
        raw = json.loads(review_file.read_text())
        if raw.get('media_sha256') != analysis['media']['sha256']:
            print(f'Producer preview updated. Review the current MP4 and update {review_file}')
            return preview
        review = pacing.producer_observations(raw, analysis)
        if any(issue['status'] == 'OPEN' for issue in review['issues']):
            print(f'Producer preview has open issues in {review_file}')
            return preview
        output = render_into(work, None)
        writejson(output.with_suffix('.audience.json'),
                  dict(review, final_media=joint.binding(output), creative=document['creative']))
        return output

    if work_dir is None and modern:
        work_dir = ROOT / 'work' / episode.name / 'episode'
    if work_dir is None:
        with TemporaryDirectory(prefix='mvn-episode-') as temporary:
            return produce_into(Path(temporary))
    work_dir = Path(work_dir).resolve()
    work_dir.mkdir(exist_ok=True, parents=True)
    with lock(work_dir / '.episode.lock', wait=True):
        return produce_into(work_dir)
