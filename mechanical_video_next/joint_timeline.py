"""The Blueprint's joint 30 fps picture/action and 48 kHz speech timeline."""

import json
import math
from fractions import Fraction
from pathlib import Path
import wave

from scripts.common import ROOT, filehash, probe

FIELD = 'timeline_policy_version'
VERSION = 1
FPS = 30
SAMPLE_RATE = 48000
SAMPLES_PER_FRAME = SAMPLE_RATE // FPS
INTEGRITY = 'film_integrity_version'


def integrity(plan):
    value = plan.get(INTEGRITY, 0)
    if type(value) is not int or value not in (0, 1):
        raise ValueError('Unsupported film integrity policy')
    return bool(value)


def enabled(data):
    value = data.get(FIELD, 0)
    if type(value) is not int or value not in (0, VERSION):
        raise ValueError('Unsupported timeline policy')
    return bool(value)


def binding(path):
    return {'path': str(Path(path).resolve()), 'sha256': filehash(path)}


def bound(ref):
    path = ROOT / ref['path']
    if not path.is_file() or filehash(path) != ref['sha256']:
        raise ValueError('Timeline source is missing or changed: ' + str(path))
    return path


def frame_number(seconds):
    if isinstance(seconds, bool) or not isinstance(seconds, (int, float)) or not math.isfinite(seconds):
        raise ValueError('Invalid picture time')
    frames = round(seconds * FPS)
    if frames < 0 or abs(frames - seconds * FPS) > 1e-6:
        raise ValueError('Picture times must be on the 30 fps grid')
    return frames


def interval(row, limit, end='end_frame'):
    start, stop = row.get('start_frame'), row.get(end)
    if type(start) is not int or type(stop) is not int or not 0 <= start < stop <= limit:
        raise ValueError('Invalid frame interval: ' + str(row.get('id')))
    return start, stop


def validate(plan, blueprint_shots=None):
    locked = integrity(plan)
    count = plan.get('frame_count')
    if type(count) is not int or count < 1:
        raise ValueError('Joint timeline needs positive output frames')
    shots, speech, actions = (plan.get(field) for field in ('shots', 'narration', 'actions'))
    if not isinstance(shots, list) or not shots or not isinstance(speech, list) or not isinstance(actions, list):
        raise ValueError('Joint timeline needs ordered picture, narration and action tracks')
    for rows in (shots, speech, actions):
        ids = [row.get('id') for row in rows]
        if any(not isinstance(key, str) or not key.strip() for key in ids) or len(set(ids)) != len(ids):
            raise ValueError('Timeline rows require unique IDs within their track')
    cursor = 0
    for shot in shots:
        start, stop = interval(shot, count)
        offset = shot.get('source_start_frame', 0)
        if start != cursor or type(offset) is not int or offset < 0:
            raise ValueError('Picture track needs contiguous output ranges and valid source offsets')
        cursor = stop
    if cursor != count:
        raise ValueError('Picture track must cover the entire film')
    if blueprint_shots is not None:
        expected = [(s['shot_id'], *(frame_number(t) for t in s['time_range'])) for s in blueprint_shots]
        actual = [(s['id'], s['start_frame'], s['end_frame']) for s in shots]
        if expected != actual:
            raise ValueError('Joint timeline cuts differ from Blueprint')
    cursor = 0
    for segment in speech:
        start, deadline = interval(segment, count, 'deadline_frame')
        words = segment.get('text')
        knowledge = segment.get('knowledge_ids')
        if (start < cursor or not isinstance(words, str) or not words.strip()
                or not isinstance(knowledge, list) or not knowledge
                or not all(isinstance(key, str) and key.strip() for key in knowledge)):
            raise ValueError('Speech slots need ordered non-overlapping windows, text and knowledge')
        cursor = deadline
    action_intervals = {}
    for action in actions:
        start, stop = interval(action, count)
        source_start = action.get('source_start_frame')
        if (type(source_start) is not int or source_start < 0
                or not all(action.get(key) for key in ('start_state', 'end_state', 'curve', 'constraints'))):
            raise ValueError('Action needs its own source clock, endpoint states, curve and constraints')
        bound(action['source'])
        if locked:
            if (type(action.get('source_end_frame')) is not int
                    or action['source_end_frame'] - source_start != stop - start):
                raise ValueError('Mechanical event is compressed, extended or truncated: ' + action['id'])
            for field in ('input', 'direction', 'transmission', 'intermediate_state', 'contact', 'knowledge_id'):
                if not isinstance(action.get(field), str) or not action[field].strip():
                    raise ValueError(f'Mechanical event {action["id"]} requires {field}')
            from .science_shots import source_binding
            source_binding(action.get('evidence'))
            if action_intervals and start < next(reversed(action_intervals.values()))[0]:
                raise ValueError('Mechanical events must be in output order')
        action_intervals[action['id']] = (start, stop, source_start)
    for shot in shots:
        start, stop = interval(shot, count)
        expected = {key: source_frame + max(0, start - left)
                    for key, (left, right, source_frame) in action_intervals.items()
                    if start < right and stop > left}
        origin = shot.get('source_clock_origin', 0)
        if (type(origin) is not int or shot.get('action_views', {}) != expected
                or any(frame != origin + shot.get('source_start_frame', 0)
                       + max(0, action_intervals[key][0] - start) for key, frame in expected.items())):
            raise ValueError('Action clock discontinuity at shot ' + shot['id'])
        if (not any(s['start_frame'] < stop and s['deadline_frame'] > start for s in speech)
                and not (isinstance(shot.get('silence_reason'), str) and shot['silence_reason'].strip())):
            raise ValueError('A silent shot requires a concrete visual purpose: ' + shot['id'])
    return plan


def validate_source_clip(path, source_start, frame_count):
    """Source windows use output frames, including for lower-rate animatics."""
    video = next(stream for stream in probe(path)['streams'] if stream['codec_type'] == 'video')
    try:
        rate = Fraction(video['avg_frame_rate'])
        count = int(video['nb_frames'])
    except (ValueError, ZeroDivisionError, KeyError):
        rate, count = 0, 0
    duration = video.get('duration')
    track = Fraction(duration) if duration not in (None, 'N/A') else 0
    if rate > 0 and count > 0:
        samples = count / rate
        track = min(track, samples) if track > 0 else samples
    # ffprobe publishes decimal seconds to six places and may round down.
    if (type(source_start) is not int or type(frame_count) is not int or source_start < 0
            or frame_count < 1 or track <= 0 or Fraction(source_start + frame_count, FPS) > track + Fraction(1, 1_000_000)):
        raise ValueError(f'Picture source does not cover the selected output interval: {path}')


def pcm_frames(path):
    with wave.open(str(path), 'rb') as audio:
        if (audio.getframerate(), audio.getnchannels(), audio.getsampwidth()) != (SAMPLE_RATE, 1, 2):
            raise ValueError('Expected original mono 48 kHz 16-bit Neil PCM')
        return audio.getnframes()


def measure(plan, sentence, output):
    """Place complete measured utterances. Overruns leave the visual plan unchanged."""
    validate(plan)
    from .text_layout import load_style, measure_text
    style = load_style()
    box = style['subtitle']['safe_box']
    measured = []
    for row in plan['narration']:
        subtitle = row.get('subtitle', row['text'])
        if (not isinstance(subtitle, str) or not subtitle.strip() or '\n' in subtitle
                or measure_text(subtitle, style=style)['width'] > box[2] - box[0]):
            raise ValueError('Rewrite or split the subtitle with measured timing: ' + row['id'])
        wav, cache = sentence(row['text'])
        start = row['start_frame'] * SAMPLES_PER_FRAME
        stop = start + pcm_frames(wav)
        if stop > row['deadline_frame'] * SAMPLES_PER_FRAME:
            need = (stop - start) / SAMPLE_RATE
            budget = (row['deadline_frame'] - row['start_frame']) / FPS
            raise ValueError(f'{row["id"]}: measured speech takes {need:.3f}s in a {budget:.3f}s slot. '
                             'Revise the dialogue or explicitly re-edit the joint timeline.')
        measured.append(dict(id=row['id'], text=row['text'], subtitle=subtitle, start_sample=start,
                             end_sample=stop, audio=binding(wav), cache=cache))
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(output.with_suffix('.tmp.wav')), 'wb') as master:
        master.setparams((1, 2, SAMPLE_RATE, 0, 'NONE', 'not compressed'))
        cursor = 0
        for row in measured:
            master.writeframesraw(bytes(2 * (row['start_sample'] - cursor)))
            with wave.open(str(bound(row['audio'])), 'rb') as clip:
                master.writeframesraw(clip.readframes(clip.getnframes()))
            cursor = row['end_sample']
        master.writeframesraw(bytes(2 * (plan['frame_count'] * SAMPLES_PER_FRAME - cursor)))
    output.with_suffix('.tmp.wav').replace(output)
    return dict(schema_version=2, timeline_policy_version=VERSION, voice='Neil', fps=FPS,
                frame_count=plan['frame_count'], seconds=plan['frame_count'] / FPS,
                shots=plan['shots'], plan=plan, speech=measured, narration_audio=binding(output),
                listening='UNKNOWN')


def receipt(plan, ref):
    path = bound(ref)
    data = json.loads(path.read_text())
    source = bound(data['narration_audio'])
    if (data.get('plan') != plan or data.get('voice') != 'Neil'
            or len(data['speech']) != len(plan['narration'])
            or pcm_frames(source) != plan['frame_count'] * SAMPLES_PER_FRAME):
        raise ValueError('Measured speech timeline differs from the approved joint plan')
    cursor = 0
    with wave.open(str(source), 'rb') as master:
        for spec, clip in zip(plan['narration'], data['speech'], strict=True):
            start = spec['start_frame'] * SAMPLES_PER_FRAME
            wav = bound(clip['audio'])
            length = pcm_frames(wav)
            stop = start + length
            if (clip['id'] != spec['id'] or clip['text'] != spec['text']
                    or clip['subtitle'] != spec.get('subtitle', spec['text'])
                    or clip['start_sample'] != start or clip['end_sample'] != stop
                    or stop > spec['deadline_frame'] * SAMPLES_PER_FRAME):
                raise ValueError('Measured speech interval differs from the plan')
            with wave.open(str(wav), 'rb') as original:
                if any(master.readframes(start - cursor)) or master.readframes(length) != original.readframes(length):
                    raise ValueError('Continuous master differs from the measured Neil clips')
            cursor = stop
        if any(master.readframes(master.getnframes() - cursor)):
            raise ValueError('Unexpected samples after the last utterance')
    return data


def cues(data):
    return [{'start': row['start_sample'] / SAMPLE_RATE, 'end': row['end_sample'] / SAMPLE_RATE,
             'text': row['subtitle']} for row in data['speech']]


def overlapping_texts(plan, shot_id):
    shot = next(s for s in plan['shots'] if s['id'] == shot_id)
    return [row['text'] for row in plan['narration']
            if row['start_frame'] < shot['end_frame'] and row['deadline_frame'] > shot['start_frame']]


def shot_narration(document, shot):
    if not enabled(document):
        return shot.get('narration', [])
    return overlapping_texts(document['timeline'], shot['shot_id'])
