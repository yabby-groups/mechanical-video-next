"""Versioned executable content contracts; no audience-performance predictions."""
import math

SHOT_FIELDS = ('section_id', 'start_time', 'end_time', 'teaching_goal', 'new_information',
               'mechanical_action', 'narration', 'visual_proof', 'audience_takeaway',
               'duration_reason', 'related_growth_goal')
GOALS = {
    'retention': ('opening_action', 'opening_question', 'first_answer', 'information_progression'),
    'engagement': ('aha_moment', 'mechanism_proof_shot', 'one_sentence_takeaway'),
    'following': ('series_value', 'final_payoff', 'next_episode_bridge'),
}


def finite(value):
    return not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value)


def shot_requirements(shot):
    return {k: shot[k] for k in SHOT_FIELDS}


def validate_contract(data, requested=None):
    shots = data.get('shots', [])
    duration = data.get('duration_seconds')
    if not finite(duration) or not 120 <= duration <= 300:
        raise ValueError('New content duration must be 120–300 seconds')
    if requested is not None and abs(duration-requested) > 1/30:
        raise ValueError('Blueprint differs from requested duration')
    if not data.get('duration_reason') or not shots:
        raise ValueError('Knowledge-driven duration_reason and shots required')
    ids = {s['shot_id']: s for s in shots}
    end = 0
    information = set()
    for shot in shots:
        if any(not shot.get(k) for k in SHOT_FIELDS if k not in {'start_time', 'end_time'}):
            raise ValueError('Shot lacks teaching, proof or duration requirements')
        a, b = shot.get('start_time'), shot.get('end_time')
        if not finite(a) or not finite(b) or a != end or b <= a or shot.get('time_range') != [a, b]:
            raise ValueError('Teaching timeline must match contiguous executable time_range')
        end = b
        if shot['new_information'] in information:
            raise ValueError('Repeated new_information: deepen explanation or remove shot')
        information.add(shot['new_information'])
        if not isinstance(shot['related_growth_goal'], list) or not set(shot['related_growth_goal']) <= GOALS.keys():
            raise ValueError('Unknown related_growth_goal')
    if end != duration or len(ids) != len(shots):
        raise ValueError('Duration or shot IDs mismatch')
    goals = data.get('growth_goals', {})
    # Every decision has the same observable binding, rather than a parallel slogan contract.
    for category, keys in GOALS.items():
        group = goals.get(category, {})
        for key in keys:
            rows = group.get(key)
            rows = rows if isinstance(rows, list) else [rows]
            if not rows:
                raise ValueError('Empty growth decision')
            for row in rows:
                if not isinstance(row, dict) or any(not row.get(k) for k in
                        ('text', 'shot_id', 'knowledge_point', 'mechanical_action', 'narration', 'observable', 'verification_method')):
                    raise ValueError('Growth decision requires observable shot binding: '+key)
                shot = ids.get(row['shot_id'])
                if shot is None or category not in shot['related_growth_goal'] or row['narration'] not in shot['narration']:
                    raise ValueError('Growth shot/narration binding mismatch')
                if key == 'next_episode_bridge':
                    from .viral import evidence_exists
                    if not evidence_exists(row.get('plan_evidence')):
                        raise ValueError('Next episode requires real plan evidence')
                if key == 'opening_action' and shot is not shots[0]:
                    raise ValueError('Opening action must bind first shot')
                if key == 'final_payoff' and shot is not shots[-1]:
                    raise ValueError('Final payoff must bind last shot')
    t = goals['retention'].get('first_answer_time')
    answer = ids[goals['retention']['first_answer']['shot_id']]
    if not finite(t) or not answer['start_time'] <= t < answer['end_time']:
        raise ValueError('First answer time must be inside answer shot')
    if {x['shot_id'] for x in goals['retention']['information_progression']} != set(ids):
        raise ValueError('Information progression must cover every shot')
    return duration


def validate_media_checks(blueprint, report):
    """Require actual reviewed media, bounded timecodes and capabilities for each goal."""
    validate_contract(blueprint)
    media = {m['sha256'] for m in report.get('media', [])}
    ids = {s['shot_id']: s for s in blueprint['shots']}
    for category, keys in GOALS.items():
        rows = report.get(category+'_checks', [])
        if {r.get('goal') for r in rows} != set(keys):
            raise ValueError('Missing growth media checks: '+category)
        for goal in keys:
            decision = blueprint['growth_goals'][category][goal]
            decisions = decision if isinstance(decision, list) else [decision]
            if {r.get('shot_id') for r in rows if r.get('goal') == goal} != {d['shot_id'] for d in decisions}:
                raise ValueError('Growth QA must cover every mapped shot')
        for row in rows:
            shot = ids.get(row.get('shot_id'))
            decision = blueprint['growth_goals'][category][row['goal']]
            decisions = decision if isinstance(decision, list) else [decision]
            if row.get('shot_id') not in {d['shot_id'] for d in decisions}:
                raise ValueError('QA goal does not match planned shot')
            t = row.get('time_range', [])
            if (row.get('status') != 'PASS' or not row.get('evidence') or not shot
                    or row.get('media_sha256') not in media or len(t) != 2
                    or not all(finite(v) for v in t)
                    or not shot['start_time'] <= t[0] < t[1] <= shot['end_time']
                    or row.get('continuous_viewing') is not True or row.get('listening') is not True):
                raise ValueError('Growth QA FAIL/UNKNOWN or unbound media evidence')


def check_media_duration(blueprint, media):
    """Measure deliverables; blueprint timing alone is not a duration check."""
    import json
    import subprocess
    from pathlib import Path
    for item in media:
        if Path(item['path']).suffix.lower() != '.mp4':
            continue
        result = subprocess.run(['ffprobe', '-v', 'error', '-show_format', '-of', 'json', item['path']],
                                capture_output=True, text=True, check=True)
        duration = float(json.loads(result.stdout)['format']['duration'])
        if not finite(duration) or not 120 <= duration <= 300 or abs(duration-blueprint['duration_seconds']) > .1:
            raise ValueError('Actual media duration differs from longform contract')
