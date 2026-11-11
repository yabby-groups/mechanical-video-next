"""Small evidence-gated ledger around the existing production scripts.

The CLI never impersonates an agent. `produce` prepares a task for the current
Codex session. `produce --codex` starts a new real Codex session instead.
"""
import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import json
from pathlib import Path
import re
import math
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
ROLES = {'Research': {'research', 'script'}, 'Asset': {'asset-plan'},
         'Animation': {'animation-manifest'}, 'Editor': {'timeline'},
         'QA': {'preview-qa', 'final-qa'}}
NEXT = {'CREATED': 'RESEARCHING', 'RESEARCHING': 'ASSET_READY',
        'ASSET_READY': 'ANIMATING', 'ANIMATING': 'PREVIEW_READY',
        'PREVIEW_READY': 'PREVIEW_CHECKING', 'PREVIEW_CHECKING': 'EDITING',
        'EDITING': 'FINAL_CHECKING', 'FINAL_CHECKING': 'COMPLETED'}
QA_CHECKS = {'mechanics', 'explosion_clarity', 'subtitle_audio_sync',
             'occlusion', 'continuity', 'encoding', 'listening'}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(',', ':')).encode()).hexdigest()


def filehash(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    temp.replace(path)


@contextmanager
def lock(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a') as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('Resource already locked: ' + str(path))
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def load(task):
    return json.loads((Path(task) / 'task.json').read_text())


def event(task, kind, **fields):
    with (Path(task) / 'events.jsonl').open('a') as f:
        f.write(json.dumps(dict(epoch=time.time(), event=kind, **fields),
                           ensure_ascii=False) + '\n')


def create_task(topic, duration=45, voice=None, config=None, task_id=None, root=ROOT):
    if not topic.strip() or not 30 <= duration <= 45:
        raise ValueError('Nonempty topic and duration 30–45 required by current templates')
    identity = task_id or ('production-' + str(time.time_ns()))
    if not re.fullmatch(r'[A-Za-z0-9_-]+', identity):
        raise ValueError('Unsafe task id')
    task = Path(root) / 'output/tasks' / identity
    task.mkdir(parents=True, exist_ok=False)
    value = dict(schema_version=1, id=identity, topic=topic, duration=duration,
                 voice=voice, config=str(config) if config else None,
                 state='CREATED', created_epoch=time.time(), handoffs={},
                 stages=[], repairs={}, human_interventions=None,
                 tokens=None, tokens_source='Not exposed to deterministic runner',
                 agent_runs=[], engineering_changes=None)
    write(task / 'task.json', value)
    prompt = f'''Act as the sole Producer in this Codex session. Produce: {topic}
Target duration: {duration}s. Requested voice: {voice or 'existing approved default'}.
Task folder: {task}. Config hint: {config or 'select verified existing template'}.
Read AGENTS.md and the three mechanical Skills. Use actual native Codex subagent
tools, at most three children. Do not spawn another Producer.
Use fresh child context (fork_turns="none" when supported), pass role file and
task/input paths rather than this full development transcript or large media.
Dispatch Research and Asset concurrently, each owning only its JSON handoff. Check immutable
handoff hashes via this ledger. Reject an unsupported model or topic; never
invent a complex assembly. Animation waits for qualified asset and mechanical
facts. Editor may prepare speech early, but final composition waits for shots.
Use python -m mechanical_video_next handoff/advance/stage/status commands.
Run keys then inspect images, preview then independent QA, then final and
independent QA. QA must open actual media and bind evidence hashes; unavailable
vision or listening remains UNKNOWN and prevents COMPLETED. Repairs require
issue IDs, measured improvement, <=2 strategies each <=2 attempts. Stop on
failed commands; do not retry automatically. Preserve evidence and report gates.
For an explicit subtitle_text defect use python -m mechanical_video_next.repairs
with exact config hash/cue binding, then dispatch independent QA on repaired media.
For other defects choose an existing asset/template/voice segment and bounded
repair ledger; unsupported alternatives must block rather than invent mechanics.
Log each real child thread ID, timing and available token usage with agent-run.
Deliver final.mp4, captions.srt, timeline.json and structured QA reports in this
task, with exact hashes. Never upload or publish. Single-agent fallback may use
the deterministic stages, but must label dispatch_mode=single and cannot claim
independent QA without another eligible reviewer.
'''
    (task / 'producer-prompt.md').write_text(prompt)
    event(task, 'created', topic=topic)
    return task


def artifact(task, name):
    data = load(task)
    entry = data['handoffs'].get(name)
    if not entry:
        raise ValueError('Missing handoff: ' + name)
    envelope = json.loads((Path(task) / entry['path']).read_text())
    body = {k: v for k, v in envelope.items() if k != 'sha256'}
    if digest(body) != entry['sha256'] or envelope['sha256'] != entry['sha256']:
        raise ValueError('Handoff hash mismatch: ' + name)
    for dep, expected in envelope['dependencies'].items():
        if data['handoffs'].get(dep, {}).get('sha256') != expected:
            raise ValueError('Stale dependency: ' + dep)
        artifact(task, dep)
    return envelope['payload']


def put_handoff(task, role, name, payload, dependencies=None):
    if name not in ROLES.get(role, set()):
        raise ValueError('Role does not own this artifact')
    if not isinstance(payload, dict):
        raise ValueError('Handoff payload must be an object')
    with lock(Path(task) / '.ledger.lock'):
        data = load(task)
        deps = {}
        for dep in dependencies or []:
            artifact(task, dep)
            deps[dep] = data['handoffs'][dep]['sha256']
        required = {'script': {'research'},
                    'animation-manifest': {'research', 'asset-plan'},
                    'preview-qa': {'animation-manifest'},
                    'timeline': {'script', 'animation-manifest'},
                    'final-qa': {'timeline'}}.get(name, set())
        if not required <= set(deps):
            raise ValueError('Required dependencies: ' + ', '.join(sorted(required)))
        if set(deps) != required:
            raise ValueError('Only declared DAG dependencies allowed')
        if role == 'QA':
            fields = {'issue_id', 'severity', 'shot_id', 'time_range', 'evidence',
                      'responsible_agent', 'suggested_fix', 'verification_method'}
            if any(not fields <= set(issue) for issue in payload.get('issues', [])):
                raise ValueError('QA issue missing required fields')
            if any(v not in {'PASS', 'FAIL', 'UNKNOWN'} for v in payload.get('checks', {}).values()):
                raise ValueError('QA checks must be PASS, FAIL or UNKNOWN')
        version = data['handoffs'].get(name, {}).get('version', 0) + 1
        envelope = dict(schema_version=1, role=role, name=name, version=version,
                        dependencies=deps, payload=payload)
        envelope['sha256'] = digest(envelope)
        path = f'handoffs/{name}.v{version}.json'
        if (Path(task) / path).exists():
            raise ValueError('Immutable handoff already exists')
        write(Path(task) / path, envelope)
        data['handoffs'][name] = dict(path=path, version=version, sha256=envelope['sha256'])
        write(Path(task) / 'task.json', data)
        event(task, 'handoff', role=role, name=name, version=version,
              sha256=envelope['sha256'])
    return envelope


def check_media(evidence):
    if not evidence:
        raise ValueError('Actual media evidence is required')
    for item in evidence:
        path = Path(item['path'])
        if path.suffix.lower() not in {'.mp4', '.png', '.wav', '.jpg', '.m4a'}:
            raise ValueError('Evidence must reference media, not a log')
        if not path.is_file() or filehash(path) != item['sha256']:
            raise ValueError('Media evidence missing or changed')


def check_qa(task, name):
    qa = artifact(task, name)
    check_media(qa.get('media'))
    production = artifact(task, 'animation-manifest' if name == 'preview-qa' else 'timeline')
    expected = {(str(Path(m['path']).resolve()), m['sha256']) for m in production.get('media', [])
                if Path(m['path']).suffix.lower() == '.mp4'}
    reviewed = {(str(Path(m['path']).resolve()), m['sha256']) for m in qa['media']
                if Path(m['path']).suffix.lower() == '.mp4'}
    if not expected or not expected <= reviewed:
        raise ValueError('QA must review the exact production MP4')
    checks = qa.get('checks', {})
    if not QA_CHECKS <= set(checks) or any(checks[k] != 'PASS' for k in QA_CHECKS):
        raise ValueError('QA FAIL/UNKNOWN or missing checks prevents advancement')
    if not qa.get('independent_reviewer') or not qa.get('reviewer_thread_id'):
        raise ValueError('Independent reviewer identity is required')
    if qa['reviewer_thread_id'] in {r['thread_id'] for r in load(task)['agent_runs']
                                   if r['role'] in {'Research', 'Asset', 'Animation', 'Editor'}}:
        raise ValueError('QA reviewer also produced this task')
    if any(i.get('severity') in {'critical', 'major', 'error'} for i in qa.get('issues', [])):
        raise ValueError('Unresolved blocking QA defects')
    return qa


def advance(task, target):
    with lock(Path(task) / '.ledger.lock'):
        data = load(task)
        current = data['state']
        if target in {'FAILED', 'BLOCKED'}:
            pass
        elif NEXT.get(current) != target:
            raise ValueError(f'Illegal transition {current} -> {target}')
        if target == 'ASSET_READY':
            artifact(task, 'research')
            artifact(task, 'script')
            asset = artifact(task, 'asset-plan')
            if asset.get('qualified') is not True:
                raise ValueError('Asset not qualified')
            model = asset.get('model', {})
            model_path = Path(model.get('path', ''))
            if (model_path.suffix.lower() not in {'.blend', '.glb'} or not model_path.is_file()
                    or filehash(model_path) != model.get('sha256')
                    or asset.get('independent_meshes') is not True
                    or asset.get('missing_required_parts') != []):
                raise ValueError('Verified model evidence and complete independent meshes required')
        if target == 'PREVIEW_READY':
            animation = artifact(task, 'animation-manifest')
            check_media(animation.get('media'))
            if not animation.get('keyframes_verified'):
                raise ValueError('Keyframe verification missing')
        if target == 'EDITING':
            check_qa(task, 'preview-qa')
        if target == 'FINAL_CHECKING':
            timeline = artifact(task, 'timeline')
            check_media(timeline.get('media'))
            if timeline.get('technical_pass') is not True:
                raise ValueError('Technical validation missing')
        if target == 'COMPLETED':
            check_qa(task, 'preview-qa')
            check_qa(task, 'final-qa')
        data['state'] = target
        write(Path(task) / 'task.json', data)
        event(task, 'state', previous=current, state=target)


def repair_attempt(task, issue_id, strategy, score):
    """Register one measured bounded attempt; lower defect score is better.

    The first score is a baseline; subsequent calls consume attempts. No
    improvement stops the issue. Reopen only through an explicit new task.
    """
    if not math.isfinite(score) or score < 0:
        raise ValueError('Defect score must be finite and nonnegative')
    with lock(Path(task) / '.ledger.lock'):
        data = load(task)
        issues = data['repairs']
        if issue_id not in issues:
            issues[issue_id] = dict(baseline=score, best=score, strategies={}, stopped=False)
            if data['state'] != 'REPAIRING':
                data['repair_return_state'] = data['state']
            data['state'] = 'REPAIRING'
            write(Path(task) / 'task.json', data)
            event(task, 'repair_baseline', issue_id=issue_id, score=score)
            return issues[issue_id]
        issue = issues[issue_id]
        if issue['stopped']:
            raise ValueError('Issue stopped: no measured improvement')
        attempts = issue['strategies']
        if strategy not in attempts and len(attempts) >= 2:
            raise ValueError('At most two repair strategies')
        if attempts.get(strategy, 0) >= 2:
            raise ValueError('At most two attempts per strategy')
        attempts[strategy] = attempts.get(strategy, 0) + 1
        previous = issue['best']
        issue['best'] = min(previous, score)
        if score >= previous:
            issue['stopped'] = True
            data['state'] = 'BLOCKED'
        else:
            if data['state'] != 'REPAIRING':
                data['repair_return_state'] = data['state']
            data['state'] = 'REPAIRING'
        write(Path(task) / 'task.json', data)
        event(task, 'repair', issue_id=issue_id, strategy=strategy, score=score,
              attempt=attempts[strategy], stopped=issue['stopped'])
    return issue


def run_stage(task, phase, config, env_file=None, workprint=False):
    """Execute existing deterministic script once; serialize all Blender work."""
    if phase not in {'keys', 'preview', 'final'}:
        raise ValueError('Unsupported stage')
    data = load(task)
    allowed = {'keys': {'ASSET_READY', 'ANIMATING'},
               'preview': {'ANIMATING', 'PREVIEW_READY', 'PREVIEW_CHECKING'},
               'final': {'EDITING', 'FINAL_CHECKING'}}
    if phase == 'final' and workprint and data['state'] == 'PREVIEW_CHECKING':
        qa = artifact(task, 'preview-qa')
        check_media(qa.get('media'))
        if any(value == 'FAIL' for value in qa.get('checks', {}).values()):
            raise ValueError('Known failed QA cannot be bypassed for workprint')
    elif data['state'] not in allowed[phase]:
        raise ValueError('Stage lacks verified prerequisites: ' + data['state'])
    if phase == 'final' and not (workprint and data['state'] == 'PREVIEW_CHECKING'):
        check_qa(task, 'preview-qa')
    # Existing cleanup only removes old completed content-addressed entries,
    # skips protected/task-referenced entries and shares our global lock.
    sys.path.insert(0, str(ROOT / 'scripts'))
    from clean import cleanup
    cleanup(older_hours=168, apply=True)
    with lock(ROOT / 'work/production.lock'):
        start = time.time()
        args = [sys.executable, str(ROOT / 'scripts/produce.py'), str(config), '--phase', phase]
        if env_file:
            args += ['--env-file', str(env_file)]
        logfile = Path(task) / ('stage-' + phase + '-' + str(time.time_ns()) + '.log')
        try:
            with logfile.open('w') as out:
                subprocess.run(args, cwd=ROOT, stdout=out, stderr=subprocess.STDOUT, check=True)
        except subprocess.CalledProcessError:
            advance(task, 'FAILED')
            event(task, 'stage_failed', phase=phase, seconds=time.time()-start, log=str(logfile))
            raise
        with lock(Path(task) / '.ledger.lock'):
            data = load(task)
            observations = []
            for line in logfile.read_text().splitlines():
                try:
                    observation = json.loads(line)
                except ValueError:
                    continue
                if isinstance(observation, dict) and 'cache_hit' in observation:
                    observations.append(observation)
            row = dict(phase=phase, seconds=round(time.time()-start, 3), log=str(logfile),
                       command_success=True, quality_accepted=False, unaccepted_workprint=workprint,
                       cache_observations=observations,
                       cache_hit_rate=(sum(r['cache_hit'] for r in observations)/len(observations)
                                       if observations else None),
                       full_shot_renders=sum(r['stage'].startswith('final:') and not r['cache_hit']
                                             for r in observations))
            data['stages'].append(row)
            write(Path(task) / 'task.json', data)
            event(task, 'stage', **row)
    return logfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('produce')
    p.add_argument('--topic', required=True)
    p.add_argument('--duration', type=int, default=45)
    p.add_argument('--voice')
    p.add_argument('--config', type=Path)
    p.add_argument('--task-id')
    p.add_argument('--codex', action='store_true', help='Start a NEW actual Codex Producer session')
    for name in ['status', 'advance', 'stage', 'handoff', 'repair', 'agent-run', 'resume-repair']:
        p = sub.add_parser(name)
        p.add_argument('task', type=Path)
        if name == 'advance':
            p.add_argument('state')
        elif name == 'stage':
            p.add_argument('phase', choices=['keys', 'preview', 'final'])
            p.add_argument('--config', required=True, type=Path)
            p.add_argument('--env-file', type=Path)
            p.add_argument('--workprint', action='store_true',
                           help='Explicitly render unaccepted final workprint after preview QA UNKNOWN')
        elif name == 'handoff':
            p.add_argument('--role', required=True, choices=ROLES)
            p.add_argument('--name', required=True)
            p.add_argument('--input', required=True, type=Path)
            p.add_argument('--depends', nargs='*', default=[])
        elif name == 'repair':
            p.add_argument('--issue', required=True)
            p.add_argument('--strategy', required=True)
            p.add_argument('--score', type=float, required=True)
        elif name == 'agent-run':
            p.add_argument('--role', required=True, choices=ROLES)
            p.add_argument('--thread-id', required=True)
            p.add_argument('--seconds', type=float, required=True)
            p.add_argument('--tokens', type=int)
    args = parser.parse_args()
    if args.command == 'produce':
        task = create_task(args.topic, args.duration, args.voice, args.config, args.task_id)
        print(task)
        if args.codex:
            event(task, 'codex_launch', dispatch_mode='native_codex')
            with (task / 'codex.jsonl').open('w') as log:
                try:
                    subprocess.run(['codex', 'exec', '--strict-config', '--json', '-C', str(ROOT),
                                    (task / 'producer-prompt.md').read_text()], stdout=log,
                                   stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, check=True)
                except (subprocess.CalledProcessError, OSError) as error:
                    advance(task, 'FAILED')
                    event(task, 'codex_launch_failed', reason=str(error),
                          log=str(task / 'codex.jsonl'))
                    raise
        return
    if args.command == 'status':
        print(json.dumps(load(args.task), ensure_ascii=False, indent=2))
    elif args.command == 'advance':
        advance(args.task, args.state)
    elif args.command == 'stage':
        print(run_stage(args.task, args.phase, args.config, args.env_file, args.workprint))
    elif args.command == 'handoff':
        print(json.dumps(put_handoff(args.task, args.role, args.name,
                                    json.loads(args.input.read_text()), args.depends), ensure_ascii=False))
    elif args.command == 'repair':
        print(json.dumps(repair_attempt(args.task, args.issue, args.strategy, args.score)))
    elif args.command == 'resume-repair':
        with lock(args.task / '.ledger.lock'):
            data = load(args.task)
            if data['state'] != 'REPAIRING' or any(i['stopped'] for i in data['repairs'].values()):
                raise ValueError('No resumable repair')
            for name in data['handoffs']:
                artifact(args.task, name)
            target = data['repair_return_state']
            if target in {'EDITING', 'FINAL_CHECKING', 'COMPLETED'}:
                check_qa(args.task, 'preview-qa')
            if target == 'COMPLETED':
                check_qa(args.task, 'final-qa')
            if any(not issue['strategies'] for issue in data['repairs'].values()):
                raise ValueError('Baseline without measured repair cannot resume')
            data['state'] = data.pop('repair_return_state')
            write(args.task / 'task.json', data)
            event(args.task, 'repair_resume', state=data['state'])
    elif args.command == 'agent-run':
        with lock(args.task / '.ledger.lock'):
            data = load(args.task)
            row = dict(role=args.role, thread_id=args.thread_id, seconds=args.seconds, tokens=args.tokens)
            data['agent_runs'].append(row)
            write(args.task / 'task.json', data)
            event(args.task, 'agent_run', **row)
