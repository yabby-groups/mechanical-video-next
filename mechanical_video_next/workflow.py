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
         'MechanicalResearch': {'research'}, 'CAD': {'cad-model', 'asset-plan'},
         'ViralResearch': {'viral-analysis', 'creative-blueprint'},
         'Producer': {'feasibility', 'diagnostic-animatic'},
         'Animation': {'animation-manifest', 'animatic-manifest', 'mechanical-diagnostics'},
         'Editor': {'timeline', 'audio-preparation'},
         'QA': {'preview-qa', 'final-qa', 'animatic-qa', 'diagnostic-qa', 'mechanical-qa'}}
NEXT = {'CREATED': 'RESEARCHING', 'RESEARCHING': 'ASSET_READY',
        'ASSET_READY': 'ANIMATING', 'ANIMATING': 'PREVIEW_READY',
        'PREVIEW_READY': 'PREVIEW_CHECKING', 'PREVIEW_CHECKING': 'EDITING',
        'EDITING': 'FINAL_CHECKING', 'FINAL_CHECKING': 'COMPLETED'}
QA_CHECKS = {'mechanics', 'explosion_clarity', 'subtitle_audio_sync',
             'occlusion', 'continuity', 'encoding', 'listening'}
FEASIBILITY_CHECKS = {'observation_basis', 'mechanics', 'model_motion',
                      'tool_support', 'unsupported_effects'}
ANIMATIC_CHECKS = QA_CHECKS | {'blueprint_fidelity'}
AUTONOMY_POLICY = {
    'mode': 'producer-managed', 'routine_user_confirmation': False,
    'repair_mode': 'until_pass', 'max_repair_rounds': None, 'token_budget': None,
    'on_no_improvement': 'change_strategy',
    'acceptance': 'existing_quality_gates', 'reference_first': True,
    'breakout_required': False, 'physical_reference_to_cad': True,
}
LEGACY_DEPENDENCIES = {'script': {'research'},
                       'animation-manifest': {'research', 'asset-plan'},
                       'preview-qa': {'animation-manifest'},
                       'timeline': {'script', 'animation-manifest'},
                       'final-qa': {'timeline'}}
V2_DEPENDENCIES = dict(LEGACY_DEPENDENCIES, **{
    'cad-model': {'research'},
    'mechanical-diagnostics': {'research', 'asset-plan', 'cad-model'},
    'audio-preparation': {'research'},
    'mechanical-qa': {'research', 'asset-plan', 'cad-model', 'mechanical-diagnostics'},
    'diagnostic-animatic': {'research', 'asset-plan'},
    'diagnostic-qa': {'diagnostic-animatic'},
    'creative-blueprint': {'viral-analysis'},
    'feasibility': {'creative-blueprint', 'research', 'asset-plan'},
    'script': {'research', 'creative-blueprint'},
    'animatic-manifest': {'research', 'asset-plan', 'creative-blueprint', 'feasibility'},
    'animatic-qa': {'animatic-manifest', 'creative-blueprint'},
    'animation-manifest': {'research', 'asset-plan', 'creative-blueprint', 'feasibility',
                           'animatic-manifest', 'animatic-qa'}})


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
    data = json.loads((Path(task) / 'task.json').read_text())
    protocol_version(data)
    return data


def protocol_version(data):
    # Historical schema-1 ledgers predate protocol_version. New schema-2
    # ledgers must carry it explicitly; stripping it must not bypass gates.
    version = data.get('protocol_version', 1 if data.get('schema_version') == 1 else None)
    if type(version) is not int or version not in {1, 2}:
        raise ValueError('Missing or unsupported production protocol_version')
    if data.get('schema_version', 1) >= 2 and version != 2:
        raise ValueError('New tasks require production protocol_version=2')
    return version


def event(task, kind, **fields):
    with (Path(task) / 'events.jsonl').open('a') as f:
        f.write(json.dumps(dict(epoch=time.time(), event=kind, **fields),
                           ensure_ascii=False) + '\n')


def create_task(topic, duration=None, voice=None, config=None, task_id=None, root=ROOT,
                protocol_version=2, asset_strategy='autonomous-cad', routes='all'):
    requested_routes = ['2d', '2.5d', '3d'] if routes == 'all' else [routes]
    if not set(requested_routes) <= {'2d', '2.5d', '3d'}:
        raise ValueError('Unsupported requested routes')
    if type(protocol_version) is not int or protocol_version not in {1, 2}:
        raise ValueError('Unsupported production protocol_version')
    minimum_duration, maximum_duration = (30, 45) if protocol_version == 1 else (120, 300)
    if duration is None:
        duration = 45 if protocol_version == 1 else None
    if not topic.strip() or (duration is not None and (isinstance(duration, bool) or not isinstance(duration, (int, float)) or not minimum_duration <= duration <= maximum_duration)):
        raise ValueError(f'Nonempty topic and duration {minimum_duration}–{maximum_duration} required for protocol {protocol_version}')
    if protocol_version == 1:
        asset_strategy = None  # Explicit historical tasks retain their original asset contract.
    elif asset_strategy not in {'autonomous-cad', 'verified-existing', 'illustrated'}:
        raise ValueError('New tasks require an explicit supported asset strategy')
    identity = task_id or ('production-' + str(time.time_ns()))
    if not re.fullmatch(r'[A-Za-z0-9_-]+', identity):
        raise ValueError('Unsafe task id')
    task = Path(root) / 'output/tasks' / identity
    task.mkdir(parents=True, exist_ok=False)
    value = dict(schema_version=protocol_version, protocol_version=protocol_version,
                 asset_strategy=asset_strategy,
                 id=identity, topic=topic, duration=duration,
                 voice=voice, config=str(config) if config else None,
                 state='CREATED', created_epoch=time.time(), handoffs={},
                 stages=[], repairs={}, human_interventions=None,
                 tokens=None, tokens_source='Not exposed to deterministic runner',
                 agent_runs=[], engineering_changes=None)
    if protocol_version == 2:
        value['content_policy_version'] = 1
        value['duration_policy'] = {'minimum': 120, 'maximum': 300, 'mode': 'knowledge-driven' if duration is None else 'requested', 'requested_seconds': duration}
        value['production_method'] = ('original-shared-script-three-routes'
                                      if len(requested_routes) == 3 else 'reference-recreation')
        value['autonomy_policy'] = dict(AUTONOMY_POLICY)
        value['requested_routes'] = requested_routes
        value['route_runs'] = {route: {'status': 'PENDING', 'outputs': {}} for route in requested_routes}
        value['shared_production'] = {
            'directory': str(task / 'shared'),
            'timeline': {'path': str(task / 'shared/timeline.json'), 'sha256': None},
            'narration': {'path': str(task / 'shared/narration.wav'), 'sha256': None},
            'cache_policy': 'content-and-config-sha256; narration shared across routes; geometry scoped by route',
            'comparison_directory': str(task / 'multiroute')}
    write(task / 'task.json', value)
    prompt = f'''Act as the sole Producer in this Codex session. Produce: {topic}
Target duration: {duration}s. Requested voice: {voice or 'existing approved default'}.
New content policy accepts 120–300s; unspecified duration is knowledge-driven, not fixed.
Before freezing, choose duration from reliable knowledge and measured Neil narration.
Bind content_policy_version=1 and growth_goals in the blueprint. See docs/longform-contract.md.
Use original narration and shot order informed by observed references, not copied expression.
Complete the current question before bridging to a documented next episode.
Historical tasks retain their existing duration and assets.
Keep a fast, information-dense pace: open immediately with a striking action, surprising
fact or concrete question; every shot advances a new fact or causal step. Synchronize
explanation with visible motion; use close-ups, sections and comparisons where useful.
Build length through supported explanation and distinct demonstrations, never slower
playback, repeated footage, filler holds or artificially accelerated narration.
End by resolving the opening question. QA must inspect the exact media for hook,
information progression, action/narration alignment, repetition and actual duration;
retain UNKNOWN for unavailable perceptual checks, never infer audience retention.
Match narration and shared shot timings naturally. Do not stretch the fixed nail-clipper
adapter or accelerate audio merely to claim a requested duration was achieved.
Task folder: {task}. Config hint: {config or 'select verified existing template'}.
Requested output routes: {', '.join(requested_routes)}. Produce ALL requested routes;
render_route remains the legacy primary-route field, not permission to omit other requested routes.
Use one shared reference, script, shot order, timeline and approved narration under {task}/shared.
Animation owns route-scoped keys, shots and manifests; Editor composes every requested route.
Keep route-specific asset/config/media hashes and caches separate; identical narration is shared.
Independent QA records each route and exact hash plus the synchronized comparison.
For multi-route completion final-qa must include route_checks keyed by every requested route,
each with media={{path,sha256}} and all standard QA checks PASS; UNKNOWN never completes a route.
Use the existing workflow route-run command with an authored deterministic plan to resume renders.
If a requested route is unavailable, record its concrete issue and next step; do not silently drop it.
Task preparation does not prove arbitrary mechanical names already have a CAD/render adapter.
Every new video requires its own reference research before script/blueprint freeze.
Breakout videos are inspiration, not a prerequisite. Followers, likes and publication
age do not gate production. Ordinary physical demonstrations, teardowns and manufacturer
videos are valid references: recreate their mechanisms and demonstrations in CAD.
Do not stop production or search indefinitely solely because no breakout was found.
Select an observed same-topic PRIMARY reference and record its true qualification.
Check its actual content and reproduction feasibility before commissioning production CAD.
The selected video's shots, timing, actions and explanation are the production specification.
Do not invent hidden structures, a new story or an industrial-design verification project.
One verified reproducible primary is sufficient; B/C references are optional supplements.
If a candidate lacks useful content, reselect autonomously; candidate lists alone
never authorize production. MechanicalResearch may assess feasibility without full modeling.
Production method: reference-recreation. Select one observed primary reference,
study its opening, narrative structure, pacing and key demonstrations; write original shot order
using our own CAD, animation and narration. Preserve the approved EP03 look and Neil voice.
Cached observations can be reused with dates and freshness checks, but each video
needs a task-specific research conclusion. Include task_id={identity} and the exact
task topic in candidates.json; viral analyze preserves that task binding.
The FROZEN blueprint must include reference_recreation={{primary_reference_id,
shot_mapping:[{{shot_id, reference_time_range:[start,end], adaptation}}]}}.
For image/diagram/structure sources replace reference_time_range with reference_region.
Map every production shot exactly once to an observed interval or depicted structure feature; adaptation explains what is recreated and any necessary changes.
Independent QA compares the exact rendered video with that mapping and reference.
Read AGENTS.md and the three mechanical Skills. Use actual native Codex subagent
tools, at most three children. Do not spawn another Producer.
Run every external Python command through uv run, including temporary scripts,
tests and child processes. For CAD use uv run --with-requirements requirements-cad.txt python.
Use fresh child context (fork_turns="none" when supported), pass role file and
task/input paths rather than this full development transcript or large media.
Dispatch Research and Asset concurrently, each owning only its JSON handoff. Check immutable
handoff hashes via this ledger. Reject an unsupported model or topic; never
invent a complex assembly. Animation waits for qualified asset and mechanical
facts. Editor may prepare speech early, but final composition waits for shots.
Production protocol: {protocol_version}. For protocol 2 dispatch ViralResearch
using .codex/agents/viral_research.toml before final scripting. It owns
viral-analysis and creative-blueprint, binding observed reference media and
shot-level adaptation. Read the viral-video-research Skill. Search the local
reference_library first and reuse dated observations before network research;
do not claim old counts are current or reanalyze an already covered video.
Start with up to 30 candidates and 10 deep analyses; expand when useful. Popularity is optional.
Images, diagrams and structure documents are valid observed references. Select 2d/2.5d
with illustrated assets and layered shots when that communicates the demonstrated mechanism;
use CAD for 3d. Never stop because a breakout video or complete CAD is unavailable. Separate A
(same topic, 50%), B (same mechanism, 30%), C (transferable expression, 20%)
references; unsupported ratios remain an explicit gap, never invented samples.
Research/Asset preparation may run before the blueprint,
but script must depend on research and creative-blueprint. Producer registers
feasibility depending exactly on creative-blueprint, research and asset-plan;
observation_basis, mechanics, model_motion, tool_support and unsupported_effects
checks must all PASS. This freezes that exact immutable blueprint version;
any change invalidates downstream approvals. Compile the executable blueprint
using uv run python -m mechanical_video_next.blueprint compile, inspect its supported template
mapping and binding receipt, then hand off a new immutable FROZEN blueprint
with production_config={{path, sha256}} matching the exact task config file.
This binding must survive every render gate; changing the config invalidates QA.
Animation then registers an actual
animatic-manifest depending on research, asset-plan, creative-blueprint and
feasibility. Use uv run python -m mechanical_video_next.blueprint animatic for the
supported screenshot-based animatic and separately validate the actual 3–5s
critical motion clip. A static animatic cannot prove motion or complete listening;
unsupported capabilities remain UNKNOWN. Register actual MP4/hash separately.
Dispatch independent QA for animatic-qa, depending on animatic-manifest and
creative-blueprint, with all ANIMATIC_CHECKS PASS and exact media/reviewer ID.
Only then may full preview or final render begin, including workprints.
animation-manifest must depend on all six approved inputs. Recheck stale hashes.
Before feasibility, Producer may register diagnostic-animatic with status
DRAFT_UNAPPROVED, exact MP4/hash and blueprint_evidence JSON path/hash, depending
on research and asset-plan. Independent diagnostic-qa may document actual defects
and repair evidence; these diagnostic artifacts never grant full render approval.
Use uv run python -m mechanical_video_next handoff/advance/stage/status commands.
Run keys then inspect images, preview then independent QA, then final and
independent QA. QA must open actual media and bind evidence hashes; unavailable
vision or listening remains UNKNOWN and prevents COMPLETED. Repairs require
issue IDs and stable defect_key (failure type plus component/requirement,
never a media hash), measured results and independent rechecks.
Renaming an issue or changing media never erases that defect's repair history.
On failed commands, preserve evidence, diagnose, repair and resume through the ledger.
For an explicit subtitle_text defect use uv run python -m mechanical_video_next.repairs
with exact config hash/cue binding, then dispatch independent QA on repaired media.
For other defects choose an evidence-supported asset/template/voice segment and measured
repair ledger; unsupported alternatives must block rather than invent mechanics.
Log each real child thread ID, timing and available token usage with agent-run.
Deliver final.mp4, captions.srt, timeline.json and structured QA reports in this
task, with exact hashes. Never upload or publish. Single-agent fallback may use
the deterministic stages, but must label dispatch_mode=single and cannot claim
independent QA without another eligible reviewer.
'''
    if asset_strategy == 'autonomous-cad':
        prompt = prompt.replace(
            'Dispatch Research and Asset concurrently, each owning only its JSON handoff.',
            'Dispatch ViralResearch and MechanicalResearch for independent creative and mechanical facts. '
            'CAD then owns parameterized solids and measured assembly evidence.')
        prompt = prompt.replace('Research/Asset preparation may run before the blueprint,',
                                'MechanicalResearch and CAD preparation may run before the blueprint,')
        prompt += '''\nAsset policy: choose 3d CAD or illustrated 2d/2.5d based on observed sources.
Before asset/blueprint handoffs, use select-route with route and reason to update this task.
The following CAD requirements apply only to the 3d route; illustrated assets use
source_files path/hash and render_route, layered shots, and actual media inspection.
Never use downloaded finished models as the default or stop on a model-site login.
MechanicalResearch owns structure, connections, constraints, dimensional evidence
and unknowns. CAD owns repeatable source, parameters, independent solids, STEP,
GLB, inventory, local frames and geometric/motion validation. ViralResearch owns
creative references only; never infer hidden dimensions from reference videos.
Use .agents/skills/cad/SKILL.md and mechanical-research/SKILL.md.
First produce assembly/exploded/section images and 3-5s closing/opening diagnostics.
Independent QA registers mechanical-qa against research, cad-model and asset-plan.
Mechanical acceptance precedes HD animation; dynamic storyboard acceptance
precedes full preview/final. Neither gate can hide incorrect mechanics by camera.
Preserve inherited defects and measured repair history while applying the current autonomy policy.
Producer is this session; never create another controller agent.\n'''
    prompt += '''\nCurrent user autonomy policy:
The user supplies a mechanism name. Producer owns research, reference selection,
modeling, implementation decisions, diagnosis, repairs and independent rechecks
without routine user confirmation. No user-imposed token or total repair-round limit.
On no improvement, diagnose and change the implementation/strategy, preserve the
same defect history and continue. A failed command ends that invocation; Producer
diagnoses, repairs and resumes automatically. Do not blindly repeat unchanged failures.
For an assigned older task, use adopt-autonomy with the user's recorded instruction
as reason; preserve all prior evidence. Quality gates and actual resource limits remain.
This is a Producer policy, not a Python agent loop or proof of unattended capability.
Unavailable required evidence stays UNKNOWN. Never waive listening/continuous-video
acceptance merely because the user asks to discuss the non-audiovisual case.
'''
    if value.get('production_method') == 'original-shared-script-three-routes':
        start = prompt.index('Every new video requires its own reference research')
        end = prompt.index('Read AGENTS.md and the three mechanical Skills.', start)
        prompt = prompt[:start] + f'''Production method: original-shared-script-three-routes.
Research observed references to learn verified structure, motion, and explanatory techniques;
reference learning is not recreation of a video's opening, narrative or shot sequence.
Write an original shared script and original shot order. Do not copy a reference shot sequence.
Keep one original script, narration and timeline across all three routes so they are comparable.
Preserve the approved EP03 look and Neil voice. Do not invent unsupported mechanical facts,
hidden structures, or an industrial-design claim. Bind research to task_id={identity} and topic.
Record factual sources and uncertainty. No fabricated viewing, metrics or qualification.
The FROZEN blueprint binds this original script, factual sources, mechanical claims,
observable shot goals and executable config/hash; it does not require reference_recreation
or a one-to-one mapping to an existing video's shot sequence.
Independent QA checks the original teaching goals, actual mechanical evidence, frozen blueprint,
exact media, all three route hashes and shared timeline. Scientific and sensory gates remain.
''' + prompt[end:]
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
        v2 = protocol_version(data) == 2
        required = (V2_DEPENDENCIES if v2 else LEGACY_DEPENDENCIES).get(name, set())
        if not v2 and name in {'viral-analysis', 'creative-blueprint', 'feasibility',
                               'animatic-manifest', 'animatic-qa',
                               'diagnostic-animatic', 'diagnostic-qa'}:
            raise ValueError('Artifact requires production protocol_version=2')
        if not required <= set(deps):
            raise ValueError('Required dependencies: ' + ', '.join(sorted(required)))
        if set(deps) != required:
            raise ValueError('Only declared DAG dependencies allowed')
        if (v2 and name in {'cad-model', 'asset-plan'}
                and data.get('autonomy_policy', {}).get('reference_first')):
            from .viral import validate_viral_analysis
            reference = artifact(task, 'viral-analysis')
            validate_viral_analysis(reference)
            check_research_binding(data, reference)
        if v2 and name in {'viral-analysis', 'creative-blueprint'}:
            from .viral import validate_viral_analysis, validate_creative_blueprint
            (validate_viral_analysis if name == 'viral-analysis'
             else validate_creative_blueprint)(payload)
            if name == 'viral-analysis' and data.get('production_method') == 'reference-recreation':
                check_research_binding(data, payload)
            if name == 'creative-blueprint':
                if data.get('content_policy_version') == 1:
                    from .growth import validate_contract
                    if payload.get('content_policy_version') != 1:
                        raise ValueError('New task requires content_policy_version=1 blueprint')
                    validate_contract(payload, data.get('duration'))
                selected = set(artifact(task, 'viral-analysis').get('selected_ids', []))
                used = {item.get('reference_id') for item in payload.get('reference_principles', [])}
                if not used or not used <= selected:
                    raise ValueError('Blueprint principles must bind selected observed references')
                if data.get('production_method') == 'reference-recreation':
                    check_recreation(task, payload)
        if v2 and name == 'feasibility':
            checks = payload.get('checks', {})
            if not FEASIBILITY_CHECKS <= set(checks) or any(
                    value != 'PASS' for value in checks.values()):
                raise ValueError('Feasibility requires every check PASS; FAIL/UNKNOWN blocks')
            check_asset(task)
        if v2 and name == 'animatic-manifest':
            check_media(payload.get('media'))
            if not any(Path(item['path']).suffix.lower() == '.mp4'
                       for item in payload['media']):
                raise ValueError('Animatic requires actual MP4 evidence')
        if v2 and name == 'diagnostic-animatic':
            if payload.get('status') != 'DRAFT_UNAPPROVED':
                raise ValueError('Diagnostic animatic must remain DRAFT_UNAPPROVED')
            check_media(payload.get('media'))
            if not any(Path(item['path']).suffix.lower() == '.mp4' for item in payload['media']):
                raise ValueError('Diagnostic animatic requires actual MP4 evidence')
            evidence = payload.get('blueprint_evidence', {})
            blueprint_path = Path(evidence.get('path', ''))
            if (blueprint_path.suffix.lower() != '.json' or not blueprint_path.is_file()
                    or filehash(blueprint_path) != evidence.get('sha256')):
                raise ValueError('Diagnostic blueprint JSON evidence missing or changed')
            if not isinstance(json.loads(blueprint_path.read_text()), dict):
                raise ValueError('Diagnostic blueprint JSON must be an object')
        if v2 and name == 'diagnostic-qa':
            check_media(payload.get('media'))
            diagnostic = artifact(task, 'diagnostic-animatic')
            expected = {(str(Path(m['path']).resolve()), m['sha256']) for m in diagnostic['media']
                        if Path(m['path']).suffix.lower() == '.mp4'}
            reviewed = {(str(Path(m['path']).resolve()), m['sha256']) for m in payload['media']
                        if Path(m['path']).suffix.lower() == '.mp4'}
            if not expected <= reviewed:
                raise ValueError('Diagnostic QA must review the exact diagnostic MP4')
            if (payload.get('independent_reviewer') is not True or not payload.get('reviewer_thread_id')
                    or payload['reviewer_thread_id'] in {
                        r['thread_id'] for r in data['agent_runs'] if r['role'] != 'QA'}):
                raise ValueError('Diagnostic QA requires independent reviewer identity')
        if v2 and name == 'animation-manifest':
            require_animatic(task)
        if role == 'QA':
            fields = {'issue_id', 'severity', 'shot_id', 'time_range', 'evidence',
                      'responsible_agent', 'suggested_fix', 'verification_method'}
            if any(not fields <= set(issue) for issue in payload.get('issues', [])):
                raise ValueError('QA issue missing required fields')
            if v2:
                for issue in payload.get('issues', []):
                    validate_defect_key(issue.get('defect_key'))
            if any(v not in {'PASS', 'FAIL', 'UNKNOWN'} for v in payload.get('checks', {}).values()):
                raise ValueError('QA checks must be PASS, FAIL or UNKNOWN')
        from .qa_images import handoff_visuals
        visual_evidence = handoff_visuals(payload)
        version = data['handoffs'].get(name, {}).get('version', 0) + 1
        envelope = dict(schema_version=1, role=role, name=name, version=version,
                        dependencies=deps, payload=payload, visual_evidence=visual_evidence)
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


def check_research_binding(data, research):
    if research.get('task_id') != data['id'] or research.get('topic') != data['topic']:
        raise ValueError('Every video requires research bound to its own task_id and topic')


def check_recreation(task, blueprint):
    from .viral import validate_reference_recreation
    data = load(task)
    if data.get('production_method') != 'reference-recreation':
        return
    research = artifact(task, 'viral-analysis')
    check_research_binding(data, research)
    validate_reference_recreation(blueprint, research)


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
    if name not in {'preview-qa', 'animatic-qa', 'final-qa'}:
        raise ValueError('Diagnostic reports cannot grant production acceptance')
    qa = artifact(task, name)
    check_media(qa.get('media'))
    production = artifact(task, {'preview-qa': 'animation-manifest',
                                 'animatic-qa': 'animatic-manifest',
                                 'final-qa': 'timeline'}[name])
    expected = {(str(Path(m['path']).resolve()), m['sha256']) for m in production.get('media', [])
                if Path(m['path']).suffix.lower() == '.mp4'}
    reviewed = {(str(Path(m['path']).resolve()), m['sha256']) for m in qa['media']
                if Path(m['path']).suffix.lower() == '.mp4'}
    if not expected or not expected <= reviewed:
        raise ValueError('QA must review the exact production MP4')
    if load(task).get('content_policy_version') == 1:
        from .growth import validate_media_checks, check_media_duration
        blueprint = artifact(task, 'creative-blueprint')
        validate_media_checks(blueprint, qa)
        check_media_duration(blueprint, production['media'])
    checks = qa.get('checks', {})
    required_checks = ANIMATIC_CHECKS if name == 'animatic-qa' else QA_CHECKS
    if not required_checks <= set(checks) or any(value != 'PASS' for value in checks.values()):
        raise ValueError('QA FAIL/UNKNOWN or missing checks prevents advancement')
    if not qa.get('independent_reviewer') or not qa.get('reviewer_thread_id'):
        raise ValueError('Independent reviewer identity is required')
    if qa['reviewer_thread_id'] in {r['thread_id'] for r in load(task)['agent_runs']
            if r['role'] in {'Research', 'MechanicalResearch', 'CAD', 'ViralResearch', 'Producer',
                                                    'Asset', 'Animation', 'Editor'}}:
        raise ValueError('QA reviewer also produced this task')
    if any(i.get('severity') in {'critical', 'major', 'error'} for i in qa.get('issues', [])):
        raise ValueError('Unresolved blocking QA defects')
    return qa


def check_asset(task):
    asset = artifact(task, 'asset-plan')
    if asset.get('qualified') is not True:
        raise ValueError('Asset not qualified')
    if load(task).get('asset_strategy') == 'illustrated':
        from PIL import Image
        if asset.get('render_route') not in {'2d', '2.5d'} or not asset.get('source_files'):
            raise ValueError('Illustrated asset requires route and image sources')
        for item in asset['source_files']:
            path = ROOT / item['path']
            if not path.is_file() or filehash(path) != item.get('sha256'):
                raise ValueError('Illustrated source missing or changed')
            with Image.open(path) as image:
                image.verify()
        return asset
    model = asset.get('model', {})
    model_path = Path(model.get('path', ''))
    if (model_path.suffix.lower() not in {'.blend', '.glb'} or not model_path.is_file()
            or filehash(model_path) != model.get('sha256')
            or asset.get('independent_meshes') is not True
            or asset.get('missing_required_parts') != []):
        raise ValueError('Verified model evidence and complete independent meshes required')
    return asset


MECHANICAL_CHECKS = {'solids', 'assembly', 'motion', 'interference',
                     'retention', 'mechanism_visibility'}
CAD_FILES = {'source', 'parameters', 'step', 'glb', 'inventory', 'validation'}


def check_cad(task):
    """Bind autonomous geometry and reports to reproducible source bytes."""
    cad = artifact(task, 'cad-model')
    files = cad.get('files', {})
    if not CAD_FILES <= set(files):
        raise ValueError('CAD source, parameters, STEP, GLB, inventory and validation required')
    for name, item in files.items():
        path = Path(item.get('path', ''))
        if not path.is_file() or filehash(path) != item.get('sha256'):
            raise ValueError('CAD artifact missing or changed: ' + name)
    if Path(files['step']['path']).suffix.lower() not in {'.step', '.stp'}:
        raise ValueError('CAD primary artifact must be STEP')
    if Path(files['glb']['path']).suffix.lower() != '.glb':
        raise ValueError('CAD independent mesh export must be GLB')
    report = json.loads(Path(files['validation']['path']).read_text())
    if report.get('numerical_status', report.get('status')) != 'PASS':
        raise ValueError('CAD numerical validation not PASS')
    asset = check_asset(task)
    if asset['model'] != files['glb']:
        raise ValueError('Asset model differs from validated CAD GLB')
    return cad


def require_mechanical(task):
    """A separate independent mechanical gate, before full production."""
    data = load(task)
    if data.get('asset_strategy') != 'autonomous-cad':
        return
    check_cad(task)
    qa = artifact(task, 'mechanical-qa')
    check_media(qa.get('media'))
    diagnostics = artifact(task, 'mechanical-diagnostics')
    expected = {(str(Path(m['path']).resolve()), m['sha256'])
                for m in diagnostics.get('media', []) if Path(m['path']).suffix.lower() == '.mp4'}
    reviewed = {(str(Path(m['path']).resolve()), m['sha256'])
                for m in qa['media'] if Path(m['path']).suffix.lower() == '.mp4'}
    if not expected or not expected <= reviewed:
        raise ValueError('Mechanical QA must review the exact closing/opening diagnostic MP4')
    checks = qa.get('checks', {})
    if not MECHANICAL_CHECKS <= set(checks) or any(v != 'PASS' for v in checks.values()):
        raise ValueError('Mechanical FAIL/UNKNOWN or missing checks blocks production')
    reviewer = qa.get('reviewer_thread_id')
    if (qa.get('independent_reviewer') is not True or not reviewer or
            reviewer in {r['thread_id'] for r in data['agent_runs'] if r['role'] != 'QA'}):
        raise ValueError('Independent mechanical reviewer required')
    if any(i.get('severity') in {'critical', 'major', 'error'} for i in qa.get('issues', [])):
        raise ValueError('Unresolved mechanical defects block production')
    return qa


def require_animatic(task):
    """Fail closed for full renders; a v1 ledger is an explicit legacy path."""
    if protocol_version(load(task)) == 1:
        return
    require_mechanical(task)
    check_production_config(task)
    feasibility = artifact(task, 'feasibility')
    checks = feasibility.get('checks', {})
    if not FEASIBILITY_CHECKS <= set(checks) or any(v != 'PASS' for v in checks.values()):
        raise ValueError('Feasibility requires every check PASS')
    check_asset(task)
    return check_qa(task, 'animatic-qa')


def check_production_config(task, config=None):
    """Bind approved story decisions to the actual executable config bytes."""
    data = load(task)
    if protocol_version(data) == 1:
        return
    blueprint = artifact(task, 'creative-blueprint')
    if data.get('content_policy_version') == 1:
        from .growth import validate_contract
        if blueprint.get('content_policy_version') != 1:
            raise ValueError('New task requires versioned growth blueprint')
        validate_contract(blueprint, data.get('duration'))
    if data.get('production_method') == 'reference-recreation':
        check_recreation(task, blueprint)
    binding = blueprint.get('production_config')
    if (not isinstance(binding, dict) or not binding.get('path')
            or not binding.get('sha256') or not data.get('config')):
        raise ValueError('Blueprint production_config path/hash and task config required')
    def resolve(value):
        path = Path(value)
        return (path if path.is_absolute() else ROOT / path).resolve()
    expected = resolve(data['config'])
    if resolve(binding['path']) != expected or (config is not None and resolve(config) != expected):
        raise ValueError('Production config path differs from frozen blueprint/task config')
    if not expected.is_file() or filehash(expected) != binding['sha256']:
        raise ValueError('Production config missing or changed after blueprint freeze')
    compiled = json.loads(expected.read_text())
    route = compiled.get('render_route', '3d')
    if data.get('asset_strategy') == 'illustrated':
        asset = check_asset(task)
        if route != asset['render_route'] or data.get('render_route', route) != route:
            raise ValueError('Illustrated route differs from approved asset')
        approved = {(str((ROOT / f['path']).resolve()), f['sha256']) for f in asset['source_files']}
        for shot in compiled.get('shots', {}).values():
            if shot.get('template') != 'layered' or shot.get('render_route') != route or not shot.get('layers'):
                raise ValueError('Illustrated config requires matching layered shots')
            for layer in shot['layers']:
                if (str((ROOT / layer['path']).resolve()), layer['sha256']) not in approved:
                    raise ValueError('Layer source not in approved illustrated asset')
    elif route != '3d':
        raise ValueError('Illustrated rendering requires illustrated asset strategy')
    program_sha = digest({k: v for k, v in blueprint.items() if k != 'production_config'})
    if not isinstance(compiled, dict) or compiled.get('blueprint_program_sha256') != program_sha:
        raise ValueError('Production config was not compiled from this exact frozen blueprint program')


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
            check_asset(task)
            if protocol_version(data) == 2:
                artifact(task, 'feasibility')
        if protocol_version(data) == 2 and target in {
                'PREVIEW_READY', 'PREVIEW_CHECKING', 'EDITING', 'FINAL_CHECKING', 'COMPLETED'}:
            require_animatic(task)
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
            check_requested_routes(task, data)
        data['state'] = target
        write(Path(task) / 'task.json', data)
        event(task, 'state', previous=current, state=target)


def check_requested_routes(task, data):
    routes = data.get('requested_routes', [])
    if len(routes) <= 1:
        return  # Existing single-route and historical ledgers keep their gates.
    from .covers import validate as validate_covers
    from .growth_report import validate as validate_growth
    if data.get('content_policy_version') == 1 or (Path(task)/'cover-plan.json').exists():
        validate_covers(task, require_pass=True)
        validate_growth(task)
    report = artifact(task, 'final-qa')
    route_checks = report.get('route_checks', {})
    for route in routes:
        result = route_checks.get(route, {})
        media = result.get('media')
        if not media:
            raise ValueError('Missing route-specific final QA media: ' + route)
        check_media([media])
        if data.get('content_policy_version') == 1:
            from .growth import validate_media_checks, check_media_duration
            blueprint = artifact(task, 'creative-blueprint')
            validate_media_checks(blueprint, dict(result, media=[media]))
            check_media_duration(blueprint, [media])
        if not all(result.get('checks', {}).get(check) == 'PASS' for check in QA_CHECKS):
            raise ValueError('Requested route final QA has FAIL/UNKNOWN/missing checks: ' + route)
        recorded = data.get('route_runs', {}).get(route, {}).get('outputs', {})
        if not recorded or recorded.get('sha256') != media.get('sha256'):
            raise ValueError('Final QA does not match recorded route output: ' + route)


def validate_defect_key(value):
    if (not isinstance(value, str) or not value.strip()
            or re.search(r'[a-fA-F0-9]{64}', value)):
        raise ValueError('QA defect_key must identify persistent failure type/component, not media hash')


def repair_key(task, issue_id):
    """Resolve versioned issue IDs to one durable repair budget identity.

    Historic QA stays usable to identify defects after dependencies change;
    it does not grant current media acceptance. Validate immutable envelopes
    without treating their now-stale production dependencies as approvals.
    """
    if protocol_version(load(task)) == 1:
        return issue_id
    keys = set()
    aliases = load(task).get('repair_aliases', {})
    for name in ROLES['QA']:
        for path in (Path(task) / 'handoffs').glob(name + '.v*.json'):
            envelope = json.loads(path.read_text())
            if (envelope.get('role') != 'QA' or envelope.get('name') != name
                    or digest({k: v for k, v in envelope.items() if k != 'sha256'})
                    != envelope.get('sha256')):
                raise ValueError('Historical QA handoff hash mismatch')
            for issue in envelope.get('payload', {}).get('issues', []):
                if issue.get('issue_id') == issue_id:
                    key = issue.get('defect_key')
                    validate_defect_key(key)
                    key = key.strip()
                    visited = set()
                    while key in aliases:
                        if key in visited:
                            raise ValueError('Cyclic repair alias')
                        visited.add(key)
                        key = aliases[key]
                        validate_defect_key(key)
                    keys.add(key)
    if not keys:
        raise ValueError('Repair requires an actual QA issue with matching issue_id')
    if len(keys) != 1:
        raise ValueError('QA issue_id has conflicting persistent defect_key values')
    return keys.pop()


def continuous_repairs(data):
    return data.get('autonomy_policy', {}).get('repair_mode') == 'until_pass'


def adopt_autonomy(task, reason):
    """Apply the user's current policy without erasing historical repair evidence."""
    if not reason.strip():
        raise ValueError('Autonomy policy adoption requires the recorded user instruction')
    with lock(Path(task) / '.ledger.lock'):
        data = load(task)
        data['autonomy_policy'] = dict(AUTONOMY_POLICY)
        write(Path(task) / 'task.json', data)
        event(task, 'autonomy_policy_adopted', reason=reason, policy=data['autonomy_policy'])
    return data['autonomy_policy']


def repair_attempt(task, issue_id, strategy, score):
    """Register measured repairs under the current or recorded historical policy.

    New tasks have no numeric cap; no improvement requires a changed strategy.
    Measurements never substitute for independent acceptance.
    """
    if not strategy.strip():
        raise ValueError('Measured repair strategy is required')
    if not math.isfinite(score) or score < 0:
        raise ValueError('Defect score must be finite and nonnegative')
    with lock(Path(task) / '.ledger.lock'):
        data = load(task)
        issues = data['repairs']
        key = repair_key(task, issue_id)
        if key not in issues:
            issues[key] = dict(baseline=score, best=score, strategies={}, stopped=False)
            if protocol_version(data) == 2:
                issues[key].update(defect_key=key, issue_ids=[issue_id])
            if data['state'] != 'REPAIRING':
                data['repair_return_state'] = (
                    'RESEARCHING' if continuous_repairs(data)
                    and data['state'] in {'BLOCKED', 'FAILED'} else data['state'])
            data['state'] = 'REPAIRING'
            write(Path(task) / 'task.json', data)
            event(task, 'repair_baseline', issue_id=issue_id, defect_key=key, score=score)
            return issues[key]
        issue = issues[key]
        if protocol_version(data) == 2 and issue_id not in issue.setdefault('issue_ids', []):
            issue['issue_ids'].append(issue_id)
        if continuous_repairs(data):
            if strategy in issue.get('failed_strategies', []):
                raise ValueError('Unimproved strategy must be replaced; no total repair-round limit')
            if issue.get('stopped'):
                issue.setdefault('historical_stops', []).append({
                    'epoch': time.time(), 'reason': issue.get('stopped_reason', 'legacy repair policy'),
                    'strategies': dict(issue.get('strategies', {})),
                })
                issue['stopped'] = False
                issue.pop('stopped_reason', None)
            attempts = issue.setdefault('strategies', {})
            attempts[strategy] = attempts.get(strategy, 0) + 1
            previous = issue.get('best')
            if previous is None:
                previous = score
                issue['baseline'] = score
            issue['best'] = min(previous, score)
            issue['last_score'] = score
            issue['rounds_used'] = sum(attempts.values())
            issue['remaining_rounds'] = None
            if score >= previous:
                issue.setdefault('failed_strategies', []).append(strategy)
                issue['next_action'] = 'change_strategy'
            else:
                issue['next_action'] = 'independent_recheck'
            if data['state'] != 'REPAIRING':
                data['repair_return_state'] = (
                    'RESEARCHING' if data['state'] in {'BLOCKED', 'FAILED'} else data['state'])
            data['state'] = 'REPAIRING'
            write(Path(task) / 'task.json', data)
            event(task, 'repair', issue_id=issue_id, defect_key=key, strategy=strategy,
                  score=score, attempt=attempts[strategy], stopped=False,
                  next_action=issue['next_action'], repair_policy='until_pass')
            return issue
        if issue['stopped']:
            raise ValueError('Issue stopped: no measured improvement')
        attempts = issue['strategies']
        if data.get('asset_strategy') == 'autonomous-cad' and sum(attempts.values()) >= 2:
            raise ValueError('Autonomous CAD tasks allow at most two repair rounds per defect')
        if strategy not in attempts and len(attempts) >= 2:
            raise ValueError('At most two repair strategies')
        if attempts.get(strategy, 0) >= 2:
            raise ValueError('At most two attempts per strategy')
        if strategy in issue.get('failed_strategies', []):
            raise ValueError('Unimproved strategy must be replaced')
        attempts[strategy] = attempts.get(strategy, 0) + 1
        previous = issue['best']
        issue['best'] = min(previous, score)
        if score >= previous:
            if data.get('asset_strategy') == 'autonomous-cad' and sum(attempts.values()) < 2:
                issue.setdefault('failed_strategies', []).append(strategy)
                data['state'] = 'REPAIRING'
            else:
                issue['stopped'] = True
                data['state'] = 'BLOCKED'
        else:
            if data['state'] != 'REPAIRING':
                data['repair_return_state'] = data['state']
            data['state'] = 'REPAIRING'
        write(Path(task) / 'task.json', data)
        event(task, 'repair', issue_id=issue_id, defect_key=key, strategy=strategy, score=score,
              attempt=attempts[strategy], stopped=issue['stopped'])
    return issue


def run_stage(task, phase, config, env_file=None, workprint=False, diagnostic=False):
    """Execute existing deterministic script once; serialize all Blender work."""
    if phase not in {'asset', 'checks', 'keys', 'local', 'preview', 'final'}:
        raise ValueError('Unsupported stage')
    data = load(task)
    if data.get('asset_strategy') == 'autonomous-cad' and phase != 'asset':
        candidate_config = json.loads(Path(config).read_text())
        if candidate_config.get('render', {}).get('preview_native'):
            require_mechanical(task)
    if diagnostic:
        # Inspect an evidenced candidate without granting production approval.
        # Never permit this route to render a full preview, final, or montage.
        if phase not in {'keys', 'checks', 'local'} or data['state'] != 'RESEARCHING':
            raise ValueError('Diagnostic stage only permits candidate keys/checks/local in RESEARCHING')
        artifact(task, 'research')
        if data.get('asset_strategy') == 'illustrated':
            check_asset(task)
        else:
            candidate = artifact(task, 'asset-plan').get('model', {})
            source = Path(candidate.get('path', ''))
            if not source.is_file() or filehash(source) != candidate.get('sha256'):
                raise ValueError('Diagnostic stage requires unchanged candidate model evidence')
        cfg = json.loads(Path(config).read_text())
        selected = cfg.get('local_preview_shots', [])
        if (len(selected) != 1 or selected[0] not in cfg.get('shots', {})
                or not 0 < cfg['shots'][selected[0]].get('seconds', 0) <= 5):
            raise ValueError('Diagnostic stage is limited to one shot of at most five seconds')
    allowed = {'asset': {'RESEARCHING', 'ASSET_READY', 'ANIMATING'},
               'keys': {'ASSET_READY', 'ANIMATING'},
               'checks': {'ASSET_READY', 'ANIMATING'},
               'local': {'ASSET_READY', 'ANIMATING'},
               'preview': {'ANIMATING', 'PREVIEW_READY', 'PREVIEW_CHECKING'},
               'final': {'EDITING', 'FINAL_CHECKING'}}
    if phase == 'final' and workprint and data['state'] == 'PREVIEW_CHECKING':
        qa = artifact(task, 'preview-qa')
        check_media(qa.get('media'))
        if any(value == 'FAIL' for value in qa.get('checks', {}).values()):
            raise ValueError('Known failed QA cannot be bypassed for workprint')
    elif not diagnostic and data['state'] not in allowed[phase]:
        raise ValueError('Stage lacks verified prerequisites: ' + data['state'])
    if phase in {'preview', 'final'}:
        require_animatic(task)
        check_production_config(task, config)
    if phase == 'final' and not (workprint and data['state'] == 'PREVIEW_CHECKING'):
        check_qa(task, 'preview-qa')
    # Existing cleanup only removes old completed content-addressed entries,
    # skips protected/task-referenced entries and shares our global lock.
    sys.path.insert(0, str(ROOT / 'scripts'))
    from clean import cleanup
    cleanup(older_hours=720, apply=True)
    with lock(ROOT / 'work/production.lock'):
        start = time.time()
        args = ['uv', 'run', '--project', str(ROOT), 'python',
                str(ROOT / 'scripts/produce.py'), str(config), '--phase', phase]
        args += ['--task', str(Path(task).resolve())]
        if diagnostic:
            args += ['--diagnostic']
        if protocol_version(data) == 1 and phase in {'preview', 'final'}:
            args += ['--legacy-workprint']
        if env_file:
            args += ['--env-file', str(env_file)]
        logfile = Path(task) / ('stage-' + phase + '-' + str(time.time_ns()) + '.log')
        try:
            with logfile.open('w') as out:
                subprocess.run(args, cwd=ROOT, stdout=out, stderr=subprocess.STDOUT, check=True)
        except subprocess.CalledProcessError:
            advance(task, 'FAILED')
            event(task, 'stage_failed', phase=phase, seconds=time.time()-start, log=str(logfile),
                  diagnostic=diagnostic, previous_state=data['state'])
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
                       diagnostic=diagnostic,
                       cache_observations=observations,
                       cache_hit_rate=(sum(r['cache_hit'] for r in observations)/len(observations)
                                       if observations else None),
                       full_shot_renders=sum(r['stage'].startswith('final:') and not r['cache_hit']
                                             for r in observations))
            data['stages'].append(row)
            write(Path(task) / 'task.json', data)
            event(task, 'stage', **row)
    return logfile


def select_route(task, route, reason):
    """Producer chooses representation before freezing production dependencies."""
    if route not in {'3d', '2d', '2.5d'} or not reason.strip():
        raise ValueError('Supported route and reason required')
    with lock(Path(task) / '.ledger.lock'):
        data = load(task)
        if data['state'] not in {'CREATED', 'RESEARCHING'} or any(
                name in data['handoffs'] for name in ('asset-plan', 'creative-blueprint', 'feasibility')):
            raise ValueError('Select route before asset and blueprint handoffs')
        data['asset_strategy'] = 'autonomous-cad' if route == '3d' else 'illustrated'
        data['render_route'] = route
        write(Path(task) / 'task.json', data)
        event(task, 'route_selected', route=route, reason=reason)
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('produce')
    p.add_argument('--topic')
    p.add_argument('--resume', type=Path, help='Resume existing task in current Producer session; no new service')
    p.add_argument('--routes', choices=['all', '2d', '2.5d', '3d'], default=None)
    p.add_argument('--asset-strategy', choices=['autonomous-cad','verified-existing','illustrated'], default='autonomous-cad')
    p.add_argument('--duration', type=int, default=None, help='Target seconds: protocol 2 knowledge-driven (120–300); protocol 1 defaults to 45 (30–45)')
    p.add_argument('--voice')
    p.add_argument('--config', type=Path)
    p.add_argument('--task-id')
    p.add_argument('--codex', action='store_true', help='Start a NEW actual Codex Producer session')
    p = sub.add_parser('route-run', help='Resume authored route render plan; no agent impersonation')
    p.add_argument('task', type=Path)
    p.add_argument('--plan', type=Path, default=ROOT / 'config/nail-clipper-three-routes-plan.json')
    p.add_argument('--env-file', type=Path, help='Credentials file forwarded only to opted-in audio step; no secrets in plan')
    for name in ['status', 'advance', 'stage', 'handoff', 'repair', 'agent-run', 'resume-repair', 'resume-asset-inspection', 'resume-stage', 'adopt-autonomy', 'select-route']:
        p = sub.add_parser(name)
        p.add_argument('task', type=Path)
        if name == 'select-route':
            p.add_argument('--route', required=True, choices=['3d','2d','2.5d'])
            p.add_argument('--reason', required=True)
        elif name == 'advance':
            p.add_argument('state')
        elif name in {'resume-asset-inspection', 'resume-stage', 'adopt-autonomy'}:
            p.add_argument('--reason', required=True)
        elif name == 'stage':
            p.add_argument('phase', choices=['asset', 'checks', 'keys', 'local', 'preview', 'final'])
            p.add_argument('--config', required=True, type=Path)
            p.add_argument('--env-file', type=Path)
            p.add_argument('--workprint', action='store_true',
                           help='Explicitly render unaccepted final workprint after preview QA UNKNOWN')
            p.add_argument('--diagnostic', action='store_true',
                           help='Inspect one evidenced candidate shot, at most five seconds; never full production')
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
        if args.resume:
            if args.codex:
                raise ValueError('Resume uses current Producer; do not start another Producer')
            data = load(args.resume)
            if args.topic and args.topic != data['topic']:
                raise ValueError('Resume topic differs from existing task')
            if args.routes and (['2d', '2.5d', '3d'] if args.routes == 'all' else [args.routes]) != data.get('requested_routes', [data.get('render_route', '3d')]):
                raise ValueError('Resume must preserve requested routes; create an explicit new task to change scope')
            event(args.resume, 'producer_resumed', dispatch_mode='current_native_codex_session')
            print(args.resume)
            return
        if not args.topic:
            parser.error('--topic is required unless --resume is supplied')
        task = create_task(args.topic, args.duration, args.voice, args.config, args.task_id,
                           asset_strategy=args.asset_strategy, routes=args.routes or 'all')
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
    if args.command == 'route-run':
        from .multiroute import prepare, run_plan
        data = load(args.task)
        plan_data = json.loads(args.plan.read_text())
        if plan_data.get('topic') and plan_data['topic'] != data['topic']:
            raise ValueError('Adapter topic does not match task; arbitrary topics require their own production plan')
        if data.get('requested_routes') and set(data['requested_routes']) != set(plan_data['routes']):
            raise ValueError('Plan route scope must match task requested_routes; single-route tasks use their assigned production stages')
        folder = Path(data.get('shared_production', {}).get('comparison_directory') or args.task / 'multiroute')
        prepare(folder, data['topic'])
        try:
            report = run_plan(folder, args.plan, args.env_file, [args.task / 'task.json'])
        except Exception:
            with lock(args.task / '.ledger.lock'):
                data = load(args.task)
                state = json.loads((folder / 'state.json').read_text())
                data['multiroute_status'] = state['status']
                data['next_step'] = state['next_step']
                write(args.task / 'task.json', data)
            raise
        with lock(args.task / '.ledger.lock'):
            data = load(args.task)
            data['route_comparison'] = {'report': str(folder / 'report.json'),
                                        'sha256': filehash(folder / 'report.json'),
                                        'status': report['status']}
            data['multiroute_status'] = report['status']
            data['next_step'] = 'Current Producer dispatches independent exact-media route QA; UNKNOWN prevents completion.'
            for route, media in report['routes'].items():
                data.setdefault('route_runs', {})[route] = {'status': 'TECHNICAL_PASS_UNACCEPTED', 'outputs': media}
            for name, path in plan_data.get('shared', {}).items():
                data.setdefault('shared_production', {})[name] = {'path': str(Path(path).resolve()), 'sha256': filehash(path)}
            write(args.task / 'task.json', data)
            # Growth deliverables are generated only after all exact route media
            # and the synchronized comparison exist. This is read-only reporting.
            if data.get('content_policy_version') == 1:
                # Production ledgers may be unit fixtures or incomplete route
                # plans. The report generator itself fails closed on missing
                # media; real delivery invokes it once all exact files exist.
                route_paths = {route: Path(media['path']) for route, media in report['routes'].items()}
                if len(route_paths) == 3 and all(path.is_file() for path in route_paths.values()) and (folder / 'compare.mp4').is_file():
                    from .growth_report import generate as generate_growth_report
                    growth = generate_growth_report(args.task, route_paths, folder / 'compare.mp4')
                    data['growth_report'] = {'path': str(args.task / 'growth-report.json'),
                                             'sha256': filehash(args.task / 'growth-report.json'),
                                             'status': growth['status']}
            write(args.task / 'task.json', data)
            event(args.task, 'route_comparison_generated', report=data['route_comparison'])
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return
    if args.command == 'select-route':
        print(json.dumps(select_route(args.task, args.route, args.reason)))
    elif args.command == 'adopt-autonomy':
        print(json.dumps(adopt_autonomy(args.task, args.reason)))
    elif args.command == 'status':
        print(json.dumps(load(args.task), ensure_ascii=False, indent=2))
    elif args.command == 'advance':
        advance(args.task, args.state)
    elif args.command == 'stage':
        print(run_stage(args.task, args.phase, args.config, args.env_file, args.workprint, args.diagnostic))
    elif args.command == 'handoff':
        print(json.dumps(put_handoff(args.task, args.role, args.name,
                                    json.loads(args.input.read_text()), args.depends), ensure_ascii=False))
    elif args.command == 'repair':
        print(json.dumps(repair_attempt(args.task, args.issue, args.strategy, args.score)))
    elif args.command in {'resume-asset-inspection', 'resume-stage'}:
        with lock(args.task / '.ledger.lock'):
            data = load(args.task)
            events = [json.loads(line) for line in (args.task/'events.jsonl').read_text().splitlines()]
            failures = [e for e in events if e['event']=='stage_failed']
            if data['state']!='FAILED' or not failures or not args.reason.strip():
                raise ValueError('A diagnosed stage failure is required')
            phase=failures[-1]['phase']
            if args.command=='resume-asset-inspection' and phase!='asset':
                raise ValueError('Not an asset inspection failure')
            diagnostic_failure = failures[-1].get('diagnostic') is True
            if data.get('asset_strategy') == 'illustrated' and phase != 'asset':
                check_asset(args.task)
            elif diagnostic_failure:
                model = artifact(args.task, 'asset-plan').get('model', {})
                path = Path(model.get('path', ''))
                if (phase not in {'keys', 'checks', 'local'} or not path.is_file()
                        or filehash(path) != model.get('sha256')):
                    raise ValueError('Unchanged diagnostic candidate evidence required to resume')
            elif phase!='asset':
                model=artifact(args.task,'asset-plan')
                if (model.get('qualified') is not True or model.get('independent_meshes') is not True
                        or model.get('missing_required_parts')!=[]
                        or filehash(model['model']['path'])!=model['model']['sha256']):
                    raise ValueError('Qualified asset evidence required to resume')
            if phase=='final':
                check_qa(args.task,'preview-qa')
            if phase in {'preview', 'final'}:
                require_animatic(args.task)
            data['state']=('RESEARCHING' if diagnostic_failure else
                           {'asset':'RESEARCHING','checks':'ANIMATING','keys':'ASSET_READY','local':'ANIMATING','preview':'ANIMATING','final':'EDITING'}[phase])
            write(args.task/'task.json',data)
            event(args.task,'stage_resumed',phase=phase,reason=args.reason,state=data['state'])
    elif args.command == 'resume-repair':
        with lock(args.task / '.ledger.lock'):
            data = load(args.task)
            if data['state'] != 'REPAIRING' or any(i['stopped'] for i in data['repairs'].values()):
                raise ValueError('No resumable repair')
            for name in data['handoffs']:
                artifact(args.task, name)
            target = data['repair_return_state']
            if target in {'PREVIEW_READY', 'PREVIEW_CHECKING', 'EDITING',
                          'FINAL_CHECKING', 'COMPLETED'}:
                require_animatic(args.task)
            if target in {'EDITING', 'FINAL_CHECKING', 'COMPLETED'}:
                check_qa(args.task, 'preview-qa')
            if target == 'COMPLETED':
                check_qa(args.task, 'final-qa')
                check_requested_routes(args.task, data)
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
