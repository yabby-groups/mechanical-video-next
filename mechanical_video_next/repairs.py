"""One bounded repair adapter: subtitles only, reusing verified final shots.

Run with python -m mechanical_video_next.repairs TASK --config ... --issue ...
--shot s1 --cue 0 --text '...'. Requires a matching structured QA defect.
Other repair types remain Producer decisions through existing templates.
"""
import argparse
import copy
import json
from pathlib import Path
import sys
import time
import re
import threading
from . import workflow as w


def subtitle_config(config, shot_id, cue, expected, text):
    cfg = copy.deepcopy(config)
    shot = next((s for s in cfg['storyboard'] if s['id'] == shot_id), None)
    if shot is None:
        raise ValueError('Unknown shot')
    current = shot.get('subtitles', shot['narration'])
    if not isinstance(cue, int) or not 0 <= cue < len(current):
        raise ValueError('Cue index out of range')
    if current[cue] != expected or not text.strip() or text == expected:
        raise ValueError('Stale defect or empty/no-op replacement')
    shot['subtitles'] = list(current)
    shot['subtitles'][cue] = text
    return cfg


def repair(task, config, issue_id, shot_id, cue, text, quality='final'):
    task = Path(task)
    if not re.fullmatch(r'[A-Za-z0-9_-]+', issue_id):
        raise ValueError('Unsafe issue ID')
    qa_name = 'final-qa' if 'final-qa' in w.load(task)['handoffs'] else 'preview-qa'
    qa = w.artifact(task, qa_name)
    w.check_media(qa['media'])
    issue = next(i for i in qa['issues'] if i['issue_id'] == issue_id)
    if issue['responsible_agent'] != 'Editor' or issue['shot_id'] != shot_id:
        raise ValueError('Repair is not assigned to this Editor shot')
    if issue.get('kind') != 'subtitle_text':
        raise ValueError('Only explicit subtitle_text defects supported')
    if issue.get('config_sha256') != w.filehash(config) or issue.get('cue_index') != cue:
        raise ValueError('QA defect not bound to this config and cue')
    cfg = json.loads(Path(config).read_text())
    fixed = subtitle_config(cfg, shot_id, cue, issue['expected_current_text'], text)
    if not re.fullmatch(r'[A-Za-z0-9_-]+', cfg['id']):
        raise ValueError('Unsafe video ID')
    sys.path.insert(0, str(w.ROOT / 'scripts'))
    import produce
    from common import Metrics, budget
    # Do not invoke asset(), make_shot(), or any Blender process in this adapter.
    media = {}
    for name in dict.fromkeys(s['shot'] for s in fixed['storyboard']):
        shot = fixed['shots'][name]
        key = produce.shot_key(shot, quality, fixed['render'])
        folder = produce.CACHE / 'shots' / key
        kind = 'image' if shot['template'] in ['overall', 'detail', 'exploded'] else 'video'
        filename = 'media.png' if kind == 'image' else 'media.mp4'
        if not produce.cached(folder, [filename, 'checks.json']):
            raise ValueError('Verified shot cache missing; cannot repair subtitles locally')
        media[name] = (folder / filename, kind, key)
    def check_attempts(attempts):
        if attempts['stopped'] or attempts['strategies'].get('subtitle-only', 0) >= 2:
            raise ValueError('Repair budget exhausted')
        if attempts.get('best') == 0:
            raise ValueError('Repair already technically resolved; independent QA required')
    existing = w.load(task)['repairs'].get(issue_id)
    if existing:
        check_attempts(existing)
    start = time.time()
    with w.lock(w.ROOT / 'work/production.lock'):
        if issue_id not in w.load(task)['repairs']:
            w.repair_attempt(task, issue_id, 'subtitle-only', 1)
        attempts = w.load(task)['repairs'][issue_id]
        check_attempts(attempts)
        version = sum(attempts['strategies'].values()) + 1
        fixed['id'] = cfg['id'] + '-subtitle-repair-' + issue_id + '-' + str(version)
        metrics = Metrics(fixed['id'])
        w.write(task / f'repairs/{issue_id}-{version}-config.json', fixed)
        stopped = threading.Event()
        sampling_errors = []
        def sample():
            while not stopped.wait(0.5):
                try:
                    metrics.peak = max(metrics.peak, budget())
                except Exception as error:
                    sampling_errors.append(str(error))
                    return
        monitor = threading.Thread(target=sample, daemon=True)
        monitor.start()
        try:
            produce.compose(fixed, quality, media, metrics)
            if sampling_errors:
                raise RuntimeError(sampling_errors[0])
        except Exception:
            w.repair_attempt(task, issue_id, 'subtitle-only', 1)
            w.event(task, 'repair_failed', issue_id=issue_id)
            w.write(task / f'repairs/{issue_id}-{version}-result.json',
                    metrics.finish(status='failed', independent_verification='PENDING'))
            raise
        finally:
            stopped.set()
            monitor.join()
        props = json.loads((w.ROOT / 'output' / (fixed['id'] + '-' + quality + '.props.json')).read_text())
        before_count = sum(len(s['narration']) for s in cfg['storyboard'][:next(i for i,s in enumerate(cfg['storyboard']) if s['id']==shot_id)])
        score = int(props['cues'][before_count + cue]['text'] != text)
        w.repair_attempt(task, issue_id, 'subtitle-only', score)
        result = metrics.finish(technical_only=True, independent_verification='PENDING',
                                full_shot_renders=0, repair_issue=issue_id)
        w.write(task / f'repairs/{issue_id}-{version}-result.json', result)
        w.event(task, 'subtitle_repair', issue_id=issue_id, seconds=time.time()-start,
                config_sha256=w.digest(fixed), independent_verification='PENDING')
    return fixed


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('task', type=Path)
    p.add_argument('--config', required=True, type=Path)
    p.add_argument('--issue', required=True)
    p.add_argument('--shot', required=True)
    p.add_argument('--cue', required=True, type=int)
    p.add_argument('--text', required=True)
    p.add_argument('--quality', choices=['preview', 'final'], default='final')
    a = p.parse_args()
    repair(a.task, a.config, a.issue, a.shot, a.cue, a.text, a.quality)


if __name__ == '__main__':
    main()
