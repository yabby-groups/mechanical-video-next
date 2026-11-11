"""Bounded research planning and evidence-led screening; no scraper or predictor."""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
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
        if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest() != e['sha256']:
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
        c.setdefault('reference_class', 'A')
        if c['reference_class'] not in REFERENCE_MIX:
            raise ValueError('Reference class must be A, B or C')
        if not c.get('id') or c['id'] in ids:
            raise ValueError('Unique nonempty candidate IDs required')
        ids.add(c['id'])
        key = identity(c['url']) if c.get('url') else 'unresolved:' + c['id']
        c['original_url_resolved'] = bool(c.get('url'))
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
                and c['original_url_resolved'] and full_view(c)
                and c.get('style') and c['screening']['coverage'] >= .60
                and (c['breakout_follower_cap'] is not None or c.get('professional_benchmark') is True
                     or c['reference_class'] == 'C')]
    # First reserve a professional benchmark, then prioritize strict follower tiers.
    eligible.sort(key=lambda c: (not c.get('professional_benchmark', False),
                                c['breakout_follower_cap'] or 100001,
                                -c['screening']['coverage'], -(c['screening']['score'] or 0)))
    selected, styles = [], set()
    for category, quota in [('A', 5), ('B', 3), ('C', 2)]:
        for c in [item for item in eligible if item['reference_class'] == category]:
            if c['style'] not in styles and sum(item['reference_class'] == category and item['id'] in selected for item in eligible) < quota:
                selected.append(c['id']); styles.add(c['style'])
    # Insufficient categories remain a documented gap; never pad with unrelated work.
    counts = {k: sum(c['id'] in selected and c['reference_class'] == k for c in eligible) for k in REFERENCE_MIX}
    ready = len(selected) >= 3 and all(counts.values())
    return {'schema_version': 1, 'topic': data['topic'], 'observed_at': data['observed_at'],
            'status': 'READY' if ready else 'BLOCKED', 'weights': WEIGHTS,
            'model_kind': 'internal_screening_heuristic_not_platform_algorithm',
            'candidates': unique, 'duplicates': duplicates, 'selected_ids': selected,
            'reference_mix': {'target': REFERENCE_MIX, 'actual_counts': counts, 'target_counts': {'A': 5, 'B': 3, 'C': 2}},
            'budget': {'candidates': len(rows), 'deep_analysis': len(deep), 'limits': [30, 10]},
            'blockers': [] if ready else ['Need fully viewed references in A (same topic), B (similar mechanism), C (science narrative); target 10, no padding'],
            'elapsed_seconds': data.get('elapsed_seconds'), 'human_interventions': None,
            'rework_reduction': None, 'tokens': None, 'cost': None}


def validate_viral_analysis(payload):
    calculated = analyze(payload)
    if payload.get('status') != 'READY' or calculated['status'] != 'READY':
        raise ValueError('Viral research evidence is not READY')
    if payload.get('selected_ids') != calculated['selected_ids']:
        raise ValueError('Selected references do not match evidence-led screening')


def validate_creative_blueprint(payload):
    if payload.get('status') != 'FROZEN' or not BLUEPRINT_FIELDS <= payload.keys():
        raise ValueError('Complete FROZEN blueprint required')
    if any(payload.get(k) in (None, '', [], {}) for k in BLUEPRINT_FIELDS):
        raise ValueError('Blueprint field lacks an executable decision')
    first = payload['first_motion_seconds']
    if isinstance(first, bool) or not isinstance(first, (int, float)) or not math.isfinite(first) or first < 0:
        raise ValueError('First mechanical motion needs a finite time')
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
    if first >= end:
        raise ValueError('First motion must occur within the storyboard')
    if payload['duration_seconds'] != end:
        raise ValueError('Blueprint duration must match actual shot timeline')
    mapped = {'production_requirement', 'shot_ids', 'expected_observable_effect',
              'verification_method', 'minimal_repair', 'decision_basis', 'implementation_cost'}
    for p in payload['reference_principles']:
        if not p.get('reference_id') or not p.get('principle') or not evidence_exists(p.get('evidence')):
            raise ValueError('Observed transferable principle evidence required')
        if not mapped <= p.keys() or any(p[k] in (None, '', [], {}) for k in mapped):
            raise ValueError('Principle must map to execution, actual QA and bounded repair')
        if not isinstance(p['shot_ids'], list) or not set(p['shot_ids']) <= shot_ids:
            raise ValueError('Principle must map to existing shots')
    for requirement in payload['qa_requirements']:
        if not {'requirement_id', 'shot_id', 'expected_observable_effect', 'verification_method', 'minimal_repair'} <= requirement.keys():
            raise ValueError('QA requirement lacks observable acceptance mapping')
        if requirement['shot_id'] not in shot_ids:
            raise ValueError('QA requirement refers to nonexistent shot')


def plan(topic, observed_at=None):
    stamp = date(observed_at) if observed_at else datetime.now(timezone.utc)
    terms = [('A', term) for term in [topic, topic+' 工作原理', topic+' 拆解', topic+' 原理动画']]
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
            'published_after': (stamp-timedelta(days=90)).isoformat(),
            'local_references': cached, 'network_policy': 'Search local cache first; browse only documented gaps',
            'queries': urls, 'max_candidates': 30, 'max_deep_analyses': 10, 'reference_mix': REFERENCE_MIX,
            'follower_caps': [10000, 50000, 100000], 'likes_exclusive_min': 1000,
            'cache_key': hashlib.sha256(json.dumps(['v2', topic, stamp.date().isoformat(), WEIGHTS, REFERENCE_MIX, 30, 10], sort_keys=True).encode()).hexdigest(),
            'cache_policy': 'Reuse dated evidence; refresh live metrics before new qualification. No automatic network requests.'}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest='command', required=True)
    p = sub.add_parser('plan'); p.add_argument('--topic', required=True); p.add_argument('--output', type=Path, required=True)
    p = sub.add_parser('analyze'); p.add_argument('--input', type=Path, required=True); p.add_argument('--output', type=Path, required=True)
    a = ap.parse_args()
    if a.command == 'plan':
        data = plan(a.topic); save(a.output/'search-plan.json', data)
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
