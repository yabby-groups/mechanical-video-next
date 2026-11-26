"""Optional local post-publication observations, with separate platform cohorts."""
import argparse
from datetime import datetime
import json
from pathlib import Path
from .workflow import filehash

METRICS = ('views', 'bounce_2s', 'retention_3s', 'retention_5s', 'average_watch_seconds',
           'completion_rate', 'likes', 'comments', 'saves', 'shares', 'new_followers',
           'attributed_followers')
RATES = {'bounce_2s', 'retention_3s', 'retention_5s', 'completion_rate',
         'like_rate', 'comment_rate', 'save_rate', 'share_rate'}


def ingest(data):
    from .growth import finite
    for key in ('video_id', 'platform', 'account_id', 'published_at', 'observed_at', 'topic', 'traffic_source'):
        if not data.get(key):
            raise ValueError('Missing comparison context: '+key)
    published, observed = (datetime.fromisoformat(data[key]) for key in ('published_at', 'observed_at'))
    if published.tzinfo is None or observed.tzinfo is None:
        raise ValueError('Timestamp needs timezone')
    if observed < published:
        raise ValueError('Observation predates publication')
    duration = data.get('duration_seconds')
    if not finite(duration) or duration <= 0:
        raise ValueError('Invalid video duration')
    result = dict(data)
    for key in (*METRICS, *sorted(RATES - set(METRICS))):
        value = data.get(key)
        if value is not None and (not finite(value) or value < 0):
            raise ValueError('Invalid metric: '+key)
        if key in RATES and value is not None and value > 1:
            raise ValueError('Rates use 0–1')
        result[key] = value
    for key in ('blueprint', 'timeline'):
        ref = data.get(key, {})
        if not ref.get('path') or filehash(Path(ref['path'])) != ref.get('sha256'):
            raise ValueError('Missing or changed '+key+' binding')
    media = data.get('published_media')
    if media is not None and filehash(Path(media['path'])) != media.get('sha256'):
        raise ValueError('Missing or changed published media binding')
    from .pacing import text_fields
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
    result['average_watch_ratio'] = None if watch_seconds is None else watch_seconds / duration
    views = result['views']
    result['per_thousand_views'] = {
        k: result[k] * 1000 / views if views and result[k] is not None else None
        for k in ('likes', 'comments', 'saves', 'shares', 'new_followers', 'attributed_followers')
    }
    result['comparison_policy'] = 'Compare within platform/account, similar duration/topic/publication window and traffic source; no causal or predictive claims.'
    return result


def comparable_observations(records, target, *, duration_tolerance, age_tolerance, publication_window):
    """Return the closest-age snapshot per video in the same publishing cohort."""
    def age(row):
        return (datetime.fromisoformat(row['observed_at']) -
                datetime.fromisoformat(row['published_at'])).total_seconds()

    context = ('platform', 'account_id', 'topic', 'traffic_source')
    target_age = age(target)
    publication = datetime.fromisoformat(target['published_at'])
    selected = {}
    for row in records:
        if row['video_id'] == target.get('video_id') or any(row[k] != target[k] for k in context):
            continue
        if abs(row['duration_seconds'] - target['duration_seconds']) > duration_tolerance:
            continue
        if abs(datetime.fromisoformat(row['published_at']) - publication).total_seconds() > publication_window:
            continue
        distance = abs(age(row) - target_age)
        if distance <= age_tolerance and (row['video_id'] not in selected or distance < selected[row['video_id']][0]):
            selected[row['video_id']] = (distance, row)
    return [row for _, row in sorted(selected.values(), key=lambda item: (item[0], item[1]['video_id']))]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    result = ingest(json.loads(a.input.read_text()))
    if a.output.exists():
        raise ValueError('Use a new observation output')
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')


if __name__ == '__main__':
    main()
