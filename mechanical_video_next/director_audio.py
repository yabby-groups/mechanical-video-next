"""Direct music from story beats and mix it on the existing measured picture clock."""
import argparse
import json
import math
from pathlib import Path
import re
from subprocess import SubprocessError
from tempfile import TemporaryDirectory
import wave

from scripts.common import ROOT, check_output, digest, execute, writejson
from . import audio_library, ducking, joint_timeline as joint
from .audio_acceptance import (check_levels, narration_module, process_mix, verify_mix)
from .media_policy import bound, validate_rights

FIELD = 'music_direction_version'
MIX_MODE_FIELD = 'music_mix_mode'
DEFAULT_BGM_FIELD = 'default_bgm'
DEFAULT_BGM = 'junge-theme-v4'
POLICY_FIELDS = (FIELD, MIX_MODE_FIELD, DEFAULT_BGM_FIELD)
DEFAULT_FADE_IN = .4
DEFAULT_FADE_OUT = 1.
VERSION = 1
CACHE = ROOT / 'assets/audio/mixes'
MODES = {
    'curiosity': (['mysterious', 'anticipation'], .30, 88, -31., 'light electronic pulse'),
    'technology': (['focused', 'precise'], .40, 100, -30., 'minimal electronic rhythm'),
    'mechanical_asmr': (['precise', 'intimate'], .18, 74, -39., 'sparse texture under verified mechanical sound'),
    'discovery': (['bright', 'resolved'], .52, 104, -29., 'gentle lift and resolution'),
}
REVEAL = re.compile(r'reveal|discover|payoff|explan|causal|resolution|result|揭晓|揭秘|原理|解开|发现|结果|验证|兑现|因果', re.I)
STRUCTURE = re.compile(r'disassembl|cutaway|section|component|structure|拆解|剖|外壳|零件|内部|结构|部件', re.I)
QUESTION = re.compile(r'hook|question|myster|opening|anomal|疑问|悬念|为什么|开场|反常|异常|谜', re.I)
RATE = joint.SAMPLE_RATE
AAC_ARGS = ['-c:a', 'aac', '-b:a', '192k', '-ar', str(RATE), '-ac', '1']


def enabled(document):
    version = document.get(FIELD, 0)
    if type(version) is not int or version not in (0, VERSION):
        raise ValueError('Unsupported music direction policy')
    return version == VERSION


def mix_mode(document):
    mode = document.get(MIX_MODE_FIELD, ducking.ADAPTIVE_V2)
    if mode not in (ducking.CONSTANT_BED, ducking.ADAPTIVE_V2):
        raise ValueError('Unsupported music mix mode')
    return mode


def policy(document):
    return (document[FIELD], mix_mode(document), default_bgm(document)) if enabled(document) else None


def asset_id(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_-]+', value):
        raise ValueError('Music asset ID must match a catalog filename')
    return value


def default_bgm(document):
    if DEFAULT_BGM_FIELD not in document:
        return None
    if mix_mode(document) != ducking.CONSTANT_BED:
        raise ValueError('A pinned default BGM requires the constant bed mix mode')
    return asset_id(document[DEFAULT_BGM_FIELD])


def story_intent(treatment, *, bgm=None):
    """Plan from the authored Treatment before any audio or rendering is needed."""
    rows = []
    for scene in treatment.get('scenes', []):
        basis = ' '.join(str(scene.get(key, '')) for key in ('story_purpose', 'visible_change', 'causal_link'))
        mode = scene.get('music_mode') or ('constant_bed' if bgm else
                'curiosity' if QUESTION.search(basis) else 'discovery' if REVEAL.search(basis)
                else 'technology' if STRUCTURE.search(basis) else
                'mechanical_asmr' if scene.get('mechanical_role') == 'core' else 'technology')
        if mode not in {*MODES, 'silence'} and not (bgm and mode == 'constant_bed'):
            raise ValueError('Unknown Treatment music mode')
        rows.append({'scene_id': scene['id'], 'mode': mode, 'reason': basis.strip()})
    return rows


def sound_stems(plan, events, *, mechanical=False):
    """Resolve frame-local triggers to the existing sample-based mix schema."""
    if not isinstance(events, list):
        raise ValueError('Sound events must be a list')
    action_index = {item['id']: item for item in plan['actions']}
    cuts = {item['id']: item for item in plan['shots']}
    stems = []
    for event in events:
        if not isinstance(event, dict):
            raise ValueError('Sound event must be an object')
        anchor = ('action_id' in event, 'shot_id' in event)
        if anchor == (True, False):
            row = action_index.get(event['action_id'])
        elif anchor == (False, True) and not mechanical:
            row = cuts.get(event['shot_id'])
        else:
            row = None
        offset, duration, lead = (event.get('offset_frames', 0), event.get('duration_frames'),
                                  event.get('lead_frames', 0))
        gain = event.get('gain_db')
        source_offset = event.get('source_start_sample', 0)
        if (not row or not all(type(value) is int and value >= 0
                               for value in (offset, duration, lead, source_offset)) or duration == 0
                or type(gain) not in (int, float) or not math.isfinite(gain) or not -80 <= gain <= 0
                or not isinstance(event.get('purpose'), str) or not event['purpose'].strip()):
            raise ValueError('Sound event needs one valid anchor, bounded timing, attenuation and purpose')
        trigger = row['start_frame'] + offset
        start, end = trigger - lead, trigger - lead + duration
        if not 0 <= start <= trigger < row['end_frame'] or end > plan['frame_count']:
            raise ValueError('Sound event is outside its trigger or film')
        if mechanical:
            evidence = event.get('trigger_evidence', {})
            bound(evidence)
            if lead or evidence.get('frame') != trigger or not evidence.get('position'):
                raise ValueError('Mechanical SFX requires verified contact timing on the exact action frame')
        validate_rights(event)
        left, right = start * joint.SAMPLES_PER_FRAME, end * joint.SAMPLES_PER_FRAME
        if source_offset + right - left > joint.pcm_frames(bound(event['source'])):
            raise ValueError('Sound event exceeds its bound PCM source')
        stems.append(dict(event, kind='sfx', start_sample=left, end_sample=right,
                          source_start_sample=source_offset))
    return stems


def plan_direction(document, *, ducking_version=ducking.VERSION):
    """Score the approved story and keep an uninterrupted action under one cue."""
    plan = joint.validate(document['timeline'])
    authored = document.get('music_direction', {})
    if not isinstance(authored, dict):
        raise ValueError('Music direction overrides must be an object')
    status = authored.get('mode', 'automatic')
    if status not in ('automatic', 'silence'):
        raise ValueError('Music direction mode must be automatic or silence')
    result = dict(schema_version=VERSION, topic=document.get('original_topic', document.get('title', '')),
                  question=document.get('core_question'), frame_count=plan['frame_count'], fps=joint.FPS,
                  mode=status, segments=[])
    mode_policy = mix_mode(document)
    constant = mode_policy == ducking.CONSTANT_BED
    if constant:
        result[MIX_MODE_FIELD] = mode_policy
    elif ducking_version == ducking.VERSION:
        result['ducking'] = dict(ducking.DEFAULT)
    elif ducking_version != 1:
        raise ValueError('Unsupported music ducking version')
    default = default_bgm(document)
    if default:
        result[DEFAULT_BGM_FIELD] = default
    if status == 'silence':
        if not isinstance(authored.get('reason'), str) or not authored['reason'].strip():
            raise ValueError('Intentional silence requires a concrete story reason')
        return dict(result, reason=authored['reason'])
    notes = authored.get('shots', {})
    ids = {cut['id'] for cut in plan['shots']}
    if not isinstance(notes, dict) or not notes.keys() <= ids:
        raise ValueError('Music overrides must identify existing shot IDs')
    if default:
        return plan_fixed_track(result, plan, authored, notes)
    shots = {row['shot_id']: row for row in document.get('shots', [])}
    moments = document.get('narrative', {}).get('moments', {})
    choices = []
    for cut in plan['shots']:
        sid = cut['id']
        shot = shots.get(sid, {})
        beat_ids = [key for key, value in moments.items() if value['shot_id'] == sid]
        cue_basis = ' '.join(str(shot.get(key, '')) for key in ('knowledge_goal', 'mechanical_action'))
        cue_basis += ' ' + ' '.join(str(shot.get('direction', {}).get(key, ''))
                                    for key in ('why_visual', 'sound_intent'))
        action_ids = list(cut.get('action_views', {}))
        basis = ' '.join([sid, *beat_ids, cue_basis, *(str(moments[key].get('observable', '')) for key in beat_ids)])
        override = notes.get(sid, {})
        if not isinstance(override, dict):
            raise ValueError('Music shot override must be an object')
        mode = override.get('mode')
        suggested = override.get('suggested_assets', [])
        adjustment = override.get('gain_adjustment_db', 0)
        if override and (mode not in {*MODES, 'silence'} or not isinstance(override.get('reason'), str)
                         or not override['reason'].strip()
                         or not isinstance(suggested, list) or any(not isinstance(key, str) for key in suggested)
                         or type(adjustment) not in (int, float) or not -12 <= adjustment <= 3):
            raise ValueError('Music override needs a valid mode, reason and bounded gain')
        if not mode:
            mode = ('discovery' if REVEAL.search(' '.join(beat_ids)) else 'curiosity' if QUESTION.search(basis)
                    else 'mechanical_asmr' if action_ids else 'technology' if STRUCTURE.search(basis)
                    else 'discovery' if REVEAL.search(basis) else 'technology')
        choices.append(dict(start_frame=cut['start_frame'], end_frame=cut['end_frame'], mode=mode,
                            shot_ids=[sid], story_node_ids=beat_ids, action_ids=action_ids,
                            reason=override.get('reason') or basis.strip() or f'Carry the explanation through {sid}',
                            suggested_assets=suggested, gain_adjustment_db=adjustment))
    if constant:
        durations = {}
        for choice in choices:
            if choice['shot_ids'][0] not in notes:
                mode = choice['mode']
                durations[mode] = durations.get(mode, 0) + choice['end_frame'] - choice['start_frame']
        if durations:
            bed_mode = max(durations, key=durations.get)
            for choice in choices:
                if choice['shot_ids'][0] not in notes:
                    choice.update(mode=bed_mode, reason='Continuous score for this story')
    for cue in choices:
        previous = result['segments'][-1] if result['segments'] else None
        shared_action = previous and set(previous['action_ids']) & set(cue['action_ids'])
        if shared_action and any(row['mode'] == 'silence' for row in (previous, cue)) and previous['mode'] != cue['mode']:
            raise ValueError('Design silence across the entire continuous mechanical action')
        if (shared_action and not constant) or (previous and all(previous[key] == cue[key]
                                               for key in ('mode', 'suggested_assets', 'gain_adjustment_db'))):
            previous['end_frame'] = cue['end_frame']
            for key in ('shot_ids', 'story_node_ids', 'action_ids'):
                previous[key] = list(dict.fromkeys(previous[key] + cue[key]))
            previous['reason'] += ' / ' + cue['reason']
        else:
            result['segments'].append(cue)
    for index, cue in enumerate(result['segments'], 1):
        mode = cue['mode']
        cue['id'] = f'music-{index:02d}'
        cue['time_range'] = [cue['start_frame'] / joint.FPS, cue['end_frame'] / joint.FPS]
        if mode != 'silence':
            mood, energy, bpm, target, style_description = MODES[mode]
            target += cue['gain_adjustment_db']
            adaptive = ducking_version == ducking.VERSION or constant
            if adaptive:
                target += 7 if mode == 'mechanical_asmr' else 5
            cue.update(style=[mode], mood=mood, energy=energy, bpm=bpm, rhythm=style_description,
                       target_lufs=target, fade_in_seconds=.35,
                       fade_out_seconds=.85 if cue['end_frame'] == plan['frame_count'] else .35,
                       speech_duck_db=0 if adaptive else max(17, target + 54),
                       action_duck_db=0 if constant else (6 if adaptive else 9))
            if constant:
                cue['constant_bed'] = True
    if constant:
        for outgoing, incoming in zip(result['segments'], result['segments'][1:]):
            if 'target_lufs' not in outgoing or 'target_lufs' not in incoming:
                continue
            frames = min(round(.35 * joint.FPS),
                         (outgoing['end_frame'] - outgoing['start_frame']) // 3,
                         (incoming['end_frame'] - incoming['start_frame']) // 3)
            if frames:
                outgoing['crossfade_out_frames'] = incoming['crossfade_in_frames'] = frames
    if all(row['mode'] == 'silence' for row in result['segments']):
        raise ValueError('Use whole-film intentional silence with an explicit reason')
    return result


def plan_fixed_track(result, plan, authored, notes):
    selected = asset_id(authored.get('asset_id', result[DEFAULT_BGM_FIELD]))
    adjustment = authored.get('gain_adjustment_db', 0.)
    if type(adjustment) not in (int, float) or not -12 <= adjustment <= 3:
        raise ValueError('Fixed-track gain adjustment must be between -12 and 3 dB')
    result.update(asset_id=selected, volume_strategy='fixed_gain', preserve_narration=True,
                  preserve_mechanical_sfx=True)
    for shot in plan['shots']:
        sid = shot['id']
        note = notes.get(sid, {})
        if (not isinstance(note, dict) or note and
                (set(note) != {'mode', 'reason'} or note['mode'] != 'silence'
                 or not isinstance(note['reason'], str) or not note['reason'].strip())):
            raise ValueError('Fixed-track shot overrides require silence and a story reason')
        mode = 'silence' if note else ducking.CONSTANT_BED
        previous = result['segments'][-1] if result['segments'] else None
        actions = list(shot.get('action_views', {}))
        if previous and previous['mode'] == mode:
            previous['end_frame'] = shot['end_frame']
            previous['shot_ids'].append(sid)
            previous['action_ids'] = list(dict.fromkeys(previous['action_ids'] + actions))
            if note and note['reason'] not in previous['reason']:
                previous['reason'] += ' / ' + note['reason']
        else:
            if previous and set(previous['action_ids']).intersection(actions):
                raise ValueError('Design silence across the entire continuous mechanical action')
            result['segments'].append(dict(mode=mode, start_frame=shot['start_frame'], end_frame=shot['end_frame'],
                                           shot_ids=[sid], action_ids=actions,
                                           reason=note.get('reason', 'Continuous fixed-gain theme')))
    for index, cue in enumerate(result['segments'], 1):
        cue.update(id=f'music-{index:02d}', time_range=[cue[key] / joint.FPS
                   for key in ('start_frame', 'end_frame')])
        if cue['mode'] != 'silence':
            cue.update(asset_id=selected, constant_bed=True, target_lufs=-28. + adjustment,
                       fade_in_seconds=DEFAULT_FADE_IN, fade_out_seconds=DEFAULT_FADE_OUT,
                       film_samples=plan['frame_count'] * joint.SAMPLES_PER_FRAME)
    if all(row['mode'] == 'silence' for row in result['segments']):
        raise ValueError('Use whole-film intentional silence with an explicit reason')
    return result


def music_envelope(left, right, fade_in, fade_out, holds):
    """Linearly interpolate amplitude, holding ducks across actual speech/effect windows."""
    limit = right - 1
    points = {left, limit, left + fade_in, limit - fade_out}
    rows = []
    for start, stop, db in holds:
        attack, release = max(left, start - round(.12 * RATE)), min(limit, stop + round(.24 * RATE))
        if attack >= release:
            continue
        start = min(release, max(attack, start))
        stop = min(release, max(attack, stop))
        rows.append((attack, start, stop, release, 10 ** (-db / 20)))
        points.update((attack, start, stop, release))
    envelope = []
    for point in sorted(points):
        gain = min(1., (point - left) / fade_in, (limit - point) / fade_out)
        for attack, start, stop, release, low in rows:
            if start <= point <= stop:
                gain = min(gain, low)
            elif attack < point < start:
                gain = min(gain, 1 - (1 - low) * (point - attack) / (start - attack))
            elif stop < point < release:
                gain = min(gain, low + (1 - low) * (point - stop) / (release - stop))
        envelope.append([point, round(gain, 8)])
    return envelope


def measured_lufs(source, profile):
    levels = narration_module().measure_loudness(source, profile)
    lufs = float(levels['input_i'])
    if not math.isfinite(lufs) or lufs <= -65:
        raise ValueError('BGM source is silent or too quiet to calibrate: ' + str(source))
    return lufs


def music_stems(direction, available, measured, effects, profile):
    stems, selections, missing, previous, levels = [], [], [], None, {}
    for cue in direction['segments']:
        if cue['mode'] == 'silence':
            previous = None
            continue
        eligible = list(available)
        while eligible:
            track, scores = audio_library.choose(cue, eligible, previous)
            if track is None:
                break
            sha = track['source']['sha256']
            if sha not in levels:
                try:
                    with audio_library.pcm_path(bound(track['source']), downmix=track.get('pcm_downmix')) as pcm:
                        # Analyze the same downmix used by the mixer, including stereo cancellation.
                        levels[sha] = measured_lufs(pcm, profile)
                except (ValueError, OSError, RuntimeError, SubprocessError) as error:
                    levels[sha] = str(error)
            if isinstance(levels[sha], float):
                break
            eligible.remove(track)
            track = None
        else:
            track = None
        if track is None:
            missing.append({'cue_id': cue['id'], 'mode': cue['mode'], 'mood': cue.get('mood', []),
                            **({'asset_id': cue['asset_id']} if 'asset_id' in cue else {}),
                            'shot_ids': cue['shot_ids'], 'reason': 'No rights-verified and audible music fits the cue',
                            'analysis_errors': [value for value in levels.values() if isinstance(value, str)]})
            continue
        previous = track
        selections.append({'cue_id': cue['id'], 'asset_id': track['id'], 'theme': track['theme'],
                           'scores': scores, 'source': track['source'], 'license': track['license'],
                           'catalog_record': track['catalog_record'], 'measured_lufs': levels[sha]})
        if 'loop_analysis' in track:
            selections[-1]['loop_analysis'] = track['loop_analysis']
        if 'pcm_downmix' in track:
            selections[-1]['pcm_downmix'] = track['pcm_downmix']
        stems.extend(lay_music(cue, track, levels[sha], measured['speech'], effects))
    return stems, selections, missing


def lay_music(cue, track, source_lufs, speech, effects):
    gain = min(3., max(-72., cue['target_lufs'] - source_lufs))
    if 'asset_id' in cue:
        yield from lay_fixed_track(cue, track, gain)
        return
    if cue.get('constant_bed'):
        yield from lay_constant_music(cue, track, gain)
        return
    left, right = (cue[key] * joint.SAMPLES_PER_FRAME for key in ('start_frame', 'end_frame'))
    tail = round(.08 * RATE)
    holds = [(row['start_sample'] - tail, row['end_sample'] + tail, cue['speech_duck_db'])
             for row in speech if cue['speech_duck_db']]
    holds.extend((row['start_sample'], row['end_sample'], cue['action_duck_db']) for row in effects)
    offset, stop = (0, track['sample_count']) if track['sample_count'] >= right - left else track['loop_samples']
    loop = min(round(.18 * RATE), (stop - offset) // 4)
    cursor = left
    while cursor < right:
        end = min(right, cursor + stop - offset)
        fade_in = round(cue['fade_in_seconds'] * RATE) if cursor == left else loop
        fade_out = round(cue['fade_out_seconds'] * RATE) if end == right else loop
        fade_limit = (end - cursor - 1) // 2
        if fade_limit < 1:
            raise ValueError('BGM cue has no room for a fade')
        envelope = music_envelope(cursor, end, min(fade_in, fade_limit), min(fade_out, fade_limit), holds)
        yield dict(track, kind='bgm', cue_id=cue['id'], start_sample=cursor, end_sample=end,
                   source_start_sample=offset, envelope=envelope, gain_db=gain)
        cursor = end if end == right else end - loop


def constant_envelope(left, right, fade_in, fade_out, *, cross_in=False, cross_out=False):
    """Sample equal-power overlaps for the existing linear-amplitude interpolator."""
    last = right - 1
    fade_in = min(fade_in, last - left)
    fade_out = min(fade_out, last - left)
    points = {left, left + fade_in, last - fade_out, last}
    step = RATE // 500
    if cross_in:
        points.update(range(left, left + fade_in, step))
    if cross_out:
        points.update(range(last - fade_out, last, step))
    envelope = []
    for point in sorted(points):
        rise = min(1., (point - left) / fade_in) if fade_in else 1.
        fall = min(1., (last - point) / fade_out) if fade_out else 1.
        if cross_in:
            rise = math.sin(rise * math.pi / 2)
        if cross_out:
            fall = math.sin(fall * math.pi / 2)
        envelope.append([point, round(rise * fall, 10)])
    return envelope


def lay_constant_music(cue, track, gain):
    cross_in = cue.get('crossfade_in_frames', 0) * joint.SAMPLES_PER_FRAME
    cross_out = cue.get('crossfade_out_frames', 0) * joint.SAMPLES_PER_FRAME
    left = cue['start_frame'] * joint.SAMPLES_PER_FRAME - cross_in
    right = cue['end_frame'] * joint.SAMPLES_PER_FRAME
    if track['sample_count'] >= right - left:
        offset, stop = 0, track['sample_count']
    elif track['loopable']:
        offset, stop = track['loop_samples']
    else:
        raise ValueError('Selected music is too short for the constant bed and its crossfade')
    loop = min(round(.18 * RATE), (stop - offset) // 4)
    if stop - offset < right - left and loop < 2:
        raise ValueError('Selected music has no room for a loop crossfade')
    cursor = left
    while cursor < right:
        end = min(right, cursor + stop - offset)
        if end < right and cross_out:
            # Reserve the whole authored crossfade if the last loop would be too short.
            end = min(end, right - cross_out)
        first, final = cursor == left, end == right
        incoming = cross_in if first else loop
        outgoing = cross_out if final else loop
        fade_in = incoming - 1 if incoming else round(cue['fade_in_seconds'] * RATE)
        fade_out = outgoing - 1 if outgoing else round(cue['fade_out_seconds'] * RATE)
        length = end - cursor - 1
        if fade_in + fade_out > length:
            if incoming:
                fade_out = max(1, length - fade_in)
            elif outgoing:
                fade_in = max(1, length - fade_out)
            else:
                fade_in, fade_out = min(fade_in, length // 2), min(fade_out, length // 2)
        envelope = constant_envelope(cursor, end, fade_in, fade_out,
                                     cross_in=bool(incoming), cross_out=bool(outgoing))
        yield dict(track, kind='bgm', cue_id=cue['id'], start_sample=cursor, end_sample=end,
                   source_start_sample=offset, envelope=envelope, gain_db=gain)
        cursor = end if final else end - loop


def lay_fixed_track(cue, track, gain):
    left, right = (cue[key] * joint.SAMPLES_PER_FRAME for key in ('start_frame', 'end_frame'))
    film = cue['film_samples']
    count = track['sample_count']
    repeats = film > count
    if repeats and not track['loopable']:
        raise ValueError('Selected music is too short for the full picture clock')
    start, stop = track['loop_samples'] if repeats else (0, count)
    overlap = track.get('loop_crossfade_samples', min(round(.18 * RATE), (stop - start) // 4))
    phase_aligned = 'loop_analysis' in track
    limit = (right - left - 1) // 2
    fade_in = min(limit, round(cue['fade_in_seconds'] * RATE))
    fade_out = min(limit, round(cue['fade_out_seconds'] * RATE))
    cue_envelope = constant_envelope(left, right, fade_in, fade_out)
    cursor, offset = 0, 0
    while cursor < right:
        end = cursor + stop - offset
        incoming = overlap - 1 if cursor else 0
        outgoing = overlap - 1 if end < film else 0
        first, last = max(left, cursor), min(right, end)
        if first < last:
            loop_envelope = constant_envelope(cursor, end, incoming, outgoing,
                                             cross_in=bool(incoming and not phase_aligned),
                                             cross_out=bool(outgoing and not phase_aligned))
            points = {first, last - 1}
            points.update(point for point, _ in cue_envelope + loop_envelope if first <= point < last)
            for start_fade, end_fade in ((cursor, cursor + incoming), (end - outgoing, end)):
                if start_fade < end_fade:
                    points.update(range(max(first, start_fade), min(last, end_fade), RATE // 500))
            envelope = [[point, round(ducking.interpolate(cue_envelope, point)
                                      * ducking.interpolate(loop_envelope, point), 10)] for point in sorted(points)]
            yield dict(track, kind='bgm', cue_id=cue['id'], start_sample=first, end_sample=last,
                       source_start_sample=offset + first - cursor, envelope=envelope, gain_db=gain)
        if end >= film:
            break
        cursor, offset = end - overlap, start


def resolve_music(direction, measured, effects, profile, directory, catalog):
    if direction['mode'] == 'silence':
        return [], [], [], []
    cues = [row for row in direction['segments'] if row['mode'] != 'silence']
    keys = ('id', 'asset_id', 'film_samples') if 'asset_id' in direction else (
        'id', 'style', 'mood', 'energy', 'bpm', 'suggested_assets')
    music_intent = [{key: row[key] for key in keys}
                    | {'frames': row['end_frame'] - row['start_frame']} for row in cues]
    if direction.get(MIX_MODE_FIELD) == ducking.CONSTANT_BED:
        for row, cue in zip(music_intent, cues, strict=True):
            row['crossfade_in_frames'] = cue.get('crossfade_in_frames', 0)
    catalog_snapshot = [joint.binding(path) for path in sorted(Path(catalog).glob('*.json'))]
    selection_path = Path(directory) / 'selections' / (digest([VERSION, music_intent, catalog_snapshot]) + '.json')
    try:
        cached = json.loads(selection_path.read_text())
        selections = cached['selections']
        stems = []
        for cue, decision in zip(cues, selections, strict=True):
            ref = decision['catalog_record']
            raw = json.loads(bound(ref).read_text())
            audio_library.require_active(raw)
            track = audio_library.inspect(raw)
            if (cue['id'] != decision['cue_id'] or track['source'] != decision['source']
                    or ('asset_id' in cue and cue['asset_id'] != track['id'])):
                raise ValueError('Cached music source changed')
            stems.extend(lay_music(cue, dict(track, catalog_record=ref), decision['measured_lufs'],
                                   measured['speech'], effects))
        return stems, selections, [], cached['rejected']
    except (OSError, ValueError, KeyError, TypeError, EOFError, wave.Error, SubprocessError):
        pass
    available, rejected = audio_library.records(catalog, selected=direction.get('asset_id'))
    stems, selections, missing = music_stems(direction, available, measured, effects, profile)
    if not missing:
        from .workflow import lock, write
        with lock(selection_path.with_suffix('.lock'), wait=True):
            write(selection_path, {'selections': selections, 'rejected': rejected})
    return stems, selections, missing, rejected


def calibrate_constant(music, effects, narration, samples, speech, selections, profile, *, diagnostic_bgm=None):
    neil_lufs = measured_lufs(narration, profile) if speech else None
    shift = 0. if neil_lufs is None else neil_lufs - profile['loudness']['integrated_lufs']
    levels = {row['cue_id']: row['measured_lufs'] for row in selections}
    calibrated = [dict(row, gain_db=min(3., max(-72., row['gain_db'] + shift))) for row in music]
    cue_lufs = {row['cue_id']: levels[row['cue_id']] + row['gain_db'] for row in calibrated}
    return ducking.constant_bed(calibrated, effects, narration, samples,
                                neil_lufs=neil_lufs, cue_lufs=cue_lufs, diagnostic_bgm=diagnostic_bgm)


def cache_mix(narration, expected, stems, *, cache=CACHE, check_masking=False, ducking_settings=None,
              constant=False, preserve_levels=False):
    from .workflow import lock, write
    ref = joint.binding(narration)
    recipe = [{key: row[key] for key in ('start_sample', 'end_sample', 'source_start_sample', 'gain_db', 'kind')}
              | {'source': row['source']['sha256'], 'envelope': row.get('envelope')} for row in stems]
    for row, item in zip(stems, recipe, strict=True):
        item.update({key: row[key] for key in ('pcm_downmix', 'loop_analysis') if key in row})
    identity = {'version': VERSION, 'encoder': AAC_ARGS, 'headroom': 1,
                'narration': ref['sha256'], 'stems': recipe, 'samples': expected}
    if ducking_settings:
        identity['ducking'] = ducking_settings
    if constant:
        identity['constant_bed'] = ducking.CONSTANT_SETTINGS
    if preserve_levels:
        identity['preserve_levels'] = True
    key = digest(identity)
    folder = Path(cache) / key
    if joint.pcm_frames(narration) != expected:
        raise ValueError('Director mix requires a complete measured narration master')
    with lock(folder.parent / (key + '.lock'), wait=True):
        folder.mkdir(parents=True, exist_ok=True)
        output = folder / 'mix.wav'
        complete = folder / 'complete.json'
        if complete.is_file():
            try:
                receipt = json.loads(complete.read_text())
                if (receipt['cache_key'] == key
                        and receipt.get(MIX_MODE_FIELD) == (ducking.CONSTANT_BED if constant else None)
                        and (not preserve_levels or receipt['output_gain_db'] == 0)):
                    receipt['stems'] = stems
                    if bool(receipt['master']) != bool(stems or receipt.get('output_gain_db')):
                        raise ValueError('Cached master receipt is incomplete')
                    if receipt['master'] is not None:
                        verify_mix(receipt, narration, expected, check_masking=check_masking)
                    (folder / '.last-used').touch()
                    return (receipt if receipt['master'] else None), True
            except (ValueError, KeyError, TypeError, OSError, EOFError, wave.Error):
                pass
        with TemporaryDirectory(dir=folder) as temp:
            candidate = Path(temp) / 'mix.wav'
            headroom = render_with_headroom(stems, narration, expected, candidate, check_masking=check_masking,
                                            preserve_levels=preserve_levels)
            if stems or headroom:
                candidate.replace(output)
        receipt = {'schema_version': 1, 'master': joint.binding(output) if stems or headroom else None,
                   'stems': stems, 'output_gain_db': headroom, 'cache_key': key}
        if constant:
            receipt[MIX_MODE_FIELD] = ducking.CONSTANT_BED
        write(complete, receipt)
        (folder / '.last-used').touch()
        return (receipt if receipt['master'] else None), False


def render_with_headroom(stems, narration, expected, output, *, check_masking, preserve_levels=False):
    """Measure the actual codec overshoot and record modest uniform bus attenuation."""
    module = narration_module()
    profile = module.effective_profile({'narration_profile': 'config/narration-neil.json'})
    peak_limit = profile['loudness']['true_peak_dbtp']
    gain = 0.
    encoded = output.with_suffix('.m4a')
    for _ in range(3):
        process_mix(stems, narration, expected, destination=output,
                    check_masking=check_masking, output_gain_db=gain)
        execute(['ffmpeg', '-v', 'error', '-y', '-i', str(output), *AAC_ARGS, str(encoded)], check=True)
        try:
            true_peak = float(module.measure_loudness(encoded, profile)['input_tp'])
        except RuntimeError:
            # A deliberately silent film has no integrated loudness to normalize.
            if not stems:
                with wave.open(str(output), 'rb') as wav:
                    if not any(wav.readframes(wav.getnframes())):
                        return gain
            raise
        if true_peak <= peak_limit:
            return gain
        if preserve_levels:
            raise ValueError(f'AAC true peak {true_peak} dBTP exceeds {peak_limit} dBTP at fixed narration/SFX gain')
        gain = round(gain - (true_peak - peak_limit) - .25, 2)
        if gain < -3:
            break
    raise ValueError('AAC true peak cannot be brought within target with a 3 dB mix-bus trim')


def arrange(document, measured, *, directory, catalog=audio_library.LIBRARY, cache=CACHE,
            ducking_version=ducking.VERSION):
    direction = plan_direction(document, ducking_version=ducking_version)
    effects = sound_stems(document['timeline'], document.get('sound_events', []), mechanical=True)
    profile = narration_module().effective_profile({'narration_profile': 'config/narration-neil.json'})
    music, selections, missing, rejected = resolve_music(direction, measured, effects, profile, directory, catalog)
    narration = joint.bound(measured['narration_audio'])
    samples = direction['frame_count'] * joint.SAMPLES_PER_FRAME
    settings = direction.get('ducking')
    constant = direction.get(MIX_MODE_FIELD) == ducking.CONSTANT_BED
    preserve_levels = bool(default_bgm(document))
    blocked_default = preserve_levels and bool(missing)
    if constant and not blocked_default:
        music, calibration = calibrate_constant(music, effects, narration, samples, measured['speech'],
                                                selections, profile)
        if not calibration['usable']:
            limiting_time = (calibration['limiting_sample'] or 0) / RATE
            levels = ', '.join(f'{cue}: {row["fixed_lufs"]} LUFS' for cue, row in calibration['cues'].items())
            raise ValueError(f'BGM does not fit the speech masking budget near {limiting_time:.3f}s at an '
                             f'audible fixed level ({levels}). Select a different licensed track or review the conflict.')
        direction['constant_bed_calibration'] = calibration
    if settings:
        music = ducking.apply(music, effects, narration, samples, measured['speech'], settings)
    add_sound_events(direction, effects)
    arrangement = dict(direction, status='BLOCKED' if missing else
                       ('SILENCE_DESIGNED' if direction['mode'] == 'silence' else 'READY'),
                       selections=selections, missing=missing, rejected_records=rejected,
                       speech=[{k: row[k] for k in ('id', 'start_sample', 'end_sample')} for row in measured['speech']],
                       narration=measured['narration_audio'], audio_perceptual_review='UNKNOWN')
    mix_receipt, hit = None, False
    if not blocked_default:
        mix_receipt, hit = cache_mix(narration, samples, music + effects, cache=cache, ducking_settings=settings,
                                     constant=constant, check_masking=constant, preserve_levels=preserve_levels)
    arrangement['mix'] = mix_receipt
    folder = Path(directory) / digest(arrangement)
    path = folder / 'audio_direction.json'
    from .workflow import lock, write
    with lock(folder / '.write.lock', wait=True):
        write(path, arrangement)
    return joint.binding(path), mix_receipt, hit


def add_sound_events(direction, effects):
    for cue in direction['segments']:
        cue['sfx_to_feature'] = [
            {key: row[key] for key in ('action_id', 'purpose', 'start_sample', 'end_sample')}
            for row in effects if row['start_sample'] < cue['end_frame'] * joint.SAMPLES_PER_FRAME
            and row['end_sample'] > cue['start_frame'] * joint.SAMPLES_PER_FRAME]


def validate_arrangement(config, *, blueprint=None, measured=None, require_ready=False, analysis=None):
    """Check the exact design and source bindings before final rendering or acceptance."""
    if not enabled(config):
        return None
    ref = config.get('audio_direction')
    direction = json.loads(bound(ref).read_text())
    constant = mix_mode(config) == ducking.CONSTANT_BED
    default = default_bgm(config)
    blocked_default = bool(default and direction['status'] == 'BLOCKED')
    if (constant != (direction.get(MIX_MODE_FIELD) == ducking.CONSTANT_BED)
            or (constant and (direction.get('ducking') is not None
                              or (not blocked_default and not direction.get('constant_bed_calibration'))
                              or (direction['mix'] and direction['mix'].get(MIX_MODE_FIELD) != ducking.CONSTANT_BED)))):
        raise ValueError('Music direction or mix receipt differs from the pinned mix mode')
    if direction['status'] not in {'READY', 'SILENCE_DESIGNED', 'BLOCKED'} or direction['mix'] != config.get('audio_mix'):
        raise ValueError('Music direction differs from the executable mix')
    if direction['status'] == 'BLOCKED' and require_ready:
        raise ValueError('BGM BLOCKED at ' + ref['path'] + ' for '
                         + ', '.join(row['cue_id'] + '/' + row.get('asset_id', row['mode']) for row in direction['missing'])
                         + ' (' + ', '.join(row['reason'] for row in direction['rejected_records']) + ')')
    if direction.get(DEFAULT_BGM_FIELD) != default or (default and
            (direction['mix'] or {}).get('output_gain_db', 0) != 0):
        raise ValueError('Fixed BGM policy or narration/SFX gain differs from the pinned defaults')
    inputs = [ref]
    stems = (direction['mix'] or {}).get('stems', [])
    music = [row for row in stems if row['kind'] == 'bgm']
    effects = [row for row in stems if row['kind'] == 'sfx']
    if measured is not None and (direction['narration'] != measured['narration_audio']
            or direction['speech'] != [{k: row[k] for k in ('id', 'start_sample', 'end_sample')}
                                       for row in measured['speech']]):
        raise ValueError('Music direction differs from the measured speech')
    cues = [row for row in direction['segments'] if row['mode'] != 'silence']
    selections = {row['cue_id']: row for row in direction['selections']}
    if (direction['status'] == 'READY' and
            (not cues or {row['id'] for row in cues} != selections.keys()
             or selections.keys() != {row['cue_id'] for row in music} or direction['missing'])):
        raise ValueError('The music design needs bound BGM throughout its intended cues')
    if direction['status'] == 'SILENCE_DESIGNED' and (direction['mode'] != 'silence' or music or selections
            or not direction.get('reason') or cues):
        raise ValueError('Intentional music silence differs from its documented design')
    for selection in selections.values():
        path = bound(selection['catalog_record'])
        raw = json.loads(path.read_text())
        validate_rights(raw)
        if default:
            audio_library.require_active(raw)
        if any(selection[key] != raw[field] for key, field in (
                ('asset_id', 'id'), ('theme', 'theme'), ('source', 'source'), ('license', 'license'))):
            raise ValueError('Selected music differs from its registered source and rights')
        if default and selection['asset_id'] != direction.get('asset_id'):
            raise ValueError('Selected music differs from the pinned or explicitly overridden asset')
        if selection.get('pcm_downmix') != raw.get('pcm_downmix'):
            raise ValueError('Selected music conversion differs from the catalog')
        inputs.extend((selection['catalog_record'], raw['license']['proof'], raw['source']))
    for row in music:
        decision = selections[row['cue_id']]
        if any(row[field] != decision[key] for field, key in (
                ('id', 'asset_id'), ('source', 'source'), ('license', 'license'), ('catalog_record', 'catalog_record'))):
            raise ValueError('Music stem differs from its selection record')
    if blueprint is not None:
        if policy(blueprint) != policy(config):
            raise ValueError('Music mix mode differs from the frozen Blueprint')
        settings = direction.get('ducking')
        if settings is not None and settings != ducking.DEFAULT:
            raise ValueError('Unexpected adaptive ducking parameters')
        expected = plan_direction(blueprint, ducking_version=ducking.VERSION if settings else 1)
        verified_effects = sound_stems(blueprint['timeline'], blueprint.get('sound_events', []), mechanical=True)
        add_sound_events(expected, verified_effects)
        if ((not blocked_default and effects != verified_effects)
                or any(direction[key] != value for key, value in expected.items())):
            raise ValueError('Sound design differs from the frozen story and verified action triggers')
        if blocked_default:
            return direction, inputs
        expected_stems = []
        for cue in cues:
            decision = selections.get(cue['id'])
            if not decision:
                continue
            row = next(stem for stem in music if stem['cue_id'] == cue['id'])
            track = audio_library.inspect(json.loads(bound(decision['catalog_record']).read_text()))
            if track.get('loop_analysis') != decision.get('loop_analysis'):
                raise ValueError('Music loop differs from the decoded source evidence')
            track['catalog_record'] = row['catalog_record']
            expected_stems.extend(lay_music(cue, track, decision['measured_lufs'], direction['speech'], effects))
        if settings or constant:
            narration = joint.bound(direction['narration'])
            samples = direction['frame_count'] * joint.SAMPLES_PER_FRAME
            dry_stems = expected_stems
            if constant:
                profile = narration_module().effective_profile({'narration_profile': 'config/narration-neil.json'})
                for decision in selections.values():
                    with audio_library.pcm_path(bound(decision['source']), downmix=decision.get('pcm_downmix')) as pcm:
                        if measured_lufs(pcm, profile) != decision['measured_lufs']:
                            raise ValueError('Constant bed source loudness differs from the measured music')
                expected_stems, calibration = calibrate_constant(dry_stems, verified_effects, narration, samples,
                                                                 direction['speech'], list(selections.values()), profile)
                if not calibration['usable'] or direction['constant_bed_calibration'] != calibration:
                    raise ValueError('Constant bed calibration differs from the measured audio')
            else:
                expected_stems = ducking.apply(dry_stems, verified_effects, narration, samples, direction['speech'],
                                               settings)
            if analysis is not None and music:
                analysis.extend(ducking.describe(
                    ducking.measurements(dry_stems, narration, samples),
                    ducking.measurements(music + effects, narration, samples), direction['speech']))
        if music != expected_stems:
            raise ValueError('BGM placement or gain envelope differs from the measured sound design')
    inputs.extend(row['trigger_evidence'] for row in effects)
    return direction, inputs


def picture_hash(path):
    return check_output(['ffmpeg', '-v', 'error', '-xerror', '-i', str(path), '-map', '0:v:0',
                         '-c:v', 'copy', '-f', 'hash', '-hash', 'sha256', '-']).decode().strip()


def mux_picture(source, track, output):
    execute(['ffmpeg', '-v', 'error', '-xerror', '-y', '-i', str(source), '-i', str(track),
             '-map', '0:v:0', '-map', '1:a:0', '-c:v', 'copy', *AAC_ARGS,
             '-movflags', '+faststart', str(output)], check=True)


def mix(plan, events, narration, output):
    """Build historical Director effects using the same streaming mixer."""
    stems = sound_stems(plan, events)
    if not stems:
        return None
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=output.parent) as temp:
        candidate = Path(temp) / 'mix.wav'
        process_mix(stems, narration, plan['frame_count'] * joint.SAMPLES_PER_FRAME, destination=candidate)
        candidate.replace(output)
    return dict(master=joint.binding(output), stems=stems)


def postprocess(source, blueprint, output, *, catalog=audio_library.LIBRARY, cache=CACHE):
    """Create a new audio revision of an existing measured-timeline picture."""
    source, output = Path(source), Path(output)
    if source.resolve() == output.resolve() or output.exists():
        raise ValueError('Audio postproduction needs a fresh output path')
    plan = joint.validate(blueprint['timeline'], blueprint.get('shots'))
    measured = joint.receipt(plan, blueprint['measured_timeline'])
    joint.validate_rendered_film(source, plan, require_audio=False)
    source_ref = joint.binding(source)
    ref, mixture, hit = arrange(blueprint, measured, directory=output.parent / 'audio-direction',
                                catalog=catalog, cache=cache)
    config = {key: blueprint[key] for key in POLICY_FIELDS if key in blueprint}
    config.update({FIELD: VERSION, 'audio_direction': ref, 'audio_mix': mixture})
    arrangement, _ = validate_arrangement(config, blueprint=blueprint, measured=measured, require_ready=True)
    track = joint.bound(mixture['master'] if mixture else measured['narration_audio'])
    if mixture:
        verify_mix(mixture, joint.bound(measured['narration_audio']), plan['frame_count'] * joint.SAMPLES_PER_FRAME)
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=output.parent) as folder:
        candidate = Path(folder) / 'audio-revision.mp4'
        mux_picture(source, track, candidate)
        joint.validate_rendered_film(candidate, plan)
        verdict = joint.validate_rendered_audio(candidate, plan, measured, track, mix=bool(mixture))
        narration = narration_module()
        profile = narration.effective_profile({'narration_profile': 'config/narration-neil.json'})
        levels = narration.measure_loudness(candidate, profile)
        reference = float(narration.measure_loudness(track, profile)['input_i'])
        check_levels(levels, profile, 'Postproduction AAC', reference_lufs=reference)
        if float(levels['input_tp']) > profile['loudness']['true_peak_dbtp']:
            raise ValueError('Postproduction AAC exceeds the configured true-peak ceiling')
        fingerprint = picture_hash(source)
        if picture_hash(candidate) != fingerprint or joint.binding(source) != source_ref:
            raise ValueError('Audio-only revision changed the bound picture')
        candidate.replace(output)
    receipt = dict(source=source_ref, media=joint.binding(output), audio_direction=ref,
                   picture_stream=fingerprint, audio_technical_status='PASS', audio_perceptual_review='UNKNOWN',
                   music_status=arrangement['status'], cache_hit=hit, measurements=levels,
                   audio=verdict, formal_acceptance=False)
    writejson(output.with_suffix('.audio-post.json'), receipt)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    plan = commands.add_parser('plan')
    post = commands.add_parser('postprocess')
    for command in (plan, post):
        command.add_argument('blueprint', type=Path)
        command.add_argument('--output', required=True, type=Path)
    post.add_argument('--picture', required=True, type=Path)
    post.add_argument('--catalog', default=audio_library.LIBRARY, type=Path)
    args = parser.parse_args()
    blueprint = json.loads(args.blueprint.read_text())
    if args.command == 'plan':
        writejson(args.output, plan_direction(blueprint))
    else:
        postprocess(args.picture, blueprint, args.output, catalog=args.catalog)
    print(args.output)


if __name__ == '__main__':
    main()
