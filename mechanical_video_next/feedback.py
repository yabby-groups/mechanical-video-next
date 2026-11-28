"""Optional local post-publication observations, with separate platform cohorts."""
import argparse
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
import json
from pathlib import Path
from statistics import median
from .workflow import filehash

METRICS = ('views', 'bounce_2s', 'retention_3s', 'retention_5s', 'average_watch_seconds',
           'average_watch_ratio', 'completion_rate', 'likes', 'comments', 'saves', 'shares',
           'new_followers', 'attributed_followers', 'recommendation_impressions',
           'impressions', 'cover_impressions', 'cover_clicks', 'cover_click_rate')
RATES = {'bounce_2s', 'retention_3s', 'retention_5s', 'completion_rate',
         'like_rate', 'comment_rate', 'save_rate', 'share_rate', 'cover_click_rate'}
FOLLOW_UP_HOURS = (24, 72, 168)
ENGAGEMENT = ('likes', 'comments', 'saves', 'shares', 'new_followers', 'attributed_followers')
DOMAIN_DIMENSIONS = ('complexity', 'phenomenon', 'familiarity', 'visual_expression',
                     'depth', 'practical_value', 'intended_audience')


def age_hours(row):
    if not row.get('published_at') or not row.get('observed_at'):
        return None
    published, observed = (datetime.fromisoformat(row[key]) for key in ('published_at', 'observed_at'))
    if published.tzinfo is None or observed.tzinfo is None:
        raise ValueError('Timestamp needs timezone')
    if observed < published:
        raise ValueError('Observation predates publication')
    return (observed - published).total_seconds() / 3600


def observation_windows(records, *, tolerance_hours=6):
    """Select one real snapshot per platform/account/post per requested age."""
    selected = {}
    for row in records:
        age = age_hours(row)
        if age is None or row.get('account_id') is None:
            continue
        for hour in FOLLOW_UP_HOURS:
            distance = abs(age - hour)
            key = (row['platform'], row['account_id'], row['video_id'], hour)
            if distance <= tolerance_hours and (key not in selected or distance < selected[key][0]):
                selected[key] = (distance, row)
    return {key: row for key, (_, row) in selected.items()}


def ingest(data, *, root=Path('.')):
    from .growth import finite
    from .pacing import text_fields
    for key in ('video_id', 'platform'):
        if not data.get(key):
            raise ValueError('Missing comparison context: '+key)
    duration = data.get('duration_seconds')
    if duration is not None and (not finite(duration) or duration <= 0):
        raise ValueError('Invalid video duration')
    result = dict(data, age_hours=age_hours(data))
    for key in ('published_at', 'observed_at'):
        if data.get(key) and datetime.fromisoformat(data[key]).tzinfo is None:
            raise ValueError('Timestamp needs timezone')
    for key in (*METRICS, *sorted(RATES - set(METRICS))):
        value = data.get(key)
        if value is not None and (not finite(value) or value < 0):
            raise ValueError('Invalid metric: '+key)
        if key in RATES and value is not None and value > 1:
            raise ValueError('Rates use 0–1')
        result[key] = value

    def check_binding(ref, key):
        if not text_fields(ref, ('path', 'sha256')):
            raise ValueError('Missing or changed '+key+' binding')
        path = root / ref['path']
        if not path.is_file() or filehash(path) != ref['sha256']:
            raise ValueError('Missing or changed '+key+' binding')

    for key in ('blueprint', 'timeline', 'published_media', 'local_media', 'platform_evidence'):
        if (ref := data.get(key)) is not None:
            check_binding(ref, key)
    result['production_binding'] = ('complete' if all(data.get(key) for key in
                                    ('blueprint', 'timeline', 'published_media')) else 'partial')
    if domain := data.get('selection_domain'):
        if not text_fields(domain, ('primary', 'basis')):
            raise ValueError('A selection domain needs a content basis')
        tags = domain.get('related', [])
        if not isinstance(tags, list) or any(not isinstance(tag, str) or not tag.strip() for tag in tags):
            raise ValueError('Related domains must be names')
        result['selection_domain'] = {
            **domain, **{name: domain.get(name) or 'UNKNOWN' for name in DOMAIN_DIMENSIONS},
        }
    features = data.get('creative_features', [])
    if not isinstance(features, list):
        raise ValueError('Creative features must be a list')
    for feature in features:
        if not text_fields(feature, ('kind', 'observation')):
            raise ValueError('Creative feature needs an observed relationship')
        evidence = feature.get('evidence')
        check_binding(evidence, 'creative feature')
        times = evidence.get('time_range')
        if not (text_fields(evidence, ('location',)) or
                (isinstance(times, list) and len(times) == 2 and all(map(finite, times))
                 and 0 <= times[0] <= times[1])):
            raise ValueError('Creative feature evidence needs a time range or a source location')
    for key, fields in (
        ('diagnosis', ('finding', 'source')),
        ('hypotheses', ('change', 'basis', 'measure')),
    ):
        rows = data.get(key, [])
        if not isinstance(rows, list) or any(not text_fields(row, fields) for row in rows):
            raise ValueError(f'Invalid post-publish {key}')
    for key in ('featured', 'featured_feedback', 'extra_distribution'):
        observation = data.get(key)
        if observation is not None:
            fields = ('source',) if key == 'featured' else ('source', 'value')
            if not text_fields(observation, fields) or (
                    key == 'featured' and type(observation.get('value')) is not bool):
                raise ValueError(f'Platform observation {key} requires a value and source')
        result[key] = observation
    watch_seconds = result['average_watch_seconds']
    if watch_seconds is not None and duration is not None:
        result['average_watch_ratio'] = watch_seconds / duration
    views = result['views']
    result['per_thousand_views'] = {
        k: result[k] * 1000 / views if views and result[k] is not None else None
        for k in ENGAGEMENT
    }
    result['comparison_policy'] = ('Compare within a platform and account at matching ages. '
                                   'Keep differences in duration, topic and traffic source visible.')
    return result


def domain_cohorts(records, *, first_weekday=0, thresholds=None, tolerance_hours=6):
    """Describe publication mix and actual outcomes for each platform/account."""
    thresholds = thresholds or {}
    records = [row for row in records if row.get('published_at')]
    latest = {}
    for row in records:
        key = row['platform'], row.get('account_id'), row['video_id']
        previous = latest.get(key)
        if previous is None or (age_hours(row) or 0) >= (age_hours(previous) or 0):
            latest[key] = row
    windows = observation_windows(records, tolerance_hours=tolerance_hours)
    groups = defaultdict(list)
    totals = defaultdict(int)
    for key, row in latest.items():
        published = date.fromisoformat(row['published_at'][:10])
        week = published - timedelta(days=(published.weekday() - first_weekday) % 7)
        cohort = (*key[:2], week.isoformat(), row.get('format') or 'UNKNOWN')
        domain = (row.get('selection_domain') or {}).get('primary') or 'UNKNOWN'
        groups[(*cohort, domain)].append((key, row))
        totals[cohort] += 1

    def describe(rows, threshold):
        values = {name: [row[name] for row in rows if row.get(name) is not None]
                  for name in (*METRICS, 'duration_seconds')}
        values['age_hours'] = [age for row in rows if (age := age_hours(row)) is not None]
        for name in ENGAGEMENT:
            values[f'{name}_per_thousand_views'] = [
                number for row in rows
                if (number := row.get('per_thousand_views', {}).get(name)) is not None
            ]
        views = values['views']
        completed = len(views) if threshold is not None else 0
        over_threshold = sum(value > threshold for value in views) if completed else None
        sources = Counter(row.get('traffic_source') or 'UNKNOWN' for row in rows)
        return dict(posts=len(rows),
                    metrics={name: dict(n=len(numbers), median=median(numbers) if numbers else None)
                             for name, numbers in values.items()},
                    traffic_sources=dict(sources),
                    threshold=threshold,
                    over_threshold=over_threshold,
                    over_threshold_rate=over_threshold / completed if completed else None,
                    threshold_sample=completed)

    result = []
    for (platform, account, week, form, domain), members in groups.items():
        threshold = thresholds.get(platform)
        combined = describe([row for _, row in members], threshold)
        matched = {hour: describe([windows[(*key, hour)] for key, _ in members
                                  if (*key, hour) in windows], threshold)
                   for hour in FOLLOW_UP_HOURS}
        result.append(dict(platform=platform, account_id=account, week=week, format=form,
                           domain=domain, share=len(members)/totals[(platform, account, week, form)],
                           latest=combined, by_age_hours=matched))
    return sorted(result, key=lambda row: (row['platform'], row['account_id'] or '',
                                           row['week'], row['format'], row['domain']))


def comparable_observations(records, target, *, duration_tolerance, age_tolerance, publication_window,
                            match_topic=True, match_traffic_source=True):
    """Return the closest-age snapshot per video in the same publishing cohort."""
    context = ['platform', 'account_id']
    if match_topic:
        context.append('topic')
    if match_traffic_source:
        context.append('traffic_source')
        if not target.get('traffic_source') or target['traffic_source'].lower() == 'unknown':
            return []
    target_age = age_hours(target)
    if target_age is None or not target.get('account_id') or target.get('duration_seconds') is None:
        return []
    publication = datetime.fromisoformat(target['published_at'])
    selected = {}
    for row in records:
        if row['video_id'] == target.get('video_id') or any(row.get(k) != target.get(k) for k in context):
            continue
        age = age_hours(row)
        if age is None or row.get('duration_seconds') is None:
            continue
        if abs(row['duration_seconds'] - target['duration_seconds']) > duration_tolerance:
            continue
        if abs(datetime.fromisoformat(row['published_at']) - publication).total_seconds() > publication_window:
            continue
        distance = abs(age - target_age) * 3600
        if distance <= age_tolerance and (row['video_id'] not in selected or distance < selected[row['video_id']][0]):
            selected[row['video_id']] = (distance, row)
    return [row for _, row in sorted(selected.values(), key=lambda item: (item[0], item[1]['video_id']))]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--cohorts', action='store_true', help='Summarize a JSON list by platform, week and domain')
    p.add_argument('--week-start', type=int, choices=range(7), default=0)
    p.add_argument('--douyin-threshold', type=int)
    a = p.parse_args()
    data = json.loads(a.input.read_text())
    if a.cohorts:
        thresholds = {'douyin': a.douyin_threshold}
        result = domain_cohorts([ingest(row) for row in data], first_weekday=a.week_start,
                                thresholds=thresholds)
    else:
        result = ingest(data)
    if a.output.exists():
        raise ValueError('Use a new observation output')
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')


if __name__ == '__main__':
    main()
