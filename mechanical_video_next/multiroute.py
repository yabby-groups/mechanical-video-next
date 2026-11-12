"""Resumable deterministic three-route media packaging; agents stay in Codex."""
import argparse
import hashlib
import glob
import json
import re
from pathlib import Path
import subprocess
import time

ROUTES = ('2d', '2.5d', '3d')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    temporary.replace(path)


def prepare(folder, topic):
    folder = Path(folder)
    state = folder / 'state.json'
    if state.exists():
        value = json.loads(state.read_text())
        if value['topic'] != topic:
            raise ValueError('Existing task topic differs; use another directory')
        return value
    value = {'schema_version': 1, 'topic': topic, 'status': 'PREPARED',
             'routes': {}, 'steps': {}, 'history': [], 'issues': [],
             'next_step': 'Producer researches reference and delegates native Codex agents; supply three actual MP4s.',
             'capability_boundary': 'Preparation does not automatically model arbitrary mechanical names.',
             'token_usage': None, 'human_interventions': None}
    write(state, value)
    return value


def command(args, log):
    with Path(log).open('w') as output:
        subprocess.run([str(a) for a in args], stdout=output, stderr=subprocess.STDOUT, check=True)


def probe(path):
    result = subprocess.run(['ffprobe', '-v', 'error', '-show_format', '-show_streams', '-of', 'json', str(path)],
                            capture_output=True, text=True, check=True)
    value = json.loads(result.stdout)
    if not any(s['codec_type'] == 'video' for s in value['streams']):
        raise ValueError(f'No video stream: {path}')
    return value


def audio_digest(path):
    """Compare decoded audio samples, not MP4 container bytes."""
    result = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(path), '-map', '0:a:0',
                             '-c:a', 'pcm_s16le', '-f', 'hash', '-hash', 'sha256', '-'],
                            capture_output=True, text=True, check=True)
    return result.stdout.strip()


def validate_timeline(media):
    durations = [value['duration'] for value in media.values()]
    starts = [value['video_start'] for value in media.values()]
    if max(durations) - min(durations) > 1 / 30 + 0.001 or max(starts) - min(starts) > 0.001:
        raise ValueError('Timeline mismatch: routes must share duration (within one 30fps frame) and video start time')
    if any(abs(value['fps'] - 30) > 0.001 for value in media.values()):
        raise ValueError('Comparison requires matching 30fps route videos')


def supplemental_evidence(folder, extra_paths=()):
    """Import authored statistics and QA with hashes; never infer perceptual scores."""
    folder = Path(folder)
    roots = [folder, folder.parent]
    sources = {}
    for root in roots:
        candidates = [root / 'shared/production-statistics.json', root / 'task.json', *root.glob('qa*.json')]
        for path in candidates:
            if path.is_file() and path.resolve() not in sources:
                sources[path.resolve()] = {'path': str(path.resolve()), 'sha256': sha(path),
                                           'data': json.loads(path.read_text())}
    for item in extra_paths:
        path = Path(item).resolve()
        sources[path] = {'path': str(path), 'sha256': sha(path), 'data': json.loads(path.read_text())}
    return list(sources.values())


def finalize(folder, paths, evidence_paths=()):
    folder = Path(folder).resolve()
    state = json.loads((folder / 'state.json').read_text())
    try:
        media = {}
        for route in ROUTES:
            path = Path(paths[route]).resolve()
            info = probe(path)
            video = next(s for s in info['streams'] if s['codec_type'] == 'video')
            audio = next((s for s in info['streams'] if s['codec_type'] == 'audio'), None)
            rate = video['avg_frame_rate'].split('/')
            media[route] = {'path': str(path), 'sha256': sha(path),
                            'duration': float(video.get('duration', info['format']['duration'])),
                            'video_start': float(video.get('start_time', 0)),
                            'fps': float(rate[0]) / float(rate[1]),
                            'audio_start': float(audio.get('start_time', 0)) if audio else None,
                            'audio_present': any(s['codec_type'] == 'audio' for s in info['streams'])}
        validate_timeline(media)
        for route in ROUTES:
            media[route]['audio_sha256'] = audio_digest(media[route]['path']) if media[route]['audio_present'] else None
        shared_audio = (all(v['audio_present'] for v in media.values())
                        and len({v['audio_sha256'] for v in media.values()}) == 1
                        and len({v['audio_start'] for v in media.values()}) == 1)
        evidence = supplemental_evidence(folder, evidence_paths)
        evidence_key = [({'path': item['path'], 'repairs': item['data'].get('repairs'),
                          'human_interventions': item['data'].get('human_interventions')}
                         if Path(item['path']).name == 'task.json' else item) for item in evidence]
        key = hashlib.sha256(json.dumps({'media': media, 'evidence': evidence_key, 'code': sha(__file__)}, sort_keys=True).encode()).hexdigest()
        old = state['steps'].get('finalize', {})
        if old.get('key') == key and all((folder / name).is_file() and sha(folder / name) == digest
                                       for name, digest in old.get('outputs', {}).items()) and old.get('outputs'):
            return json.loads((folder / 'report.json').read_text())
        start = time.monotonic()
        duration = max(v['duration'] for v in media.values())
        inputs = [item for route in ROUTES for item in ('-i', media[route]['path'])]
        labels = ('2D', '2.5D', '3D')
        filters = ';'.join(
            f'[{i}:v]setpts=PTS-STARTPTS,scale=1080:608:force_original_aspect_ratio=decrease,'
            f'pad=1080:640:(ow-iw)/2:32+(608-ih)/2,setsar=1,fps=30,'
            f"drawtext=text='{labels[i]}':fontsize=28:fontcolor=white:x=20:y=2,"
            f'tpad=stop_mode=clone:stop_duration=0.04[v{i}]' for i in range(3))
        filters += ';[v0][v1][v2]vstack=inputs=3[out]'
        audio_args = ['-map', '0:a:0', '-c:a', 'aac', '-b:a', '192k'] if shared_audio else ['-an']
        command(['ffmpeg', '-y', *inputs, '-filter_complex', filters, '-map', '[out]', *audio_args, '-t', str(duration),
                 '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '22', '-pix_fmt', 'yuv420p', folder / 'compare.mp4'], folder / 'compare.log')
        comparison_info = probe(folder / 'compare.mp4')
        comparison_video = next(s for s in comparison_info['streams'] if s['codec_type'] == 'video')
        if (comparison_video['width'], comparison_video['height']) != (1080, 1920):
            raise ValueError('Encoded comparison has incorrect portrait dimensions')
        if shared_audio and not any(s['codec_type'] == 'audio' for s in comparison_info['streams']):
            raise ValueError('Encoded comparison lost shared audio')
        command(['ffmpeg', '-y', '-ss', str(min(1, duration / 2)), '-i', folder / 'compare.mp4',
                 '-frames:v', '1', '-update', '1', folder / 'preview.jpg'], folder / 'preview.log')
        report = {'status': 'TECHNICAL_PASS_UNACCEPTED_COMPARISON', 'routes': media,
                  'comparison': {'order_top_to_bottom': list(ROUTES), 'width': 1080, 'height': 1920, 'fps': 30, 'duration': duration,
                                 'audio': 'shared first-route audio; decoded samples match' if shared_audio else 'silent: route audio missing or different; original audio retained',
                                 'scope': 'Matching timeline required; sub-frame duration differences pad last frame to longest input.'},
                  'checks': {'video_streams': 'PASS', 'comparison_encoding': 'PASS', 'timeline_alignment': 'PASS',
                             'shared_audio': 'PASS' if shared_audio else 'UNKNOWN',
                             'continuous_visual_review': 'UNKNOWN', 'listening_review': 'UNKNOWN',
                             'mechanical_correctness': 'UNKNOWN', 'reference_fidelity': 'UNKNOWN'},
                  'issues': [{'issue_id': 'REVIEW-UNKNOWN', 'defect_key': 'independent-review-unavailable', 'severity': 'blocking', 'shot_id': 'all',
                              'time_range': [0, max(v['duration'] for v in media.values())],
                              'evidence': 'No independent continuous visual, auditory, or mechanical review supplied.',
                              'responsible_agent': 'QA', 'suggested_fix': 'Review exact original media against reference.',
                              'verification_method': 'Independent QA bound to media SHA256.'}]}
        if not shared_audio:
            report['issues'].append({'issue_id': 'AUDIO-NOT-SHARED', 'defect_key': 'comparison-audio-not-shared', 'severity': 'blocking', 'shot_id': 'all', 'time_range': [0, duration], 'evidence': 'Decoded audio is absent or differs between routes.', 'responsible_agent': 'Editor', 'suggested_fix': 'Render routes with identical shared narration.', 'verification_method': 'Decoded PCM hashes match for all three routes.'})
        task_data = next((item['data'] for item in evidence if Path(item['path']).name == 'task.json'), {})
        stats = next((item['data'] for item in evidence if Path(item['path']).name == 'production-statistics.json'), {})
        route_receipts = [dict(path=item['path'], sha256=item['sha256'], seconds=item['data'].get('seconds'))
                          for item in evidence if Path(item['path']).name in {'final.json', 'animatic.json'}]
        reported_epoch = time.time()
        report['production_metrics'] = {
            'comparison_seconds': time.monotonic() - start,
            'production_seconds': stats.get('production_seconds'),
            'task_created_epoch': task_data.get('created_epoch'),
            'reported_epoch': reported_epoch,
            'wall_elapsed_since_task_creation_seconds': max(0, reported_epoch - task_data['created_epoch']) if isinstance(task_data.get('created_epoch'), (int, float)) else None,
            'wall_elapsed_scope': 'Includes research, waiting, repairs and idle time; not active renderer time.',
            'route_receipt_timings': route_receipts,
            'route_receipt_scope': 'Runtime recorded by each originating media receipt; cached reuse does not rerun that work. Unknown components remain null.',
            'sum_known_route_receipt_seconds': sum(item['seconds'] for item in route_receipts) if route_receipts and all(isinstance(item['seconds'], (int, float)) for item in route_receipts) else None,
            'repair_count': stats.get('repair_count', sum(sum(issue.get('strategies', {}).values()) for issue in task_data.get('repairs', {}).values()) if task_data else None),
            'human_interventions': stats.get('human_interventions', task_data.get('human_interventions')),
            'cache_reuse': stats.get('cache_reuse', state.get('last_run')),
            'visual_differences': [dict(path=item['path'], sha256=item['sha256'], observations=item['data']['visual_differences'])
                                   for item in evidence if 'visual_differences' in item['data']],
            'source_evidence': evidence}
        write(folder / 'report.json', report)
        state['routes'] = media
        state['steps']['finalize'] = {'key': key, 'elapsed_seconds': time.monotonic() - start,
                                     'outputs': {name: sha(folder / name) for name in ('compare.mp4', 'preview.jpg', 'report.json')}}
        state['status'] = report['status']
        state['issues'] = report['issues']
        state['next_step'] = 'Independent QA reviews exact three original MP4s; UNKNOWN prevents acceptance.'
        state['history'].append({'event': 'finalized', 'time': time.time(), 'key': key})
        write(folder / 'state.json', state)
        return report
    except Exception as error:
        state['status'] = 'FAILED'
        issue = {'issue_id': 'COMPARISON-TECHNICAL', 'defect_key': 'comparison-input-or-encoding',
                 'severity': 'blocking', 'shot_id': 'all', 'time_range': None,
                 'evidence': str(error), 'responsible_agent': 'Editor',
                 'suggested_fix': 'Align route timelines and inspect exact inputs and logs.',
                 'verification_method': 'Rerun finalize on corrected media hashes.'}
        state['issues'] = [issue]
        write(folder / 'report.json', {'status': 'FAIL', 'checks': {'comparison': 'FAIL'}, 'issues': [issue]})
        state['history'].append({'event': 'failure', 'time': time.time(), 'error': str(error)})
        state['next_step'] = 'Inspect logs, repair the failed input or command, rerun finalize.'
        write(folder / 'state.json', state)
        raise


def run_plan(folder, plan_path, env_file=None, extra_evidence=()):
    """Run already-authored deterministic commands serially, never spawn agents."""
    folder = Path(folder)
    state = json.loads((folder / 'state.json').read_text())
    plan = json.loads(Path(plan_path).read_text())
    state['last_run'] = {'started_epoch': time.time(), 'cache_hits': 0, 'executed_steps': 0}
    state['status'] = 'RUNNING'
    missing = [path for path in plan.get('prerequisite_inputs', []) if not Path(path).is_file()]
    if missing:
        state['status'] = 'FAILED'
        state['next_step'] = 'Current Producer must prepare required evidence before any render or paid audio: ' + ', '.join(missing)
        state['history'].append({'event': 'prerequisite_missing', 'paths': missing, 'time': time.time()})
        write(folder / 'state.json', state)
        raise ValueError(state['next_step'])
    for step in plan['steps']:
        if not re.fullmatch(r'[A-Za-z0-9_-]+', step['id']):
            raise ValueError('Step id must be a safe filename identifier')
        args = list(step['command'])
        if env_file and step.get('accepts_env_file') is True:
            args.extend(['--env-file', str(env_file)])
        if not isinstance(args, list) or not args or not all(isinstance(a, str) for a in args):
            raise ValueError('Commands must be argv arrays')
        if any(Path(a).name.startswith('python') for a in args[:2]) and args[:2] != ['uv', 'run']:
            raise ValueError('Python commands must use uv run')
        try:
            inputs = {str(Path(p).resolve()): sha(p) for p in step.get('inputs', [])}
        except (OSError, ValueError) as error:
            state['status'] = 'FAILED'
            state['history'].append({'event': 'input_failure', 'step': step['id'], 'error': str(error), 'time': time.time()})
            state['next_step'] = f"Restore the evidenced inputs for {step['id']} before resuming."
            write(folder / 'state.json', state)
            raise
        outputs = step['outputs']
        key = hashlib.sha256(json.dumps({'command': args, 'inputs': inputs}, sort_keys=True).encode()).hexdigest()
        old = state['steps'].get(step['id'], {})
        if old.get('key') == key and old.get('outputs') and all(Path(p).is_file() and sha(p) == h for p, h in old['outputs'].items()):
            old['inputs'] = inputs
            state['last_run']['cache_hits'] += 1
            state['history'].append({'event': 'cache_reused', 'step': step['id'], 'time': time.time(), 'key': key})
            write(folder / 'state.json', state)
            continue
        start = time.monotonic()
        state['current_step'] = step['id']
        state['next_step'] = f"Running {step['id']}; then continue remaining authored steps."
        write(folder / 'state.json', state)
        try:
            command(args, folder / (step['id'] + '.log'))
            state['last_run']['executed_steps'] += 1
            state['steps'][step['id']] = {'key': key, 'inputs': inputs, 'outputs': {str(Path(p).resolve()): sha(p) for p in outputs},
                                          'elapsed_seconds': time.monotonic() - start}
            state['history'].append({'event': 'step_complete', 'step': step['id'], 'time': time.time()})
        except Exception as error:
            state['status'] = 'FAILED'
            state['history'].append({'event': 'failure', 'step': step['id'], 'error': str(error), 'time': time.time()})
            state['next_step'] = f"Inspect {step['id']}.log and repair before resuming."
            write(folder / 'state.json', state)
            raise
        write(folder / 'state.json', state)
    state.pop('current_step', None)
    evidence = [*plan.get('evidence', []), *extra_evidence]
    for pattern in plan.get('evidence_globs', []):
        evidence.extend(sorted(glob.glob(pattern)))
    return finalize(folder, plan['routes'], evidence)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    p = sub.add_parser('prepare'); p.add_argument('--topic', required=True); p.add_argument('--output', required=True)
    p = sub.add_parser('finalize'); p.add_argument('folder')
    p.add_argument('--evidence', type=Path, action='append', default=[])
    for flag in ('2d', '25d', '3d'):
        p.add_argument('--route-' + flag, required=True)
    p = sub.add_parser('run'); p.add_argument('folder'); p.add_argument('--plan', required=True)
    args = parser.parse_args()
    if args.action == 'prepare':
        result = prepare(args.output, args.topic)
    elif args.action == 'run':
        result = run_plan(args.folder, args.plan)
    else:
        result = finalize(args.folder, {'2d': args.route_2d, '2.5d': args.route_25d, '3d': args.route_3d}, args.evidence)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
