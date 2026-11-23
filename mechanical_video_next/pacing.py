"""Audit the existing picture, native motion and measured speech clocks."""

import argparse
import json
import math
from pathlib import Path

from scripts.common import digest
from . import joint_timeline as joint

VERSION = 1
OPERATIONS_REVIEW = 'docs/plans/operations-growth-review-20261123.md'
BRIEF = ('phenomenon', 'opening', 'first_result', 'first_answer')
SHOT = ('watch_task', 'mechanical_event', 'camera_reason', 'exit_condition')
CHECKS = ('opening_event', 'first_result_and_answer', 'idle_wait', 'camera_value',
          'repetition', 'motion_speed', 'audiovisual_sync', 'knowledge_progression')
KINDS = {'input', 'contact', 'transmission', 'output', 'reset', 'answer'}
# Earlier remedies preserve both the source clock and Neil's natural delivery.
REPAIR_ORDER = ('trim_wait', 'remove_repetition', 'merge_camera_move', 'reorder',
                'revise_narration', 'redistribute_animation', 'render_if_needed')


def enabled(document):
    return document.get('formal_duration_version') == 2


def text_fields(row, fields):
    return isinstance(row, dict) and all(isinstance(row.get(key), str) and row[key].strip() for key in fields)


def validate_brief(brief, task):
    seconds = brief.get('shortest_complete_seconds') if isinstance(brief, dict) else None
    if (not text_fields(brief, BRIEF) or type(seconds) not in (int, float)
            or not 0 < seconds <= 300):
        raise ValueError('Pacing brief needs the phenomenon, opening, first result, first answer and shortest complete estimate')
    for key in ('essential_scenes', 'decorative_scenes'):
        values = brief.get(key)
        if (not isinstance(values, list) or not all(isinstance(value, str) and value.strip() for value in values)
                or len(set(values)) != len(values)):
            raise ValueError('Identify essential and decorative scenes by Treatment ID')
    if not brief['essential_scenes'] or set(brief['essential_scenes']) & set(brief['decorative_scenes']):
        raise ValueError('Essential scenes are required and cannot also be decorative')
    decision = brief.get('operations')
    fields = ('platform_observation', 'shot_observation', 'hypothesis', 'edit_decision', 'follow_up')
    if not text_fields(decision, fields) or decision.get('source') != task.get('operations_review'):
        raise ValueError('Tie an editorial experiment and follow-up to the pinned operations review')
    joint.bound(decision['source'])


def window(value, start, end):
    if (not isinstance(value, list) or len(value) != 2 or any(type(frame) is not int for frame in value)
            or not start <= value[0] < value[1] <= end):
        raise ValueError(f'Pacing interval must be inside frames [{start}, {end})')
    return value


def validate(plan, design, *, facts=None):
    """Keep the annotations inside the existing executable film clock."""
    cuts = {cut['id']: cut for cut in plan['shots']}
    actions = {action['id']: action for action in plan['actions']}
    speech = {line['id'] for line in plan['narration']}
    if not isinstance(design, dict) or design.keys() != cuts.keys():
        raise ValueError('Pacing direction must cover every Joint Timeline shot by ID')
    event_ids = set()
    for sid, cut in cuts.items():
        row = design[sid]
        if not text_fields(row, SHOT):
            raise ValueError(f'Pacing direction for {sid} needs a viewing task, event, camera reason and exit condition')
        start, end = cut['start_frame'], cut['end_frame']
        for key in ('increments', 'observation', 'events'):
            if not isinstance(row.get(key), list):
                raise ValueError(f'Pacing direction for {sid} needs a {key} list')
        for span in row['increments']:
            window(span['frames'], start, end)
            if (not text_fields(span, ('id', 'discovery', 'evidence'))
                    or (facts is not None and span.get('knowledge_id') not in facts)
                    or ('speech_id' in span and span['speech_id'] not in speech)):
                raise ValueError(f'Invalid information increment in {sid}')
        for span in row['observation']:
            window(span['frames'], start, end)
            if not text_fields(span, ('task', 'evidence')):
                raise ValueError(f'Observation time in {sid} requires a viewing task and visible evidence')
        for event in row['events']:
            left, right = window(event['frames'], start, end)
            if (not text_fields(event, ('id', 'description')) or event.get('kind') not in KINDS
                    or event['id'] in event_ids or ('speech_id' in event and event['speech_id'] not in speech)
                    or ('onset_tolerance_frames' in event and
                        (type(event['onset_tolerance_frames']) is not int
                         or event['onset_tolerance_frames'] < 0 or 'speech_id' not in event))
                    or ('opening' in event and type(event['opening']) is not bool)):
                raise ValueError(f'Invalid pacing event in {sid}')
            event_ids.add(event['id'])
            if event['kind'] == 'answer':
                if not any(span['frames'][0] <= left < span['frames'][1] for span in row['increments']):
                    raise ValueError(f'First answer in {sid} needs a timed information increment')
                continue
            action = actions.get(event.get('action_id'))
            if (not action or action['id'] not in cut.get('action_views', {})
                    or not action['start_frame'] <= left < right <= action['end_frame']):
                raise ValueError(f'Pacing event in {sid} must map to a source-bound mechanical action')
            if 'state_id' in event and not text_fields(event, ('state_id',)):
                raise ValueError(f'Invalid native state reference in {sid}')
    return design


def load_states(ref):
    """Read native trajectories through the evidence hashes in the manifest."""
    states = json.loads(joint.bound(ref).read_text())
    for state in states:
        samples = json.loads(joint.bound(state['source']).read_text())
        for key in state.pop('sample_path'):
            samples = samples[key]
        if 'sample_key' in state:
            samples = [row[state['sample_key']] for row in samples]
        state['samples'] = samples
    return states


def intervals(flags, offset):
    start = None
    for frame, flagged in enumerate([*flags, False], offset):
        if flagged and start is None:
            start = frame
        if not flagged and start is not None:
            yield [start, frame]
            start = None


def time_range(frames):
    return [round(frame / joint.FPS, 6) for frame in frames]


def measure_event(event, cut, states):
    state = states.get((cut['id'], event.get('action_id'), event.get('state_id')))
    if state is None:
        return None
    start, end = event['frames']
    offset = cut.get('source_start_frame', 0) - cut['start_frame']
    samples = state['samples']
    before = max(0, start + offset - 1)
    stop = end + offset
    if before >= stop or stop > len(samples):
        return None
    values = samples[before:stop]
    if len(values) < 2 or not all(type(value) in (float, int) and math.isfinite(value) for value in values):
        return None
    tolerance = state.get('tolerance', 1e-6)
    changes = [abs(b - a) > tolerance for a, b in zip(values, values[1:])]
    return {'source': state.get('source'), 'frame_range': [start, end],
            'source_frame_range': [start + offset, stop],
            'observed_minimum': min(values), 'observed_maximum': max(values),
            'motion_ranges': list(intervals(changes, before + 1 - offset))}


def analyze(media, plan, design, *, measured=None, states=(), inputs=None, wait_seconds=1.0):
    """Report authored semantics and technical observations with their evidence scope."""
    from .video_review import finding
    validate(plan, design)
    measured_speech = {
        row['id']: dict(id=row['id'], time_range=[row['start_sample'] / joint.SAMPLE_RATE,
                                                 row['end_sample'] / joint.SAMPLE_RATE])
        for row in (measured or {}).get('speech', [])
    }
    state_by_id = {(row['shot_id'], row['action_id'], row['id']): row for row in states}
    findings, shots, events = [], [], []
    known = set()
    wait_frames = math.ceil(wait_seconds * joint.FPS)
    action_by_id = {row['id']: row for row in plan['actions']}

    def flag(code, frames, detail, fix, sid=None, status='REVIEW'):
        findings.append(dict(finding(code, *frames, detail, shot=sid, status=status),
                             repair=fix, repair_order=REPAIR_ORDER.index(fix) + 1))

    for cut in plan['shots']:
        sid, start, end = cut['id'], cut['start_frame'], cut['end_frame']
        row = design[sid]
        coverage = [False] * (end - start)

        def cover(frames):
            left, right = max(start, frames[0]), min(end, frames[1])
            for i in range(left, right):
                coverage[i - start] = True

        increments = []
        for span in row['increments']:
            frames = span['frames']
            if span['id'] in known:
                flag('repeated_information', frames, span['discovery'], 'remove_repetition', sid)
            else:
                cover(frames)
                increments.append(dict(span, time_range=time_range(frames)))
                known.add(span['id'])
        for observation in row['observation']:
            cover(observation['frames'])
        shot_events = []
        for event in row['events']:
            frames = event['frames']
            native = measure_event(event, cut, state_by_id)
            moving = native['motion_ranges'] if native else []
            # Only native state change or a directed semantic window can
            # locate a candidate event. Pixel movement never enters this logic.
            result = dict(event, shot_id=sid, time_range=time_range(frames), native=native,
                          technical_status='MEASURED' if native else 'UNKNOWN', sensory_status='UNKNOWN')
            shot_events.append(result)
            events.append(result)
            for motion_range in moving:
                cover(motion_range)
            if event.get('state_id') and native is None:
                flag('native_event_unverified', frames, event['description'], 'redistribute_animation', sid, 'UNKNOWN')
            if event.get('speech_id'):
                line = measured_speech.get(event['speech_id'])
                if line is None:
                    flag('speech_measurement_missing', frames, event['speech_id'], 'revise_narration', sid, 'UNKNOWN')
                else:
                    a, b = line['time_range']
                    anchors = moving or [frames]
                    # The author chooses the action window in which this phrase
                    # belongs. A phrase can lead or bridge a cut while overlapping it.
                    delta = min(max(left / joint.FPS - b, a - right / joint.FPS)
                                for left, right in anchors)
                    onset_difference = a - anchors[0][0] / joint.FPS
                    tolerance = event.get('onset_tolerance_frames')
                    result['speech'] = {**line,
                                        'gap_seconds': round(max(0, delta), 6),
                                        'onset_difference_seconds': round(onset_difference, 6),
                                        'comparison': 'native motion' if moving else 'authored event window'}
                    if delta >= 0 or (tolerance is not None and abs(onset_difference) > tolerance / joint.FPS):
                        flag('speech_action_mismatch', frames, result['speech'], 'revise_narration', sid,
                             'MEASURED' if moving else 'REVIEW')
        native_tracks = []
        for (shot_id, action_id, channel), state in state_by_id.items():
            if shot_id != sid or action_id not in cut.get('action_views', {}):
                continue
            action = action_by_id[action_id]
            frames = [max(start, action['start_frame']), min(end, action['end_frame'])]
            track = measure_event({'frames': frames, 'action_id': action_id, 'state_id': channel},
                                  cut, state_by_id)
            if track is not None:
                motion = track['motion_ranges']
                native_tracks.append(dict(track, action_id=action_id, state_id=channel,
                                          start_frame=motion[0][0] if motion else None,
                                          completion_frame=motion[-1][1] - 1 if motion else None))
        activity = [span for track in native_tracks for span in track['motion_ranges']]
        for frames in intervals([not value for value in coverage], start):
            code = 'no_directed_progress'
            if activity and frames[1] <= min(a for a, _ in activity):
                code = 'pre_action_wait'
            if activity and frames[0] >= max(b for _, b in activity):
                code = 'post_action_wait'
            threshold = min(wait_frames, joint.FPS // 2) if frames[0] == 0 and code == 'pre_action_wait' else wait_frames
            if frames[1] - frames[0] < threshold:
                continue
            flag(code, frames, row['watch_task'], 'trim_wait', sid)
        if not increments and not row['observation'] and not shot_events:
            flag('camera_without_demonstration', [start, end], row['camera_reason'], 'merge_camera_move', sid)
        speech = [line for line in measured_speech.values()
                  if line['time_range'][0] < end / joint.FPS and line['time_range'][1] > start / joint.FPS]
        shots.append(dict(shot_id=sid, frame_range=[start, end], time_range=time_range([start, end]),
                          source_start_frame=cut.get('source_start_frame', 0),
                          watch_task=row['watch_task'], camera_reason=row['camera_reason'],
                          exit_condition=row['exit_condition'], mechanical_event=row['mechanical_event'],
                          information_increments=increments, measured_speech=speech,
                          observation=row['observation'], events=shot_events, native_tracks=native_tracks))
    early = [event for event in events if event.get('opening') and event['kind'] != 'answer']
    results = sorted((event for event in events if event['kind'] == 'output'), key=lambda e: e['frames'][0])
    answers = sorted((event for event in events if event['kind'] == 'answer'), key=lambda e: e['frames'][0])
    advances = results + [event for event in events if event['kind'] in {'contact', 'transmission', 'answer'}]
    def first_frame(event):
        motion = (event['native'] or {}).get('motion_ranges', [])
        return motion[0][0] if motion else event['frames'][0]

    end = plan['frame_count']
    for code, seconds, candidates, detail in (
        ('opening_event_missing', 2, early, 'Show a recognizable object performing a relevant function'),
        ('early_progress_missing', 5, advances, 'Show the first result or a meaningful causal step'),
    ):
        limit = min(seconds * joint.FPS, end)
        if not any(first_frame(event) < limit for event in candidates):
            flag(code, [0, limit], detail, 'reorder', plan['shots'][0]['id'])
    return {'schema_version': VERSION, 'media': media, 'frame_count': end,
            'duration_seconds': end / joint.FPS, 'design_sha256': digest(design),
            'inputs': inputs or {}, 'shots': shots, 'findings': findings,
            'first_result': next(iter(results), None), 'first_answer': next(iter(answers), None),
            'continuous_viewing': 'UNKNOWN', 'perceptual_listening': 'UNKNOWN',
            'sensory_status': 'UNKNOWN'}


def review_status(report, review):
    """Validate the existing independent QA's timed sensory assessments."""
    checks = review.get('pacing_checks', {})
    if not isinstance(checks, dict) or checks.keys() != set(CHECKS):
        return 'UNKNOWN'
    end = report['frame_count']
    statuses = set()
    for key in CHECKS:
        row = checks[key]
        if not text_fields(row, ('observation',)) or row.get('status') not in {'PASS', 'FAIL', 'UNKNOWN'}:
            return 'UNKNOWN'
        try:
            window(row.get('frames'), 0, end)
        except ValueError:
            return 'UNKNOWN'
        if key == 'opening_event' and row['frames'] != [0, min(2 * joint.FPS, end)]:
            return 'UNKNOWN'
        if key == 'knowledge_progression' and row['frames'] != [0, end]:
            return 'UNKNOWN'
        statuses.add(row['status'])
    if 'FAIL' in statuses:
        return 'FAIL'
    if (review.get('full_video_reviewed') is not True or review.get('full_audio_listened') is not True
            or len(statuses) != 1 or 'PASS' not in statuses):
        return 'UNKNOWN'
    return 'PASS'


def main():
    from .video_review import write_report
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('media', type=Path)
    parser.add_argument('blueprint', type=Path)
    parser.add_argument('--states', type=Path, help='JSON list of native state series with bound source receipts')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    document = json.loads(args.blueprint.read_text())
    plan = joint.validate(document['timeline'])
    media = joint.binding(args.media)
    joint.validate_rendered_film(joint.bound(media), plan)
    inputs = {'blueprint': joint.binding(args.blueprint)}
    measured = None
    if document.get('measured_timeline'):
        inputs['measured_timeline'] = document['measured_timeline']
        measured = joint.receipt(plan, inputs['measured_timeline'])
    states = []
    if args.states:
        inputs['state_manifest'] = joint.binding(args.states)
        states = load_states(inputs['state_manifest'])
    report = analyze(media, plan, document['pacing'], measured=measured, states=states, inputs=inputs)
    joint.bound(media)
    write_report(args.output, report)


if __name__ == '__main__':
    main()
