"""Bounded research planning and evidence-led screening; no scraper or predictor."""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
from scripts.common import filehash
import json
import math
from pathlib import Path
from urllib.parse import quote

WEIGHTS = {'relevance': .25, 'engagement': .20, 'opening': .20,
           'mechanical_clarity': .20, 'feasibility': .15}
REFERENCE_MIX = {'A': .50, 'B': .30, 'C': .20}
METRICS = ('followers', 'likes', 'comments', 'saves', 'shares', 'views')
BLUEPRINT_FIELDS = {'core_question', 'opening_0_3', 'first_motion_seconds',
                    'disassembly_order', 'closeups', 'annotations', 'narration_structure',
                    'sound_design', 'causal_ending', 'shots', 'reference_principles',
                    'original_topic', 'knowledge_goals', 'duration_seconds', 'pacing',
                    'voice_requirements', 'subtitle_requirements', 'creative_decisions',
                    'qa_requirements', 'sources'}


def now():
    return datetime.now(timezone.utc).isoformat()


def date(value):
    if not isinstance(value, str):
        raise ValueError('Timestamp must be an ISO string')
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('Timestamp needs timezone')
    return parsed


def save(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')


def identity(url):
    # Shared normalization avoids scoring the same work separately on mobile,
    # modal, short-form and tracking variants. No network link resolution.
    from .reference_library import canonical_video_id
    return canonical_video_id(url)


def evidence_exists(items):
    if not isinstance(items, list) or not items:
        return False
    for e in items:
        if not isinstance(e, dict) or not e.get('path') or not e.get('sha256'):
            return False
        p = Path(e['path'])
        try:
            actual = filehash(p)
        except OSError:
            return False
        if actual != e['sha256']:
            return False
    return True


def full_view(c):
    v = c.get('viewing') or {}
    return (v.get('status') == 'FULL_VIDEO_VIEWED'
            and v.get('continuous_visual') is True
            and isinstance(c.get('duration_seconds'), (int, float))
            and c['duration_seconds'] > 0
            and isinstance(v.get('covered_seconds'), (int, float))
            and v['covered_seconds'] >= c['duration_seconds']
            and evidence_exists(v.get('evidence')))


def observed_reference(c):
    kind = c.get('source_kind', 'video')
    if kind == 'video':
        return full_view(c)
    viewing = c.get('viewing') or {}
    expected = {'image': 'IMAGE_INSPECTED', 'diagram': 'IMAGE_INSPECTED',
                'structure': 'STRUCTURE_READ'}.get(kind)
    return bool(expected and viewing.get('status') == expected
                and evidence_exists(viewing.get('evidence')) and c.get('observations'))


def breakout(c, observed):
    f, likes = c.get('followers'), c.get('likes')
    if f is None or likes is None or not c.get('published_at'):
        return None
    if not c.get('metrics_evidence') or not evidence_exists(c.get('evidence')):
        return None
    age = observed - date(c['published_at'])
    if not timedelta(0) <= age <= timedelta(days=90) or likes <= 1000:
        return None
    return next((cap for cap in (10000, 50000, 100000) if f < cap), None)


def score_candidate(c):
    scores, refs = c.get('scores', {}), c.get('scores_evidence', {})
    available = {}
    for key, weight in WEIGHTS.items():
        value = scores.get(key)
        if value is None or not refs.get(key):
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 100:
            raise ValueError('Score must be null or finite 0–100')
        if key in {'opening', 'mechanical_clarity'} and not full_view(c):
            continue
        if key == 'engagement' and (c.get('followers') is None or c.get('likes') is None
                                    or not c.get('metrics_evidence')
                                    or not evidence_exists(c.get('evidence'))):
            continue
        available[key] = value
    coverage = sum(WEIGHTS[k] for k in available)
    return {'score': round(sum(WEIGHTS[k]*v for k, v in available.items())/coverage, 3) if coverage else None,
            'coverage': round(coverage, 3), 'available': available,
            'normalized_weights': {k: round(WEIGHTS[k]/coverage, 6) for k in available}}


def analyze(data):
    observed = date(data['observed_at'])
    rows = data['candidates']
    if len(rows) > 30:
        raise ValueError('Default candidate budget exceeded (30)')
    unique, seen, duplicates = [], set(), []
    ids = set()
    for source in rows:
        c = dict(source)
        if c.get('source_kind', 'video') not in {'video', 'image', 'diagram', 'structure'}:
            raise ValueError('Unsupported reference source_kind')
        c.setdefault('reference_class', 'A')
        if c['reference_class'] not in REFERENCE_MIX:
            raise ValueError('Reference class must be A, B or C')
        if not c.get('id') or c['id'] in ids:
            raise ValueError('Unique nonempty candidate IDs required')
        ids.add(c['id'])
        local_source = evidence_exists(c.get('source_files'))
        key = (identity(c['url']) if c.get('url') else
               'local:' + c['source_files'][0]['sha256'] if local_source else 'unresolved:' + c['id'])
        c['original_url_resolved'] = bool(c.get('url'))
        c['source_resolved'] = (bool(c.get('url')) or local_source) and (not c.get('source_files') or local_source)
        if key in seen or c.get('duplicate_of'):
            duplicates.append(c['id'])
            continue
        seen.add(key)
        date(c['observed_at'])
        for field in METRICS:
            c.setdefault(field, None)
            v = c[field]
            if v is not None and (isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0):
                raise ValueError('Metrics must be nonnegative real values or null')
        c['viewing'] = c.get('viewing') or {'status': 'VIDEO_NOT_VIEWED'}
        c['breakout_follower_cap'] = breakout(c, observed)
        c['screening'] = score_candidate(c)
        unique.append(c)
    deep = [c for c in unique if c.get('deep_analysis')]
    if len(deep) > 10:
        raise ValueError('Default deep-analysis budget exceeded (10)')
    eligible = [c for c in deep if (c.get('directly_related') is True if c['reference_class'] == 'A'
                                   else bool(c.get('transfer_rationale')))
                and c['source_resolved'] and observed_reference(c) and c.get('style')]
    # Popularity is a preference, never an admission gate. An observed physical
    # demonstration can be recreated in CAD without public engagement metrics.
    eligible.sort(key=lambda c: (c['breakout_follower_cap'] is None,
                                c['breakout_follower_cap'] or 100001,
                                -c['screening']['coverage'], -(c['screening']['score'] or 0)))
    selected, styles = [], set()
    for category, quota in [('A', 5), ('B', 3), ('C', 2)]:
        for c in [item for item in eligible if item['reference_class'] == category]:
            if c['style'] not in styles and sum(item['reference_class'] == category and item['id'] in selected for item in eligible) < quota:
                selected.append(c['id']); styles.add(c['style'])
    # Insufficient categories remain a documented gap; never pad with unrelated work.
    counts = {k: sum(c['id'] in selected and c['reference_class'] == k for c in eligible) for k in REFERENCE_MIX}
    primary_candidates = [c['id'] for c in eligible if c['id'] in selected
                          and c['reference_class'] == 'A']
    primary = data.get('primary_reference_id') or next(iter(primary_candidates), None)
    # Recreation needs one qualifying primary. Supplementary categories are not
    # prerequisites for reproducing an already observed, qualifying video.
    ready = primary in primary_candidates
    primary_row = next((c for c in eligible if c['id'] == primary), None) if ready else None
    primary_kind = (('verified-breakout' if primary_row['breakout_follower_cap'] is not None
                     else 'observed-reference') if primary_row else None)
    return {'schema_version': 1, 'topic': data['topic'], 'observed_at': data['observed_at'],
            'task_id': data.get('task_id'),
            'primary_reference_id': primary,
            'primary_reference_kind': primary_kind,
            'breakout_required': False,
            'status': 'READY' if ready else 'BLOCKED', 'weights': WEIGHTS,
            'model_kind': 'internal_screening_heuristic_not_platform_algorithm',
            'candidates': unique, 'duplicates': duplicates, 'selected_ids': selected,
            'reference_mix': {'target': REFERENCE_MIX, 'actual_counts': counts, 'target_counts': {'A': 5, 'B': 3, 'C': 2}},
            'budget': {'candidates': len(rows), 'deep_analysis': len(deep), 'limits': [30, 10]},
            'blockers': [] if ready else ['Need observed same-topic video, image, diagram or structure evidence; popularity and source format are not production requirements'],
            'elapsed_seconds': data.get('elapsed_seconds'), 'human_interventions': None,
            'rework_reduction': None, 'tokens': None, 'cost': None}


def validate_viral_analysis(payload):
    calculated = analyze(payload)
    if payload.get('status') != 'READY' or calculated['status'] != 'READY':
        raise ValueError('Viral research evidence is not READY')
    if payload.get('selected_ids') != calculated['selected_ids']:
        raise ValueError('Selected references do not match evidence-led screening')
    if payload.get('primary_reference_id') != calculated['primary_reference_id']:
        raise ValueError('Primary reference does not match observed reference selection')
    if payload.get('primary_reference_kind') != calculated['primary_reference_kind']:
        raise ValueError('Reference kind must distinguish observed material from verified breakout metrics')


VIDEO_VIEWING = {'FULL_VIDEO_VIEWED', 'PARTIAL_VIDEO_VIEWED', 'SCREENSHOTS_ONLY',
                 'PAGE_ONLY', 'VIDEO_NOT_VIEWED'}


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _seconds(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def _viewed_video(candidate):
    viewing = candidate['viewing']
    duration = candidate.get('duration_seconds')
    if viewing['status'] == 'FULL_VIDEO_VIEWED':
        covered = viewing.get('covered_seconds')
        return (_seconds(duration) and _seconds(covered) and covered == duration
                and full_view(candidate))
    if viewing['status'] != 'PARTIAL_VIDEO_VIEWED':
        return False
    ranges = viewing.get('time_ranges')
    return (isinstance(ranges, list) and bool(ranges)
            and all(isinstance(span, list) and len(span) == 2
                    and all(_seconds(t) for t in span) and span[0] < span[1]
                    and (duration is None or _seconds(duration) and span[1] <= duration)
                    for span in ranges)
            and evidence_exists(viewing.get('evidence')))


def reusable_expression(candidate):
    observations = candidate.get('observations')
    viewing = candidate.get('viewing') or {}
    return (candidate.get('source_kind', 'video') == 'video'
            and isinstance(viewing, dict)
            and viewing.get('status') in ('FULL_VIDEO_VIEWED', 'PARTIAL_VIDEO_VIEWED')
            and (viewing['status'] == 'FULL_VIDEO_VIEWED' or _text(viewing.get('limitation')))
            and isinstance(observations, list) and bool(observations) and all(map(_text, observations))
            and _text(candidate.get('transfer_rationale')) and _viewed_video(candidate))


def validate_techniques(candidate):
    techniques = candidate.get('techniques', [])
    if not isinstance(techniques, list):
        raise ValueError('Reference techniques must be a list')
    if not techniques:
        return
    if not reusable_expression(candidate):
        raise ValueError('Reference techniques require observed video and located evidence')
    viewing = candidate['viewing']
    coverage = ([[0, viewing['covered_seconds']]] if viewing['status'] == 'FULL_VIDEO_VIEWED'
                else viewing['time_ranges'])
    ids = set()
    for row in techniques:
        if (not isinstance(row, dict) or not all(_text(row.get(key)) for key in
                ('id', 'visual_method', 'use_condition', 'viewer_effect', 'implementation'))
                or row['id'] in ids):
            raise ValueError('Reference technique needs a unique ID, method, conditions, effect and implementation')
        ids.add(row['id'])
        span = row.get('source_range')
        if (not isinstance(span, list) or len(span) != 2 or not all(map(_seconds, span))
                or not any(left <= span[0] < span[1] <= right for left, right in coverage)):
            raise ValueError('Technique timecode must be inside an actually viewed segment')
        if row.get('shot_id') is not None and not any(
                shot['id'] == row['shot_id'] and shot['time_range'][0] <= span[0]
                and span[1] <= shot['time_range'][1] for shot in candidate.get('shot_analysis', [])):
            raise ValueError('Technique does not fit its observed source shot')


def validate_shot_analysis(candidate):
    """Store only properties observed within the covered excerpt."""
    if 'shot_analysis' not in candidate:
        return
    rows = candidate['shot_analysis']
    if not isinstance(rows, list) or not rows or not _viewed_video(candidate):
        raise ValueError('Reference shot analysis needs observed video')
    viewing = candidate['viewing']
    coverage = ([[0, viewing['covered_seconds']]] if viewing['status'] == 'FULL_VIDEO_VIEWED'
                else viewing['time_ranges'])
    previous, seen = 0, set()
    for row in rows:
        if not isinstance(row, dict) or not all(_text(row.get(key)) for key in (
                'id', 'composition', 'subject_motion', 'camera_motion', 'reveal', 'edit', 'style')):
            raise ValueError('Reference shot needs timecoded visual observations')
        span = row.get('time_range')
        if (row['id'] in seen or not isinstance(span, list) or len(span) != 2
                or not all(map(_seconds, span)) or not previous <= span[0] < span[1]
                or not any(left <= span[0] < span[1] <= right for left, right in coverage)):
            raise ValueError('Reference shot lies outside the observed sequence')
        if row.get('sound') is not None and (
                not _text(row['sound']) or not evidence_exists(row.get('listening_evidence'))):
            raise ValueError('Reference sound needs listening evidence for that shot')
        previous = span[1]
        seen.add(row['id'])


def match_reference_techniques(blueprint, analysis):
    selected = set(analysis['selected_ids'])
    techniques = {(candidate['id'], technique['id'])
                  for candidate in analysis['candidates'] if candidate['id'] in selected
                  for technique in candidate.get('techniques', [])}
    for row in blueprint.get('reference_principles', []):
        if (row['reference_id'], row['technique_id']) not in techniques:
            raise ValueError('Blueprint technique must refer to a timecoded selected observation')


def validate_reference_direction(treatment, analysis):
    rows = treatment.get('reference_principles', [])
    scenes = {scene['id'] for scene in treatment['scenes']}
    if not isinstance(rows, list) or any(
            not isinstance(row, dict) or not all(_text(row.get(key)) for key in (
                'reference_id', 'technique_id', 'principle', 'production_requirement', 'expected_observable_effect'))
            or not isinstance(row.get('scene_ids'), list) or not row['scene_ids']
            or not all(_text(scene) and scene in scenes for scene in row['scene_ids'])
            or len(row['scene_ids']) != len(set(row['scene_ids'])) for row in rows):
        raise ValueError('Adapt observed techniques to existing Treatment scenes and visible effects')
    pairs = {(row['reference_id'], row['technique_id']) for row in rows}
    if len(pairs) != len(rows) or {reference for reference, _ in pairs} != set(analysis['selected_ids']):
        raise ValueError('Adapt each selected reference in the Treatment with distinct technique IDs')
    match_reference_techniques(treatment, analysis)


def reference_shot_map(treatment, plan):
    from .joint_timeline import FPS

    fields = ('reference_id', 'technique_id', 'production_requirement', 'expected_observable_effect')
    expected = {tuple(row[key] for key in fields): set(row['scene_ids'])
                for row in treatment.get('reference_principles', [])}
    cuts = plan['timeline']['shots']
    scene_ids = {cut['id']: cut.get('scene_id') for cut in cuts}
    actual = {}
    mappings = plan.get('reference_principles', [])
    if not isinstance(mappings, list):
        raise ValueError('Reference shot mappings must be a list')
    for row in mappings:
        if not isinstance(row, dict) or not all(_text(row.get(key)) for key in fields):
            raise ValueError('Bind the Treatment reference decision and visible effect to a shot')
        key = tuple(row[field] for field in fields)
        shots = row.get('shot_ids')
        if (key in actual or not isinstance(shots, list) or not shots
                or not all(_text(shot) and shot in scene_ids for shot in shots)
                or len(set(shots)) != len(shots)):
            raise ValueError('A reference decision needs distinct cuts from the actual picture clock')
        actual[key] = {scene_ids[shot] for shot in shots}
    if actual != expected:
        raise ValueError('The picture cut must carry the Treatment reference effects in the corresponding scenes')
    return dict(reference_principles=mappings, shots=[dict(
        shot_id=cut['id'], time_range=[cut['start_frame'] / FPS, cut['end_frame'] / FPS]) for cut in cuts])


def validate_reference_effects(blueprint, report, media_sha):
    """Each applied method gets a finding on the rendered original shot."""
    expected = {(row['reference_id'], row['technique_id'], shot_id)
                for row in blueprint.get('reference_principles', []) for shot_id in row['shot_ids']}
    shots = {row['shot_id']: row['time_range'] for row in blueprint['shots']}
    seen, statuses = set(), set()
    for row in report.get('reference_effects', []):
        fields = ('reference_id', 'technique_id', 'shot_id')
        if not isinstance(row, dict) or not all(_text(row.get(key)) for key in fields):
            raise ValueError('Reference effect needs its reference, technique and shot IDs')
        key = tuple(row[field] for field in fields)
        span, status = row.get('time_range'), row.get('status')
        if (key not in expected or key in seen or not isinstance(span, list) or len(span) != 2
                or not all(map(_seconds, span)) or not shots[key[2]][0] <= span[0] < span[1] <= shots[key[2]][1]
                or row.get('media_sha256') != media_sha or not _text(row.get('observation'))
                or status not in ('PASS', 'FAIL', 'UNKNOWN')
                or (status == 'PASS' and row.get('method') not in ('continuous_video', 'continuous_audiovisual'))
                or (status == 'UNKNOWN' and not _text(row.get('limitation')))):
            raise ValueError('Reference effect needs an exact-media, timecoded observation and honest status')
        seen.add(key)
        statuses.add(status)
    if seen != expected:
        raise ValueError('Workprint review must cover the effects of applied reference techniques')
    return statuses


def validate_directed_analysis(payload, *, require_techniques=False, require_attempts=False):
    """Record a bounded research pass, including a pass without applicable viewing."""
    date(payload.get('observed_at'))
    candidates, selected = payload.get('candidates'), payload.get('selected_ids')
    if not isinstance(candidates, list) or not isinstance(selected, list) or not all(map(_text, selected)):
        raise ValueError('Reference research requires candidates and selected_ids arrays')
    if not selected and not _text(payload.get('limitation')):
        raise ValueError('Record why the search or cache check yielded no usable reference')
    if require_attempts and not selected:
        attempts = payload.get('search_attempts')
        if (not isinstance(attempts, list) or not attempts or any(
                not isinstance(row, dict) or not all(_text(row.get(key)) for key in ('url', 'result'))
                or not row['url'].startswith(('https://', 'http://')) for row in attempts)):
            raise ValueError('Record attempted public reference searches or playback and their actual results')
    seen, ids, usable = set(), set(), set()
    for candidate in candidates:
        if not isinstance(candidate, dict) or candidate.get('source_kind', 'video') != 'video':
            raise ValueError('Candidate must describe a video work')
        candidate_id = candidate.get('id')
        if not _text(candidate_id) or candidate_id in ids:
            raise ValueError('Unique nonempty candidate IDs required')
        ids.add(candidate_id)
        date(candidate.get('observed_at'))
        if candidate.get('url'):
            source = identity(candidate['url'])
        elif evidence_exists(candidate.get('source_files')):
            source = 'local:' + candidate['source_files'][0]['sha256']
        else:
            raise ValueError('Reference needs an original work URL or hashed local source')
        if source in seen:
            raise ValueError('Record each reference work once')
        seen.add(source)
        viewing = candidate.get('viewing') or {}
        if not isinstance(viewing, dict):
            raise ValueError('Record the actual video viewing scope')
        status = viewing.get('status')
        if not isinstance(status, str) or status not in VIDEO_VIEWING:
            raise ValueError('Record the actual video viewing scope')
        if status != 'FULL_VIDEO_VIEWED' and not _text(viewing.get('limitation')):
            raise ValueError('Record the limits of incomplete viewing')
        if status in {'FULL_VIDEO_VIEWED', 'PARTIAL_VIDEO_VIEWED'} and not _viewed_video(candidate):
            raise ValueError('Viewing claim requires matching time coverage and hashed observation evidence')
        validate_shot_analysis(candidate)
        validate_techniques(candidate)
        metrics = [key for key in METRICS if candidate.get(key) is not None]
        if metrics and (not all(_seconds(candidate[key]) for key in metrics)
                        or not all(_text((candidate.get('metrics_evidence') or {}).get(key)) for key in metrics)
                        or not evidence_exists(candidate.get('evidence'))):
            raise ValueError('Public metrics require located evidence or null values')
        if (candidate_id in selected and reusable_expression(candidate)
                and (not require_techniques or candidate.get('techniques'))):
            usable.add(candidate_id)
    if len(selected) != len(set(selected)) or not set(selected) <= usable:
        if require_techniques:
            raise ValueError('Selected references require observed video and a timecoded technique')
        raise ValueError('Selected references require observed video and a transferable analysis')


def directed_plan(topic, library_root, *, product=None):
    from .reference_library import search

    try:
        local = search(product or topic, root=library_root)
    except (ValueError, OSError, KeyError, TypeError) as error:
        local = {'results': [], 'limitation': str(error)}
    for work in local['results']:
        for observation in work['observations']:
            observation['reusable_expression'] = reusable_expression(observation['candidate'])
    queries = {'douyin': f'{product} 拆解' if product else topic,
               'xiaohongshu': f'{product} 拆机' if product else topic,
               'bilibili': f'{product} 拆解 三维 原理' if product else topic,
               'youtube': f'{product} teardown how it works animation' if product else topic}
    return {'topic': topic, 'observed_at': now(), 'local_references': local,
            'queries': [{'platform': platform, 'url': base + quote(queries[platform], safe='')}
                        for platform, base in (
                            ('douyin', 'https://www.douyin.com/search/'),
                            ('xiaohongshu', 'https://www.xiaohongshu.com/search_result?keyword='),
                            ('bilibili', 'https://search.bilibili.com/all?keyword='),
                            ('youtube', 'https://www.youtube.com/results?search_query='))]}


def validate_reference_recreation(blueprint, research):
    recreation = blueprint.get('reference_recreation')
    if not isinstance(recreation, dict):
        raise ValueError('Reference recreation requires a primary reference and shot mapping')
    primary = recreation.get('primary_reference_id')
    if primary not in research.get('selected_ids', []):
        raise ValueError('Primary reference must be a selected observed reference')
    if primary != research.get('primary_reference_id'):
        raise ValueError('Recreation must use the selected observed primary reference')
    candidate = next((c for c in research.get('candidates', []) if c.get('id') == primary), None)
    static = candidate is not None and candidate.get('source_kind', 'video') != 'video'
    duration = candidate.get('duration_seconds') if candidate else None
    if not static and (isinstance(duration, bool) or not isinstance(duration, (int, float))
                       or not math.isfinite(duration) or duration <= 0):
        raise ValueError('Primary reference needs its observed duration')
    if primary not in {p.get('reference_id') for p in blueprint.get('reference_principles', [])}:
        raise ValueError('Primary reference must supply a production principle')
    rows = recreation.get('shot_mapping')
    shots = [s['shot_id'] for s in blueprint.get('shots', [])]
    if (not isinstance(rows, list) or not rows or not all(isinstance(r, dict) for r in rows)
            or len(rows) != len(shots) or {r.get('shot_id') for r in rows} != set(shots)):
        raise ValueError('Recreation mapping must cover every production shot exactly once')
    for row in rows:
        if static:
            if row.get('reference_time_range') is not None:
                raise ValueError('Static references use regions or structure features, not video timestamps')
            if not isinstance(row.get('reference_region'), str) or not row['reference_region'].strip():
                raise ValueError('Static reference mapping requires the depicted region or structure feature')
        times = row.get('reference_time_range')
        if not static and (not isinstance(times, list) or len(times) != 2
                or any(isinstance(t, bool) or not isinstance(t, (int, float))
                       or not math.isfinite(t) for t in times)
                or not 0 <= times[0] < times[1] <= duration):
            raise ValueError('Recreation reference interval must be within the observed video')
        if not isinstance(row.get('adaptation'), str) or not row['adaptation'].strip():
            raise ValueError('Each recreated shot needs an adaptation decision')


def validate_creative_blueprint(payload):
    from .production_contract import directed_story, producer_directed, science_story
    fields = BLUEPRINT_FIELDS
    if producer_directed(payload):
        fields = {'core_question', 'original_topic', 'shots', 'duration_seconds', 'sources'}
    elif science_story(payload):
        fields = fields - {'disassembly_order', 'reference_principles'}
    if payload.get('content_policy_version') == 1 or payload.get('growth_policy_version') == 2:
        from .growth import validate_contract
        validate_contract(payload)
    if payload.get('status') != 'FROZEN' or not fields <= payload.keys():
        raise ValueError('Complete FROZEN blueprint required')
    if any(payload.get(k) in (None, '', [], {}) for k in fields):
        raise ValueError('Blueprint field lacks an executable decision')
    first = payload.get('first_motion_seconds')
    if 'first_motion_seconds' in fields or first is not None:
        if isinstance(first, bool) or not isinstance(first, (int, float)) or not math.isfinite(first) or first < 0:
            raise ValueError('First visible motion needs a finite time')
    end = 0
    shot_ids = set()
    for s in payload['shots']:
        if not {'shot_id', 'time_range', 'knowledge_goal', 'asset', 'template', 'feasibility_evidence'} <= s.keys():
            raise ValueError('Shot missing executable asset/template/evidence mapping')
        times = s['time_range']
        if (not isinstance(times, list) or len(times) != 2
                or any(isinstance(t, bool) or not isinstance(t, (int, float)) or not math.isfinite(t) for t in times)
                or times[0] != end or times[1] <= times[0]):
            raise ValueError('Shot time ranges must be contiguous and increasing from zero')
        end = times[1]
        if not s['shot_id'] or s['shot_id'] in shot_ids:
            raise ValueError('Unique shot IDs required')
        shot_ids.add(s['shot_id'])
        if any(not s[k] for k in ('knowledge_goal', 'asset', 'template')):
            raise ValueError('Shot mappings must not be empty')
        if not evidence_exists(s['feasibility_evidence']):
            raise ValueError('Shot feasibility evidence missing or changed')
    if first is not None and first >= end:
        raise ValueError('First motion must occur within the storyboard')
    if payload['duration_seconds'] != end:
        raise ValueError('Blueprint duration must match actual shot timeline')
    mapped = {'production_requirement', 'shot_ids', 'expected_observable_effect',
              'verification_method', 'minimal_repair', 'decision_basis', 'implementation_cost'}
    for p in payload.get('reference_principles', []):
        if producer_directed(payload):
            if (not isinstance(p, dict) or not all(_text(p.get(key)) for key in
                    ('reference_id', 'principle', 'production_requirement'))
                    or not isinstance(p.get('shot_ids'), list) or not p['shot_ids']
                    or not all(_text(s) and s in shot_ids for s in p['shot_ids'])):
                raise ValueError('Reference technique needs an original production decision and existing shot IDs')
            if directed_story(payload) and not all(_text(p.get(key)) for key in
                    ('technique_id', 'expected_observable_effect')):
                raise ValueError('Bind the located technique and its expected observable effect')
            continue
        if not p.get('reference_id') or not p.get('principle') or not evidence_exists(p.get('evidence')):
            raise ValueError('Observed transferable principle evidence required')
        if not mapped <= p.keys() or any(p[k] in (None, '', [], {}) for k in mapped):
            raise ValueError('Principle must map to execution, actual QA and bounded repair')
        if not isinstance(p['shot_ids'], list) or not set(p['shot_ids']) <= shot_ids:
            raise ValueError('Principle must map to existing shots')
    for requirement in payload.get('qa_requirements', []):
        if not {'requirement_id', 'shot_id', 'expected_observable_effect', 'verification_method', 'minimal_repair'} <= requirement.keys():
            raise ValueError('QA requirement lacks observable acceptance mapping')
        if requirement['shot_id'] not in shot_ids:
            raise ValueError('QA requirement refers to nonexistent shot')


def plan(topic, observed_at=None, *, creative=False):
    stamp = date(observed_at) if observed_at else datetime.now(timezone.utc)
    terms = [('A', term) for term in ([topic, topic+' 日常使用', topic+' 使用时的现象',
                                     topic+' 常见误解', topic+' 对比实验', topic+' 微距',
                                     topic+' 工作原理', topic+' 剖面图'] if creative else
                                    [topic, topic+' 工作原理', topic+' 拆解',
                                     topic+' 实物演示', topic+' 厂家演示', topic+' 原理动画',
                                     topic+' 结构图', topic+' 剖面图'])]
    if '拉链' in topic or 'zipper' in topic.lower():
        terms += [('A', '拉链链牙啮合'), ('A', 'zipper mechanism animation'),
                  ('B', '啮合 锁止 导向 机构 微距 原理')]
    else:
        terms += [('B', '机械 啮合 弹簧 连杆 锁止 剖面 动画')]
    terms += [('C', '科普 动画 原理 讲解')]
    urls = []
    for category, term in terms:
        urls.extend([{'reference_class': category, 'platform': 'douyin', 'keyword': term, 'url': 'https://www.douyin.com/search/'+quote(term)},
                     {'reference_class': category, 'platform': 'xiaohongshu', 'keyword': term, 'url': 'https://www.xiaohongshu.com/search_result?keyword='+quote(term)}])
    from .reference_library import search
    cached = search(topic)
    return {'topic': topic, 'observed_at': stamp.isoformat(),
            'breakout_required': False,
            'breakout_preferences': {
                'published_after': (stamp-timedelta(days=90)).isoformat(),
                'follower_caps': [10000, 50000, 100000], 'likes_exclusive_min': 1000},
            'local_references': cached, 'network_policy': 'Search local cache first; browse only documented gaps',
            'queries': urls, 'max_candidates': 30, 'max_deep_analyses': 10, 'reference_mix': REFERENCE_MIX,
            'source_policy': 'Inspect actual product use and teardown first; verify product/model identity and exact observed intervals or regions. Prefer licensed correct media, then verified assemblies, then evidence-based teaching models. Patents do not prove all market products share one mechanism.',
            'growth_policy_version': 2,
            'growth_objectives': ['retention', 'like', 'save', 'comment', 'follow'],
            'cache_key': hashlib.sha256(json.dumps(['v5-creative-first' if creative else 'v4-real-product-five-growth-goals', topic, stamp.date().isoformat(), WEIGHTS, REFERENCE_MIX, 30, 10], sort_keys=True).encode()).hexdigest(),
            'cache_policy': 'Reuse dated evidence; refresh live metrics before new qualification. No automatic network requests.'}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest='command', required=True)
    p = sub.add_parser('plan'); p.add_argument('--topic', required=True); p.add_argument('--output', type=Path, required=True)
    p.add_argument('--production-contract', type=int, choices=(1, 2), default=2)
    p = sub.add_parser('analyze'); p.add_argument('--input', type=Path, required=True); p.add_argument('--output', type=Path, required=True)
    a = ap.parse_args()
    if a.command == 'plan':
        data = plan(a.topic, creative=a.production_contract == 2); save(a.output/'search-plan.json', data)
    else:
        data = analyze(json.loads(a.input.read_text()))
        save(a.output/'viral-analysis.json', data)
        lines = ['# Reference screening', '', 'Status: '+data['status'], '', '|ID|Original URL|Viewing|Score coverage|Follower tier|', '|---|---|---|---|---|']
        for c in data['candidates']:
            lines.append('|{}|{}|{}|{}|{}|'.format(c['id'], c['url'], c['viewing']['status'], c['screening']['coverage'], c['breakout_follower_cap']))
        lines += ['', 'Missing public metrics remain null. Scores are screening heuristics, not retention or success evidence.', *data['blockers']]
        (a.output/'reference-screening.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps({'status': data.get('status', 'PLANNED'), 'output': str(a.output)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
