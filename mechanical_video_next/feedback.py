"""Optional local post-publication observations, with separate platform cohorts."""
import argparse
from datetime import datetime
import json
from pathlib import Path
from .workflow import filehash

METRICS = ('views', 'retention_3s', 'retention_5s', 'average_watch_seconds', 'completion_rate',
           'likes', 'comments', 'saves', 'shares', 'new_followers')


def ingest(data):
    from .growth import finite
    for key in ('video_id', 'platform', 'account_id', 'published_at', 'observed_at', 'topic', 'traffic_source'):
        if not data.get(key):
            raise ValueError('Missing comparison context: '+key)
    for key in ('published_at', 'observed_at'):
        stamp = datetime.fromisoformat(data[key])
        if stamp.tzinfo is None:
            raise ValueError('Timestamp needs timezone')
    duration = data.get('duration_seconds')
    if not finite(duration) or duration <= 0:
        raise ValueError('Invalid video duration')
    result = dict(data)
    for key in METRICS:
        value = data.get(key)
        if value is not None and (not finite(value) or value < 0):
            raise ValueError('Invalid metric: '+key)
        if key in {'retention_3s', 'retention_5s', 'completion_rate'} and value is not None and value > 1:
            raise ValueError('Rates use 0–1')
        result[key] = value
    for key in ('blueprint', 'timeline'):
        ref = data.get(key, {})
        if not ref.get('path') or filehash(Path(ref['path'])) != ref.get('sha256'):
            raise ValueError('Missing or changed '+key+' binding')
    views = result['views']
    result['per_thousand_views'] = {k: result[k]*1000/views if views and result[k] is not None else None
                                    for k in ('likes', 'saves', 'new_followers')}
    result['comparison_policy'] = 'Compare within platform/account, similar duration/topic/publication window and traffic source; no causal or predictive claims.'
    return result


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
