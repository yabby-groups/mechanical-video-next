"""Measure Neil and compose the complete native route B picture and sound."""
import argparse
from array import array
import json
import os
from pathlib import Path
import wave

from cinematic_edit import TASK, compose, ffmpeg, write_wav
from mechanical_video_next import joint_timeline as joint
from mechanical_video_next.audio_acceptance import check_levels, verify_mix
from mechanical_video_next.production_contract import validate_formal_duration
from mechanical_video_next.video_review import inspect, pixel_findings, status
from scripts.common import ROOT, writejson

HERE = Path(__file__).resolve().parent
PROFILE = ROOT / 'config/narration-neil.json'
SOURCE = TASK / 'visual-story/contact-refined'
BASELINE = TASK / 'cinematic/animatic-revised'
LABELS = {
    'reveal': '把手根部的回位机构',
    'explode': '沿方轴拆开',
    'lost': '沿轴看方孔',
    'upper': '固定端',
    'lower': '活动端',
    'energy': '弹性势能',
    'torque': '轴心与推力作用点',
    'stops': '壳体上的止挡',
    'design': '锁控连杆的预留空间',
    'map': '按下  ·  把手 → 方轴 → 拨片 → 弹簧',
}


def read(path):
    return json.loads(path.read_text())


def measure(folder, story):
    os.environ.setdefault('OPENAI_BASE_URL', 'https://api.huabot.com/v1')
    os.environ.setdefault('OPENAI_API_KEY', os.environ.get('HUABOT_OPENAI_API_KEY', ''))
    profile = compose.narration.load_profile(PROFILE)
    if profile['voice'] != 'Neil' or profile['target_speed'] != 1.0:
        raise ValueError('Use the original-speed Neil profile')
    recorded = {line: compose.narration.sentence(line, profile)
                for shot in story['shots'] for line in shot['lines']}
    action_source = joint.binding(SOURCE / 'scene.blend')
    source_evidence = joint.binding(SOURCE / 'mechanical-verification.json')
    events = {
        'hook': (22, 97, 0, '手柄下压', '安装状态下复位', '把手受压后抬回'),
        'lost': (475, 529, 52, '按下把手', '方轴带动金色拨片', '蓝色拨片保持原位'),
        'mid': (540, 652, 51, '继续按下', '弹簧缩短', '下端压入，上端由壳体挡住'),
        'lower': (652, 711, 0, '维持按压', '保持压缩状态', '两端保持与端座相邻'),
        'release': (711, 886, 8, '撤去手力', '把手回正', '弹簧推下端座，拨片反向带轴回转'),
    }
    shots, narration, actions = [], [], []
    cursor = 0
    for shot in story['shots']:
        name = shot['id']
        start = cursor
        for index, line in enumerate(shot['lines'], 1):
            cursor += 8 if index == 1 else 10
            length = joint.pcm_frames(recorded[line][0])
            end = cursor + (length + joint.SAMPLES_PER_FRAME - 1) // joint.SAMPLES_PER_FRAME
            narration.append(dict(id=f'{name}-{index}', start_frame=cursor, deadline_frame=end,
                                  text=line, knowledge_ids=[name]))
            cursor = end
        cursor = max(cursor + 14, start + round(shot['seconds'] * joint.FPS))
        if name == 'answer':
            cursor = max(cursor, start + 154)
        cut = dict(id=name, start_frame=start, end_frame=cursor)
        if name in events:
            first, stop, offset, initial, outcome, contact = events[name]
            cut.update(source_start_frame=0, source_clock_origin=first-offset,
                       action_views={name: first})
            actions.append(dict(id=name, start_frame=start+offset, end_frame=start+offset+stop-first,
                                source_start_frame=first, source_end_frame=stop,
                                source=action_source, evidence={**source_evidence, 'position': 'results[0]'},
                                start_state=initial, end_state=outcome,
                                curve='Native 30 fps, one source pose per output frame',
                                constraints=['lever and square spindle rotate together',
                                             'opposite driver held at its stop'],
                                input=initial, direction='回程' if name == 'release' else '工作行程',
                                transmission=outcome, intermediate_state=contact,
                                contact=contact, knowledge_id=name))
        shots.append(cut)
    plan = joint.validate(dict(film_integrity_version=1, frame_count=cursor, shots=shots,
                               narration=narration, actions=actions))
    validate_formal_duration(read(folder / 'task.json'), cursor / joint.FPS)
    joint_file = folder / 'joint-timeline.json'
    writejson(joint_file, plan)
    voice = folder / 'neil.wav'
    measured = joint.measure(plan, recorded.__getitem__, voice)
    writejson(folder / 'measured-neil.json', measured)
    joint.receipt(plan, joint.binding(folder / 'measured-neil.json'))
    print(f'{cursor / joint.FPS:.3f}s, {cursor} frames, {len(narration)} measured Neil clips')


def audio_mix(folder, plan):
    count = plan['frame_count'] * joint.SAMPLES_PER_FRAME
    effects = array('h', [0]) * count
    source = BASELINE / 'mechanical-foley.wav'
    recipe = BASELINE / 'foley-source.json'
    cues = []
    with wave.open(str(source), 'rb') as foley:
        foley.setpos(round(29.39 * joint.SAMPLE_RATE))
        samples = array('h')
        samples.frombytes(foley.readframes(round(.11 * joint.SAMPLE_RATE)))
        for action_id, relative in (('hook', 73), ('release', 171)):
            action = next(row for row in plan['actions'] if row['id'] == action_id)
            frame = action['start_frame'] + relative
            index = frame * joint.SAMPLES_PER_FRAME
            effects[index:index + len(samples)] = array('h', (round(x * .45) for x in samples))
            cues.append(dict(id=action_id, frame=frame, sample_count=len(samples)))
    stem = folder / 'foley.wav'
    write_wav(stem, effects)
    proof = folder / 'foley-source.json'
    writejson(proof, dict(source=joint.binding(source), recipe=joint.binding(recipe),
                         source_start=29.39, gain=.45, cues=cues, license='CC0-1.0'))
    voice = folder / 'neil.wav'
    with wave.open(str(voice), 'rb') as speech:
        samples = array('h')
        samples.frombytes(speech.readframes(count))
    master = folder / 'neil-and-foley.wav'
    write_wav(master, array('h', (a+b for a,b in zip(samples, effects, strict=True))))
    mix = {'master': joint.binding(master), 'stems': [{
        'kind': 'sfx', 'source': joint.binding(stem), 'start_sample': 0, 'end_sample': count,
        'source_start_sample': 0, 'gain_db': 0, 'source_type': 'GENERATED',
        'license_status': 'VERIFIED', 'usage_restrictions': [],
        'credit': '君哥拆机器 · 原创拟音',
        'license': {'name': 'CC0-1.0', 'holder': '君哥拆机器', 'status': 'VERIFIED',
                    'editing_and_distribution': True, 'commercial_use': True,
                    'proof': {**joint.binding(proof), 'position': 'Original recipe and stop sound interval'}},
    }]}
    verify_mix(mix, voice, count)
    writejson(folder / 'audio-mix.json', mix)
    return master


def srt_time(sample):
    millis = round(sample / 48)
    seconds, ms = divmod(millis, 1000)
    minutes, ss = divmod(seconds, 60)
    return f'{minutes//60:02}:{minutes%60:02}:{ss:02},{ms:03}'


def captions(folder, plan, measured):
    header = compose.HEADER.replace('Heiti SC,25,', 'Heiti SC,22,')
    events, srt = [], []
    for cut in plan['shots']:
        name = cut['id']
        starts, ends = cut['start_frame'] / 30, cut['end_frame'] / 30
        label = LABELS.get(name)
        if label:
            label_end = (starts + ends) / 2 if name == 'map' else min(ends, starts + 3.6)
            events.append(compose.cue(starts + .1, label_end, 'Label', label))
        if name == 'map':
            events.append(compose.cue((starts + ends) / 2, ends, 'Label',
                                      '松手  ·  弹簧 → 拨片 → 方轴 → 把手'))
        if name == 'coils':
            middle = (starts + ends) / 2
            events.append(compose.cue(starts, middle, 'Label', '回位时'))
            events.append(compose.cue(middle, ends, 'Label', '压缩时'))
    for index, row in enumerate(measured['speech'], 1):
        a, b, text = row['start_sample'], row['end_sample'], row['subtitle']
        events.append(compose.cue(a / 48000, b / 48000, 'Sub', text))
        srt.append(f'{index}\n{srt_time(a)} --> {srt_time(b)}\n{text}\n')
    (folder / 'captions.ass').write_text(header + ''.join(events))
    (folder / '门把手回正.srt').write_text('\n'.join(srt))


def subtitle_seconds(text):
    hours, minutes, seconds = text.replace(',', '.').split(':')
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def checked_captions(folder, measured):
    source = folder / '门把手回正.srt'
    cues = []
    for block in source.read_text().strip().split('\n\n'):
        _, window, text = block.splitlines()
        start, end = map(subtitle_seconds, window.split(' --> '))
        cues.append(dict(start=start, end=end, text=text))
    ass = [line.split(',', 9) for line in (folder / 'captions.ass').read_text().splitlines()
           if line.startswith('Dialogue:')]
    burned = [dict(start=subtitle_seconds(row[1]), end=subtitle_seconds(row[2]), text=row[-1])
              for row in ass if row[3] == 'Sub']
    for cue, actual in zip(joint.cues(measured), burned, strict=True):
        if (cue['text'] != actual['text']
                or any(abs(cue[key] - actual[key]) > .005001 for key in ('start', 'end'))):
            raise ValueError('Burned subtitle clock differs from measured Neil PCM')
    return cues


def checked_media(out, target, picture, blueprint, measured, master):
    plan = blueprint['timeline']
    action_views = {}
    for cut in plan['shots']:
        if not cut.get('action_views'):
            continue
        start, end = cut['start_frame'], cut['end_frame']
        clip = out / f"source-{cut['id']}.mp4"
        ffmpeg('-i', picture, '-vf', f'trim=start_frame={start}:end_frame={end},setpts=PTS-STARTPTS',
               '-an', '-c:v', 'libx264', '-crf', '17', '-pix_fmt', 'yuv420p', clip)
        action_views[cut['id']] = joint.binding(clip)
    report = inspect(joint.binding(target), plan, measured=measured, playback=master, mix=True,
                     blueprint=blueprint, required_ids=[s['id'] for s in plan['shots']],
                     rendered_cues=checked_captions(out.parent, measured), sources=action_views)
    report['findings'].extend(pixel_findings(target, picture, 0, plan['frame_count'], 0, 'full-film'))
    levels = compose.narration.measure_loudness(target, compose.narration.load_profile(PROFILE))
    check_levels(levels, compose.narration.load_profile(PROFILE), 'Encoded Neil mix')
    report['checks']['aac_loudness'] = levels
    report['caption_files'] = [joint.binding(out.parent / name) for name in ('captions.ass', '门把手回正.srt')]
    report['caption_precision'] = 'ASS timestamps rounded to the nearest centisecond from measured PCM.'
    report['action_sources'] = action_views
    report['technical_status'] = status(report['findings'])
    writejson(out / 'technical-review.json', report)


def render_edit(folder, quality, story):
    task = read(folder / 'task.json')
    plan = read(folder / 'joint-timeline.json')
    measured_ref = joint.binding(folder / 'measured-neil.json')
    measured = joint.receipt(plan, measured_ref)
    master = audio_mix(folder, plan)
    captions(folder, plan, measured)
    out = folder / quality
    picture = out / 'picture.mp4'
    target = out / ('门把手回正.mp4' if quality == 'final' else '门把手回正-完整动态预演.mp4')
    joint.validate_rendered_film(picture, plan, require_audio=False)
    ffmpeg('-i', picture, '-i', master, '-vf', 'subtitles=captions.ass',
           '-c:v', 'libx264', '-preset', 'fast', '-crf', '17',
           '-c:a', 'aac', '-b:a', '320k', '-pix_fmt', 'yuv420p', '-movflags', '+faststart',
           target, cwd=folder)
    ffmpeg('-xerror', '-i', target, '-f', 'null', '-')
    shots = [dict(shot_id=cut['id'], time_range=[cut[key]/30 for key in ('start_frame', 'end_frame')],
                  knowledge_ids=[cut['id']], render_engine='blender',
                  mechanical_role='core' if cut.get('action_views') else 'support') for cut in plan['shots']]
    moments = {cut['id']: dict(shot_id=cut['id'], knowledge_id=cut['id'], observable=cut['discovery'],
                             start_frame=window['start_frame'], end_frame=window['end_frame'],
                             visual_evidence=f"{out / 'source-clock.json'} · {cut['id']}")
               for cut, window in zip(story['shots'], plan['shots'], strict=True)}
    blueprint = dict(formal_duration_version=task['formal_duration_version'],
                     production_contract_version=task['production_contract_version'],
                     production_method=task['production_method'], story_development_version=2,
                     mechanical_object=task['mechanical_object'], core_question=task['core_question'],
                     growth_design=read(folder / 'story-treatment.json')['growth_design'],
                     narrative=dict(question=task['core_question'], moments=moments), shots=shots,
                     title=story['title'], timeline=plan, measured_timeline=measured_ref,
                     picture=joint.binding(picture), story=joint.binding(HERE / 'formal-story.json'),
                     core_3d=[dict(scene_id=cut['id'], shot_id=cut['id'],
                                   source=joint.binding(out / 'scene.blend'))
                              for cut in plan['shots'] if cut.get('action_views')],
                     duration_seconds=plan['frame_count'] / 30,
                     output_type='Final Film' if quality == 'final' else 'Full Animatic')
    writejson(out / 'blueprint.json', blueprint)
    checked_media(out, target, picture, blueprint, measured, master)
    print(joint.binding(target), plan['frame_count'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('folder', type=Path)
    parser.add_argument('phase', choices=('measure', 'preview', 'final'))
    args = parser.parse_args()
    folder = args.folder.resolve()
    story = read(HERE / 'formal-story.json')
    if args.phase == 'measure':
        measure(folder, story)
    else:
        render_edit(folder, args.phase, story)


if __name__ == '__main__':
    main()
