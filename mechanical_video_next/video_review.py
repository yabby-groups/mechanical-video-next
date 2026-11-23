"""Deterministic review of a real edit, with timecoded evidence and no sensory claims."""

import argparse
from contextlib import ExitStack
import json
import math
from pathlib import Path
import re
import subprocess
from tempfile import NamedTemporaryFile, TemporaryDirectory
import wave

from PIL import Image, ImageChops, ImageStat

from scripts.common import probe
from . import joint_timeline as joint
from .media_revision import decode_errors, frames
from .qa_images import CACHE, prepare_contact_sheet, visual_packet

FIELD = 'video_review_version'
VERSION = 1
CHECK_ERRORS = (ValueError, OSError, RuntimeError, KeyError, TypeError, EOFError,
                StopIteration, wave.Error, subprocess.SubprocessError)
FRAME_SIZE = 160 * 90 * 3
CAPABILITY = {
    'picture': 'Decoded frames and ordered reduced-resolution pixel comparisons',
    'audio': 'Decoded PCM comparison against measured narration and any verified mix',
    'continuous_viewing': 'UNKNOWN',
    'perceptual_listening': 'UNKNOWN',
    'semantic_visibility_and_story': 'UNKNOWN',
}


def finding(code, start, end, detail, *, shot=None, status='FAIL'):
    return {
        'code': code, 'status': status, 'shot_id': shot,
        'frame_range': [start, end],
        'time_range': [round(start / joint.FPS, 6), round(end / joint.FPS, 6)],
        'evidence': str(detail),
    }


def status(findings):
    states = {row['status'] for row in findings}
    return 'FAIL' if 'FAIL' in states else 'UNKNOWN' if 'UNKNOWN' in states else 'PASS'


def require_technical_pass(report):
    if report['technical_status'] != 'PASS' or status(report['findings']) != 'PASS':
        raise ValueError('Video Review ' + report['technical_status'] + ': '
                         + '; '.join(row['code'] for row in report['findings']))


def require_current(production):
    report = production.get('video_review', {})
    films = [row for row in production.get('media', []) if Path(row['path']).suffix.lower() == '.mp4']
    if (report.get('schema_version') != VERSION or len(films) != 1
            or report.get('media') != films[0]):
        raise ValueError('Current exact-media Video Review is missing')
    joint.bound(films[0])
    require_technical_pass(report)


def write_report(path, report):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(dir=path.parent, delete=False, mode='w', encoding='utf-8') as output:
        temporary = Path(output.name)
        try:
            json.dump(report, output, ensure_ascii=False, indent=2)
            output.write('\n')
            output.close()
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)


def story_findings(plan, blueprint, required_ids):
    picture = {cut['id']: cut for cut in plan['shots']}
    used = {key for shot in blueprint.get('shots', []) if shot['shot_id'] in picture
            for key in shot.get('knowledge_ids', [])}
    for key in sorted(set(required_ids) - used):
        yield finding('story_missing_knowledge', plan['frame_count'], plan['frame_count'], key)
    if joint.integrity(plan):
        from .production_contract import validate_story_moments
        try:
            validate_story_moments(blueprint, blueprint['narrative'])
        except CHECK_ERRORS as error:
            yield finding('story_moment_invalid', 0, plan['frame_count'], error)


def state_findings(plan, states):
    """Review evaluated scalar states on their original source frame clock."""
    cuts = {cut['id']: cut for cut in plan['shots']}
    for check in states:
        cut = cuts[check['shot_id']]
        first, last = check.get('frame_range', [cut['start_frame'], cut['end_frame']])
        source = cut.get('source_start_frame', 0) + first - cut['start_frame']
        values = check['samples'][source:source + last - first]
        if (not cut['start_frame'] <= first < last <= cut['end_frame']
                or len(values) != last - first or not all(math.isfinite(v) for v in values)):
            yield finding('mechanical_state_coverage', first, last, check['id'],
                          shot=cut['id'], status='UNKNOWN')
            continue
        direction = check.get('direction')
        tolerance = check.get('tolerance', 0)
        differences = [b - a for a, b in zip(values, values[1:])]
        if direction is not None:
            if direction not in (-1, 1):
                raise ValueError('Direction must be +1 or -1')
            if direction * (values[-1] - values[0]) <= tolerance:
                yield finding('mechanical_direction', first, last, check['id'], shot=cut['id'])
            elif any(direction * step < -tolerance for step in differences):
                index = next(i for i, step in enumerate(differences, first + 1)
                             if direction * step < -tolerance)
                yield finding('mechanical_direction', index, index + 1, check['id'], shot=cut['id'])
        if 'min_motion_frames' in check or 'max_step' in check:
            steps = list(map(abs, differences))
            moving = sum(step > tolerance for step in steps)
            if moving < check.get('min_motion_frames', 0):
                yield finding('mechanical_action_compressed', first, last,
                              f"{check['id']} has {moving} moving frames", shot=cut['id'])
            for index, step in enumerate(steps, first + 1):
                if step > check.get('max_step', math.inf) + tolerance:
                    yield finding('mechanical_step', index, index + 1,
                                  f"{check['id']} step {step:.6g}", shot=cut['id'])
        previous_hit = -1
        for event in check.get('events', []):
            low, high = event['range']
            hit = next((i for i in range(previous_hit + 1, len(values))
                        if low - tolerance <= values[i] <= high + tolerance), None)
            if hit is None:
                yield finding('mechanical_event_missing', first, last,
                              f"{check['id']} / {event['id']}", shot=cut['id'])
                break
            previous_hit = hit
        if 'continue_from' in check:
            previous = cuts[check['continue_from']]
            if previous['end_frame'] != first:
                raise ValueError('State continuity requires adjacent output windows')
            prior = check.get('previous_samples', check['samples'])
            previous_index = (previous.get('source_start_frame', 0)
                              + previous['end_frame'] - previous['start_frame'] - 1)
            if previous_index >= len(prior) or not math.isfinite(prior[previous_index]):
                yield finding('mechanical_state_coverage', first - 1, first + 1,
                              check['id'], shot=cut['id'], status='UNKNOWN')
                continue
            delta = abs(values[0] - prior[previous_index])
            if delta > check['max_cut_step'] + tolerance:
                yield finding('mechanical_cut_jump', first - 1, first + 1,
                              f"{check['id']} jump {delta:.6g}", shot=cut['id'])


def pixel_findings(path, source, first, last, offset, shot, *, region=None, source_region=None):
    """Compare each output frame to its selected source, with spatial tolerance for overlays."""
    count = last - first
    source_region = source_region if source_region is not None else region
    with ExitStack() as cleanup:
        decoders = [
            cleanup.enter_context(frames(file, start / joint.FPS, count / joint.FPS, crop))
            for file, start, crop in ((path, first, region), (source, offset, source_region))
        ]
        output, expected = (process for process, _ in decoders)
        mismatches = []
        black = []
        for index in range(first, last):
            actual_bytes = output.stdout.read(FRAME_SIZE)
            expected_bytes = expected.stdout.read(FRAME_SIZE)
            if len(actual_bytes) != FRAME_SIZE or len(expected_bytes) != FRAME_SIZE:
                return [finding('picture_source_short', index, last, 'Incomplete decoded source or edit. '
                                + decode_errors(*decoders),
                                shot=shot)]
            actual, reference = (Image.frombytes('RGB', (160, 90), data)
                                 for data in (actual_bytes, expected_bytes))
            diff = ImageChops.difference(actual, reference).convert('L')
            # Gross mismatches in the body of the picture. Local overlays and
            # codec noise are handled by independent visual review.
            center = diff.crop((16, 16, 144, 74))
            average = ImageStat.Stat(center).mean[0]
            if average >= 9 and sum(center.histogram()[24:]) >= 0.10 * 128 * 58:
                mismatches.append(index)
                if ImageStat.Stat(actual.convert('L')).mean[0] < 12:
                    black.append(index)
        if any([output.wait(), expected.wait()]):
            return [finding('picture_decode_error', first, last, 'FFmpeg failed decoding the comparison. '
                            + decode_errors(*decoders),
                            shot=shot)]
    return [
        finding(code, start, end, detail, shot=shot)
        for code, indices, detail in (
            ('picture_source_mismatch', mismatches, f'Actual pixels differ from source clock, offset {offset}'),
            ('unexpected_black_picture', black, 'Decoded picture is dark while the expected source is visible'),
        )
        for start, end in contiguous_ranges(indices)
    ]


def contiguous_ranges(indices):
    intervals = []
    for index in indices:
        if intervals and intervals[-1][1] == index:
            intervals[-1][1] += 1
        else:
            intervals.append([index, index + 1])
    return intervals


def inspect(media, plan, *, measured=None, playback=None, mix=False, blueprint=None,
            required_ids=(), sources=None, states=(), rendered_cues=None):
    path = joint.bound(media)
    end = plan['frame_count']
    findings = []
    metrics = {}
    actual = 0
    try:
        from .production_contract import validate_formal_duration
        validate_formal_duration(blueprint or {}, end / joint.FPS)
        picture = next(row for row in probe(path)['streams'] if row['codec_type'] == 'video')
        actual = int(picture.get('nb_frames', 0))
        joint.validate_rendered_film(path, plan)
        metrics['decoded_frames'] = actual
    except CHECK_ERRORS as error:
        located = re.search(r'at frame (\d+)', str(error))
        start = int(located[1]) if located else min(actual, end) if actual != end else 0
        stop = start + 1 if located else max(actual, end)
        findings.append(finding('picture_timeline', start, stop, error))
    if measured is None:
        findings.append(finding('audio_reference_missing', 0, end, 'Measured Neil receipt unavailable',
                                status='UNKNOWN'))
    else:
        try:
            metrics['audio'] = joint.validate_rendered_audio(path, plan, measured, playback, mix=mix)
            from .audio_acceptance import verify_speech_silence
            verify_speech_silence(joint.bound(measured['narration_audio']), [
                {'id': line['id'], 'samples': [line['start_sample'], line['end_sample']]}
                for line in measured['speech']
            ])
        except CHECK_ERRORS as error:
            match = re.search(r'(\d+(?:\.\d+)?)s\b', str(error))
            first = min(end - 1, int(float(match[1]) * joint.FPS)) if match else 0
            code = 'audio_reference_mismatch'
            findings.append(finding(code, first, min(end, first + 3) if match else end, error))
        if rendered_cues is None:
            findings.append(finding('caption_schedule_unavailable', 0, end,
                                    'Exact composition cue schedule unavailable', status='UNKNOWN'))
        else:
            expected_cues = joint.cues(measured)
            if len(rendered_cues) != len(expected_cues):
                findings.append(finding('caption_count', 0, end, 'Missing or extra caption cues'))
            end_tolerance = .001 if joint.integrity(plan) else 1 / joint.FPS
            for actual_cue, expected_cue in zip(rendered_cues, expected_cues):
                if (actual_cue['text'] != expected_cue['text']
                        or abs(actual_cue['start'] - expected_cue['start']) > .001
                        or abs(actual_cue['end'] - expected_cue['end']) > end_tolerance):
                    first = math.floor(expected_cue['start'] * joint.FPS)
                    last = math.ceil(expected_cue['end'] * joint.FPS)
                    findings.append(finding('caption_schedule_mismatch', first, last, expected_cue['text']))
    try:
        joint.validate(plan, blueprint.get('shots') if blueprint else None)
    except CHECK_ERRORS as error:
        findings.append(finding('edit_mechanical_timeline', 0, end, error))
    if blueprint:
        findings.extend(story_findings(plan, blueprint, required_ids))
    else:
        findings.append(finding('story_source_missing', 0, end, 'Source story coverage unavailable',
                                status='UNKNOWN'))
    try:
        findings.extend(state_findings(plan, states))
    except CHECK_ERRORS as error:
        findings.append(finding('mechanical_state_invalid', 0, end, error, status='UNKNOWN'))
    sources = sources or {}
    for cut in plan['shots']:
        shot = cut['id']
        first, last = cut['start_frame'], cut['end_frame']
        ref = sources.get(shot)
        if ref is None:
            if cut.get('action_views'):
                findings.append(finding('mechanical_picture_source_missing', first, last, shot,
                                        shot=shot, status='UNKNOWN'))
            continue
        try:
            offset = cut.get('source_start_frame', 0)
            if ref.get('source_start_frame', offset) != offset:
                findings.append(finding('picture_source_offset', first, last, shot, shot=shot))
                continue
            findings.extend(pixel_findings(path, joint.bound(ref), first, last, offset, shot,
                                           region=ref.get('region'), source_region=ref.get('source_region')))
        except CHECK_ERRORS as error:
            findings.append(finding('picture_source_unavailable', first, last, error,
                                    shot=shot, status='UNKNOWN'))
    joint.bound(media)
    return {'schema_version': VERSION, 'media': media, 'technical_status': status(findings),
            'independent_acceptance': 'UNKNOWN', 'capabilities': CAPABILITY,
            'checks': metrics, 'findings': findings}


def require_mechanical_positioning(task, review, production):
    """Require the existing independent QA to evaluate the mechanical brief."""
    from .creative_selection import validate_creative_gate

    films = [row['path'] for row in production['media'] if Path(row['path']).suffix.lower() == '.mp4']
    if len(films) != 1:
        raise ValueError('Mechanical positioning review needs the exact complete moving edit')
    duration = float(probe(films[0])['format']['duration'])
    status = validate_creative_gate(task, review, duration=duration)
    if status != 'PASS':
        raise ValueError('Independent mechanical positioning review is ' + status)


def for_composition(media, blueprint, research, config, public):
    """Read the actual Remotion inputs and compare them with the frozen edit."""
    from .director import validate_action_programs

    plan = blueprint['timeline']
    end = plan['frame_count']
    measured = None
    playback = None
    cues = None
    sources = {}
    states = []
    findings = []
    science = research['science']
    verified = {row['id'] for row in science['facts'] if row['status'] == 'VERIFIED'}
    required = science.get('required_knowledge_ids', sorted(verified))
    if (not isinstance(required, list) or not required
            or any(not isinstance(key, str) or key not in verified for key in required)):
        findings.append(finding('story_research_scope', 0, end, 'Essential story facts must be verified research IDs'))
        required = sorted(verified)
    inputs = {'source_clips': sources}
    try:
        validate_action_programs(config)
    except CHECK_ERRORS as error:
        findings.append(finding('mechanical_program_clock', 0, end, error))
    try:
        inputs['measured_timeline'] = blueprint['measured_timeline']
        measured = joint.receipt(plan, inputs['measured_timeline'])
        if config.get('audio_mix'):
            from .audio_acceptance import verify_mix
            playback, _ = verify_mix(config['audio_mix'], joint.bound(measured['narration_audio']),
                                     end * joint.SAMPLES_PER_FRAME, check_masking=False)
    except CHECK_ERRORS as error:
        findings.append(finding('audio_input_invalid', 0, end, error))
    try:
        path = joint.bound(media).with_suffix('.props.json')
        inputs['composition'] = joint.binding(path)
        props = json.loads(path.read_text())
        receipt_path = path.with_name(path.name.replace('.props.json', '.review-sources.json'))
        inputs['render_sources'] = joint.binding(receipt_path)
        receipt = json.loads(receipt_path.read_text())
        if (receipt['media']['sha256'] != media['sha256']
                or receipt['props'] != inputs['composition']):
            raise ValueError('Render source receipt differs from the exact MP4 or Remotion props')
        cues = props['cues']
        rows = props['shots']
        actions = {action['id']: action for action in plan['actions']}
        film = next(stream for stream in probe(media['path'])['streams'] if stream['codec_type'] == 'video')
        if [row['id'] for row in rows] != [cut['id'] for cut in plan['shots']]:
            findings.append(finding('picture_composition_order', 0, end, 'Remotion cut order differs'))
        for row, cut in zip(rows, plan['shots']):
            first, last = cut['start_frame'], cut['end_frame']
            if round(row['seconds'] * joint.FPS) != last - first:
                findings.append(finding('picture_composition_cut', first, last, cut['id'], shot=cut['id']))
            if not cut.get('action_views'):
                continue
            source = (public / row['media']).resolve()
            if not source.is_relative_to(public.resolve()):
                raise ValueError('Composition source must stay within the local media cache')
            ref = joint.binding(source)
            rendered = receipt['shots'][cut['id']]
            if ref['sha256'] != rendered['video']['sha256']:
                findings.append(finding('mechanical_render_source', first, last, cut['id'], shot=cut['id']))
            ref['source_start_frame'] = row.get('mediaStartFrame', 0)
            video = next(stream for stream in probe(source)['streams'] if stream['codec_type'] == 'video')
            ratio = (video['width'] * film['height']) / (video['height'] * film['width'])
            if ratio < .999 or ratio > 1.001:
                width, height = min(1, ratio), min(1, 1 / ratio)
                ref['region'] = [(1 - width) / 2, (1 - height) / 2, width, height]
                ref['source_region'] = [0, 0, 1, 1]
            sources[cut['id']] = ref
            for action_id in cut['action_views']:
                action = actions[action_id]
                for check in action.get('state_checks', {}).get(cut['id'], []):
                    try:
                        state = dict(check, shot_id=cut['id'],
                                     samples=constraint_samples(rendered, check['constraint_index']),
                                     frame_range=[max(first, action['start_frame']),
                                                  min(last, action['end_frame'])])
                        if 'continue_from' in check:
                            previous = receipt['shots'][check['continue_from']]
                            state['previous_samples'] = constraint_samples(
                                previous, check.get('previous_constraint_index', check['constraint_index']))
                        states.append(state)
                    except CHECK_ERRORS + (IndexError,) as error:
                        findings.append(finding('mechanical_state_unavailable', first, last,
                                                error, shot=cut['id'], status='UNKNOWN'))
    except CHECK_ERRORS as error:
        findings.append(finding('composition_evidence_unavailable', 0, end, error, status='UNKNOWN'))
    report = inspect(media, plan, measured=measured, playback=playback, mix=bool(config.get('audio_mix')),
                     blueprint=blueprint, required_ids=required, sources=sources, states=states,
                     rendered_cues=cues)
    report['inputs'] = inputs
    report['findings'].extend(findings)
    report['technical_status'] = status(report['findings'])
    return report


def constraint_samples(rendered, index):
    native = json.loads(joint.bound(rendered['blender_checks']).read_text())
    return native['checks']['numerical_constraints']['samples'][index]['review_samples']


def ordered_picture_evidence(media, frame_indices, *, cache_dir=CACHE):
    """Make a timecoded sheet from exact decoded indices on a verified 30 fps edit."""
    if (not 1 <= len(frame_indices) <= 16 or any(type(i) is not int or i < 0 for i in frame_indices)
            or list(frame_indices) != sorted(set(frame_indices))):
        raise ValueError('Use 1..16 increasing, zero-based decoded frame indices')
    source = joint.bound(media)
    video = next((row for row in probe(source)['streams'] if row['codec_type'] == 'video'), {})
    if (video.get('avg_frame_rate') != '30/1' or video.get('r_frame_rate') != '30/1'
            or float(video.get('start_time', 'inf')) != 0):
        raise ValueError('Ordered evidence requires a zero-start 30 fps picture track')
    directory = Path(cache_dir)
    directory.mkdir(parents=True, exist_ok=True)
    select = '+'.join(f'eq(n\\,{index})' for index in frame_indices)
    with TemporaryDirectory(dir=directory) as tmp:
        subprocess.run(['ffmpeg', '-v', 'error', '-nostdin', '-i', str(source), '-map', '0:v:0',
                        '-vf', 'select=' + select, '-frames:v', str(len(frame_indices)), '-fps_mode',
                        'passthrough', '-threads', '1', str(Path(tmp) / '%02d.png')],
                       check=True, capture_output=True)
        paths = sorted(Path(tmp).glob('*.png'))
        if len(paths) != len(frame_indices):
            raise ValueError('Requested frame falls outside the decoded film')
        labels = [f'f{index:04d}   {index / joint.FPS:.3f}s' for index in frame_indices]
        sheet = prepare_contact_sheet(paths, labels=labels, cache_dir=directory)
    packet = visual_packet(sheets=[sheet])
    return dict(packet, media=media, frame_indices=list(frame_indices), method='ordered_decoded_images',
                continuous_viewing='UNKNOWN')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('media', type=Path)
    parser.add_argument('inputs', type=Path, help='JSON with plan and available review inputs')
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    inputs = json.loads(args.inputs.read_text())
    report = inspect(joint.binding(args.media), **inputs)
    report['inputs'] = joint.binding(args.inputs)
    write_report(args.output, report)
    print(f"{report['technical_status']} {args.output}")
    return {'PASS': 0, 'FAIL': 1, 'UNKNOWN': 2}[report['technical_status']]


if __name__ == '__main__':
    raise SystemExit(main())
