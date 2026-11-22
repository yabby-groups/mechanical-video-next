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


GOALS_V2 = {
    'retention': ('product_opening', 'first_answer', 'information_progression', 'final_payoff'),
    'like': ('counterintuitive_observation', 'mechanical_answer', 'memorable_discovery'),
    'save': ('knowledge_summary', 'product_mechanism_mapping', 'replay_value'),
    'comment': ('grounded_discussion',),
    'follow': ('complete_answer', 'series_value'),
}
GOAL_FIELDS = ('goal_id', 'knowledge_point', 'reference_id', 'shot_id', 'time_range',
               'planned_action', 'visual_proof', 'narration', 'verification_method',
               'actual_media_evidence', 'qa_status')


def goal_schema(data):
    return GOALS_V2 if data.get('growth_policy_version') == 2 else GOALS


def validate_growth_design(design):
    """The Producer's Treatment gives one concrete decision for each goal."""
    if (not isinstance(design, dict) or design.keys() != GOALS_V2.keys()
            or not all(isinstance(decision, str) and decision.strip() for decision in design.values())):
        raise ValueError('Treatment requires retention, like, save, comment and follow decisions')


def validate_goal_bindings(data):
    """Validate plans, not audience understanding or predicted platform results."""
    from .viral import evidence_exists
    from .joint_timeline import enabled as joint, shot_narration
    ids = {s['shot_id']: s for s in data.get('shots', [])}
    references = {r.get('reference_id', r.get('id')) for r in data.get('reference_principles', [])}
    references.update(r.get('reference_id') for r in data.get('evidence_map', []))
    seen = set()
    goals = data.get('growth_goals', {})
    for category, keys in GOALS_V2.items():
        group = goals.get(category, {})
        for key in keys:
            rows = group.get(key)
            # A missing honest discussion opportunity is a recorded optimization
            # gap, never permission to manufacture controversy or claim PASS.
            if category == 'comment' and isinstance(rows, dict) and rows.get('qa_status') == 'UNKNOWN' and rows.get('gap_reason'):
                continue
            rows = rows if isinstance(rows, list) else [rows]
            if not rows:
                raise ValueError('Empty growth decision: '+key)
            for row in rows:
                if not isinstance(row, dict) or any(k not in row for k in GOAL_FIELDS):
                    raise ValueError('Growth v2 requires complete goal binding: '+key)
                optional = {'actual_media_evidence', 'qa_status'}
                if joint(data):
                    optional.add('narration')
                if any(not row[k] for k in GOAL_FIELDS if k not in optional):
                    raise ValueError('Empty observable growth binding: '+key)
                if row['goal_id'] in seen:
                    raise ValueError('Duplicate growth goal_id')
                seen.add(row['goal_id'])
                shot = ids.get(row['shot_id'])
                t = row['time_range']
                if (not shot or category not in shot['related_growth_goal'] or not isinstance(t,list)
                    or len(t)!=2 or not all(finite(x) for x in t)
                    or not shot['start_time'] <= t[0] < t[1] <= shot['end_time']):
                    raise ValueError('Growth shot/time binding mismatch: '+key)
                if row['reference_id'] not in references:
                    raise ValueError('Growth reference is not a mapped source')
                narration = shot_narration(data, shot)
                if row['narration'] not in (narration or ([None] if joint(data) else [])):
                    raise ValueError('Growth narration differs from shot')
                if row.get('qa_status') == 'PASS' and not evidence_exists(row.get('actual_media_evidence')):
                    raise ValueError('Growth PASS requires actual media evidence')
                if row.get('qa_status') not in {'PLANNED','UNKNOWN','FAIL','PASS'}:
                    raise ValueError('Invalid growth qa_status')
                if key == 'product_opening' and (shot is not data['shots'][0] or t[1] > 5):
                    raise ValueError('Product/action/why/payoff opening must occur within five seconds')
                if key == 'grounded_discussion':
                    if row.get('discussion_relation') != 'same-product-observable-question' or row.get('misleading') is not False:
                        raise ValueError('Comment requires relevant non-misleading discussion')
                if key == 'complete_answer' and (row.get('answer_withheld') is not False or row.get('answer_complete') is not True):
                    raise ValueError('Follow cannot rely on withholding the answer')
                if row.get('next_episode') and not evidence_exists(row.get('plan_evidence')):
                    raise ValueError('Next episode requires real plan evidence')
    answer = goals['retention']['first_answer']
    answer_time = goals['retention'].get('first_answer_time')
    if not isinstance(answer,dict) or not finite(answer_time) or not answer['time_range'][0] <= answer_time < answer['time_range'][1]:
        raise ValueError('First answer time must be inside answer observation')
    progression = goals['retention']['information_progression']
    progression = progression if isinstance(progression,list) else [progression]
    if {r['shot_id'] for r in progression} != set(ids):
        raise ValueError('Information progression must cover every shot')
    return data['duration_seconds']


def finite(value):
    return not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value)


def shot_requirements(shot, document=None):
    from .joint_timeline import enabled as joint, shot_narration
    if joint(document or {}):
        return {k: shot[k] for k in SHOT_FIELDS if k != 'narration'} | {'narration': shot_narration(document, shot)}
    return {k: shot[k] for k in SHOT_FIELDS}


def duration_bounds(data):
    """Keep the longform default; trace an explicitly requested concise recut."""
    from .production_contract import FORMAL_DURATION, formal_duration_enabled
    if formal_duration_enabled(data):
        return FORMAL_DURATION
    from .joint_timeline import enabled as joint
    if joint(data):
        return 1 / 30, math.inf
    from .production_contract import creative_first, CREATIVE_DURATION
    if creative_first(data):
        return CREATIVE_DURATION
    override = data.get('duration_policy_override')
    if override is None:
        return 120, 300
    from .viral import evidence_exists
    if (not isinstance(override, dict)
            or override.get('kind') != 'user-requested-concise-recut'
            or not evidence_exists(override.get('evidence'))):
        raise ValueError('Concise recut requires recorded user instruction evidence')
    return 1, 300


def validate_contract(data, requested=None):
    shots = data.get('shots', [])
    duration = data.get('duration_seconds')
    minimum, maximum = duration_bounds(data)
    if not finite(duration) or not minimum <= duration <= maximum:
        raise ValueError(f'Content duration must be {minimum}–{maximum} seconds')
    if requested is not None and abs(duration-requested) > 1/30:
        raise ValueError('Blueprint differs from requested duration')
    if not data.get('duration_reason') or not shots:
        raise ValueError('Knowledge-driven duration_reason and shots required')
    ids = {s['shot_id']: s for s in shots}
    end = 0
    information = set()
    from .joint_timeline import enabled as joint
    nonessential = {'start_time', 'end_time'} | ({'narration'} if joint(data) else set())
    for shot in shots:
        if any(not shot.get(k) for k in SHOT_FIELDS if k not in nonessential):
            raise ValueError('Shot lacks teaching, proof or duration requirements')
        a, b = shot.get('start_time'), shot.get('end_time')
        if not finite(a) or not finite(b) or a != end or b <= a or shot.get('time_range') != [a, b]:
            raise ValueError('Teaching timeline must match contiguous executable time_range')
        end = b
        if shot['new_information'] in information:
            raise ValueError('Repeated new_information: deepen explanation or remove shot')
        information.add(shot['new_information'])
        if not isinstance(shot['related_growth_goal'], list) or not set(shot['related_growth_goal']) <= goal_schema(data).keys():
            raise ValueError('Unknown related_growth_goal')
    if end != duration or len(ids) != len(shots):
        raise ValueError('Duration or shot IDs mismatch')
    if data.get('growth_policy_version') == 2:
        return validate_goal_bindings(data)
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
                    bridge = goals.get('following', {}).get('next_episode_bridge', {})
                    if (len(shots) < 2 or shot is not shots[-2]
                            or not isinstance(bridge, dict)
                            or bridge.get('shot_id') != shots[-1]['shot_id']):
                        raise ValueError('Final payoff must end the explanation before any final bridge')
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
    if blueprint.get('growth_policy_version') == 2:
        return validate_actual_goals(blueprint, report)
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
    minimum, maximum = duration_bounds(blueprint)
    for item in media:
        if Path(item['path']).suffix.lower() != '.mp4':
            continue
        result = subprocess.run(['ffprobe', '-v', 'error', '-show_format', '-of', 'json', item['path']],
                                capture_output=True, text=True, check=True)
        duration = float(json.loads(result.stdout)['format']['duration'])
        if not finite(duration) or not minimum <= duration <= maximum or abs(duration-blueprint['duration_seconds']) > .1:
            raise ValueError('Actual media duration differs from content contract')


def validate_actual_goals(blueprint, report):
    """Reject plan-only PASS, stale clips, missing sensory review and wrong actions.

    This verifies recorded independent observations, not real viewer behavior.
    Independent sensory review remains a capability-bound external requirement.
    """
    from .viral import evidence_exists
    if report.get('independent_reviewer') is not True or not report.get('reviewer_thread_id'):
        raise ValueError('Growth requires independent actual-media reviewer')
    if not evidence_exists(report.get('media')):
        raise ValueError('Growth requires existing hash-bound actual media')
    check_media_duration(blueprint, report['media'])
    import json
    import subprocess
    for item in report['media']:
        if not item['path'].lower().endswith('.mp4'):
            raise ValueError('Growth requires complete MP4 evidence')
        result = subprocess.run(['ffprobe','-v','error','-show_streams','-of','json',item['path']],
                                capture_output=True,text=True,check=True)
        kinds = {stream.get('codec_type') for stream in json.loads(result.stdout).get('streams',[])}
        if not {'video','audio'} <= kinds:
            raise ValueError('Growth requires actual video and narration audio streams')
    media = {m['sha256'] for m in report['media']}
    shots = {shot['shot_id']:shot for shot in blueprint['shots']}
    for category, keys in GOALS_V2.items():
        checks = report.get(category+'_checks', [])
        for key in keys:
            plans = blueprint['growth_goals'][category][key]
            plans = plans if isinstance(plans,list) else [plans]
            if any(p.get('gap_reason') for p in plans):
                raise ValueError('Growth optimization gap remains UNKNOWN: '+key)
            for plan in plans:
                for digest in media:
                    matching = [r for r in checks if r.get('goal_id') == plan['goal_id']
                                and r.get('goal') == key and r.get('media_sha256') == digest]
                    if len(matching) != 1:
                        raise ValueError('Missing or duplicate actual growth observation for each media: '+key)
                    row = matching[0]
                    t = row.get('time_range')
                    observations = row.get('observed', {})
                    shot = shots[plan['shot_id']]
                    heard = ('heard_narration' in observations and observations['heard_narration'] is None
                             if plan.get('narration') is None else bool(observations.get('heard_narration')))
                    if (row.get('status') != 'PASS' or row.get('shot_id') != plan['shot_id']
                        or not isinstance(t,list) or len(t)!=2 or not all(finite(v) for v in t)
                        or not shot['start_time'] <= t[0] <= plan['time_range'][0] < plan['time_range'][1] <= t[1] <= shot['end_time']
                        or row.get('continuous_viewing') is not True or row.get('listening') is not True
                        or not evidence_exists(row.get('actual_media_evidence'))
                        or not heard or not all(observations.get(k) for k in ('visible_action','knowledge_demonstrated'))
                        or observations.get('action_matches_plan') is not True
                        or observations.get('narration_matches_action') is not True
                        or observations.get('goal_realized') is not True):
                        raise ValueError('Growth QA FAIL/UNKNOWN or absent actual visual/audio proof: '+key)
                    _validate_observation_receipts(row, plan, report['reviewer_thread_id'])
    return True


def _validate_observation_receipts(row, plan, reviewer):
    """Review records themselves bind observations to exact content and coverage.

    A hash-bound unrelated photograph or note cannot attest continuous viewing.
    These are independent-review receipts, not an automated perceptual oracle.
    """
    import json
    from pathlib import Path
    covered = []
    for ref in row['actual_media_evidence']:
        try:
            receipt = json.loads(Path(ref['path']).read_text())
        except (OSError, ValueError, UnicodeError):
            raise ValueError('Growth evidence must be a readable actual-media review receipt') from None
        t = receipt.get('time_range') if isinstance(receipt,dict) else None
        if (not isinstance(receipt,dict)
            or receipt.get('media_sha256') != row['media_sha256']
            or receipt.get('goal_id') != plan['goal_id'] or receipt.get('shot_id') != plan['shot_id']
            or receipt.get('reviewer_thread_id') != reviewer
            or receipt.get('independent_reviewer') is not True
            or receipt.get('continuous_viewing') is not True or receipt.get('listening') is not True
            or receipt.get('status') != 'PASS' or receipt.get('observed') != row['observed']
            or not isinstance(t,list) or len(t)!=2 or not all(finite(v) for v in t)
            or not row['time_range'][0] <= t[0] < t[1] <= row['time_range'][1]):
            raise ValueError('Growth actual evidence does not bind reviewed media, goal, observations and timecodes')
        covered.append(t)
    cursor = plan['time_range'][0]
    for a,b in sorted(covered):
        if b <= cursor:
            continue
        if a > cursor:
            break
        cursor = b
    if cursor < plan['time_range'][1]:
        raise ValueError('Growth actual evidence does not cover the complete planned action')
