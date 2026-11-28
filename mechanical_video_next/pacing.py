"""Audit the existing picture, native motion and measured speech clocks."""

import argparse
import json
import math
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.common import digest, probe, run
from . import joint_timeline as joint
from .growth import CONTENT_REVIEW_FIELDS, OPENING_GOAL_SECONDS, OPPORTUNITIES
from .production_contract import (
    FORMAL_DURATION_FIELD, FORMAL_DURATION_VERSION, SHORT_FORMAL_DURATION_VERSION,
)

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


OPENING_WINDOWS = ((0, .25), (.25, .5), (.5, 1), (1, 1.5), (1.5, 2))
OPENING_QUESTIONS = {
    'first_frame': '第一帧因为什么有或没有观看价值？',
    'product': '第一眼靠什么识别产品？',
    'attention': '视线首先落在哪里？',
    'ordinary': '哪里像经常见到的普通展示？',
    'phenomenon': '哪个现象值得追看，为什么？',
    'hidden': '有哪些平时看不到的内容？',
    'change': '有哪些反常状态、变化或有价值的静态关系？',
    'narration': '旁白何时用哪个信息建立兴趣？',
    'subtitles': '字幕建立了哪个具体的知识期待？',
    'muted': '静音时什么信息仍然成立？',
    'phone': '手机尺寸下哪个细节还能看清？',
    'third_second': '仅依据 0–2 秒内已经出现在画面上的内容，为什么愿意或不愿意看第三秒？',
}


def opening_analysis(path, *, expected_sha=None):
    """Locate the opening on the actual picture clock and identify its audio track."""
    media = joint.binding(path)
    if expected_sha is not None and media['sha256'] != expected_sha:
        raise ValueError('Opening MP4 SHA-256 differs from the requested version')
    info = probe(media['path'])
    video = next((row for row in info['streams'] if row['codec_type'] == 'video'
                  and not row.get('disposition', {}).get('attached_pic')), None)
    if video is None:
        raise ValueError('Opening MP4 needs a playable picture stream')
    duration = float(video.get('duration') or info['format']['duration'])
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError('Opening MP4 needs a positive finite picture duration')
    audio = [row for row in info['streams'] if row['codec_type'] == 'audio']
    default_audio = next((row for row in audio if row.get('disposition', {}).get('default')),
                         audio[0] if audio else None)
    joint.bound(media)
    analysis = {
        'media': media, 'picture_duration': duration, 'picture_stream': video['index'],
        'audio_stream': default_audio['index'] if default_audio else None,
        'subtitle_streams': [row['index'] for row in info['streams'] if row['codec_type'] == 'subtitle'],
        'continuous_viewing': 'UNKNOWN', 'perceptual_listening': 'UNKNOWN',
    }
    analysis.update({key: {'time_range': [0, min(seconds, duration)], 'editorial_review': None}
                     for key, seconds in OPENING_GOAL_SECONDS.items()})
    analysis['knowledge_progression'] = {'time_range': [0, duration], 'editorial_review': None}
    analysis['retention_2s'].update(
        checkpoints=[[start, min(end, duration)] for start, end in OPENING_WINDOWS if start < duration],
        questions=OPENING_QUESTIONS.copy(),
    )
    return analysis


def _encode_playback(analysis, target, video_options, *, audio_codec='aac'):
    """Keep the displayed picture, selected dialogue and soft subtitles together."""
    directory = target.parent
    directory.mkdir(parents=True, exist_ok=True)
    media = analysis['media']
    path = joint.bound(media)
    mapping = ['-map', f"0:{analysis['picture_stream']}"]
    audio = analysis['audio_stream']
    if audio is not None:
        mapping.extend(['-map', f'0:{audio}'])
    for stream in analysis['subtitle_streams']:
        mapping.extend(['-map', f'0:{stream}'])
    with TemporaryDirectory(dir=directory) as staging:
        clip = Path(staging) / target.name
        run(['ffmpeg', '-v', 'error', '-xerror', '-i', path, *mapping, *video_options,
             '-c:v', 'libx264', '-crf', '17', '-c:a', audio_codec, '-c:s', 'copy',
             '-movflags', '+faststart', clip])
        run(['ffmpeg', '-v', 'error', '-xerror', '-i', clip, '-map', '0:v:0',
             '-map', '0:a:0?', '-f', 'null', '-'])
        joint.bound(media)
        clip.replace(target)
    return joint.binding(target)


def extract_opening(analysis, directory, *, through=None):
    """Make time-aligned playback clips for review and verify their decoded streams."""
    windows = dict(OPENING_GOAL_SECONDS)
    if through is not None:
        if not math.isfinite(through) or through <= 0:
            raise ValueError('--through must give positive finite seconds')
        windows['through'] = through
        analysis['through'] = {'time_range': [0, min(through, analysis['picture_duration'])]}
    media = analysis['media']
    for key, seconds in windows.items():
        end = analysis[key]['time_range'][1]
        target = directory / f"{Path(media['path']).stem}-{media['sha256'][:16]}-{seconds:g}s.mp4"
        # Use the input clock and accurate encoding rather than keyframe-only stream copy.
        analysis[key]['playback'] = _encode_playback(analysis, target, ['-t', str(end)])


def extract_phone_preview(analysis, directory):
    """Create a full playback proxy for checking composition at a narrow display size."""
    media = analysis['media']
    target = directory / f"{Path(media['path']).stem}-{media['sha256'][:16]}-phone.mp4"
    playback = _encode_playback(analysis, target, ['-vf', 'scale=384:-2', '-fps_mode', 'passthrough'],
                                audio_codec='copy')
    picture = next(row for row in probe(playback['path'])['streams'] if row['codec_type'] == 'video')
    analysis['phone_preview'] = {
        'playback': playback, 'resolution': [picture['width'], picture['height']],
    }


def producer_preview(path, directory):
    """Prepare full moving review material with the exported dialogue and sound."""
    analysis = opening_analysis(path)
    if analysis['audio_stream'] is None:
        raise ValueError('Episode preview needs its exported audio track')
    extract_phone_preview(analysis, directory)
    return analysis


def producer_observations(review, analysis):
    """Record Producer observations without assigning independent sensory acceptance."""
    duration = analysis['picture_duration']
    checked = opening_review(review, analysis['media'], duration)
    required = {'retention_2s', 'retention_5s', 'knowledge_progression'}
    if not required <= checked.keys():
        raise ValueError('Check the first two seconds, first answer and full preview')
    issues = review.get('issues', [])
    if not isinstance(issues, list) or any(
            not text_fields(issue, ('finding', 'next_step'))
            or issue.get('status') not in {'OPEN', 'FIXED'}
            or (issue['status'] == 'FIXED' and not text_fields(issue, ('before_sha256', 'recheck')))
            for issue in issues):
        raise ValueError('Record preview issues, repairs and what was checked again')
    for issue in issues:
        span = issue.get('time_range')
        if (not isinstance(span, list) or len(span) != 2
                or not all(type(value) in (int, float) for value in span)
                or not 0 <= span[0] < span[1] <= duration
                or issue.get('before_sha256') == analysis['media']['sha256']):
            raise ValueError('Locate the issue on the preview clock and identify any prior version')
    return dict(media=analysis['media'], observations=checked, issues=issues,
                continuous_viewing='UNKNOWN', perceptual_listening='UNKNOWN',
                audience_acceptance='UNKNOWN', platform_outcome='UNKNOWN')


def opening_review(review, media, duration):
    """Check provenance and evidence limits of a supplied editorial observation."""
    if not isinstance(review, dict) or review.get('media_sha256') != media['sha256']:
        raise ValueError('Opening review must bind the exact MP4 hash')
    result = {}
    for key, limit in dict(OPENING_GOAL_SECONDS, knowledge_progression=duration).items():
        if key not in review:
            continue
        row = review[key]
        if not text_fields(row, ('conclusion',)) or row.get('coverage') not in (
                'continuous_picture', 'continuous_av', 'sampled_picture', 'UNKNOWN'):
            raise ValueError(f'{key} requires an editorial conclusion and picture/listening coverage')
        references = row.get('evidence', [])
        if not isinstance(references, list) or (not references and row['coverage'] != 'UNKNOWN'):
            raise ValueError(f'{key} requires timed evidence for observed coverage')
        end = min(limit, duration)
        for ref in references:
            times = ref.get('time_range') if isinstance(ref, dict) else None
            if (not text_fields(ref, ('observation',)) or not isinstance(times, list) or len(times) != 2
                    or any(type(value) not in (float, int) or not math.isfinite(value) for value in times)
                    or not 0 <= times[0] <= times[1] <= end
                    or times[0] == times[1] == end):
                raise ValueError(f'{key} evidence falls outside its review window')
        if row['coverage'] in ('continuous_picture', 'continuous_av'):
            covered = 0
            for ref in sorted(references, key=lambda item: item['time_range']):
                start, stop = ref['time_range']
                if start > covered:
                    break
                covered = max(covered, stop)
            if covered < end:
                raise ValueError(f'{key} continuous coverage requires evidence spanning the window')
        if key == 'retention_2s' and row['coverage'] != 'UNKNOWN':
            if not text_fields(row.get('answers'), OPENING_QUESTIONS):
                raise ValueError('Two-second review requires answers to the opening questions (UNKNOWN where needed)')
            cited = row.get('third_second_evidence')
            if (not isinstance(cited, list)
                    or any(type(index) is not int or not 0 <= index < len(references) for index in cited)
                    or not cited and row['answers']['third_second'] != 'UNKNOWN'):
                raise ValueError('Third-second judgment must cite evidence from the two-second window')
            if 'revision' in row and not text_fields(row['revision'], ('focus', 'method', 'candidate')):
                raise ValueError('Opening revision requires a focus, method and candidate design')
        if key == 'knowledge_progression':
            def observed(point):
                return (text_fields(point, ('reason',))
                        and type(point.get('evidence')) is int
                        and 0 <= point['evidence'] < len(references)
                        and row['coverage'] != 'UNKNOWN')

            opportunities = row.get('opportunities', [])
            if not isinstance(opportunities, list) or any(
                not observed(point) or point.get('kind') not in OPPORTUNITIES
                for point in opportunities
            ):
                raise ValueError('Potential interaction opportunities require observed, timed evidence')
            takeaways = row.get('takeaways', {})
            if not isinstance(takeaways, dict) or any(
                field not in CONTENT_REVIEW_FIELDS or (point != 'UNKNOWN' and (
                    not observed(point) or (field == 'early_knowledge'
                    and references[point['evidence']]['time_range'][1] > 10)
                )) for field, point in takeaways.items()
            ):
                raise ValueError('Content takeaways require observed, timed evidence or UNKNOWN')
        result[key] = row
    return result


def opening_arguments(parser):
    parser.add_argument('media', type=Path, help='Actual opening workprint or final MP4')
    parser.add_argument('--sha256', help='Require this source version')
    parser.add_argument('--clips', type=Path, help='Write playable two-, five- and ten-second excerpts')
    parser.add_argument('--phone-preview', type=Path, help='Write full playback at 384 pixels wide')
    parser.add_argument('--through', type=float, help='With --clips, also export through this observation time')
    parser.add_argument('--review', type=Path, help='Import a timed editorial observation for these exact bytes')
    parser.add_argument('--output', type=Path, help='Write the analysis JSON here')


def run_opening(args):
    from .video_review import write_report

    report = opening_analysis(args.media, expected_sha=args.sha256)
    if args.review:
        authored = json.loads(args.review.read_text())
        for key, observation in opening_review(authored, report['media'], report['picture_duration']).items():
            report[key]['editorial_review'] = observation
    if args.clips:
        extract_opening(report, args.clips, through=args.through)
    elif args.through is not None:
        raise ValueError('--through requires --clips')
    if args.phone_preview:
        extract_phone_preview(report, args.phone_preview)
    if args.output:
        if args.output.resolve() == joint.bound(report['media']).resolve():
            raise ValueError('Analysis output must differ from input media')
        write_report(args.output, report)
    else:
        print(json.dumps(report, ensure_ascii=False, indent=2))


def enabled(document):
    return document.get(FORMAL_DURATION_FIELD) in {
        SHORT_FORMAL_DURATION_VERSION, FORMAL_DURATION_VERSION,
    }


def text_fields(row, fields):
    return isinstance(row, dict) and all(isinstance(row.get(key), str) and row[key].strip() for key in fields)


def validate_brief(brief, task):
    seconds = brief.get('shortest_complete_seconds') if isinstance(brief, dict) else None
    maximum = math.inf if task.get(FORMAL_DURATION_FIELD) == FORMAL_DURATION_VERSION else 300
    if (not text_fields(brief, BRIEF) or type(seconds) not in (int, float)
            or not math.isfinite(seconds) or not 0 < seconds <= maximum):
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
        for frames in activity:
            cover(frames)
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
        ('opening_event_missing', 2, early, 'Locate the planned opening event or review the value of the opening state'),
        ('early_progress_missing', 5, advances, 'Show the first result or a meaningful causal step'),
    ):
        limit = min(seconds * joint.FPS, end)
        if not any(first_frame(event) < limit for event in candidates):
            flag(code, [0, limit], detail, 'reorder', plan['shots'][0]['id'])
    return {'schema_version': VERSION, 'media': media, 'frame_count': end,
            'duration_seconds': end / joint.FPS, 'design_sha256': digest(design),
            'inputs': inputs or {}, 'shots': shots, 'findings': findings,
            'first_result': next(iter(results), None), 'first_answer': next(iter(answers), None),
            'retention_2s': {'purpose': 'opening interest', 'status': 'UNKNOWN',
                             'time_range': [0, min(2, end / joint.FPS)]},
            'retention_5s': {'purpose': 'opening continuation', 'status': 'UNKNOWN',
                             'time_range': [0, min(5, end / joint.FPS)]},
            'continuous_viewing': 'UNKNOWN', 'perceptual_listening': 'UNKNOWN',
            'sensory_status': 'UNKNOWN'}


def episode_diagnostics(media, document, count, measured, intervals):
    from .video_review import scan_media

    plan = document['plan']
    cuts = [cut for cut in plan['shots'] if cut['end_frame'] <= count]
    authored = document.get('pacing')
    measured_rows = [row for row in measured['speech'] if row['start_sample'] < count * joint.SAMPLES_PER_FRAME]
    frames = [cut['end_frame'] - cut['start_frame'] for cut in cuts]
    report = scan_media(media)
    report.update(frame_count=count, shot_count=len(cuts), average_shot_seconds=count / len(cuts) / joint.FPS,
                  shot_seconds=[length / joint.FPS for length in frames],
                  narration_coverage=sum(min(row['end_sample'], count * joint.SAMPLES_PER_FRAME) - row['start_sample']
                                         for row in measured_rows) / (count * joint.SAMPLES_PER_FRAME),
                  continuous_viewing='UNKNOWN', perceptual_listening='UNKNOWN')
    if authored:
        states = []
        for cut, interval in zip(cuts, intervals, strict=True):
            motion = interval.get('evaluated_motion')
            if not motion or not cut.get('action_views'):
                continue
            for action in cut['action_views']:
                for channel, samples in motion['samples'].items():
                    states.append(dict(shot_id=cut['id'], action_id=action, id=channel,
                                       samples=samples[::motion['substeps']]))
        result = analyze(media, dict(plan, shots=cuts, frame_count=count),
                         {cut['id']: authored[cut['id']] for cut in cuts},
                         measured={'speech': measured_rows}, states=states)
        starts = sorted(span['frames'][0] for shot in result['shots'] for span in shot['information_increments'])
        report['discovery_gaps_seconds'] = [(end - start) / joint.FPS
                                            for start, end in zip([0, *starts], [*starts, count])]
        report['direction'] = result
    return report


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
