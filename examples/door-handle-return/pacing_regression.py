"""Re-cut the hash-bound historical 40.5-second door-handle workprint."""

import argparse
import json
from pathlib import Path

from cinematic_edit import TASK, compose, ffmpeg
from mechanical_video_next import joint_timeline as joint, pacing, video_review
from scripts.common import writejson

BASE = TASK / 'cinematic/animatic-revised'
OLD_SHA = '1bb6c1d936aeac0420ea81cea8022cd4b81490d1662a67db64e154ae567948f1'
# Source-frame coordinates of the decoded native 30 fps picture.
BASE_CUTS = (
    ('use', 0, 159), ('explode', 159, 330), ('spindle', 330, 466),
    ('load', 466, 608), ('seat', 608, 641), ('release', 641, 990),
    ('return', 990, 1215),
)
NEW_CUTS = (
    ('use', 22, 121), ('explode', 300, 420), ('load', 460, 608),
    ('seat', 608, 641), ('compare', 641, 661), ('release', 715, 973),
)
STARTS = {'use-1': 0, 'explode-2': 99, 'load-1': 230, 'load-2': 318,
          'release-1': 432, 'release-2': 521}
HOOK, CYCLE, REPLAY = ('installed-press-and-return', 'exposed-press-and-return',
                       'installed-return-replay')


def clock(cuts, narration, source_actions, revised):
    shots, actions = [], []
    cursor = 0
    for sid, first, last in cuts:
        shots.append(dict(id=sid, start_frame=cursor, end_frame=cursor + last - first,
                          source_start_frame=first, action_views={},
                          silence_reason='Inspect the structural evidence in the selected view.'))
        cursor += last - first
    for event in source_actions:
        name, left, right = event['id'], event['source_start_frame'], event['source_end_frame']
        pieces = [(name, left, right)]
        if revised and name == REPLAY:
            continue
        if revised and name == CYCLE:
            pieces = [('compress', left, 661), ('recover', 715, right)]
        for key, start, stop in pieces:
            action_shot = next(shot for shot in shots if shot['source_start_frame'] <= start <
                               shot['source_start_frame'] + shot['end_frame'] - shot['start_frame'])
            delta = action_shot['start_frame'] - action_shot['source_start_frame']
            changes = {}
            if revised and key == 'compress':
                changes['end_state'] = 'Depressed lever and compressed coil against the fixed seat'
            if revised and key == 'recover':
                changes['start_state'] = 'Depressed lever and compressed coil against the fixed seat'
            actions.append(dict(event, id=key, source_start_frame=start, source_end_frame=stop,
                                start_frame=start + delta, end_frame=stop + delta, **changes))
    for shot in shots:
        shot['action_views'] = {
            action['id']: action['source_start_frame'] + max(0, shot['start_frame'] - action['start_frame'])
            for action in actions if shot['start_frame'] < action['end_frame']
            and shot['end_frame'] > action['start_frame']
        }
    if revised:
        narration = [dict(line, start_frame=STARTS[line['id']]) for line in narration if line['id'] in STARTS]
        for i, line in enumerate(narration):
            line['deadline_frame'] = narration[i + 1]['start_frame'] if i + 1 < len(narration) else cursor
    return joint.validate(dict(film_integrity_version=1, frame_count=cursor, shots=shots,
                               narration=narration, actions=actions))


def direction(plan, native, revised):
    descriptions = {
        'use': 'Compare the mounted lever before the press and after it returns.',
        'explode': 'Find the spring and its two seats under the cover.',
        'spindle': 'Identify the square fit in the active driver.',
        'load': 'Trace the lever through the square spindle to the gold driver.',
        'seat': 'Compare the gold seat to the stationary blue seat.',
        'compare': 'Compare the compressed spring with the earlier unloaded assembly.',
        'release': 'Follow spring expansion, return rotation and the off-axis force.',
        'return': 'Repeat the installed lever motion at the end.',
    }
    design, states = {}, []
    rows = [
        ('use', 'press', 'input', 22, 52, HOOK, 'handle', None),
        ('use', 'first-home', 'output', 94, 96, HOOK, 'handle', None),
        ('load', 'drive', 'transmission', 469, 608, 'compress' if revised else CYCLE, 'spindle', 'load-1'),
        ('seat', 'seat-motion', 'contact', 608, 631, 'compress' if revised else CYCLE, 'spring_compression', None),
        ('release', 'let-go', 'reset', 730, 748, 'recover' if revised else CYCLE, 'spring_compression', 'release-1'),
        ('release', 'spring-returns', 'transmission', 748, 882, 'recover' if revised else CYCLE, 'active_driver', 'release-2'),
        ('release', 'exposed-home', 'output', 882, 886, 'recover' if revised else CYCLE, 'handle', None),
    ]
    if not revised:
        rows.extend([
            ('load', 'press-command', 'input', 469, 474, CYCLE, 'handle', 'load-1'),
            ('return', 'replayed-return', 'reset', 1090, 1126, REPLAY, 'handle', 'return-1'),
        ])
    increments = {
        'use': [(22, 96, 'external-return', 'Mounted lever visibly returns to horizontal')],
        'explode': [(300 if revised else 159, 420 if revised else 330, 'spring-under-cover', 'Displaced trim exposes two seats and arc spring')],
        'spindle': [(330, 420, 'square-fit', 'The square spindle fits the driven opening')],
        'load': [(469, 608, 'transmission', 'Lever, spindle and gold driver turn together')],
        'seat': [(608, 631, 'compressed-end', 'Gold seat closes toward the fixed end')],
        'compare': [],
        'release': [(731, 883, 'spring-return', 'The spring pushes the driver back and lifts the handle'),
                    (883, 960 if revised else 883, 'return-torque', 'Off-axis spring force produces the return torque')],
        'return': [(1020, 1126, 'external-return', 'The same installed lever returns to horizontal again')],
    }
    for cut in plan['shots']:
        sid = cut['id']
        first = cut['source_start_frame']
        offset = cut['start_frame'] - first
        last = cut['end_frame'] - offset
        task = descriptions[sid]
        row = dict(watch_task=task, mechanical_event=task, camera_reason=task,
                   exit_condition='Cut when the named relationship has been shown.',
                   increments=[], observation=[], events=[])
        design[sid] = row
        for left, right, key, explanation in increments[sid]:
            if first <= left < right <= last:
                row['increments'].append(dict(id=key, discovery=explanation,
                                              frames=[left + offset, right + offset], evidence=task))
        if sid == 'release':
            row['events'].append(dict(id='first-answer', kind='answer', frames=[731 + offset, 732 + offset],
                                      description='Spring extends and pushes the active driver back.'))
        if sid == 'compare' or (sid == 'release' and not revised):
            a, b = 641, 661
            row['observation'].append(dict(frames=[a + offset, b + offset], task='Inspect the loaded state.',
                                           evidence='Compare the gold seat with the fixed blue seat and the unloaded state.'))
        for shot, key, kind, left, right, action, channel, speech in rows:
            if shot != sid:
                continue
            event = dict(id=key, kind=kind, frames=[left + offset, right + offset], action_id=action,
                         description=task, state_id=channel)
            if key == 'press':
                event['opening'] = True
            if speech:
                event['speech_id'] = speech
            if key in {'let-go', 'press-command'}:
                event['onset_tolerance_frames'] = 9
            row['events'].append(event)
            state = dict(shot_id=sid, id=channel, action_id=action, source=native,
                         sample_path=['samples'], sample_key=channel, tolerance=1e-5)
            if state not in states:
                states.append(state)
    return design, states


def build(out):
    source = json.loads((BASE / 'technical.json').read_text())
    old = joint.bound(source['preview']['media'])
    if source['preview']['media']['sha256'] != OLD_SHA:
        raise ValueError('Unexpected historical picture version')
    plate = joint.bound(source['native_picture'])
    native = joint.binding(out / 'native-motion.json')
    samples = json.loads(joint.bound(native).read_text())
    if samples['scene']['sha256'] != source['scene']['sha256']:
        raise ValueError('Native state samples use a different Blender scene')
    old_config = json.loads((BASE / 'preview-blueprint.json').read_text())
    original = joint.receipt(old_config['timeline'], old_config['measured_timeline'])
    recordings = {clip['text']: (joint.bound(clip['audio']), clip['cache']) for clip in original['speech']}
    actions = json.loads((BASE / 'action-bound-blueprint.json').read_text())['timeline']['actions']

    for name, specs, revised in (('before', BASE_CUTS, False), ('after', NEW_CUTS, True)):
        plan = clock(specs, old_config['timeline']['narration'], actions, revised)
        report = out / f'{name}-neil.json'
        measured = joint.measure(plan, recordings.__getitem__, out / f'{name}-neil.wav')
        writejson(report, measured)
        if not revised and measured['narration_audio']['sha256'] != original['narration_audio']['sha256']:
            raise ValueError('Historical narration PCM changed')
        design, states = direction(plan, native, revised)
        writejson(out / f'{name}-blueprint.json', dict(timeline=plan, pacing=design, measured_timeline=joint.binding(report)))
        writejson(out / f'{name}-states.json', states)
        if revised:
            graph = [f'[0:v]split={len(specs)}' + ''.join(f'[p{i}]' for i, _ in enumerate(specs))]
            graph += [f'[p{i}]trim=start_frame={first}:end_frame={last},setpts=PTS-STARTPTS[v{i}]'
                      for i, (_, first, last) in enumerate(specs)]
            graph += [''.join(f'[v{i}]' for i, _ in enumerate(specs)) + f'concat=n={len(specs)}:v=1:a=0[out]']
            picture = out / 'after-picture.mp4'
            ffmpeg('-i', plate, '-filter_complex', ';'.join(graph), '-map', '[out]', '-an',
                   '-c:v', 'libx264', '-crf', 16, '-pix_fmt', 'yuv420p', picture)
            captions = compose.HEADER
            for cue in joint.cues(measured):
                captions += compose.cue(cue['start'], cue['end'], 'Sub', cue['text'])
            captions += compose.cue(17.0, 21.35, 'Label', '弹簧推力偏离轴心，产生回转力矩')
            (out / 'after.ass').write_text(captions)
            film = out / 'door-handle-pacing-candidate.mp4'
            # The historical Foley is written in the old clock. Move only retained
            # original sample intervals onto the same edit clock as the picture.
            import wave
            effect = BASE / 'mechanical-foley.wav'
            mix = out / 'after-mix.wav'
            from array import array
            with wave.open(str(effect), 'rb') as src, wave.open(str(joint.bound(measured['narration_audio'])), 'rb') as voice:
                samples_per_frame = joint.SAMPLES_PER_FRAME
                foley = array('h')
                for _, first, last in specs:
                    src.setpos(first * samples_per_frame)
                    foley.frombytes(src.readframes((last - first) * samples_per_frame))
                speech = array('h')
                speech.frombytes(voice.readframes(voice.getnframes()))
            from cinematic_edit import write_wav
            write_wav(mix, array('h', (a + b for a, b in zip(speech, foley, strict=True))))
            ffmpeg('-i', picture, '-i', mix, '-vf', 'subtitles=after.ass', '-c:v', 'libx264',
                   '-crf', 17, '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k',
                   '-movflags', '+faststart', film, cwd=out)
            if not all(samples['samples'][i] == samples['samples'][660] for i in range(661, 716)):
                raise ValueError('The cut removed moving or discontinuous native states')
            for action in (row for row in plan['actions'] if row['id'] in {'compress', 'recover'}):
                retained = samples['samples'][action['source_start_frame']:action['source_end_frame']]
                if any(abs(row['handle'] - row['spindle']) > 1e-5
                       or abs(row['spindle'] - row['active_driver']) > 1e-5
                       or abs(row['fixed_driver']) > 1e-5 for row in retained):
                    raise ValueError('Core transmission changed or fixed driver moved')
            technical = video_review.inspect(joint.binding(film), plan, measured=measured,
                playback=mix, mix=True, blueprint=story_blueprint(plan, report, design, source),
                required_ids={key for row in plan['narration'] for key in row['knowledge_ids']},
                rendered_cues=joint.cues(measured),
                sources={row['id']: dict(source['native_picture'], region=[0, 0, 1, .82],
                                         source_region=[0, 0, 1, .82]) for row in plan['shots']})
            technical['mechanical_recut'] = dict(unchanged_native_speed=True, equal_cut_state=True,
                                                 spindle_driver_coupling=True,
                                                 geometry_reference=joint.binding(TASK / 'restored-3d/revised/motion.json'))
            writejson(out / 'technical.json', technical)
            ffmpeg('-i', old, '-i', film, '-filter_complex',
                   '[0:v][0:a][1:v][1:a]concat=n=2:v=1:a=1[v][a]', '-map', '[v]', '-map', '[a]',
                   '-c:v', 'libx264', '-crf', 18, '-pix_fmt', 'yuv420p', '-c:a', 'aac',
                   '-b:a', '192k', '-movflags', '+faststart', out / 'full-before-after.mp4')


def story_blueprint(plan, measured, design, source):
    shots, moments = [], {}
    actions = {row['id']: row for row in plan['actions']}
    question = '门把手为什么松手就回到水平？'
    for cut in plan['shots']:
        sid = cut['id']
        first, last = cut['start_frame'], cut['end_frame']
        knowledge = {fact for line in plan['narration'] for fact in line['knowledge_ids']
                     if line['start_frame'] < last and line['deadline_frame'] > first}
        knowledge.update(actions[key]['knowledge_id'] for key in cut['action_views'])
        shot_facts = sorted(knowledge)
        shots.append(dict(shot_id=sid, time_range=[first / joint.FPS, last / joint.FPS],
                          knowledge_ids=shot_facts, render_engine='blender',
                          mechanical_role='core' if cut['action_views'] else 'support'))
        moments[sid] = dict(shot_id=sid, start_frame=first, end_frame=last,
                            knowledge_id=shot_facts[0], observable=design[sid]['watch_task'],
                            visual_evidence=source['native_picture']['path'])
    return dict(story_development_version=2, core_question=question, timeline=plan, shots=shots,
                measured_timeline=joint.binding(measured), narrative=dict(question=question, moments=moments))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('out', type=Path)
    build(parser.parse_args().out.resolve())
