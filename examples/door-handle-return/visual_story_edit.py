"""Build the measured Neil workprint, silent review, and dynamic A/B exports."""

import argparse
from array import array
import json
from pathlib import Path
import wave

from cinematic_edit import TASK, compose, ffmpeg, write_wav
from mechanical_video_next import joint_timeline as joint
from mechanical_video_next.audio_acceptance import verify_mix
from scripts.common import writejson

HERE = Path(__file__).resolve().parent
BASELINE = TASK / 'cinematic/animatic-revised'
WORKPRINT = TASK / 'visual-story/final-preview'
PICTURE_CODEC = ('-c:v', 'libx264', '-crf', 17, '-preset', 'fast',
                 '-pix_fmt', 'yuv420p', '-movflags', '+faststart')

# Half-open speech slots on the edited 30 fps output clock.
SPEECH = (
    ('question', 2, 84, '门把手为什么松手就回到水平？', 'handle-return'),
    ('drive', 162, 249, '按下把手，方轴和拨片一起转。', 'square-spindle'),
    ('compression', 249, 345, '金色拨片压一端，蓝色拨片挡在另一端。', 'one-end-load'),
    ('release', 472, 575, '一松手，回位弹簧把把手带回水平。', 'spring-return'),
)


def picture_timeline(edit, clock, scene):
    source_blend = joint.bound(clock['source'])
    source_rows = json.loads((BASELINE / 'action-bound-blueprint.json').read_text())['timeline']['actions']
    event_ids = {'installed-press-and-return', 'exposed-press-and-return'}
    source_events = [event for event in source_rows if event['id'] in event_ids]
    if {event['id'] for event in source_events} != event_ids:
        raise ValueError('Baseline is missing one of the two source actions')
    actions, shots = [], []
    cursor = 0
    for shot in edit['shots']:
        start, end = shot['source']
        row = dict(id=shot['id'], start_frame=cursor, end_frame=cursor + end - start,
                   source_start_frame=start, action_views={})
        for event in source_events:
            left, right = event['source_start_frame'], event['source_end_frame']
            if start <= left < end:
                offset = cursor - start
                actions.append(dict(event, source=joint.binding(source_blend),
                                    start_frame=left + offset, end_frame=right + offset))
            if start < right and end > left:
                row['action_views'][event['id']] = max(start, left)
        if shot['id'] == 'cover':
            row['silence_reason'] = 'Watch the fixed exterior uncover the spring channel and shaft.'
        if shot['id'] in edit['contact_shots']:
            row['silence_reason'] = 'Inspect the compressed wire at the held position.'
        if shot['id'] == 'answer':
            row['silence_reason'] = 'Watch the reset lever stay level as the cover view returns.'
        shots.append(row)
        cursor = row['end_frame']
    speech = [dict(id=name, start_frame=start, deadline_frame=end, text=text, knowledge_ids=[fact])
              for name, start, end, text, fact in SPEECH]
    plan = dict(film_integrity_version=1, frame_count=cursor,
                shots=shots, narration=speech, actions=actions)
    native = [index + 1 for shot in edit['shots'] for index in range(*shot['source'])]
    if (clock['scene_sha256'] != scene['sha256'] or clock['source_frames'] != native
            or clock['camera_config_sha256'] != joint.binding(HERE / 'visual_story.json')['sha256']):
        raise ValueError('Edit, scene and native render clock differ')
    return joint.validate(plan)


def output_frame(plan, source):
    for shot in plan['shots']:
        offset = source - shot['source_start_frame']
        if 0 <= offset < shot['end_frame'] - shot['start_frame']:
            return shot['start_frame'] + offset
    raise ValueError(f'Editorial frame missing for source index {source}')


def sound(out, plan):
    profile = compose.narration.load_profile(compose.ROOT / 'config/narration-neil.json')
    if profile['voice'] != 'Neil' or profile['target_speed'] != 1:
        raise ValueError('Workprint requires Neil PCM at original speed')
    voice = out / 'neil.wav'
    measured = joint.measure(plan, lambda line: compose.narration.sentence(line, profile), voice)
    receipt = out / 'measured-neil.json'
    writejson(receipt, measured)
    joint.receipt(plan, joint.binding(receipt))

    # Keep a single quiet home-stop sound at the end of the exposed cycle.
    foley_base = BASELINE / 'mechanical-foley.wav'
    old_recipe = BASELINE / 'foley-source.json'
    total = plan['frame_count'] * joint.SAMPLES_PER_FRAME
    effects = array('h', [0]) * total
    cues = []
    with wave.open(str(foley_base), 'rb') as source:
        original, length, frame = 29.39, .11, output_frame(plan, 882)
        start = round(original * joint.SAMPLE_RATE)
        source.setpos(start)
        clip = array('h')
        clip.frombytes(source.readframes(round(length * joint.SAMPLE_RATE)))
        index = frame * joint.SAMPLES_PER_FRAME
        effects[index:index + len(clip)] = clip
        cues.append(dict(id='handle-home', output_frame=frame, original_start_sample=start,
                         count=len(clip)))
    stem = out / 'foley.wav'
    write_wav(stem, effects)
    proof = out / 'foley-source.json'
    writejson(proof, dict(source=joint.binding(foley_base), original_recipe=joint.binding(old_recipe),
                         cues=cues, license='CC0-1.0', scope='Illustrative stop sounds at return to horizontal.'))
    with wave.open(str(voice), 'rb') as source:
        speech = array('h')
        speech.frombytes(source.readframes(total))
    master = out / 'neil-and-foley.wav'
    write_wav(master, array('h', (a + b for a, b in zip(speech, effects, strict=True))))
    mix = {'master': joint.binding(master), 'stems': [{
        'kind': 'sfx', 'source': joint.binding(stem), 'start_sample': 0,
        'end_sample': total, 'source_start_sample': 0, 'gain_db': 0,
        'source_type': 'GENERATED', 'license_status': 'VERIFIED', 'usage_restrictions': [],
        'credit': '君哥拆机器 · 原创拟音',
        'license': {'name': 'CC0-1.0', 'holder': '君哥拆机器', 'status': 'VERIFIED',
                    'editing_and_distribution': True, 'commercial_use': True,
                    'proof': {**joint.binding(proof), 'position': 'Original recipe and reused intervals'}},
    }]}
    verify_mix(mix, voice, total)
    writejson(out / 'audio-mix.json', mix)
    return master, measured


def native_picture(out, plan, edit):
    start, end = edit['seat_fill']['source']
    first, last = (output_frame(plan, frame) for frame in (start, end))
    folder = out / f'source-{start + 1:04d}-{end:04d}'
    patch = folder / 'picture.mp4'
    receipt = json.loads((folder / 'chunk-result.json').read_text()) if patch.exists() else None
    native = out / 'native-picture.mp4'
    if receipt:
        baseline = joint.bound(json.loads((WORKPRINT / 'technical.json').read_text())['native_picture'])
        clock = json.loads((out / 'source-clock.json').read_text())
        old_clock = json.loads((WORKPRINT / 'source-clock.json').read_text())
        if old_clock['source_frames'] != clock['source_frames']:
            raise ValueError('Workprint and revision have different source clocks')
        if (receipt['signature']['selected'] != list(range(start + 1, end + 1))
                or joint.binding(patch)['sha256'] != receipt['output_sha256']):
            raise ValueError('Rendered patch differs from its source frame receipt')
        joint.validate_rendered_film(patch, {'frame_count': last - first}, require_audio=False)
        ffmpeg('-i', baseline, '-i', patch, '-filter_complex',
               '[0:v]split=2[before][after];'
               f'[before]trim=end_frame={first},setpts=PTS-STARTPTS[a];'
               '[1:v]setpts=PTS-STARTPTS[b];'
               f'[after]trim=start_frame={last},setpts=PTS-STARTPTS[c];'
               '[a][b][c]concat=n=3:v=1:a=0[v]', '-map', '[v]', *PICTURE_CODEC, native)
        reuse = dict(baseline=joint.binding(baseline), replacement=joint.binding(patch),
                     replacement_frames=[first, last], render_receipt=joint.binding(folder / 'chunk-result.json'))
    else:
        paths = sorted(out.glob('source-*/picture.mp4'))
        if len(paths) != 2:
            raise ValueError('Expected both complete source ranges or the exact repaired span')
        playlist = out / 'source-pictures.ffconcat'
        playlist.write_text('ffconcat version 1.0\n' +
                            ''.join(f"file '{path.parent.name}/picture.mp4'\n" for path in paths))
        ffmpeg('-f', 'concat', '-safe', '1', '-i', playlist, '-c', 'copy', native)
        reuse = None
    joint.validate_rendered_film(native, plan, require_audio=False)
    return native, reuse


def render_edit(out, plan, scene, edit, master, measured):
    native, reuse = native_picture(out, plan, edit)
    contact = [shot for shot in plan['shots'] if shot['id'] in edit['contact_shots']]
    captions = compose.HEADER.replace('Heiti SC,25', 'Heiti SC,23')
    captions += compose.cue(3.0, 5.1, 'Label', '剖视示意')
    captions += compose.cue(output_frame(plan, 900) / joint.FPS, plan['frame_count'] / joint.FPS,
                            'Label', '剖视结束')
    for row in measured['speech']:
        captions += compose.cue(row['start_sample'] / joint.SAMPLE_RATE,
                                row['end_sample'] / joint.SAMPLE_RATE, 'Sub', row['subtitle'])
    caption_path = out / 'captions.ass'
    caption_path.write_text(captions)
    film = out / 'door-handle-visual-story.mp4'
    ffmpeg('-i', native, '-i', master, '-vf', 'subtitles=captions.ass',
           '-map', '0:v:0', '-map', '1:a:0', *PICTURE_CODEC,
           '-c:a', 'aac', '-b:a', '160k', film, cwd=out)
    silent_start = 0
    silent = out / 'mechanism-silent-no-subtitles.mp4'
    ffmpeg('-i', native, '-an', '-c:v', 'copy', '-movflags', '+faststart', silent)
    joint.validate_rendered_film(silent, {'frame_count': plan['frame_count'] - silent_start}, require_audio=False)

    return film, native, dict(
        film=joint.binding(film), native_picture=joint.binding(native), silent=joint.binding(silent),
        scene=scene, captions=joint.binding(caption_path), source_clock=joint.binding(out / 'source-clock.json'),
        contact_frames={shot['id']: [shot['start_frame'], shot['end_frame']] for shot in contact},
        native_reuse=reuse,
        silent_start_frame=silent_start,
        picture=joint.validate_rendered_film(film, plan),
        audio=joint.validate_rendered_audio(film, plan, measured, playback=master, mix=True),
    )


def ab_exports(out, film, native, plan):
    baseline = json.loads((WORKPRINT / 'technical.json').read_text())
    old = joint.bound(baseline['film'])
    old_native = joint.bound(baseline['native_picture'])
    full = out / 'ab-full-old-then-new.mp4'
    boundary = int(baseline['picture']['nb_frames'])
    frame_count = boundary + plan['frame_count']
    ffmpeg('-i', old, '-i', film, '-filter_complex',
           '[0:v]scale=768:432,setsar=1,'
           "drawtext=text='A':x=w-tw-24:y=22:fontsize=24:fontcolor=white:box=1:boxcolor=0x182229[v0];"
           '[1:v]setsar=1,'
           "drawtext=text='B':x=w-tw-24:y=22:fontsize=24:fontcolor=white:box=1:boxcolor=0x182229[v1];"
           '[v0][0:a][v1][1:a]concat=n=2:v=1:a=1[v][a]',
           '-map', '[v]', '-map', '[a]', *PICTURE_CODEC, '-c:a', 'aac', '-b:a', '160k', full)
    joint.validate_rendered_film(full, {'frame_count': frame_count})
    aligned = out / 'ab-same-motion.mp4'
    first, last = 469, 888
    start = output_frame(plan, first)
    count = last - first
    ffmpeg('-i', old, '-i', native, '-filter_complex',
           f'[0:v]trim=start_frame={start}:end_frame={start+count},setpts=PTS-STARTPTS,setsar=1[a];'
           f'[1:v]trim=start_frame={start}:end_frame={start+count},setpts=PTS-STARTPTS,setsar=1[b];'
           '[a][b]hstack=inputs=2[v]',
           '-map', '[v]', '-an', *PICTURE_CODEC, aligned)
    joint.validate_rendered_film(aligned, {'frame_count': count}, require_audio=False)
    same_camera = out / 'ab-same-camera.mp4'
    first_same, last_same = (output_frame(plan, source) for source in (540, 652))
    same_range = f'trim=start_frame={first_same}:end_frame={last_same},setpts=PTS-STARTPTS,setsar=1'
    ffmpeg('-i', old_native, '-i', native, '-filter_complex',
           f'[0:v]{same_range}[a];[1:v]{same_range}[b];'
           '[a][b]hstack=shortest=1,setpts=N/(30*TB)[v]',
           '-map', '[v]', '-an', *PICTURE_CODEC, '-movie_timescale', '30000', same_camera)
    joint.validate_rendered_film(same_camera, {'frame_count': last_same - first_same}, require_audio=False)
    return dict(baseline=joint.binding(old), baseline_native=joint.binding(old_native),
                full=joint.binding(full), comparison_boundary_frame=boundary,
                aligned=joint.binding(aligned), source_frames=[first, last], new_start_frame=start,
                same_camera=joint.binding(same_camera), same_camera_source_frames=[540, 652])


def record_sources(out, plan, measured, proof):
    writejson(out / 'sources.json', {
        'mechanical_reference': plan['actions'][1]['evidence'],
        'reference_use': 'Patent figures and description informed the locally authored model. '
                         'Patent images and third-party footage are absent from the exports.',
        'authored_model': plan['actions'][1]['source'],
        'scene': proof['scene'],
        'native_picture': proof['native_picture'],
        'native_render_receipts': [joint.binding(path) for path in
                                   sorted(out.glob('source-*/chunk-result.json'))],
        'picture_clock': proof['source_clock'],
        'contact_frames': proof['contact_frames'],
        'native_reuse': proof['native_reuse'],
        'neil': {
            'profile': joint.binding(compose.ROOT / 'config/narration-neil.json'),
            'measured_timeline': joint.binding(out / 'measured-neil.json'),
            'utterances': [row['audio'] for row in measured['speech']],
        },
        'audio_mix': joint.binding(out / 'audio-mix.json'),
        'ab_baseline': proof['ab']['baseline'],
        'ab_baseline_native': proof['ab']['baseline_native'],
        'exports': [proof['film'], proof['silent'], proof['ab']['full'], proof['ab']['aligned'],
                    proof['ab']['same_camera']],
        'programs': [joint.binding(path) for path in (
            HERE / 'visual_story_scene.py', HERE / 'visual_story.json', Path(__file__),
        )],
    })


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('out', type=Path)
    parser.add_argument('--audio-only', action='store_true')
    args = parser.parse_args()
    out = args.out.resolve()
    edit_path = HERE / 'visual_story.json'
    edit = json.loads(edit_path.read_text())
    clock = json.loads((out / 'source-clock.json').read_text())
    scene = joint.binding(out / 'scene.blend')
    plan = picture_timeline(edit, clock, scene)
    master, measured = sound(out, plan)
    writejson(out / 'preview-blueprint.json', {
        'title': edit['title'], 'timeline': plan, 'timeline_policy_version': 1,
        'measured_timeline': joint.binding(out / 'measured-neil.json'),
        'camera_config': joint.binding(edit_path),
        'core_3d': [{'shot_id': shot['id'], 'scene_id': shot['id'], 'source': scene}
                    for shot in edit['shots']],
    })
    if args.audio_only:
        return
    film, native, proof = render_edit(out, plan, scene, edit, master, measured)
    proof['ab'] = ab_exports(out, film, native, plan)
    writejson(out / 'technical.json', proof)
    record_sources(out, plan, measured, proof)


if __name__ == '__main__':
    main()
