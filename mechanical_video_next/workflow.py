"""Production CLI and recovery commands for existing task ledgers."""
import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import json
from pathlib import Path
from . import pacing, source_policy, video_review
import re
import math
import subprocess
import sys
import time
import wave

from . import creative_selection as editorial_policy
from .production_contract import (
    POSITIONING, PRODUCER_DIRECTED, PRODUCER_DIRECTION, SKILL_DRIVEN, STORY_DEVELOPMENT,
    FORMAL_DURATION_FIELD, FORMAL_DURATION_VERSION, SHORT_FORMAL_DURATION_VERSION,
    formal_duration_enabled, validate_formal_duration,
    directed_story, flexible_story, match_mechanical_scope, mechanism_first, producer_directed,
    skill_driven, story_development,
)
from scripts.common import CleanupBusy, filehash, input_hashes, read_input_bytes, read_input_json

ROOT = Path(__file__).resolve().parents[1]
ROLES = {'Research': {'research', 'script'}, 'Asset': {'asset-plan'},
         'MechanicalResearch': {'research', 'reference-to-model'}, 'CAD': {'cad-model', 'asset-plan'},
         'ViralResearch': {'viral-analysis', 'creative-blueprint'},
         'Producer': {'feasibility', 'story-treatment', 'diagnostic-animatic', 'creative-blueprint'},
         'Animation': {'animation-manifest', 'animatic-manifest', 'mechanical-diagnostics'},
         'Editor': {'timeline', 'audio-preparation', 'animatic-manifest'},
         'QA': {'story-qa', 'preview-qa', 'final-qa', 'content-qa', 'reference-model-qa', 'animatic-qa', 'diagnostic-qa', 'mechanical-qa', 'hd-workprint-qa'}}
NEXT = {'CREATED': 'RESEARCHING', 'RESEARCHING': 'ASSET_READY',
        'ASSET_READY': 'ANIMATING', 'ANIMATING': 'PREVIEW_READY',
        'PREVIEW_READY': 'PREVIEW_CHECKING', 'PREVIEW_CHECKING': 'EDITING',
        'EDITING': 'FINAL_CHECKING', 'FINAL_CHECKING': 'COMPLETED'}
QA_CHECKS = {'mechanics', 'explosion_clarity', 'subtitle_audio_sync',
             'occlusion', 'continuity', 'encoding', 'listening'}
FEASIBILITY_CHECKS = {'observation_basis', 'mechanics', 'model_motion',
                      'tool_support', 'unsupported_effects'}
ANIMATIC_CHECKS = QA_CHECKS | {'blueprint_fidelity'}
PERCEPTUAL_CHECKS = {'explosion_clarity', 'subtitle_audio_sync', 'occlusion',
                     'continuity', 'listening', 'observation_basis',
                     'mechanism_visibility'}


def production_checks(checks, required, *, perceptual_extra=()):
    """Unknown perception is pending review; unknown mechanical facts are not."""
    return (required <= set(checks) and all(
        value == 'PASS' or (key in PERCEPTUAL_CHECKS | set(perceptual_extra) and value == 'UNKNOWN')
        for key, value in checks.items()))


def active_media_repair(data, *, final=False):
    """A recorded defect can re-render through the normal gates before resuming."""
    from .production_contract import enabled
    return (enabled(data) and data.get('state') == 'REPAIRING'
            and data.get('repair_return_state') in ({'EDITING', 'FINAL_CHECKING'} if final else NEXT)
            and any(row.get('issue_ids') and not row.get('stopped', False)
                    for row in data.get('repairs', {}).values()))


def reference_model_required(data):
    from .production_contract import nonmechanical_subject, science_story
    return data.get('reference_model_policy_version') == 1 and not (
        science_story(data) and nonmechanical_subject(data))


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
    'reference-to-model': {'research', 'asset-plan'},
    'reference-model-qa': {'research', 'asset-plan'},
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


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    temp.replace(path)


@contextmanager
def lock(path, wait=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a') as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | (0 if wait else fcntl.LOCK_NB))
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


def require_current_scheme(data, candidate_preview=False):
    """Reject old pointers; same-task replacement must bind new existing artifacts."""
    if data.get('reference_remake', {}).get('old_scheme_status') == 'REJECTED_BY_USER':
        remake = data['reference_remake']
        binding = remake.get('production_binding', {})
        expected = {'research', 'asset-plan'}
        if not candidate_preview:
            expected.update({'creative-blueprint', 'mechanical-qa'})
        handoffs = binding.get('handoffs', {})
        plan = binding.get('production_plan', {})
        try:
            basis = remake.get('mechanism_basis', {})
            technical_basis = (basis.get('status') == 'PASS'
                and basis.get('mechanism_id') and basis.get('scope') and basis.get('evidence')
                and basis.get('source_bindings')
                and all(Path(row['path']).is_file() and filehash(row['path']) == row['sha256']
                        for row in basis['source_bindings']))
            if technical_basis:
                expected = {'research', 'asset-plan'}
            # Compare against the preserved ledger, not a mutable readiness label.
            before = read_input_json(remake['previous_task_snapshot'])
            if ((remake.get('primary_reference') or technical_basis)
                    and (candidate_preview or remake.get('preview_accepted') is True or technical_basis)
                    and expected <= set(handoffs)
                    and all(handoffs[name] == data.get('handoffs', {}).get(name)
                            and handoffs[name] != before.get('handoffs', {}).get(name)
                            for name in expected)
                    and plan == data.get('production_plan')
                    and plan != before.get('production_plan')
                    and filehash(plan['path']) == plan['sha256']):
                return
        except (KeyError, OSError, ValueError, TypeError):
            pass
        raise ValueError('User-rejected scheme cannot resume old handoffs or render plans. '
                         'Bind a newly watched qualified primary reference or a documented, source-bound '
                         'PASS mechanism_basis for the same concrete implementation; '
                         'pass independent 10-15 second preview QA, then bind replacement research, asset-plan, '
                         'creative-blueprint and mechanical-qa handoff entries plus production_plan in '
                         'reference_remake.production_binding on this task. Set previous_task_snapshot to '
                         'the preserved pre-rejection ledger. To create the candidate preview first, bind the '
                         'new research, asset-plan and plan, then run stage local with '
                         'the replacement full production config selecting only 10-15 seconds of local preview shots; '
                         'preview_accepted is not required for that candidate. '
                         'Existing production/QA gates still apply.')


def require_source_supported_render(task, config=None):
    """Permit technical rendering from concrete sources, never grant acceptance."""
    data = load(task)
    config = Path(config or data.get('config') or '')
    if not config.is_file():
        return False
    cfg = read_input_json(config)
    if source_policy.enabled(data):
        validate_production_sources(task, cfg, policy=data)
    from .visual_narrative import VERSION, match_policy, version
    match_policy(data, cfg)
    if version(cfg) == VERSION and any(
            s.get('template') == 'editorial' for s in cfg.get('shots', {}).values()
    ) and cfg.get('production_scope') in {'verified-shots', 'source-supported-film', 'mechanism-preview'}:
        raise ValueError('Scoped mechanical evidence gates do not authorize editorial media')
    scoped_film = (cfg.get('production_scope') == 'source-supported-film'
                   and cfg.get('shot_evidence_version') == 1 and data.get('shot_production'))
    from .production_contract import science_story
    if cfg.get('production_scope') == 'source-supported-film' and science_story(data):
        raise ValueError('A full science-story render requires the regular dynamic animatic gate')
    if cfg.get('production_scope') == 'verified-shots' or scoped_film:
        require_current_scheme(data)
        from .three_d import validate_config
        from .reference_policy import validate_shot_evidence
        from .science_shots import referenced_parts, validate_assembly_shot, validate_asset
        validate_config(cfg)
        selected = list(cfg.get('shots', {})) if scoped_film else cfg.get('local_preview_shots', [])
        if not selected or set(selected) != set(cfg.get('shots', {})):
            raise ValueError('Scoped config must contain exactly its selected shots')
        for name in selected:
            row = data.get('shot_production', {}).get(name, {})
            validate_shot_evidence(row, data.get('mechanism_id'))
            exact = row.get('config', {})
            if (Path(exact.get('path', '')).resolve() != config.resolve()
                    or exact.get('sha256') != filehash(config)
                    or row.get('render_shot_sha256') != digest(cfg['shots'][name])):
                raise ValueError('Scoped shot requires exact executable config binding')
            bound = {Path(m['path']).resolve(): m['sha256'] for m in row['model_bindings']}
            assembly = Path(cfg['assembly_config']).resolve()
            if bound.get(assembly) != filehash(assembly):
                raise ValueError('Scoped assembly is not the evidenced model')
            assembly_data = read_input_json(assembly)
            validate_asset(assembly_data, data.get('mechanism_id'))
            if assembly_data.get('model_source'):
                model_source = assembly_data['model_source']
                if filehash(model_source['path']) != model_source['sha256']:
                    raise ValueError('Scoped authored model source changed')
            depicted = cfg['shots'][name]
            validate_assembly_shot(depicted, assembly_data)
            allowed_parts = set(row.get('verified_parts', []))
            visible = set(depicted.get('visible_parts', assembly_data.get('required_parts', [])))
            animated = {t['object'] for t in depicted.get('tracks', []) + depicted.get('mesh_tracks', [])}
            animated |= referenced_parts(depicted)
            if depicted.get('science', {}).get('driver') == 'asset_motion':
                animated.update(assembly_data['reuse']['controls'][depicted['science']['control']]['parts'])
            if not allowed_parts or not (visible | animated) <= allowed_parts:
                raise ValueError('MECHANISM_UNKNOWN: visible/animated part outside verified scope')
            inventory = row.get('inventory', {})
            if filehash(inventory.get('path', '')) != inventory.get('sha256'):
                raise ValueError('Scoped numerical inventory missing or stale')
            solids = read_input_json(inventory['path'])
            inspected = {s['name'] for s in solids if s.get('valid') is True and s.get('solids') == 1 and s.get('volume_mm3', 0) > 0}
            if not allowed_parts <= inspected:
                raise ValueError('Scoped geometry has invalid or unknown solids')
            for source in assembly_data.get('source_files', []):
                if filehash(ROOT / source['path']) != source['sha256']:
                    raise ValueError('Scoped assembly source changed')
        if scoped_film:
            from .growth import duration_bounds
            minimum, maximum = duration_bounds(cfg)
            storyboard = cfg.get('storyboard', [])
            if ({s.get('shot') for s in storyboard} != set(selected)
                    or not minimum <= sum(s.get('seconds', 0) for s in storyboard) <= maximum
                    or any(not s.get('narration') for s in storyboard)):
                raise ValueError('Full film requires complete measured narration and chapter coverage')
            preview = data.get('technical_preview', {})
            check_media([preview.get('media', {})])
            if (filehash(preview['config']['path']) != preview['config']['sha256']
                    or preview.get('assembly_sha256') != filehash(cfg['assembly_config'])):
                raise ValueError('Full film cannot substitute the source-bound preview assembly')
            preview_cfg = read_input_json(preview['config']['path'])
            if filehash(preview_cfg['assembly_config']) != preview['assembly_sha256']:
                raise ValueError('Actual preview must use the same source-bound assembly')
            info = json.loads(subprocess.check_output(['ffprobe','-v','error','-show_format',
                '-of','json',preview['media']['path']]))
            if not 10 <= float(info['format']['duration']) <= 15.1:
                raise ValueError('Actual continuous 10-15 second technical preview required')
            if not any(s.get('command_success') and s.get('config_sha256') == preview['config']['sha256']
                       for s in data.get('stages', [])):
                raise ValueError('Preview must come from an actual successful stage')
            if any(r.get('status') != 'RESOLVED' and r.get('shot_id') in selected
                   for r in data.get('content_repairs', [])):
                raise ValueError('Unresolved depicted mechanical defect requires repair')
        return True
    if cfg.get('production_scope') != 'source-supported-film':
        return False
    require_current_scheme(data)
    remake = data.get('reference_remake', {})
    basis = remake.get('mechanism_basis', {})
    if basis.get('status') != 'PASS' or not basis.get('source_bindings'):
        raise ValueError('Core mechanism evidence UNKNOWN; continue research before this structure')
    for item in basis['source_bindings']:
        if filehash(item['path']) != item['sha256']:
            raise ValueError('Technical mechanism source changed')
    research = artifact(task, 'research')
    if basis.get('mechanism_id') != research.get('mechanism_id'):
        raise ValueError('Technical basis must identify the exact researched implementation')
    from .reference_policy import validate_research
    from .comprehension import validate_product_research
    validate_research(research)
    validate_product_research(research)
    asset = check_asset(task)
    if asset.get('mechanism_id') != research.get('mechanism_id'):
        raise ValueError('Technical asset/research mechanism mismatch')
    binding = remake.get('production_binding', {})
    exact = binding.get('config', {})
    if Path(exact.get('path', '')).resolve() != config.resolve() or exact.get('sha256') != filehash(config):
        raise ValueError('Technical render requires exact new config binding')
    candidate = next(c for c in asset['candidates'] if c.get('id') == asset['selected_candidate_id'])
    inventory = candidate.get('validation_evidence', {})
    if not isinstance(inventory, dict) or filehash(inventory.get('path', '')) != inventory.get('sha256'):
        raise ValueError('Current CAD numerical inventory binding required')
    rows = read_input_json(inventory['path'])
    if not isinstance(rows, list) or not rows or any(
            row.get('valid') is not True or row.get('solids') != 1 or row.get('volume_mm3', 0) <= 0 for row in rows):
        raise ValueError('Invalid/UNKNOWN CAD solids prevent technical rendering')
    from .three_d import validate_config
    validate_config(cfg)
    preview = binding.get('preview', {})
    check_media([preview])
    info = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', preview['path']]))
    if not 10 <= float(info['format']['duration']) <= 15.1 or not any(s['codec_type'] == 'video' for s in info['streams']):
        raise ValueError('Actual new 10-15 second technical preview required')
    preview_config = binding.get('preview_config', {})
    if filehash(preview_config.get('path', '')) != preview_config.get('sha256'):
        raise ValueError('Exact preview config binding required')
    if not any(row.get('phase') == 'local' and row.get('command_success') is True
               and row.get('config_sha256') == preview_config['sha256'] for row in data.get('stages', [])):
        raise ValueError('Successful actual new preview stage evidence required')
    old_cfg = read_input_json(preview_config['path'])
    def assembly(value):
        path = Path(value['assembly_config'])
        return path if path.is_absolute() else ROOT / path
    if filehash(assembly(old_cfg)) != filehash(assembly(cfg)):
        raise ValueError('Full rendering cannot substitute the previewed 3D assembly')
    if any(row.get('status') != 'RESOLVED' for row in data.get('content_repairs', [])):
        raise ValueError('Known mechanical/content defect requires repair')
    for name in ('preview-qa', 'mechanical-qa'):
        if name in binding.get('handoffs', {}):
            qa = artifact(task, name)
            if 'FAIL' in qa.get('checks', {}).values():
                raise ValueError('Known preview/mechanical FAIL requires repair')
    return True


def complete_media(data, media, final=True):
    """Check actual full-length streams plus explicit chapter coverage bindings.

    Chapter records establish editorial coverage, not perceptual correctness;
    independent exact-media QA remains mandatory for acceptance.
    """
    from .multiroute import probe
    if Path(media.get('path', '')).suffix.lower() != '.mp4':
        raise ValueError('Complete MP4 required')
    check_media([media])
    info = probe(media['path'])
    video = next(row for row in info['streams'] if row.get('codec_type') == 'video')
    audio = [row for row in info['streams'] if row.get('codec_type') == 'audio']
    duration = float(video.get('duration', info.get('format', {}).get('duration', 0)))
    validate_formal_duration(data, duration, preview=not final)
    if final and formal_duration_enabled(data) and (video.get('codec_name') != 'h264'
            or not audio or audio[0].get('codec_name') != 'aac'):
        raise ValueError('Formal film requires H.264 video and AAC audio')
    policy = data.get('duration_policy') or {'minimum': 30, 'maximum': 45}
    if not final and data.get(FORMAL_DURATION_FIELD) == FORMAL_DURATION_VERSION:
        policy = {'minimum': 1 / 30, 'maximum': None}
    maximum = policy['maximum']
    if (not math.isfinite(duration) or duration < policy['minimum'] - 1 / 30
            or (maximum is not None and duration > maximum + 1 / 30)):
        raise ValueError('Full media duration outside task policy: ' + str(duration))
    if not audio or float(audio[0].get('duration', info.get('format', {}).get('duration', 0))) < duration - 0.1:
        raise ValueError('Complete narration audio stream required')
    numerator, denominator = video.get('avg_frame_rate', '0/1').split('/')
    fps = float(numerator) / float(denominator)
    if (final and abs(fps - 30) > 0.001) or (not final and min(abs(fps - rate) for rate in (15, 30)) > 0.001):
        raise ValueError('Final media requires 30fps; full preview permits 15/30fps')
    if final and (video.get('width'), video.get('height')) != (1920, 1080):
        raise ValueError('Final route requires 1920x1080')
    timeline = data.get('shared_production', {}).get('timeline', {})
    path = Path(timeline.get('path', ''))
    if not path.is_file() or timeline.get('sha256') != filehash(path):
        raise ValueError('Complete measured timeline binding required')
    content = json.loads(path.read_text())
    chapters = content.get('shots', content.get('chapters', []))
    expected = {row.get('shot_id', row.get('id')) for row in chapters}
    coverage = media.get('chapter_ids', [])
    if not expected or None in expected or set(coverage) != expected:
        raise ValueError('Complete chapter coverage must match the measured shared timeline')
    timeline_duration = content.get('duration_seconds', content.get('duration', content.get('seconds')))
    if (timeline_duration is None or not math.isfinite(float(timeline_duration))
            or abs(float(timeline_duration) - duration) > 1 / 30 + 0.001):
        raise ValueError('Full media duration does not match measured shared timeline')
    return dict(duration=duration, fps=fps, chapter_ids=coverage)


def source_supported_film_config(data):
    if not (data.get('shot_production') or data.get('technical_preview')):
        return None
    config_path = data.get('config')
    if config_path:
        path = Path(config_path)
        contents = read_input_bytes(path)
        config = json.loads(contents)
        config_sha256 = hashlib.sha256(contents).hexdigest()
        if config.get('production_scope') == 'source-supported-film' and config.get('shot_evidence_version') == 1:
            return path, config, config_sha256
    return None


def reject_superseded_scoped_final(data, media):
    """Keep a historical scoped stage from being accepted through an ordinary route."""
    if not media.get('sha256'):
        return
    for row in data.get('stages', []):
        if (row.get('phase') != 'final' or row.get('command_success') is not True
                or row.get('media', {}).get('sha256') != media['sha256']):
            continue
        # Legacy scoped ledgers have a technical preview of the same assembly.
        # Their stage writer recorded exact final media for technical renders.
        # Ordinary mixed-contract final stages also recorded previous_media.
        legacy_scoped = (row.get('config_sha256') and 'previous_media' not in row
                         and (data.get('technical_preview')
                              or (data.get('shot_production') and row.get('unaccepted_workprint') is True)))
        if row.get('source_supported_film', legacy_scoped):
            raise ValueError('Current configuration has superseded the source-supported final stage')


def source_supported_stage_media(task, data, scoped_config):
    path, config, config_sha256 = scoped_config
    if (not data.get('shot_production') or not require_source_supported_render(task, path)
            or filehash(path) != config_sha256):
        raise ValueError('Current source-supported film configuration is stale: ' + str(path))
    row = next((stage for stage in reversed(data.get('stages', []))
                if stage.get('command_success') is True and stage.get('phase') == 'final'
                and stage.get('config_sha256') == config_sha256), None)
    if row is None:
        return None
    if not row.get('media'):
        raise ValueError('Current source-supported final stage lacks a media binding')
    media = dict(row['media'], chapter_ids=[shot['id'] for shot in config['storyboard']])
    complete_media(data, media)
    return media


def current_source_supported_film(task, data, *, for_cover=False):
    """Resolve a current scoped final, or an exact scoped preview for covers."""
    output = data.get('route_runs', {}).get('3d', {}).get('outputs', {})
    scoped_config = source_supported_film_config(data)
    if scoped_config is None:
        reject_superseded_scoped_final(data, output)
        return None
    media = source_supported_stage_media(task, data, scoped_config)
    if media is not None:
        return media
    candidate = output.get('candidate')
    if for_cover and candidate:
        complete_media(data, candidate, final=False)
        _, _, config_sha256 = scoped_config
        if not any(row.get('phase') == 'preview' and row.get('command_success') is True
                   and row.get('config_sha256') == config_sha256
                   and row.get('media', {}).get('sha256') == candidate['sha256']
                   and Path(row['media']['path']).resolve() == Path(candidate['path']).resolve()
                   for row in data.get('stages', [])):
            raise ValueError('Cover candidate must bind a successful preview of the exact current scoped configuration')
        return dict(candidate, candidate=True)
    raise ValueError('Current source-supported final stage media is missing')


def require_source_supported_review(review, media):
    exact = (Path(media['path']).resolve(), media['sha256'])
    if not any((Path(item['path']).resolve(), item['sha256']) == exact for item in review['media']):
        raise ValueError('Final QA must review the current source-supported stage media')


def continuation(task, persist=True):
    """Reconcile evidence, not child/session exit codes, into a Producer action.

    This is a resumable ledger, not an unattended agent scheduler. Missing or
    stale handoffs are explicit work for the current native Producer.
    """
    task = Path(task)
    data = load(task)
    source_supported = None
    scoped_film = False
    scoped_error = None
    try:
        scoped_config = source_supported_film_config(data)
        if scoped_config is None:
            output = data.get('route_runs', {}).get('3d', {}).get('outputs', {})
            reject_superseded_scoped_final(data, output)
    except (ValueError, OSError) as error:
        scoped_config = None
        scoped_error = str(error)
        scoped_film = True
    # Independent verified shots precede global research/handoff dependencies.
    # Keep this branch task-opt-in; historical ledgers retain their semantics.
    if data.get('shot_production'):
        require_current_scheme(data)
        if scoped_config is not None:
            scoped_film = True
            full_config, _, config_sha256 = scoped_config
            # A newer partial model may supersede the complete film. Preserve
            # previous stages and reconcile independently evidenced shots.
            try:
                media = source_supported_stage_media(task, data, scoped_config)
            except (ValueError, OSError, KeyError, TypeError, subprocess.SubprocessError, StopIteration, ZeroDivisionError) as error:
                scoped_error = str(error)
            else:
                done = {row['phase'] for row in data.get('stages', [])
                        if row.get('command_success') and row.get('config_sha256') == config_sha256}
                if media:
                    source_supported = media
                else:
                    phase = 'final' if 'preview' in done else 'preview'
                    status = 'PRODUCTION_IN_PROGRESS'
                    action = dict(owner='Producer', kind='EXECUTABLE_COMMAND',
                        action='Render the evidenced full 3D workprint; acceptance remains pending',
                        command=['uv','run','python','-m','mechanical_video_next','stage',str(task),
                                 phase,'--config',str(full_config)])
                    failure = data.get('production_execution_failure', {})
                    if (failure.get('status') == 'OPEN'
                            and failure.get('config_sha256') == config_sha256):
                        action = dict(owner='Producer', kind='REASONING_REQUIRED', command=None,
                            action='Diagnose the preserved failed full-film command and change its inputs or strategy before retrying', evidence=failure)
                    result = dict(schema_version=1, milestone=status, production_status=status,
                        lifecycle='WORKING', delivered=False, blockers=[], workflow_state=data['state'],
                        next_action=action, rendered_routes={},
                        background_execution=False, execution_mode='current_native_codex_session')
                    if persist:
                        with lock(task / '.ledger.lock', wait=True):
                            current = load(task)
                            current.update(continuation=result, production_status=status, next_step=action['action'])
                            write(task / 'task.json', current)
                    return result
        rows = data['shot_production']
        ready, pending, rendered_shots, invalid_shots = [], [], {}, {}
        for name, row in rows.items():
            try:
                if row.get('status') == 'RESEARCH_REQUIRED':
                    pending.append(name)
                    continue
                require_source_supported_render(task, row['config']['path'])
                media = row.get('media')
                if media:
                    check_media([media])
                    from .multiroute import probe
                    info = probe(media['path'])
                    if not any(s.get('codec_type') == 'video' for s in info['streams']):
                        raise ValueError('Rendered shot has no video')
                    rendered_shots[name] = media
                else:
                    ready.append(name)
            except (ValueError, OSError, KeyError) as error:
                pending.append(name)
                invalid_shots[name] = str(error)
        if ready:
            name = ready[0]
            action = dict(owner='Producer', kind='EXECUTABLE_COMMAND', shot_id=name,
                action='Render the independently evidenced 3D shot; continue research on other shots',
                command=['uv','run','python','-m','mechanical_video_next','stage',str(task),
                         'local','--config',rows[name]['config']['path']])
        else:
            action = dict(owner='Producer', kind='REASONING_REQUIRED', command=None,
                action='Resolve the evidence gaps for the listed shots or assess a supported alternative. Prepare narration and continue QA on independently rendered shots.',
                research_required=pending)
        # Hand back to the existing full-film workflow once a full plan is bound.
        if source_supported is None and (ready or not data.get('production_plan') or (scoped_error and pending)):
            status = 'PARTIAL_3D_RENDERED' if rendered_shots else 'PRODUCTION_IN_PROGRESS' if ready else 'RESEARCH_PARTIAL'
            result = dict(schema_version=1, milestone=status, production_status=status,
                lifecycle='WORKING', delivered=False, blockers=[], workflow_state=data['state'],
                next_action=action, remaining_work=pending, rendered_routes={},
                rendered_shots=rendered_shots, invalid_evidence=invalid_shots, background_execution=False,
                execution_mode='current_native_codex_session')
            if scoped_error:
                invalid_shots['route:3d'] = scoped_error
            if persist:
                with lock(task / '.ledger.lock', wait=True):
                    current = load(task)
                    current.update(continuation=result, production_status=status, next_step=action['action'])
                    write(task / 'task.json', current)
            return result
    elif scoped_config is not None:
        scoped_film = True
        scoped_error = 'Current source-supported film has no current shot bindings'
    try:
        if (data.get('reference_remake', {}).get('old_scheme_status') == 'REJECTED_BY_USER'
                and data['reference_remake'].get('preview_accepted') is not True):
            raise ValueError('Replacement preview requires generation and inspection before full production')
        require_current_scheme(data)
    except ValueError as error:
        action = dict(owner='Producer', action=str(error), command=None, kind='REASONING_REQUIRED')
        rendered_workprint = {}
        try:
            require_current_scheme(data, candidate_preview=True)
            binding = data['reference_remake']['production_binding']
            config = binding.get('preview_config') or binding['config']
            if filehash(config['path']) != config['sha256']:
                raise ValueError('Candidate config changed')
            done = any(row.get('phase') == 'local' and row.get('command_success')
                       and row.get('config_sha256') == config['sha256'] for row in data.get('stages', []))
            if not done:
                action = dict(owner='Producer', action='Render source-bound replacement candidate; no formal acceptance implied',
                    kind='EXECUTABLE_COMMAND', command=['uv', 'run', 'python', '-m', 'mechanical_video_next',
                    'stage', str(task), 'local', '--config', config['path']])
            else:
                action = dict(owner='Producer', action='Inspect the replacement preview and repair or obtain preview acceptance; continue independent preparation',
                              command=None, kind='REASONING_REQUIRED')
                full_config = binding.get('config', {})
                if full_config != config and require_source_supported_render(task, full_config.get('path')):
                    completed = {row['phase'] for row in data.get('stages', []) if row.get('command_success')
                                 and row.get('config_sha256') == full_config['sha256']}
                    phase = 'preview' if 'preview' not in completed else 'final' if 'final' not in completed else None
                    if phase:
                        action = dict(owner='Producer', action='Render source-supported unaccepted workprint; final sensory QA remains pending',
                            kind='EXECUTABLE_COMMAND', command=['uv','run','python','-m','mechanical_video_next',
                            'stage',str(task),phase,'--config',full_config['path']])
                    workprint = binding.get('workprint', {})
                    if workprint.get('config') == full_config:
                        for name in ('media', 'timeline', 'provenance', 'verification'):
                            ref = workprint[name]
                            if not Path(ref['path']).is_file() or filehash(ref['path']) != ref['sha256']:
                                raise ValueError('Missing/stale current workprint: ' + name)
                        check_data = dict(data, shared_production={'timeline': workprint['timeline']})
                        complete_media(check_data, workprint['media'])
                        proof = json.loads(Path(workprint['provenance']['path']).read_text())
                        receipt = json.loads(Path(workprint['verification']['path']).read_text())
                        for ref in [proof['input_manifest'], *receipt['verifier']]:
                            if not Path(ref['path']).is_file() or filehash(ref['path']) != ref['sha256']:
                                raise ValueError('Missing/stale workprint source verification')
                        manifest = json.loads(Path(proof['input_manifest']['path']).read_text())
                        if (manifest.get('config') != full_config
                                or proof.get('media') != {k: workprint['media'][k] for k in ('path', 'sha256')}
                                or proof.get('measured_timeline') != workprint['timeline']
                                or receipt.get('provenance') != workprint['provenance']
                                or receipt.get('full_build_replayed') is not True):
                            raise ValueError('Current workprint requires exact config, timeline and verified 3D build')
                        rendered_workprint = {'3d': workprint['media']}
                        action = dict(owner='Producer', kind='REASONING_REQUIRED', command=None,
                            action='Complete workprint exists; inspect exact media and resolve formal QA without rerendering')
        except (ValueError, KeyError, OSError, TypeError):
            pass
        blockers = [row for row in data.get('production_blockers', []) if row.get('status') == 'OPEN'
                    and row.get('kind') in {'permission', 'login', 'technical-evidence', 'resource', 'EXTERNAL_BLOCKED'}
                    and row.get('evidence') and row.get('alternatives')
                    and row.get('alternatives_checked') is True and row.get('remaining_executable_work') is False]
        blocked = bool(blockers) and not action.get('command')
        if blocked: action['kind'] = 'EXTERNAL_BLOCKED'
        result = dict(schema_version=1, milestone='FINAL_RENDERED' if rendered_workprint else 'SCHEME_REJECTED', lifecycle='BLOCKED' if blocked else 'REPAIRING',
                      blockers=blockers if blocked else [], delivered=False,
                      workflow_state=data['state'], next_action=action,
                      remaining_work=[action], invalid_evidence={'rejected-scheme': str(error)},
                      rendered_routes=rendered_workprint, preview_routes={}, diagnostic_clips_only=False,
                      resume_command=['uv', 'run', 'python', '-m', 'mechanical_video_next',
                                      'produce', '--resume', str(task)],
                      execution_mode='current_native_codex_session', background_execution=False)
        if persist:
            with lock(task / '.ledger.lock', wait=True):
                current = load(task)
                current['continuation'] = result
                current['next_step'] = action['action']
                write(task / 'task.json', current)
        return result
    valid, invalid = {}, {}
    for name in data.get('handoffs', {}):
        try:
            valid[name] = artifact(task, name)
        except (ValueError, OSError, KeyError) as error:
            invalid[name] = str(error)
    history = data.get('creative_history', [])
    stages = data.get('stages', [])[history[-1]['stage_offset'] if history else 0:]
    routes = data.get('requested_routes', [data.get('render_route', '3d')])
    rendered, route_previews = {}, {}
    for route in routes:
        if route == '3d' and scoped_error:
            invalid['route:3d'] = scoped_error
            continue
        media = ((source_supported or {}) if route == '3d' and scoped_film
                 else data.get('route_runs', {}).get(route, {}).get('outputs', {}))
        candidate = media.get('candidate')
        if candidate:
            try:
                complete_media(data, candidate, final=False)
                route_previews[route] = candidate
            except (ValueError, OSError, KeyError, TypeError, subprocess.SubprocessError, StopIteration, ZeroDivisionError) as error:
                invalid['preview:' + route] = str(error)
        try:
            complete_media(data, media)
            rendered[route] = media
        except (ValueError, OSError, KeyError, TypeError, subprocess.SubprocessError, StopIteration, ZeroDivisionError) as error:
            invalid['route:' + route] = str(error)
    milestone = 'SUBTASK_COMPLETED' if data.get('agent_runs') else 'CREATED'
    if 'research' in valid:
        milestone = 'RESEARCH_READY'
    if 'asset-plan' in valid and valid['asset-plan'].get('qualified') is True:
        milestone = 'MODEL_READY'
    if route_previews and set(route_previews) == set(routes):
        milestone = 'PREVIEW_READY'
    if flexible_story(data) and 'diagnostic-animatic' in valid and milestone in {
            'CREATED', 'SUBTASK_COMPLETED', 'RESEARCH_READY'}:
        milestone = 'STORY_PREVIEW_RENDERED'
    if 'animation-manifest' in valid:
        try:
            previews = valid['animation-manifest'].get('media', [])
            if not previews:
                raise ValueError('Complete preview MP4 missing')
            for preview in previews:
                complete_media(data, preview, final=False)
            milestone = 'PREVIEW_READY'
        except (ValueError, OSError, KeyError, TypeError, subprocess.SubprocessError, StopIteration, ZeroDivisionError) as error:
            invalid['complete-preview'] = str(error)
    video_reviews = {
        name: valid[name]['video_review'] for name in ('animation-manifest', 'timeline')
        if name in valid and 'video_review' in valid[name]
    }
    review_gap = next(((name, report) for name, report in reversed(video_reviews.items())
                       if report['technical_status'] != 'PASS'), None)
    from . import director_audio
    music_blocker = None
    if director_audio.enabled(data) and 'creative-blueprint' in valid and data.get('config'):
        try:
            config = read_input_json(data['config'])
            director_audio.validate_arrangement(config, require_ready=True)
        except (ValueError, OSError, KeyError, TypeError) as error:
            music_blocker = str(error)
            invalid['music-direction'] = music_blocker
    if routes and len(rendered) == len(routes):
        milestone = 'FINAL_RENDERED'
    accepted = False
    unresolved_content = [row for row in data.get('content_repairs', []) if row.get('status') != 'RESOLVED']
    failed_qa = {name: report for name, report in valid.items()
                 if name.endswith('-qa') and
                 ('FAIL' in report.get('checks', {}).values() or report.get('audio_technical_status') == 'FAIL'
                  or report.get('audio_perceptual_review') == 'FAIL'
                  or any(row.get('status') == 'FAIL' for row in report.get('creative_review', {}).values()) or any(
                     (issue.get('requires_audio_review') is True or
                      str(issue.get('severity', '')).lower() in {'critical', 'major', 'error'})
                     and issue.get('status') != 'RESOLVED' for issue in report.get('issues', [])))}
    if milestone == 'FINAL_RENDERED' and data['state'] == 'COMPLETED' and not unresolved_content:
        try:
            check_qa(task, 'preview-qa')
            check_qa(task, 'final-qa')
            check_requested_routes(task, data)
            accepted = True
            milestone = 'QA_ACCEPTED'
        except (ValueError, OSError, KeyError, TypeError) as error:
            invalid['delivery-qa'] = str(error)
    receipt = data.get('delivery_receipt', {})
    if accepted and receipt.get('routes') == rendered and receipt.get('provided_to_user') is True:
        files = receipt.get('files', [])
        if files and all(Path(item['path']).is_file() and filehash(item['path']) == item['sha256'] for item in files):
            try:
                provided = {(str(Path(item['path']).resolve()), item['sha256']) for item in files}
                required = delivery_files(task, data, rendered)
                if not all((str(Path(item['path']).resolve()), item['sha256']) in provided for item in required):
                    raise ValueError('Delivery receipt omits a required current deliverable')
                milestone = 'DELIVERED'
            except (ValueError, OSError, KeyError, TypeError) as error:
                invalid['delivery-receipt'] = str(error)
    sequence = [('research', 'Research', 'Verify the concrete mechanism and register source-bound research'),
                ('asset-plan', 'Asset', 'Select and verify legal matching assets or evidence-based CAD'),
                ('creative-blueprint', 'ViralResearch', 'Bind the complete original storyboard to measured narration and evidence'),
                ('script', 'Research', 'Register the complete shared original script'),
                ('feasibility', 'Producer', 'Validate the exact storyboard and production config'),
                ('animatic-manifest', 'Animation', 'Produce the complete dynamic storyboard with shared audio and captions'),
                ('animatic-qa', 'QA', 'Independently verify exact dynamic-storyboard media'),
                ('animation-manifest', 'Animation', 'Produce all chapter shots and complete route previews'),
                ('preview-qa', 'QA', 'Independently inspect each exact complete preview'),
                ('timeline', 'Editor', 'Compose complete route videos using existing measured narration'),
                ('final-qa', 'QA', 'Independently inspect exact final media and all route deliverables')]
    if protocol_version(data) == 1:
        sequence = [row for row in sequence if row[0] not in {
            'creative-blueprint', 'feasibility', 'animatic-manifest', 'animatic-qa'}]
    elif data.get('asset_strategy') == 'autonomous-cad':
        sequence[2:2] = [('cad-model', 'CAD', 'Register the reference-matched model and dimensional approximations'),
                         ('mechanical-diagnostics', 'Animation', 'Validate input, transmission, output and return motion'),
                         ('mechanical-qa', 'QA', 'Independently compare reference, CAD, motion and visible mechanism')]
    from .production_contract import discovery, mechanical_story, science_story
    from .visual_narrative import scene_direction_enabled
    directed = producer_directed(data)
    if directed:
        optional = {'animatic-manifest', 'animatic-qa', 'preview-qa'}
        if directed_story(data):
            optional.remove('preview-qa')
        sequence = [row for row in sequence if row[0] not in optional]
        sequence[0] = ('research', 'Producer', 'Research the real machine and develop a complete story grounded in located facts')
        blueprint_action = ('Direct the original shots using the observed reference techniques, located facts and measured narration'
                            if data.get('reference_search_plan') else
                            'Direct the complete visual story and bind it to measured narration and evidence')
        sequence = [
            (name, 'Producer', blueprint_action)
            if name == 'creative-blueprint' else
            (name, 'Producer', 'Register the original script developed with the visual edit')
            if name == 'script' else
            (name, 'Animation', 'Verify keyframes and bind the complete low-cost preview')
            if name == 'animation-manifest' else
            (name, 'Editor', 'Compose the complete film with the measured joint timeline')
            if name == 'timeline' else (name, owner, action)
            for name, owner, action in sequence
        ]
        if story_development(data):
            research_action = ('Verify the requested mechanism, its parts, motion and scientific causality'
                               if mechanism_first(data) else
                               'Investigate use, historical context, earlier limits, design changes and science')
            sequence[:1] = [
                ('research', 'Producer', research_action),
                ('story-treatment', 'Producer', 'Develop the complete design story and causal storyboard before choosing assets'),
                ('story-qa', 'QA', 'Independently review the written story against the account positioning'),
                ('diagnostic-animatic', 'Producer', 'Make the complete low-cost moving story after independent story PASS'),
                ('diagnostic-qa', 'QA', 'Independently review the complete exact-media visual narrative before formal production'),
            ]
        elif skill_driven(data):
            sequence[1:1] = [
                ('diagnostic-animatic', 'Producer', 'Bind the low-cost moving story preview'),
                ('diagnostic-qa', 'QA', 'Review the actual story preview independently'),
            ]
        if data.get('reference_search_plan'):
            sequence.insert(1 if mechanism_first(data) else 0, ('viral-analysis', 'Producer',
                'Reuse matching viewed references and search for gaps. Play relevant excerpts, record their timecodes and adapt the useful methods into the original shots.'))
        if directed_story(data):
            from .joint_timeline import integrity
            preview_action = 'Review the exact workprint and record creative observations and reference effects'
            if integrity(data):
                preview_action += '. Cover the full moving edit and each bound event and story moment in review_observations.'
            sequence = [(name, owner, preview_action
                         if name == 'preview-qa' else action) for name, owner, action in sequence]
    elif science_story(data):
        sequence[0] = ('research', 'Research', 'Verify the science and identify the most revealing audience question')
        if mechanical_story(data):
            sequence[0] = ('research', 'Research', 'Compare evidence-backed mechanical design stories and their visible payoffs before choosing an implementation or assets')
            if editorial_policy.enabled(data):
                sequence[0] = ('research', 'Producer', 'Record editorial priority based on real use, a design tension and a visible discovery')
        elif discovery(data):
            sequence[0] = ('research', 'Research', 'Explore distinct stories and develop the Producer selection with located evidence')
        sequence.insert(1, ('diagnostic-animatic', 'Producer', 'Draft and play the complete low-cost visual story before committing to assets'))
        if scene_direction_enabled(data):
            sequence.insert(2, ('diagnostic-qa', 'QA', 'Review the complete picture story and any capability gaps before measured narration'))
        sequence = [(name, 'Producer', 'Own the visual story and lock picture/action before measured dialogue')
                    if name == 'creative-blueprint' else
                    (name, 'Editor', 'Shape the complete picture, timing, dialogue, music and effects')
                    if name == 'animatic-manifest' else (name, owner, action)
                    for name, owner, action in sequence]
    if data.get('reference_policy_version') == 1:
        index = next(i for i, row in enumerate(sequence) if row[0] == 'feasibility')
        sequence.insert(index, ('content-qa', 'QA', 'Verify complete evidence-to-model-to-shot mapping before expensive rendering'))
    if reference_model_required(data):
        index = next((i for i, row in enumerate(sequence) if row[0] == 'content-qa'), 2)
        sequence.insert(index, ('reference-model-qa', 'QA', 'Verify part-level references, model, constraints and depicted motion'))
    missing = [dict(handoff=name, owner=owner, action=action)
               for name, owner, action in sequence if name not in valid]
    if missing and missing[0]['handoff'] == 'viral-analysis':
        missing[0].update(search_plan=str(task / data['reference_search_plan']),
                          analysis_input=str(task / 'research/viral-analysis.json'))
    if scene_direction_enabled(data) and 'diagnostic-qa' in valid:
        review = valid['diagnostic-qa']['visual_story_review']
        if review['status'] != 'PASS':
            owner = 'Producer' if review['status'] == 'FAIL' else 'QA'
            missing.insert(0, dict(handoff='diagnostic-qa', owner=owner, action=review.get(
                'revision', 'Independently watch the current complete picture draft before formal Neil or HD')))
    editorial = creative_gate_next_action(valid) if story_development(data) else None
    if editorial_policy.enabled(data):
        editorial = creative_next_action(data, valid)
    resume = ['uv', 'run', 'python', '-m', 'mechanical_video_next', 'produce', '--resume', str(task)]
    plan = data.get('production_plan', {})
    plan_path = Path(plan.get('path', ''))
    render_handoffs = {'feasibility', 'content-qa'} if directed else {
        'feasibility', 'animatic-manifest', 'animatic-qa'}
    executable_plan = (plan_path.is_file() and plan.get('sha256') == filehash(plan_path)
                       and render_handoffs <= set(valid))
    execution_failure = data.get('production_execution_failure', {})
    execution_needs_repair = (execution_failure.get('status') == 'OPEN'
        and execution_failure.get('plan_sha256') == plan.get('sha256')
        and execution_failure.get('handoffs_sha256') == digest(data.get('handoffs', {})))
    low_cost = data.get('low_cost_animatic_approval', {})
    low_cost_valid = False
    try:
        for item in (low_cost['config'], low_cost['qa']):
            if filehash(item['path']) != item['sha256']:
                raise ValueError('Low-cost animatic approval changed')
        low_cost_valid = True
    except (KeyError, OSError, ValueError):
        pass
    low_cost_rendered = low_cost_valid and any(row.get('animatic_diagnostic') and row.get('command_success')
                                              and row.get('config_sha256') == low_cost['config']['sha256'] for row in stages)
    if milestone == 'DELIVERED':
        action = dict(owner='Producer', action='Delivery recorded; no production work remains', command=None)
    elif editorial:
        action = editorial
    elif any(r.get('status') != 'RESOLVED' for r in data.get('content_repairs', [])):
        # Persisted independent content failures supersede old render approvals.
        # A new session must repair the actual defect rather than repeat a cached
        # render or schedule a missing downstream handoff as if content passed.
        unresolved = [r for r in data['content_repairs'] if r.get('status') != 'RESOLVED']
        if unresolved:
            repair = unresolved[0]
            action = dict(owner=repair.get('responsible_agent', 'Producer'),
                          action=repair['suggested_fix'], defect_key=repair['defect_key'],
                          evidence=repair.get('evidence'), command=None)
        elif missing:
            action = missing[0]
        else:
            action = dict(owner='Producer', action='Reconcile repaired content and bind a current production plan', command=None)
    elif data['state'] == 'FAILED':
        action = dict(owner='Producer', action='Diagnose the preserved failed command and change its execution strategy before resuming', command=None,
                      recovery_command=['uv', 'run', 'python', '-m', 'mechanical_video_next', 'resume-stage', str(task), '--reason', '<actual diagnosis and changed strategy>'])
    elif execution_needs_repair:
        action = dict(owner='Producer', action='Diagnose the preserved command failure; repair inputs, bind a changed plan or record an evidenced resolution before execution',
                      evidence=execution_failure, command=None)
    elif music_blocker and data['state'] in {'EDITING', 'FINAL_CHECKING'}:
        action = dict(owner='Editor', handoff='creative-blueprint', command=None,
                      action='Resolve blocked music sources and recompile the sound design',
                      evidence=music_blocker)
    elif review_gap:
        name, report = review_gap
        action = dict(owner='Producer', handoff=name, command=None,
                      action='Investigate the timecoded Video Review findings, repair the affected edit or source and register the new complete MP4',
                      evidence=report['findings'])
    elif failed_qa:
        name, report = next(iter(failed_qa.items()))
        issues = [issue for issue in report.get('issues', []) if issue.get('status') != 'RESOLVED']
        issue = next((issue for issue in issues if str(issue.get('severity', '')).lower()
                      in {'critical', 'major', 'error'}), issues[0] if issues else {})
        audio_failure = report.get('audio_technical_evidence', {}).get('reason')
        action = dict(owner=issue.get('responsible_agent', 'Producer'),
                      action=issue.get('suggested_fix', audio_failure or 'Diagnose the failed exact-media checks, repair affected shots and obtain independent re-verification'),
                      qa_handoff=name, defect_key=issue.get('defect_key'),
                      evidence=issue.get('evidence', report.get('media')), command=None)
    elif directed and milestone == 'FINAL_RENDERED' and 'timeline' not in valid:
        action = dict(owner='Editor', handoff='timeline', command=None, media=rendered,
                      action='Bind the rendered film and technical verification to the current edit')
    elif routes and len(rendered) == len(routes) and not accepted:
        action = dict(owner='QA/Producer',
                      action='Bind missing provenance handoffs to the existing complete route media and resolve final exact-media acceptance gaps; preserve verified renders',
                      missing_handoffs=[row['handoff'] for row in missing],
                      media=rendered, command=None)
    elif low_cost_valid and any(row.get('status') == 'REPAIRING'
                               and row.get('config_sha256') == low_cost['config']['sha256']
                               for row in data.get('candidate_failures', [])):
        action = dict(owner='Producer', action='Diagnose the failed candidate and change its execution strategy; independently approved other route work remains executable',
                      command=None, failed_config=low_cost['config'])
    elif low_cost_valid and not low_cost_rendered and data['state'] == 'RESEARCHING':
        action = dict(owner='Producer', action='Render the independently permitted full low-cost raw dynamic animatic',
                      command=['uv', 'run', 'python', '-m', 'mechanical_video_next', 'stage', str(task), 'local',
                               '--config', low_cost['config']['path'], '--animatic-diagnostic', '--preproduction-qa', low_cost['qa']['path']])
    elif low_cost_rendered and 'animatic-manifest' not in valid:
        action = dict(owner='Editor', action='Compose all rendered low-cost chapters with existing narration and captions, then hand off exact dynamic animatic to independent QA', command=None)
    elif len(rendered) != len(routes) and executable_plan:
        action = dict(owner='Producer', action='Execute the authored remaining route plan through production gates',
                      command=['uv', 'run', 'python', '-m', 'mechanical_video_next',
                               'route-run', str(task), '--plan', str(plan_path)])
    elif missing:
        action = missing[0]
    elif len(rendered) != len(routes):
        plan = data.get('production_plan', {})
        path = Path(plan.get('path', ''))
        if path.is_file() and plan.get('sha256') == filehash(path):
            action = dict(owner='Producer', action='Execute the authored remaining route plan',
                          command=['uv', 'run', 'python', '-m', 'mechanical_video_next',
                                   'route-run', str(task), '--plan', str(path)])
        else:
            action = dict(owner='Producer', action='Author and bind a topic-specific route plan; do not use the nail-clipper default', command=None)
    elif not accepted:
        action = dict(owner='QA', action='Resolve exact-media acceptance gaps; rendered media is not accepted delivery', command=None)
    else:
        action = dict(owner='Producer', action='Provide the accepted actual files and report to the user, then record delivery', command=None)
    if action.get('handoff') == 'research' and data.get('product_search_plan'):
        action = dict(action)
        plan = task / data['product_search_plan']
        discovery = plan.with_name('product-discovery.json')
        action['product_search_plan'] = str(plan)
        action['product_discovery'] = str(discovery)
        search_plan = read_input_json(plan)
        result = read_input_json(discovery) if discovery.is_file() else {}
        if result.get('plan_sha256') != digest(search_plan):
            action.update(kind='EXECUTABLE', command=['uv', 'run', 'python', '-m',
                          'mechanical_video_next.product_research', str(task.resolve())])
        elif result.get('status') == 'INSPECTION_REQUIRED' and not any(
                lead['category'] != 'user_reference' for lead in result.get('leads', [])):
            action['browser_lookups'] = [row['url'] for row in search_plan['queries']
                                         if row['category'] == 'repair' and row.get('url')][:3]
            if action['browser_lookups']:
                action['action'] += '. Open the supplied browser lookups for gaps; the automated queries added no distinct sources'
        action['action'] += '. Use the cached sources and bounded multilingual public lookups in the product search plan.'
    # A QA gap is work, not proof that every possible production step is blocked.
    blockers = [row for row in data.get('production_blockers', []) if row.get('status') == 'OPEN'
                and row.get('kind') in {'permission', 'login', 'technical-evidence', 'resource', 'EXTERNAL_BLOCKED'}
                and row.get('evidence') and row.get('alternatives')
                and row.get('alternatives_checked') is True
                and row.get('remaining_executable_work') is False]
    lifecycle = ('DELIVERED' if milestone == 'DELIVERED' else
                 'BLOCKED' if blockers and not action.get('command') else
                 'REPAIRING' if unresolved_content or failed_qa or review_gap or execution_needs_repair or data['state'] in {'FAILED', 'REPAIRING'}
                 or any(row.get('status') == 'REPAIRING' for row in data.get('candidate_failures', [])) else 'WORKING')
    action['kind'] = ('DELIVERED' if milestone == 'DELIVERED' else
                      'EXECUTABLE_COMMAND' if action.get('command') else
                      'EXTERNAL_BLOCKED' if lifecycle == 'BLOCKED' else 'REASONING_REQUIRED')
    result = dict(schema_version=1, milestone=milestone, lifecycle=lifecycle,
                  production_status=('DELIVERED' if milestone == 'DELIVERED' else
                      'EXTERNAL_BLOCKED' if lifecycle == 'BLOCKED' else
                      'FINAL_QA_PENDING' if milestone == 'FINAL_RENDERED' and not accepted else
                      'FULL_3D_RENDERED' if rendered else
                      'PARTIAL_3D_RENDERED' if stages else 'RESEARCH_PARTIAL'),
                  blockers=blockers, delivered=milestone == 'DELIVERED',
                  workflow_state=data['state'], next_action=action, remaining_work=missing,
                  invalid_evidence=invalid, rendered_routes=rendered, preview_routes=route_previews,
                  diagnostic_clips_only=not route_previews and milestone not in {'PREVIEW_READY', 'FINAL_RENDERED', 'QA_ACCEPTED', 'DELIVERED'} and bool(stages) and all(row.get('diagnostic') or row.get('phase') in {'asset', 'keys', 'checks'} for row in stages),
                  resume_command=resume, execution_mode='current_native_codex_session',
                  background_execution=False)
    if persist:
        with lock(task / '.ledger.lock', wait=True):
            current = load(task)
            current['continuation'] = result
            current['next_step'] = action['action']
            write(task / 'task.json', current)
    return result


def continue_production(task):
    """Drain executable ledger actions in this process; return reasoning to Codex.

    The commands remain the existing evidence-gated stage/route entry points.
    This does not fabricate an AI repair loop or schedule background work.
    """
    task = Path(task)
    with lock(task / '.producer-execution.lock'):
        attempted = set()
        executed = 0
        while True:
            result = continuation(task)
            command = result['next_action'].get('command')
            if result['delivered'] or not command:
                result['execution'] = dict(commands_executed=executed,
                    returned_to_native_producer=result['next_action'].get('kind', 'REASONING_REQUIRED') == 'REASONING_REQUIRED',
                    required_next_action=result['next_action'], background_execution=False)
                return result
            # A successful command that does not change its own prerequisites
            # must not be repeated forever. A native Producer diagnoses it.
            fingerprint = digest(dict(command=command, milestone=result['milestone'],
                action=result['next_action'], rendered_routes=result['rendered_routes'],
                handoffs=load(task).get('handoffs', {}), plan=load(task).get('production_plan', {})))
            if fingerprint in attempted:
                with lock(task / '.ledger.lock'):
                    data = load(task)
                    data['production_execution_failure'] = dict(status='OPEN', command=command,
                        error='Successful command made no ledger progress; native diagnosis required',
                        plan_sha256=data.get('production_plan', {}).get('sha256'),
                        handoffs_sha256=digest(data.get('handoffs', {})), epoch=time.time())
                    write(task / 'task.json', data)
                event(task, 'producer_no_progress', command=command,
                      reason='Identical executable action remained after execution; native diagnosis required')
                result = continuation(task)
                result['execution'] = dict(commands_executed=executed,
                    returned_to_native_producer=True, no_progress=True, background_execution=False)
                return result
            attempted.add(fingerprint)
            command_config_sha256 = (filehash(command[command.index('--config')+1])
                                     if '--config' in command else None)
            event(task, 'producer_action_started', command=command)
            try:
                subprocess.run(command, cwd=ROOT, check=True)
            except (subprocess.SubprocessError, OSError) as error:
                with lock(task / '.ledger.lock'):
                    data = load(task)
                    data['production_execution_failure'] = dict(status='OPEN', command=command,
                        error=str(error), plan_sha256=data.get('production_plan', {}).get('sha256'),
                        config_sha256=command_config_sha256,
                        handoffs_sha256=digest(data.get('handoffs', {})), epoch=time.time())
                    write(task / 'task.json', data)
                event(task, 'producer_action_failed', command=command, error=str(error),
                      next_owner='Producer', background_execution=False)
                continuation(task)
                raise
            executed += 1
            event(task, 'producer_action_completed', command=command)


def delivery_files(task, data, routes):
    """Resolve mandatory files from accepted reports, never a topic-specific path."""
    scoped_media = current_source_supported_film(task, data)
    if scoped_media is not None and routes.get('3d') != scoped_media:
        raise ValueError('Delivery media differs from the current source-supported final stage')
    if scoped_media is None:
        reject_superseded_scoped_final(data, routes.get('3d', {}))
    required = list(routes.values())
    if len(data.get('requested_routes', [])) != 3 and data.get('three_d_policy_version') != 1:
        return required
    from .growth_report import validate as validate_growth
    from .covers import validate as validate_covers, SIZES
    growth = validate_growth(task)
    covers = validate_covers(task, require_pass=True)
    comparison = growth.get('comparison', {})
    if data.get('three_d_policy_version') != 1 and (not comparison.get('path') or Path(comparison['path']).suffix.lower() != '.mp4'):
        raise ValueError('Accepted synchronized comparison binding required for delivery')
    if data.get('three_d_policy_version') != 1:
        required.append(comparison)
    else:
        from .provenance import validate
        from .media_policy import enabled as asset_first, validate_manifest, bound
        if asset_first(data):
            provenance = Path(routes['3d']['path']).with_suffix('.media-provenance.json')
            manifest = validate_manifest(provenance, routes['3d'])
            validate(bound(manifest['build_proof']), routes['3d'])
        else:
            provenance = Path(task) / '3d-provenance.json'
            validate(provenance, routes['3d'])
        required.append(dict(path=str(provenance), sha256=filehash(provenance)))
    for name in SIZES:
        matches = [item for item in covers.get('artifacts', []) if Path(item['path']).name == name]
        if len(matches) != 1:
            raise ValueError('Both accepted cover ratios required for delivery: ' + name)
        required.extend(matches)
    growth_path = Path(task).resolve() / 'growth-report.json'
    required.append(dict(path=str(growth_path), sha256=filehash(growth_path)))
    directed = producer_directed(data)
    if directed:
        artifact(task, 'final-qa')
        qa_path = Path(task) / data['handoffs']['final-qa']['path']
        required.append(dict(path=str(qa_path), sha256=filehash(qa_path)))
    from . import director_audio
    if director_audio.enabled(data):
        from .media_policy import bound
        qa = artifact(task, 'final-qa')
        direction = qa['audio_technical_evidence']['mix_check']['direction']
        bound(direction)
        required.append(direction)
    reference = data.get('reference_model_report')
    if not reference:
        names = ('reference-to-model', 'reference-model-qa')
        if directed and not reference_model_required(data):
            names += ('research',)
        name = next((name for name in names if name in data.get('handoffs', {})), None)
        if not name:
            raise ValueError('Reference-to-model report binding required for three-route delivery')
        artifact(task, name)
        path = Path(task) / data['handoffs'][name]['path']
        reference = dict(path=str(path), sha256=filehash(path))
    required.append(reference)
    for item in required:
        if not Path(item['path']).is_file() or filehash(item['path']) != item['sha256']:
            raise ValueError('Required delivery file missing or stale: ' + item['path'])
    return required


def record_delivery(task, files, reason):
    """Record an explicit post-acceptance handoff; never infer it from an exit."""
    task = Path(task)
    if not reason.strip():
        raise ValueError('Delivery description required')
    bindings = []
    for path in files:
        path = Path(path)
        if not path.is_file():
            raise ValueError('Delivery file missing: ' + str(path))
        bindings.append(dict(path=str(path.resolve()), sha256=filehash(path)))
    provided = {(item['path'], item['sha256']) for item in bindings}
    with lock(task / '.ledger.lock'):
        report = continuation(task, persist=False)
        if report['milestone'] not in {'QA_ACCEPTED', 'DELIVERED'}:
            raise ValueError('Actual complete route MP4s and independent QA acceptance required before delivery')
        data = load(task)
        for media in delivery_files(task, data, report['rendered_routes']):
            if (str(Path(media['path']).resolve()), media['sha256']) not in provided:
                raise ValueError('Every required delivery file must be provided to the user: ' + media['path'])
        if source_policy.enabled(data):
            require_source_supported_render(task)
            source_policy.validate_sources(bindings, policy=data)
        data['delivery_receipt'] = dict(provided_to_user=True, routes=report['rendered_routes'],
                                       files=bindings, reason=reason, epoch=time.time())
        write(task / 'task.json', data)
        event(task, 'delivered', files=bindings, reason=reason)
    return continuation(task)


def producer_prompt(data, task):
    identity, topic = data['id'], data['topic']
    if mechanism_first(data):
        question = data.get('core_question') or 'Frame a question within the requested mechanical object.'
        formal_instruction = '''Develop one complete Full Animatic and one complete Final Film.
Reserve shot tests, mechanism previews and social cutdowns for their own purposes.
Plan retention, like, save, comment and follow in the Treatment, and carry each
decision into the Blueprint and package. Choose source-backed findings from how
it works, why it was designed this way, design comparisons, practical use and
hidden discoveries. Connect each finding to an observable shot and its narration.
Compare inexpensive moving edits before HD. Look for the first useful answer,
distinct reasons to like and follow, and a grounded discussion point. Use the
remaining scenes for further discoveries and a short, visible knowledge summary.
If a related unpublished topic is confirmed, its question can carry the series
forward. Use actual MP4 timecodes for creative observations and real platform
data for next-episode hypotheses and measured outcomes.
''' if formal_duration_enabled(data) else ''
        if data.get(FORMAL_DURATION_FIELD) == 1:
            formal_instruction += 'This historical task requires 120–300 seconds.\n'
        if data.get(FORMAL_DURATION_FIELD) == FORMAL_DURATION_VERSION:
            formal_instruction += (
                'The final film needs at least 60 seconds of earned content. Aim for 90–180 seconds '
                'or 180–300 for a knowledge-rich mechanism. Expand source-backed causal depth, design '
                'comparisons and practical use before trimming. Judge the moving edit for useful insight, '
                'mechanical surprise, expressive picture and sound, and recognizable daily experience. '
                'Check that new discoveries continue after the opening. Drafts may be shorter.\n')
        if pacing.enabled(data):
            formal_instruction += (
                'Answer the pacing brief in the Treatment before asset work. Use the pinned operations '
                'review to choose a testable editorial decision. Budget for verified knowledge, source motion, '
                'observation and measured Neil speech. Aim for a visible functional event by 2 s and '
                'a result or causal advance by 5 s. Maximum 300 s.\n')
        if data.get('reference_search_plan'):
            formal_instruction += (
                'Use viral-video-research and research/search-plan.json before the Treatment. '
                'Look for real teardowns, original 3D animation and hybrid videos. Inspect actual '
                'playback for gaps in the verified cache. Record original execution and expected '
                'visible effects on Treatment scenes, then verify the same effects on moving edits.\n')
        return f'''You are the sole native Producer for {identity} ({topic}).
Read {task}/task.json and docs/history/production-contract-20261124.md. 君哥拆机器 is 「{POSITIONING}」
Requested mechanical object: {data['mechanical_object']}
Core question: {question}
{formal_instruction}
Keep the requested object and question throughout research, treatment and edit.
Use the product_search_plan in task.json to inspect cached evidence and run public
lookups for uncovered parts and actions. Register located observations in the reference library.
For selective native reveals, attach product_assembly to the existing assembly
config and use science.assembly_reveal to select the installed connection and
retained part datums. Use verified component geometry and the existing motion,
section and camera settings for the causal action.
Use mechanical-research to verify the exact source-backed implementation, appearance,
key parts and contacts. Show a continuous cycle from input through transmission,
output and reset. Explain the scientific cause and return to ordinary use.
Use mechanical-video and director to design the complete Treatment and storyboard
around inspectable native Blender 3D. Use OpenCascade and existing constraints as
needed. Emphasize disassembly, cutaway, contact close-ups and action continuity.
Use history, live footage, everyday scenes and graphics in support of the mechanism.
Public creator media is REFERENCE_ONLY unless rights authorize reuse.

Use existing independent QA with $video-review for story-qa and diagnostic-qa.
Review the same object and question, internal 3D, whole motion and mechanical cause
on the current moving preview. Judge actual product recognition, installed-to-revealed
orientation and visible input through output and reset. Repair the failing shot first.
Reject scope drift and core 3D substitution.
Continue formal production after independent mechanical and visual PASS.
Use the existing Blueprint, scientific and mechanical checks, rights, audio,
render and media QA. Record technical evidence and actual viewing separately.
No platform publication or drafts.
'''
    if story_development(data):
        return f'''You are the sole native Producer for {identity} ({topic}).
Read {task}/task.json and docs/history/production-contract-20261124.md. The fixed positioning of
君哥拆机器 is 「{POSITIONING}」. Combine invention and design history, real science
and mechanics, and original visual storytelling. User authorization is needed to change that positioning.

Use mechanical-research to investigate origin, use problem, historical context, earlier design
limits, subsequent changes and the scientific principle. Bind each finding or explicit knowledge
gap to the fact ledger. Then author the complete story-treatment and causal storyboard with
mechanical-video and director. Decide the question, narrative form, pace and media by the story.
Find an observable design conflict, compare choices and return to what changes for people.
Direct lived and historical scenes, demonstrations and mechanisms wherever they carry that story.
Historical attribution and lineage require evidence. Distinguish located evolution and functional comparisons.
Choose the Treatment before selecting or making production assets. Existing references are optional inputs.

Use existing independent QA with $video-review for story-qa. Only PASS authorizes the complete
low-cost diagnostic-animatic. Obtain independent diagnostic-qa on its exact MP4. A structural
REJECT returns to Treatment development. REVISE targets the cited local changes. UNKNOWN
needs the missing review capability. Only PASS unlocks formal asset and HD work.
Keep public creator media REFERENCE_ONLY unless rights authorize reuse.
Bind the accepted story to the existing Blueprint. Continue through existing source, rights,
mechanical, audio, render and independent Video Review gates. Record technical and creative
verdicts on their own evidence. No publication or platform drafts.
'''
    if skill_driven(data):
        return f'''You are the sole native Producer for {identity} ({topic}).
Read {task}/task.json and the Skill-driven pilot section of docs/history/production-contract-20261124.md.
Develop an original film for 君哥拆机器. Choose the Skills and the working order the subject needs.
Use mechanical-research to ground history, use and mechanisms, and mechanical-video and director to
explore materially different stories. Seek an independent editorial judgment before committing.
Author a complete cheap moving test. Use video-review on the actual picture and preserve the verdict.
Make the story, scene order, media, pacing and ending your decisions. Write those decisions into
the existing Blueprint when ready to bind execution. Pick visuals that earn their screen time.
Use mechanical-asset, mechanical-animation and the existing editing/audio tools as the cut requires.
Keep source hashes, evidence boundaries, rights, native action clocks, measured Neil and independent
preview/final QA. Diagnose locally where possible. Deliver through the existing final verification.
No platform publication or drafts.
'''
    if producer_directed(data):
        from .audio_acceptance import MODE
        story_direction = ''
        if directed_story(data):
            story_direction = '''
Start from an everyday question viewers can test with their eyes. In research.audience_decision,
record the question, use, design tension, visible test, viewer takeaway and reason to choose it.
Consider why a simpler-looking design may fail and choose the question before matching assets.
Bind opening, first discovery, causal reveal and payoff to observable frame intervals in
narrative.moments. Let the subject determine the structure. Cut repeated explanation or views
when they add no new relation, evidence or needed observation time.
For each shot, direct the visible target, composition, light, transition and sound. Choose when
to move the camera and when to hold through contact. Keep an anchor across wide and macro views
and protect the action window from cuts and captions. Choose different settings when the story
needs them. For sound, leave room to see the result and sync rights-verified effects to visible events.
Personally review the complete cheap moving edit. Have QA record creative_review and applied
reference_effects in the existing preview-qa before the final stage. Keep perceptual gaps UNKNOWN.
Fix structural problems in the cut and render only affected shot inputs.
'''
            from .director import enabled as creative_direction
            if creative_direction(data):
                story_direction += '''
Use the project $director Skill (.agents/skills/director/SKILL.md) to direct the shots and review the actual cut.
Write three treatments in the research director record: mystery, failure_inference and
direct_experiment. Choose one for this subject before matching assets. For each shot name
its new information in the Blueprint, assess visual routes, and bind the strategy to executable
fields. Use the shared picture/speech/action clock for editorial decisions and optional
sound events. See docs/creative-direction.md for the fields and execution.
'''
            from .joint_timeline import integrity
            if integrity(data):
                story_direction += '''
Use film_integrity_version=1 in the Joint Timeline. Bind each necessary event to its verified source,
source frames, output frames and knowledge. Preserve that clock through the camera edit. Bind the
scientific explanation and action result in narrative.moments alongside the opening, discovery,
causal reveal and payoff. In preview-qa and final-qa, use continuous review_observations of the
exact film. Identify mechanical_event_ids and source_comparison for mechanical_motion, and
story_moment_ids for narrative_comprehension. Cover the full film and the entire bound interval
of each event and moment. A technical check cannot establish these observations.
Follow the film integrity fields and acceptance checks in docs/history/production-contract-20261124.md.
'''
        if data.get(video_review.FIELD):
            story_direction += '''
Use the project $video-review Skill for the existing independent preview-qa and final-qa.
Before the edit, record the essential verified facts in research.science.required_knowledge_ids.
When the animation-manifest and timeline are registered, read their generated video_review.
Return timecoded failures to the Producer. After the targeted repair, register the new complete
media and obtain independent QA on that exact MP4 before advancing.
'''
        audio_review = ('Use the verified Neil technical audio gate for the exact final MP4. '
                        'Record actual listening only when it happened. Register any known audio concern '
                        'as a timecoded QA issue for targeted review.'
                        if data.get('audio_acceptance_policy') == MODE else
                        'Have independent QA listen to the exact complete MP4.')
        from . import director_audio
        if director_audio.enabled(data):
            audio_review = ('Use the task music_direction_version and music mix mode in the Blueprint. '
                            f'The effective mode is {director_audio.mix_mode(data)}. '
                            f'Copy default_bgm={director_audio.default_bgm(data)} when pinned. '
                            'Design intentional silence where needed. Compilation resolves the catalog and writes audio_direction.json. '
                            'Bind verified mechanical sound_events to action frames. '
                            'Use technical evidence and independent full music_listening_review on the exact final MP4. '
                            'See docs/audio-direction.md for fields, explicit silence and audio-only revisions.')
        reference_work = ''
        if data.get('reference_search_plan'):
            reference_work = f'''Start with the next action from `uv run python -m mechanical_video_next continue "{task}"` and the task's
{data['reference_search_plan']}. It already searched the local reference library and supplies public searches
for Douyin, Xiaohongshu, Bilibili and YouTube. Reuse sufficient matching observations with verified evidence.
Otherwise search the same machine first and then related mechanisms or transferable visual treatments.
Use available browser/playback tools to observe actual video. Switch sources when playback is unavailable.
Record timecoded observations of the opening, new discoveries, payoff, teardown/cutaway, motion, camera,
and narration where observed. Record the exact viewing scope and limitations. Treat verified public counts
as dated interaction evidence. Retention requires separate evidence. Pick a small useful set by clarity,
audience appeal, pacing, transferability and feasibility in Blender/EAS.

Do the research yourself or assign an unresolved public viewing question to ViralResearch after checking
the cache and active work. Save observations and attempted sources in `research/viral-analysis.json`
as you go and reuse that work if interrupted. Register the task-bound `viral-analysis` handoff once,
including a limitation with empty `selected_ids` when options are exhausted. Resume from an existing
handoff. Follow the payload and cache instructions in the Producer-directed section of docs/history/production-contract-20261124.md.

Carry useful techniques from the selection into the existing Blueprint `reference_principles` with the reference ID, technique,
original execution decision and actual shot IDs. Author the resulting camera, action, staging or edit in those
shots. Learn general methods and keep the script, shots, music and distinctive expression original. Treat
public footage as REFERENCE_ONLY unless its reuse rights are verified independently.

'''
            if directed_story(data):
                reference_work += ('For reusable techniques record source_range, visual_method, use_condition, '
                                   'viewer_effect and implementation. Bind each adopted technique_id and expected '
                                   'observable effect to the original Blueprint shots.\n\n')
        return f'''You are the sole native Codex Producer for {identity} ({topic}).
Task directory {task}. Read its ledger and the Producer-directed section of docs/history/production-contract-20261124.md.
You make the complete film for 君哥拆机器. 拆开机器，看懂它怎么工作。用三维动画讲清身边的机械原理。

{reference_work}Research the actual machine and find the story worth telling. Follow the subject into its invention,
people, use, design tradeoffs or evolution where they make the film more revealing. Choose the story,
visual language and length. Then choose an evidenced implementation and assets that serve it.
Direct the whole visual story, including where the viewer needs to see a teardown, cutaway or mechanism
in motion. Use lawful context and original graphics where they help. Use Research, CAD, Animation and
Editor as needed. Own the decisions about the picture, narration, pacing and sound throughout.
Use the recognizable 君哥拆机器 teardown identity and meaningful links between episodes. Give viewers a
reason to return through the mechanical discoveries. Keep actual viewing, likes and follows as separate
observations in the existing production/growth reporting when post-publication data is available.
{story_direction}

Record located facts and verify the exact implementation, constraints and depicted motion. Scope
unknowns to affected shots. Use inspectable native 3D or rights-verified, independently observed
real footage for core actions. Keep REFERENCE_ONLY media and internal source or model identifiers
out of audience copy. Explain consequential model limits plainly.

Use the existing Blueprint, Blender/EAS, measured Neil, Joint Timeline and Remotion/FFmpeg.
Inspect key actions and a low-cost full edit, then finish the film. Use existing handoffs, serial
rendering and caches. Diagnose failed work before retrying. Have independent QA watch
the exact complete MP4 and check science, motion, clarity, originality and rights. {audio_review} Record
unavailable observations as UNKNOWN. Deliver 1920×1080/30, phone-readable single-line subtitles,
both covers and the existing provenance, QA and production records. Preserve historical assets
and use local delivery only.
'''
    from .production_contract import enabled as science_contract, creative_first, discovery, mechanical_story, science_story
    if science_contract(data):
        creative = creative_first(data)
        approach = (
            'Start with a recognizable daily event, a real question and a visible discovery. '
            'Research tests the question and exact mechanism while exploring ways to show the answer. '
            'Put the audience decision in research before choosing assets or authoring CAD. '
            'Develop the original visual story and then write the dialogue. Prioritize lawfully owned '
            'real use or product exterior, matching licensed supporting footage, and targeted original 3D or '
            'information animation according to the scene. Record missing materials and credible substitutes. '
            'Require independent opening, visual-task, pace, everyday-link, voice/sound and payoff '
            'review on the entire measured dynamic animatic before HD. Reviewer findings need timecodes '
            'and a specific replacement for each defect.'
            if creative else 'Execute research -> original script -> visual direction -> lawful assets.')
        from .joint_timeline import enabled as joint_timing
        if science_story(data):
            positioning = (
                'You produce exclusively for the Douyin account 君哥拆机器. '
                '拆开机器，看懂它怎么工作。用三维动画讲清身边的机械原理。'
                if mechanical_story(data) else 'Follow the historical topic scope pinned in this task.')
            research_instruction = (
                'Start with a machine, tool, mechanism, mechanical structure or everyday engineered object. '
                'With a bare topic, independently explore distinct questions about why it was invented, why it was '
                'designed this way, clever details, tradeoffs, alternatives, actual use, evolution, failures and '
                'improvements, and mechanical applications in other fields. Science enters through the design, '
                'instrument or application. For an off-domain prompt, pursue a faithful, evidenced mechanical angle '
                'when one exists. Otherwise record the scope mismatch. '
                'For each shortlisted story, record a mechanical_focus naming the device and consequential design '
                'choice, located facts, the observable payoff and the editorial tradeoff. Compare audience curiosity, '
                'design insight, specificity of evidence, visual payoff and feasibility. Select one story before locking '
                'the exact implementation, assets, shots or voice. Avoid a sequence of part identifications. '
                'Use original 3D disassembly, cutaways and motion to reveal the decisive design. Real use, archival '
                'context and original graphics can carry the scenes they serve.'
                if mechanical_story(data) else
                'Begin with bounded exploration of the subject, including historical context, design choices, '
                'tradeoffs, alternative solutions, applications and testable surprises where relevant. '
                'Compare a short list of distinct audience questions and their strongest visible moments. '
                'Make the editorial selection before matching assets. Record why the other directions are deferred '
                'and keep useful leads for later episodes. Deepen only the evidence for the shortlist and selected story. '
                'An archive can establish a technological change, while a model can test a physical cause. '
                'Choose the story form and preview its full edit before investing in production.'
                if discovery(data) else
                'Start with a familiar event, a surprising observable change and a specific discovery the viewer can take away. '
                'Choose the visual language by what best reveals the cause. Compare an alternative in the audience decision.')
            from .visual_narrative import scene_direction_enabled
            direction_instruction = (
                'Direct scene events before selecting tools. Give each scene a subject, setting, visible change, '
                'focus, camera, transition, story purpose and source. Connect story scenes and explanatory views '
                'through a recognizable object, viewpoint or result. Plan the whole picture draft about what '
                'viewers can see without narration. If a tool fails, test another viable treatment and record '
                'any missing visual capability. Have QA review the exact complete draft before formal Neil or HD. '
                'Look for text-only explanation, repetitive views and absent events. A hold can earn its time.'
                if scene_direction_enabled(data) else '')
            competition_instruction = (
                'Read broad topic sources before drafting a shortlist or matching any implementation. '
                'Register the provisional EDITORIAL research handoff with distinct design premises, visible tests '
                'and audience takeaways. Check the facts and visual feasibility of each standalone story. '
                'As Producer, compare those findings and record your choice and reasons in the DECISION handoff. '
                'Treat the initial order as provisional. Investigate an alternative depiction before passing '
                'over a high-priority story for production reasons. Bring the strongest '
                'alternative and relevant past evidence to the existing QA reviewer. Ask QA to make a reasoned '
                'creative verdict on the exact edit and explain whether the problem is local or structural. '
                'Use continuation after a structural veto. Try one substantial rewrite of the same design '
                'question when the evidence supports it. If it still fails, compare the remaining candidates. '
                'Register the real QA run and preserve any sensory UNKNOWN. '
                if editorial_policy.enabled(data) else '')
            return f'''You are the sole native Codex Producer for {identity}: {topic}.
Task: {task}. Read docs/history/production-contract-20261124.md and the current ledger.
{positioning}
Own the creative decision yourself. {research_instruction}
{direction_instruction}
{competition_instruction}
Use the research-bound diagnostic-animatic for an inexpensive
moving edit of the complete story before committing to a production method.
Research owns facts and content value. Asset owns matching and rights. Use CAD
and Animation where the picture needs spatial geometry or verified mechanism
motion. Editor co-authors the picture/action/sound rhythm with you, including
silence, speech across cuts and a visual payoff. Use measured Neil for authored
speech on the joint timeline. Let the story set the duration.
Build the audience copy intentionally from the story. Keep model provenance,
identifiers, engineering details and QA in internal evidence. Explain material
limits in plain language and preserve required credits. Validate each science
claim and exact implementation where relevant. Core mechanical actions need
inspectable 3D or exact continuously observed footage with verified rights.
Third-party research media defaults to REFERENCE_ONLY. Check actual reuse rights.
Use the existing roles, handoffs, cache, stage lock and media provenance. The 3d
route name is compatibility only. Independent QA evaluates the full moving edit
and judges creative quality separately from science and technical correctness.
Keep formal rendering pending until the exact animatic passes creative review.
Revise the visual story when the evidence warrants it. Final acceptance still
requires the exact full film and sound, science, rights, both covers and existing
delivery reports. Preserve historical assets and tasks. No platform writes.
'''
        duration_instruction = ('Author picture cuts and source-bound action windows first. Place measured Neil '
                                'utterances on one continuous track independent of the cuts. Revise overflowing speech '
                                'or explicitly re-edit the picture; keep meaningful observation time. '
                                'Freeze the joint timeline after the dynamic animatic review.'
                                if joint_timing(data) else 'Use measured Neil audio and the story to set duration.'
                                if creative else 'Use measured Neil audio to determine knowledge-supported 120–300 s.')
        return f'''You are the sole native Codex Producer for {identity}: {topic}.
Task: {task}. Read docs/history/production-contract-20261124.md as the effective contract, then only
the applicable role/tool details. This task explicitly uses {data['production_contract']};
the compatible route remains 3d, but do not claim mixed media is 3D-only.
{approach}
Use measured Neil audio/full dynamic animatic -> supported shots -> full composition -> independent
six-dimension exact-media QA -> scoped repair -> complete delivery. Use the current
native agents and role TOML routing with compact hash-bound assignments. No second
Producer, scheduler, extra agents or platform writes. Native reasoning remains your
work; a command=None or a completed child is never delivery.
Research records a concise science.facts ledger: located sources, derived assumptions,
units, exact implementation and unknowns. Reuse verified facts/assets without duplicate
research. Unknown facts block only dependent depictions. Never invent internal parts,
mix implementations or present a teaching path as a physical simulation.
Before CAD/rendering, each Blueprint shot needs actual incremental knowledge, observable
action, why_visual/composition/lighting/continuity/sound_intent in direction, reusable
assets and evidence. Design an original question-to-answer narrative, not repeated CAD
angles. Prefer owned assets and generate meaningful gaps; check lawful external rights.
For cinematic shots read docs/cinematic-shots.md and config/cinematic-shots.json.
Choose by knowledge goal, actual action, named contact objects, observation scale,
screen continuity and viewing difficulty. Stable overviews remain valid. Only independently
validated entries may become production defaults; experiments require explicit draft
scope and exact-media comparison. Do not move the camera just to create activity.
Other creators default to REFERENCE_ONLY and cannot be composited without verified rights.
Use real 3D or independently verified licensed actual mechanism footage for core actions,
and original scientific/information animation for explanation. Keep native 3D provenance
and separate complete mixed-media provenance. Bind the compiled config and all handoffs.
{duration_instruction} No padding, repeated
shots, forced speed changes or static cards standing in for motion. Gray/metal brand,
phone-readable single-line subtitles, 1920x1080/30 and both covers remain required.
Keep Blender serial under existing stage lock, work <=2 GiB/free disk >=3 GiB, per-shot
content caches and chunk encoding. Caption/chart edits only recompose. A wrong mechanism
requires evidence-based replacement; unchanged failures require a changed diagnosis.
Perceptual UNKNOWN permits technically supported production, never acceptance. Review
the complete real film/audio and continuous key-action intervals independently; disclose
unavailable senses. No sampled image, test, hash, loudness or ASR grants visual/listening
PASS. Revisions bind previous/current MP4s, shots, claimed ranges, defects and decoded
visual differences; pixel changes alone never prove improvement.
Actually deliver the full MP4, 3:4/4:3 covers, references/material manifests/provenance,
QA and production/growth reports before record-delivery. Report Level 1, 2 and 3 separately.
No missing or UNKNOWN required check may become DELIVERED. Preserve historical files,
cache and failure evidence; no upload/publication. Token/cost without telemetry are null.
'''
    from .visual_narrative import VERSION, version
    from .knowledge_progression import enabled as evidence_progression
    mixed = version(data) == VERSION
    visual_guidance = (
        'Use visual_policy_version=2 and docs/visual-narrative.md. Core movements stay native 3D. '
        'Licensed footage and original Remotion graphics may support verified claims. '
        'Record visual_research and a provisional Blueprint shots list in the research handoff before CAD. '
        'Compare a small set of audience questions in their daily context. For new work, record the selected '
        'opening visual, viewer takeaway, and choice rationale in narrative.audience_decision, linked to the '
        'first shot and the shot that delivers the answer. Use actual comparable platform observations when available. '
        'Freeze the final supported knowledge and visual decisions in the existing creative-blueprint. '
        'Use visual_checks in content, animatic, preview and final QA. In independent media review, locate '
        'opening clarity, narrative progress, visual continuity, causal understanding and reasons to return '
        'in actual time ranges. Tie each defect to its shot, viewer impact, repair owner and verification method.'
        if mixed else 'Apply the original 3D-only policy to the full timeline.'
    )
    if data.get('presentation_style') == 'natural_science':
        visual_guidance += (
            ' Author presentation_style=natural_science in the Blueprint before binding QA. '
            'Open with an everyday question and use visible motion to explain its cause. Introduce terms '
            'after explaining the relationship in ordinary language. Keep source scope and model assumptions '
            'in internal records. Speak consequential limitations plainly. Use subtitles for narration, and '
            'show part names, quantities, conditions and credits only when they serve the scene. '
            'Independent final QA checks actual visible titles, Blender marks, labels and subtitles, then '
            'listens for classroom phrasing, subtitle alignment and accurate model boundaries. Record UNKNOWN '
            'when actual viewing or listening is unavailable.'
        )
    if evidence_progression(data):
        visual_guidance += (
            ' Apply knowledge_progression_version=1. Explicitly connect the knowledge of the previous shot '
            'to a new claim or distinct observable demonstration. Show the start and end states of important '
            'changes and causal comparisons in continuous motion. Reject recaps with no visual increment. '
            'Check repeated compositions and idle frames, test graphics at 360/390/430 pixels, and bind '
            'visual observations to exact frames of the reviewed MP4.'
        )
    from .media_policy import enabled as asset_first
    if asset_first(data):
        visual_guidance += (
            ' Apply media_policy_version=1 and docs/asset-first-media.md. After visual planning, '
            'Original science content comes first: every video needs independent research, original narration, '
            'knowledge structure, storyboard and visual arrangement. Prefer project-owned/generated 3D, models, '
            'graphics and real footage; external material is supporting only. Other creators default to research '
            'references. Learn general techniques, never copy their distinctive script, full shot organization '
            'or signature visual expression. Cropping, flipping, speed changes, watermark removal or redubbing '
            'do not create original expression. Fair-use/quotation is never presumed. Never sacrifice originality '
            'to save rendering or force monotonous CAD views to claim full generation. '
            'match each shot using reference_library media-match: approved project clips, local history/assets, '
            'authorized footage, lawful Pexels/Pixabay/Wikimedia footage, then licensed 3D/animations. '
            'Use actual browser/provider tools for NOT_SEARCHED gaps; never call them searched. '
            'Default third-party content to REFERENCE_ONLY; cached bytes do not grant rights. '
            'Record every shot source_type/source_url/source_time_range/license_status/usage_restrictions/'
            'selected_asset/reuse_decision/generation_required, matching attempts, credit and rights proof. '
            'Generate only unavailable knowledge-bearing visuals, never padding. Core footage is allowed only '
            'with independent exact-interval observation proving the real mechanism and knowledge claims; '
            'otherwise use verified native 3D. Preserve generated scene provenance and write a separate '
            'media-provenance.json for the full hybrid timeline, never original 3D-only acceptance. '
            'Mute all source audio; Neil remains the narration. Independent hybrid_media_review binds '
            'the complete manifest, each shot, exact media and actual continuous viewing/listening.'
            ' Independent copyright_review and original_expression_review are separate QA findings; bind '
            'the latter to this task research/script/Blueprint, never determine originality from asset ratios.'
        )
    return f"""You are the sole native Codex Producer for {identity}: {topic}.
Task: {task}. {visual_guidance}
requested_routes=["3d"],
render_route="3d". No 2d, 2.5d, all, illustrated/layered mechanical subjects,
photo planes, parallax substitutes or fallback after a 3D failure. No comparison
or other-route film is a delivery dependency. Never start a second Producer.
Read AGENTS.md, README.md, docs/science-production.md, docs/3d-only-contract.md, docs/reference-first-contract.md,
docs/product-comprehension-contract.md, existing task ledger and applicable skills.
First inspect local verified references, actual product appearance and operation,
reliable internal mechanics and lawful assets. Prefer verified matching existing
3D assemblies; otherwise build evidence-grounded parametric teaching CAD. A patent
alone cannot establish a named retail product. Label teaching scope precisely.
Continuous reference viewing is optional for production; never invent observations.
Use reliable located manufacturer documents, photos and same-model structure sources.
REFERENCE_VIEW_UNKNOWN does not block evidenced shots. MECHANISM_UNKNOWN blocks only
dependent parts/actions; continue independent verified-shots via stage local while
researching same-model internals or evaluating a fully documented alternative product.
PERCEPTUAL_QA_UNKNOWN permits rendering and encoding, never formal acceptance.
Reject a fundamentally wrong product/mechanism plan, retaining its failure history;
until_pass never authorizes endless local patches to a rejected plan.
Bind evidence_map from claims to sources, parts, motion, shots and verification.
Plan knowledge goals before narration. Reuse exact implementation/asset controls and
combine evidence-bound 3D templates; mark conceptual and mathematical modes visibly.
For abstract phenomena use a bounded teaching model and identify the measured or
derived relationship. Never present prescribed motion as a verified solver result.
Use original narration and arrangement, locked studio style, Neil, measured audio,
1920x1080/30fps, readable single-line subtitles and knowledge-driven 120-300 seconds.
Keep shared narration and validated CAD/cache; subtitle edits only recompose.
Open with a supported action; every shot advances a new fact or causal step.
Never pad with repetition, slow playback, idle holds or rushed narration.
Show product, use, disassembly, internal power path, principle and product function.
Prepare real low-cost 3D previews and source/model/motion QA before costly rendering.
First produce a continuous 10-15 second real-3D preview showing recognizable product,
user operation, rotation/output, external-to-internal correspondence and core motion
with return. Partial exterior clips are not this preview. Preserve strict mechanical
evidence for every depicted action; sensory UNKNOWN remains pending at final acceptance.
Use existing roles only; immutable hashed handoffs and advance/stage gates remain.
Follow docs/agent-dispatch-efficiency.md before every native Agent call. Reuse
hash/version-bound work across sessions; deterministic checks run tools, not Agents.
Default to two concurrent children; a justified independent research/verification
exception permits three with an explicit session override. Use role TOML models,
never silently substitute a model. Pass only task, scoped paths/hashes, defects,
output and verification, using fork_turns=none. Mechanical conflicts go to Sol.
Record actual model/effort and usage in existing agent_runs; unknown cost is null.
Retain actual native thread IDs; never invent an independent review or capabilities.
Export inspectable scene, model and spatial motion files per core shot. Save
3d-provenance.json with camera, engine, assets/references, render outputs and complete
MP4 build. Run executable provenance validation, full decode, mechanism/comprehension,
phone subtitles, style and five-goal growth QA on the exact MP4 hash. A filename,
ffprobe result or perspective screenshot never proves 3D. Follow the task's visual
policy for supporting material. No UNKNOWN may be marked accepted.
Continue research -> assets -> scene -> animation -> preview -> render -> composition
-> QA -> scoped repair -> delivery. A failed subtask is a repair action, not global
completion. Diagnose and change ineffective strategies, never repeat unchanged
failure blindly; preserve repair history. Keep Blender serial and disk/work budgets.
Research, code upgrades, passing tests, CAD and local diagnostics are subtask work,
never completed delivery. Reuse existing QA and handoffs; do not build a new QA system.
Deliver one complete 3D MP4, 3:4 and 4:3 covers, product/reference report, provenance,
mechanical and viewer-comprehension QA and retention/like/save/comment/follow report.
Use continue TASK to reconcile exact evidence; never borrow another topic's plan.
Actual files must precede record-delivery. Completed historical media remain intact;
do not recreate the pull-back car. No upload, publication or platform draft.
command=None returns reasoning work to this current native Producer; it is not completion.
Use EXTERNAL_BLOCKED only with evidenced unavailable permission/resources/materials and
exhausted alternatives when every independent step is unavailable. Preserve partial media.
Track RESEARCH_PARTIAL, PRODUCTION_IN_PROGRESS, PARTIAL_3D_RENDERED, FULL_3D_RENDERED,
FINAL_QA_PENDING and DELIVERED separately. background_execution=false on session exit.
Token/cost/intervention measurements without telemetry are null, not invented zero.
"""


def sync_producer_prompt(task, data):
    task = Path(task)
    path = task / 'producer-prompt.md'
    content = producer_prompt(data, task)
    if data.get('mechanical_object') and not mechanism_first(data):
        content = (f"User scope for this task: {data['mechanical_object']}\n"
                   f"Required question: {data.get('core_question', data['topic'])}\n"
                   f"Account positioning: {POSITIONING}\n"
                   "Preserve this scope and use inspectable native 3D for the core mechanical explanation.\n\n"
                   + content)
    if path.exists() and path.read_text() != content:
        audit = task / 'recovery' / ('producer-prompt.before-3d-' + filehash(path)[:16] + '.md')
        audit.parent.mkdir(parents=True, exist_ok=True)
        if not audit.exists():
            audit.write_bytes(path.read_bytes())
        data.setdefault('producer_prompt_history', []).append(dict(path=str(audit), sha256=filehash(audit)))
        write(task / 'task.json', data)
    path.write_text(content)


def create_task(topic, duration=None, voice=None, config=None, task_id=None, root=ROOT,
                protocol_version=2, asset_strategy='reference-first', routes='3d', visual_policy_version=1,
                media_policy_version=0, presentation_style='natural_science', contract_version=None,
                *, skill_driven_pilot=False, story_development_version=2,
                mechanical_object=None, core_question=None, operations_review=None,
                product_model=None, product_references=(), lock_product_model=False, allow_short=False):
    from .production_contract import (NATURAL_SCIENCE, PRESENTATION_STYLE, FIELD as CONTRACT_FIELD,
                                      CONTRACT_NAMES, CREATIVE_FIRST_VERSION, STORY_VERSION,
                                      DISCOVERY_VERSION, CREATIVE_SELECTION_VERSION, CREATIVE_DURATION,
                                      FORMAL_DURATION, FORMAL_DURATION_POLICIES)
    if presentation_style not in {NATURAL_SCIENCE, 'legacy'}:
        raise ValueError('Unsupported presentation style')
    from .three_d import require_route, validate_config
    from .visual_narrative import DIRECTION_FIELD, DIRECTION_VERSION, FIELD, VERSION, match_policy, version
    from .knowledge_progression import FIELD as PROGRESSION_FIELD, VERSION as PROGRESSION_VERSION
    source_rules = {source_policy.FIELD: source_policy.NO_PATENT_POLICY_VERSION}
    require_route(routes)
    from .media_policy import FIELD as MEDIA_FIELD, enabled as asset_first
    hybrid = asset_first({FIELD: visual_policy_version, MEDIA_FIELD: media_policy_version})
    if hybrid and protocol_version != 2:
        raise ValueError('Asset-first media is only available for new protocol 2 tasks')
    if contract_version is not None and (not hybrid or config or type(contract_version) is not int
                                         or contract_version not in CONTRACT_NAMES):
        raise ValueError('Explicit mixed production contract requires a new topic-only hybrid task')
    directed = hybrid and not config and contract_version is None
    if skill_driven_pilot and not directed:
        raise ValueError('Skill-driven production requires a new topic-only mixed-media task')
    development = directed and story_development({STORY_DEVELOPMENT: story_development_version})
    if (mechanical_object is not None or core_question is not None) and not (
            development and story_development_version == 2):
        raise ValueError('Mechanical scope options require a new mechanism-first task')
    if (product_model or product_references or lock_product_model) and not (
            development and story_development_version == 2):
        raise ValueError('Product search options require a new mechanism-first task')
    if lock_product_model and not product_model:
        raise ValueError('Locking the product requires a model')
    if any(value is not None and not value.strip() for value in (mechanical_object, core_question)):
        raise ValueError('Mechanical scope options require nonempty text')
    if directed:
        contract_version = CREATIVE_SELECTION_VERSION
    creative = contract_version is not None and contract_version >= CREATIVE_FIRST_VERSION
    if asset_strategy == 'illustrated':
        raise ValueError('3D-only production rejects illustrated assets')
    progression = visual_policy_version == VERSION
    if config:
        cfg = read_input_json(config)
        source_policy.validate_sources(cfg, policy=source_rules)
        validate_config(cfg)
        policy = {FIELD: visual_policy_version}
        if hybrid:
            policy[MEDIA_FIELD] = media_policy_version
        if progression:
            policy[PROGRESSION_FIELD] = PROGRESSION_VERSION
        match_policy(policy, cfg)
    requested_routes = ['3d']
    if type(protocol_version) is not int or protocol_version not in {1, 2}:
        raise ValueError('Unsupported production protocol_version')
    if version({FIELD: visual_policy_version}) == VERSION and protocol_version != 2:
        raise ValueError('Visual production needs protocol 2')
    formal_duration = directed and story_development_version == 2 and not skill_driven_pilot
    minimum_duration, maximum_duration = (30, 45) if protocol_version == 1 else FORMAL_DURATION
    if formal_duration:
        duration_version = SHORT_FORMAL_DURATION_VERSION if allow_short else FORMAL_DURATION_VERSION
        minimum_duration, maximum_duration = FORMAL_DURATION_POLICIES[duration_version]
        if math.isinf(maximum_duration):
            maximum_duration = None
        from .joint_timeline import binding
        feedback_source = binding(operations_review or ROOT / pacing.OPERATIONS_REVIEW)
    elif operations_review is not None:
        raise ValueError('Operations review applies to new formal tasks')
    if creative and not formal_duration:
        minimum_duration, maximum_duration = CREATIVE_DURATION[0], None
    if duration is None:
        duration = 45 if protocol_version == 1 else None
    if not topic.strip() or (duration is not None and (
            isinstance(duration, bool) or not isinstance(duration, (int, float)) or not math.isfinite(duration)
            or duration < minimum_duration or (maximum_duration is not None and duration > maximum_duration))):
        limits = f'{minimum_duration}–{maximum_duration}' if maximum_duration is not None else f'>={minimum_duration}'
        raise ValueError(f'Nonempty topic and duration {limits} required for protocol {protocol_version}')
    if protocol_version == 1:
        asset_strategy = None  # Explicit historical tasks retain their original asset contract.
    elif asset_strategy not in {'reference-first', 'existing-media', 'autonomous-cad', 'verified-existing', 'illustrated'}:
        raise ValueError('New tasks require an explicit supported asset strategy')
    if development and asset_strategy == 'reference-first':
        asset_strategy = None
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
    value.update(source_rules)
    value.update(three_d_policy_version=1, requested_routes=['3d'], render_route='3d')
    if visual_policy_version == VERSION:
        value[FIELD] = VERSION
    if hybrid:
        value[MEDIA_FIELD] = media_policy_version
        value['media_contract'] = 'asset-first-hybrid-v1'
        if config is None:
            value.update({CONTRACT_FIELD: contract_version or 1,
                          'production_contract': CONTRACT_NAMES[contract_version]})
    if progression and not directed:
        value[PROGRESSION_FIELD] = PROGRESSION_VERSION
    if contract_version is not None and contract_version >= DISCOVERY_VERSION and not directed:
        value[DIRECTION_FIELD] = DIRECTION_VERSION
    if creative:
        from .joint_timeline import FIELD as TIMELINE_FIELD, VERSION as TIMELINE_VERSION
        value[TIMELINE_FIELD] = TIMELINE_VERSION
    if directed:
        from .viral import directed_plan
        from .audio_acceptance import MODE
        from .director import FIELD as CREATIVE_DIRECTION, VERSION as CREATIVE_DIRECTION_VERSION
        from .joint_timeline import INTEGRITY
        value[PRODUCER_DIRECTION] = 1
        if development:
            value[STORY_DEVELOPMENT] = story_development_version
            if mechanism_first(value):
                value['mechanical_object'] = (mechanical_object or topic).strip()
                supplied_question = core_question or (topic if topic.rstrip().endswith(('?', '？')) else None)
                if supplied_question:
                    value['core_question'] = supplied_question.strip()
                if lock_product_model:
                    value['requested_product_model'] = product_model.strip()
                from .reference_library import product_search_plan
                value['product_search_plan'] = 'research/product-search-plan.json'
                write(task / value['product_search_plan'],
                      product_search_plan(value['mechanical_object'], supplied_question or topic,
                                          model=product_model, model_locked=lock_product_model, seeds=product_references,
                                          root=Path(root) / 'references'))
                value['reference_search_plan'] = 'research/search-plan.json'
                write(task / value['reference_search_plan'], directed_plan(
                    topic, Path(root) / 'references', product=value['mechanical_object']))
        value[INTEGRITY] = 1
        value[video_review.FIELD] = video_review.VERSION
        value['audio_acceptance_policy'] = MODE
        from . import director_audio
        value[director_audio.FIELD] = director_audio.CURRENT_VERSION
        from .ducking import CONSTANT_BED
        value[director_audio.MIX_MODE_FIELD] = CONSTANT_BED
        value[director_audio.DEFAULT_BGM_FIELD] = director_audio.DEFAULT_BGM
        if not skill_driven_pilot and not development:
            value[CREATIVE_DIRECTION] = CREATIVE_DIRECTION_VERSION
            value['reference_search_plan'] = 'research/search-plan.json'
            write(task / value['reference_search_plan'], directed_plan(topic, Path(root) / 'references'))
    if protocol_version == 2:
        value[PRESENTATION_STYLE] = presentation_style
        value['reference_policy_version'] = 1
        value['reference_model_policy_version'] = 1
        if not directed:
            value.update(product_policy_version=1, growth_policy_version=2, content_policy_version=1)
        value['duration_policy'] = {'minimum': minimum_duration, 'maximum': maximum_duration,
                                    'mode': 'knowledge-driven' if duration is None else 'requested',
                                    'requested_seconds': duration}
        if formal_duration:
            value[FORMAL_DURATION_FIELD] = duration_version
            value['growth_policy_version'] = 2
            value['operations_review'] = feedback_source
        value['production_method'] = 'reference-grounded-3d'
        if hybrid:
            value['production_method'] = 'asset-first-hybrid'
        value['autonomy_policy'] = dict(AUTONOMY_POLICY)
        if contract_version is not None and contract_version >= STORY_VERSION:
            value['production_method'] = PRODUCER_DIRECTED if directed else 'science-story'
            value['autonomy_policy'].update(reference_first=False, physical_reference_to_cad=False)
        if skill_driven_pilot:
            value['production_method'] = SKILL_DRIVEN
        value['requested_routes'] = requested_routes
        value['route_runs'] = {route: {'status': 'PENDING', 'outputs': {}} for route in requested_routes}
        value['shared_production'] = {
            'directory': str(task / 'shared'),
            'timeline': {'path': str(task / 'shared/timeline.json'), 'sha256': None},
            'narration': {'path': str(task / 'shared/narration.wav'), 'sha256': None},
            'cache_policy': 'content-and-config-sha256; narration shared across routes; geometry scoped by route',
            'render_directory': str(task / '3d')}
    write(task / 'task.json', value)
    sync_producer_prompt(task, value)
    event(task, 'created', topic=topic)
    continuation(task)
    return task


SOURCE_HANDOFFS = {'research', 'reference-to-model', 'asset-plan', 'cad-model', 'script', 'story-treatment',
                   'creative-blueprint', 'diagnostic-animatic', 'animatic-manifest',
                   'animation-manifest', 'mechanical-diagnostics', 'timeline'}


def validate_production_sources(task, config, *, policy, require_reveal=False):
    """Tie the assembly's declared source lineage to this task's inspected research."""
    source_policy.validate_sources(config, policy=policy)
    if not mechanism_first(policy):
        return
    if not config.get('assembly_config'):
        raise ValueError('SOURCE_IDENTITY_UNKNOWN: native product render needs its source-bound assembly')
    from .reference_policy import validate_research

    research = artifact(task, 'research')
    from .comprehension import validate_native_reveal, validate_product_research
    validate_product_research(research, policy=policy)
    refs = validate_research(research, policy=policy)
    assembly = read_input_json(ROOT / config['assembly_config'])
    if require_reveal:
        validate_native_reveal(config)
    source_ids = source_policy.require_source_ids(assembly, refs, 'render assembly')
    if 'product_assembly' in assembly:
        from .product_assembly import validate as validate_product_assembly

        validate_product_assembly(assembly['product_assembly'], assembly['required_parts'],
                                  source_ids=source_ids,
                                  model=research['product_identity'].get('model',
                                        research['product_identity']['model_scope']))
    if 'asset-plan' in policy['handoffs']:
        asset = artifact(task, 'asset-plan')
        candidate = next(row for row in asset['candidates'] if row['id'] == asset['selected_candidate_id'])
        if source_ids != set(candidate['source_ids']):
            raise ValueError('Render assembly source lineage differs from the selected asset')


def artifact(task, name):
    data = load(task)
    entry = data['handoffs'].get(name)
    if not entry:
        raise ValueError('Missing handoff: ' + name)
    path = Path(task) / entry['path']
    envelope = read_input_json(path)
    body = {k: v for k, v in envelope.items() if k != 'sha256'}
    if digest(body) != entry['sha256'] or envelope['sha256'] != entry['sha256']:
        raise ValueError('Handoff hash mismatch: ' + name)
    for dep, expected in envelope['dependencies'].items():
        if data['handoffs'].get(dep, {}).get('sha256') != expected:
            raise ValueError('Stale dependency: ' + dep)
        artifact(task, dep)
    payload = envelope['payload']
    if name in SOURCE_HANDOFFS:
        source_policy.validate_sources(payload, policy=data)
    if name == 'story-treatment' and 'document' in payload:
        from .joint_timeline import bound
        bound(payload['document'])
    if name == 'diagnostic-animatic':
        from .production_contract import science_story
        if science_story(data):
            check_media(payload['media'])
            evidence = payload['blueprint_evidence']
            plan_path = Path(evidence['path'])
            if not plan_path.is_file() or filehash(plan_path) != evidence['sha256']:
                raise ValueError('Creative draft edit plan missing or changed')
            if mechanism_first(data):
                from .joint_timeline import bound
                plan = read_input_json(plan_path)
                source_policy.validate_sources(plan, policy=data)
                for shot in plan['core_3d']:
                    bound(shot['source'])
    return payload


def require_visual_story_review(task):
    """Check the current pre-voice picture review, including unresolved media substitutions."""
    from .visual_narrative import scene_direction_enabled, validate_scene_direction, validate_scene_review
    data = load(task)
    if story_development(data):
        require_creative_pass(task, 'diagnostic-qa')
        return
    if not scene_direction_enabled(data):
        return
    draft = artifact(task, 'diagnostic-animatic')
    plan = read_input_json(draft['blueprint_evidence']['path'])
    if validate_scene_direction(plan, draft['media']):
        raise ValueError('Resolve the recorded visual capability gaps before formal production')
    review = artifact(task, 'diagnostic-qa')
    if editorial_policy.enabled(data) and review['story_review']['outcome'] != 'PASS':
        raise ValueError('The current story requires an independent creative PASS')
    if validate_scene_review(review.get('visual_story_review', {})) != 'PASS':
        raise ValueError('Independent complete picture review is pending')


def require_creative_pass(task, name):
    decision = artifact(task, name)['creative_decision']
    if decision['status'] != 'PASS':
        raise ValueError(f"Independent {name} requires PASS (current: {decision['status']})")


def creative_gate_next_action(valid):
    for name, revision_target in (('story-qa', 'story-treatment'),
                                  ('diagnostic-qa', 'diagnostic-animatic')):
        if name not in valid:
            continue
        decision = valid[name]['creative_decision']
        status = decision['status']
        if status == 'PASS':
            continue
        if status == 'UNKNOWN':
            return dict(owner='QA', handoff=name, command=None, creative_status=status,
                        action='Complete the missing independent review on the exact input')
        target = 'story-treatment' if status == 'REJECT' else revision_target
        return dict(owner='Producer', handoff=target, command=None, creative_status=status,
                    action=decision['revision'])
    return None


def previous_creative_input(task, ledger, review_name, input_name, statuses):
    """Read the exact input of a previous veto even after its dependencies change."""
    review = ledger['handoffs'].get(review_name)
    if not review:
        return None
    envelope = json.loads((task / review['path']).read_text())
    if digest({key: value for key, value in envelope.items() if key != 'sha256'}) != review['sha256']:
        raise ValueError('Previous creative review changed')
    if envelope['payload']['creative_decision']['status'] not in statuses:
        return None
    expected = envelope['dependencies'][input_name]
    for path in (task / 'handoffs').glob(input_name + '.v*.json'):
        source = json.loads(path.read_text())
        if source['sha256'] != expected:
            continue
        if digest({key: value for key, value in source.items() if key != 'sha256'}) != expected:
            raise ValueError('Previous creative input changed')
        return source['payload']
    raise ValueError('Previous creative input missing')


def treatment_content(payload):
    return {key: payload[key] for key in ('question', *editorial_policy.TREATMENT_FIELDS, 'scenes', 'growth_design',
                                        'pacing_brief', 'reference_principles')
            if key in payload}


def validate_development_handoff(task, data, name, payload):
    from .production_contract import validate_research

    vetoes = {'REJECT', 'REVISE'}
    if name == 'story-treatment':
        research = artifact(task, 'research')
        match_mechanical_scope(data, payload, payload.get('question'))
        if mechanism_first(data) and payload.get('question') != research['science']['question']:
            raise ValueError('Treatment must preserve the researched core question')
        editorial_policy.validate_treatment(payload, validate_research(research), mechanics=mechanism_first(data))
        if mechanism_first(data) and data.get('reference_search_plan'):
            from .viral import validate_reference_direction
            validate_reference_direction(payload, artifact(task, 'viral-analysis'))
        if formal_duration_enabled(data):
            from .growth import validate_growth_design
            validate_growth_design(payload.get('growth_design'))
        if pacing.enabled(data):
            brief = payload.get('pacing_brief')
            pacing.validate_brief(brief, data)
            scenes = {row['id'] for row in payload['scenes']}
            core = {row['id'] for row in payload['scenes'] if row['mechanical_role'] == 'core'}
            if not core <= set(brief['essential_scenes']) <= scenes or not set(brief['decorative_scenes']) <= scenes:
                raise ValueError('Pacing brief scene IDs must match the Treatment and retain all core scenes')
        if 'document' in payload:
            from .joint_timeline import bound
            bound(payload['document'])
        previous = previous_creative_input(task, data, 'story-qa', name, vetoes)
        if previous and treatment_content(payload) == treatment_content(previous):
            raise ValueError('Revise the vetoed story before resubmitting the Treatment')
        rejected_draft = previous_creative_input(
            task, data, 'diagnostic-qa', 'diagnostic-animatic', {'REJECT'})
        if rejected_draft and rejected_draft['story_content_sha256'] == digest(treatment_content(payload)):
            raise ValueError('Visual narrative REJECT requires a revised Treatment')
    elif name == 'story-qa':
        treatment = artifact(task, 'story-treatment')
        previous = previous_creative_input(task, data, name, 'story-treatment', vetoes)
        if previous and treatment_content(previous) == treatment_content(treatment):
            raise ValueError('Revise the Treatment before re-reviewing a creative veto')
        rejected_draft = previous_creative_input(
            task, data, 'diagnostic-qa', 'diagnostic-animatic', {'REJECT'})
        if rejected_draft and rejected_draft['story_content_sha256'] == digest(treatment_content(treatment)):
            raise ValueError('Visual narrative REJECT requires a revised Treatment before re-review')
        if 'document' in treatment:
            from .joint_timeline import bound
            if bound(payload.get('reviewed_input', {})).resolve() != bound(treatment['document']).resolve():
                raise ValueError('Story QA must review the exact Treatment document')
        editorial_policy.validate_creative_gate(data, payload)
    elif name in {'diagnostic-animatic', 'diagnostic-qa'}:
        require_creative_pass(task, 'story-qa')
        prior = previous_creative_input(task, data, 'diagnostic-qa', 'diagnostic-animatic', vetoes)
        treatment = artifact(task, 'story-treatment')
        treatment_digest = digest(treatment_content(treatment))
        if prior:
            current = payload if name == 'diagnostic-animatic' else artifact(task, 'diagnostic-animatic')
            if (prior['story_content_sha256'] == treatment_digest and
                    previous_creative_input(task, data, 'diagnostic-qa', 'diagnostic-animatic', {'REJECT'})):
                raise ValueError('Visual narrative REJECT requires a revised Treatment and story PASS')
            old_mp4 = {item['sha256'] for item in prior['media'] if Path(item['path']).suffix.lower() == '.mp4'}
            if any(item['sha256'] in old_mp4 for item in current.get('media', [])):
                raise ValueError('Revise the vetoed moving picture before submitting again')
        if name == 'diagnostic-animatic':
            if payload.get('story_treatment_sha256') != digest(treatment):
                raise ValueError('Bind the draft to the exact approved Treatment')
        else:
            from scripts.common import probe
            draft = artifact(task, 'diagnostic-animatic')
            film = next(row['path'] for row in draft['media'] if Path(row['path']).suffix.lower() == '.mp4')
            duration = float(probe(film)['format']['duration'])
            verdict = editorial_policy.validate_creative_gate(data, payload, duration=duration)
            if mechanism_first(data) and data.get('reference_search_plan'):
                from .viral import reference_shot_map, validate_reference_effects
                plan = read_input_json(draft['blueprint_evidence']['path'])
                mapping = reference_shot_map(treatment, plan)
                effects = validate_reference_effects(mapping, payload, filehash(film))
                if verdict == 'PASS' and effects - {'PASS'}:
                    raise ValueError('A passing diagnostic needs successful visible reference effects')
            if pacing.enabled(data):
                from .joint_timeline import binding
                report = draft['pacing_review']
                if report['media'] != binding(film):
                    raise ValueError('Diagnostic pacing review must bind the exact MP4')
                if (payload.get('creative_decision', {}).get('status') == 'PASS'
                        and pacing.review_status(report, payload) != 'PASS'):
                    raise ValueError('A passing diagnostic needs independent, exact-media pacing review')


def creative_next_action(data, valid):
    research = valid.get('research')
    if research is None:
        return None
    history = data.get('creative_history', [])
    story = research['story_exploration']
    selected = story['selected_id']
    if story['phase'] == 'EDITORIAL':
        return dict(owner='Producer', handoff='research', command=None,
                    creative_status='EDITORIAL_PRIORITY_RECORDED',
                    action='Verify each standalone story and have the Producer compare the findings before choosing or deferring')
    if selected is None:
        return dict(owner='Producer', action=story['stop_reason'], command=None,
                    creative_status='SHORTLIST_EXHAUSTED')
    if history and 'diagnostic-animatic' not in valid:
        last = history[-1]
        return dict(owner='Producer', command=None, creative_status=last['outcome'],
                    evidence=last['review'],
                    action=('Recompare the shortlist and register the next viable story or the topic limit'
                            if last['story_id'] == selected and last['outcome'] == 'RESELECT_STORY'
                            else 'Author a new moving draft addressing the independent story verdict'))
    for name in reversed(editorial_policy.REVIEW_INPUTS):
        if name not in valid:
            continue
        verdict = valid[name]['story_review']
        if verdict['outcome'] == 'PASS':
            continue
        if verdict['outcome'] == 'LOCAL_REPAIR':
            issue = valid[name]['issues'][0]
            return dict(owner=issue['responsible_agent'], action=issue['suggested_fix'],
                        qa_handoff=name, defect_key=issue['defect_key'], command=None,
                        creative_status=verdict['outcome'])
        return dict(owner='QA', action=verdict['reason'], qa_handoff=name, command=None,
                    creative_status=verdict['outcome'])
    return None


def retire_creative_direction(data, name, verdict):
    """Preserve the failed round while retiring its authority to produce."""
    history = data.setdefault('creative_history', [])
    story_id = verdict['story_id']
    outcome = verdict['outcome']
    if outcome == 'REVISE_STORY' and any(row['story_id'] == story_id for row in history):
        outcome = 'RESELECT_STORY'
    retired = {'config': data.get('config'), 'asset_strategy': data.get('asset_strategy')}
    for key in ('handoffs', 'production_plan', 'route_runs', 'shared_production', 'delivery_receipt',
                'repairs', 'repair_return_state', 'content_repairs', 'low_cost_animatic_approval',
                'production_execution_failure', 'candidate_failures', 'growth_report', 'shot_production'):
        if key in data:
            retired[key] = data.pop(key)
    data['handoffs'] = {'research': retired['handoffs']['research']}
    data.update(state='RESEARCHING', config=None, asset_strategy='reference-first', repairs={}, route_runs={
        route: {'status': 'PENDING', 'outputs': {}} for route in data['requested_routes']})
    draft = retired['handoffs'].get('diagnostic-animatic')
    history.append(dict(outcome=outcome, story_id=story_id,
                        review=retired['handoffs'][name], retired=retired,
                        media_sha256=[verdict['evidence']['media_sha256']],
                        draft=draft,
                        stage_offset=len(data['stages'])))


def prepare_handoff(task, envelope):
    """Recover a sealed orphan or reserve the next unused immutable version."""
    folder = Path(task) / 'handoffs'
    while True:
        name, version = envelope['name'], envelope['version']
        path = folder / f'{name}.v{version}.json'
        expected = dict(envelope, sha256=digest(envelope))
        if not path.exists() and not path.is_symlink():
            write(path, expected)
            return path, expected, False
        if path.is_symlink() or not path.is_file():
            raise ValueError(f'Invalid immutable handoff path: {path}')
        try:
            existing = json.loads(path.read_text())
        except (UnicodeError, json.JSONDecodeError) as error:
            raise ValueError(f'Invalid orphan handoff; preserved at {path}') from error
        if (not isinstance(existing, dict) or existing.get('schema_version') != 1
                or existing.get('name') != name or type(existing.get('version')) is not int
                or existing['version'] != version
                or not isinstance(existing.get('role'), str)
                or not isinstance(existing.get('dependencies'), dict)
                or not isinstance(existing.get('payload'), dict)
                or not isinstance(existing.get('visual_evidence'), dict)
                or not isinstance(existing['visual_evidence'].get('images'), list)
                or any(not isinstance(image, dict) for image in existing['visual_evidence']['images'])
                or existing.get('sha256') != digest({k: v for k, v in existing.items() if k != 'sha256'})):
            raise ValueError(f'Invalid orphan handoff identity or hash; preserved at {path}')
        if handoff_identity(existing) == handoff_identity(expected):
            return path, existing, True
        envelope['version'] += 1


def handoff_identity(envelope):
    content = {key: value for key, value in envelope.items() if key != 'sha256'}
    visuals = content['visual_evidence']
    # Preparation time and cache telemetry can change during a retry.
    content['visual_evidence'] = dict(visuals, images=[
        {key: value for key, value in image.items() if key not in {'elapsed_seconds', 'cache_hit'}}
        for image in visuals['images']
    ])
    return digest(content)


def put_handoff(task, role, name, payload, dependencies=None):
    if not isinstance(payload, dict):
        raise ValueError('Handoff payload must be an object')
    with lock(Path(task) / '.ledger.lock', wait=True):
        data = load(task)
        if name in SOURCE_HANDOFFS:
            source_policy.validate_sources(payload, policy=data)
        competition = editorial_policy.enabled(data)
        directed = producer_directed(data)
        development = story_development(data)
        flexible = flexible_story(data)
        if not development and name in {'story-treatment', 'story-qa'}:
            raise ValueError('This handoff requires the Story Development policy')
        directed_references = directed and (
            data.get('reference_search_plan') or
            (flexible and (name == 'viral-analysis' or
                           name == 'creative-blueprint' and payload.get('reference_principles'))))
        producer_work = role == 'Producer' and (
            ((competition or directed) and name == 'research') or (directed and name == 'script')
            or (directed_references and name == 'viral-analysis'))
        if ((name not in ROLES.get(role, set()) and not producer_work)
                or ((directed_references or flexible) and name == 'creative-blueprint' and role != 'Producer')):
            raise ValueError('Role does not own this artifact')
        deps = {}
        for dep in dependencies or []:
            artifact(task, dep)
            deps[dep] = data['handoffs'][dep]['sha256']
        v2 = protocol_version(data) == 2
        from .production_contract import (NATURAL_SCIENCE, PRESENTATION_STYLE, validate_audience_copy,
                                          creative_first, science_story, validate_audience_decision)
        story = science_story(data)
        history = data.get('creative_history', [])
        if competition and name in {'creative-blueprint', 'asset-plan', 'cad-model'}:
            require_visual_story_review(task)
        if competition and name == 'diagnostic-animatic':
            state = data.get('repair_return_state') if data['state'] == 'REPAIRING' else data['state']
            if state != 'RESEARCHING':
                raise ValueError('Moving story drafts must be registered during research')
        if name == 'creative-blueprint' and role == 'Producer' and not story:
            raise ValueError('Producer Blueprint ownership requires the science-story contract')
        from . import director_audio
        if name == 'creative-blueprint' and director_audio.policy(data) != director_audio.policy(payload):
            raise ValueError('Blueprint music direction policy differs from the task')
        if name == 'story-treatment' and director_audio.enabled(data):
            payload = dict(payload, audio_intent=director_audio.story_intent(
                payload, bgm=director_audio.default_bgm(data)))
        if name == 'animatic-manifest' and role == 'Editor' and not story:
            raise ValueError('Editor animatic ownership requires the science-story contract')
        if name == 'creative-blueprint' and data.get(PRESENTATION_STYLE) == NATURAL_SCIENCE:
            for shot in payload.get('shots', []):
                validate_audience_copy(shot, creative=creative_first(data))
        from .production_contract import (enabled as science_contract, discovery, selected_story,
                                          version as contract_version, validate_research as validate_science)
        if science_contract(data):
            if name in {'research', 'creative-blueprint'} and (
                    producer_directed(payload) != directed
                    or skill_driven(payload) != skill_driven(data)
                    or payload.get(STORY_DEVELOPMENT, 0) != data.get(STORY_DEVELOPMENT, 0)):
                raise ValueError('Handoff production method differs from task creation policy')
            if name in {'research', 'creative-blueprint'} and directed_story(data) != directed_story(payload):
                raise ValueError('Handoff Producer direction differs from task creation policy')
            if name == 'research':
                match_mechanical_scope(data, payload, payload.get('science', {}).get('question'))
                if data.get('requested_product_model') and (
                        payload.get('product_identity', {}).get('model') != data['requested_product_model']):
                    raise ValueError('Research must use the locked product model')
                if discovery(data) and contract_version(payload) != contract_version(data):
                    raise ValueError('Research must use the task discovery policy')
                if creative_first(data) and not directed and not (competition and
                        payload.get('story_exploration', {}).get('selected_id') is None):
                    validate_audience_decision(payload.get('audience_decision'), creative=True, story=story)
                validate_science(payload)
                from . import director
                if director.enabled(data):
                    chosen = director.validate_treatments(payload.get('director'))
                    if chosen['question'] != payload.get('audience_decision', {}).get('question'):
                        raise ValueError('Creative treatment must use the chosen audience question')
                if competition:
                    previous = artifact(task, 'research') if 'research' in data['handoffs'] else None
                    editorial_policy.validate_competition(payload, previous, history)
                if not competition or payload['story_exploration']['phase'] == 'DECISION':
                    data['subject_kind'] = payload['science']['subject_kind']
            if name == 'creative-blueprint':
                match_mechanical_scope(data, payload, payload.get('narrative', {}).get('question'))
                if payload.get(FORMAL_DURATION_FIELD) != data.get(FORMAL_DURATION_FIELD):
                    raise ValueError('Blueprint formal duration policy differs from task')
                require_visual_story_review(task)
                from .production_contract import validate_direction
                from . import joint_timeline as joint
                from . import director
                if director.enabled(data) != director.enabled(payload):
                    raise ValueError('Blueprint creative direction differs from task creation policy')
                director.validate(payload)
                if director.enabled(data) and payload['director'] != artifact(task, 'research')['director']:
                    raise ValueError('Update the research handoff before changing the selected treatment')
                if joint.enabled(data):
                    if joint.integrity(data) != joint.integrity(payload['timeline']):
                        raise ValueError('Blueprint joint timeline differs from the task film integrity policy')
                    joint.validate(payload['timeline'], payload.get('shots'))
                    validate_formal_duration(data, payload['timeline']['frame_count'] / joint.FPS)
                    measured = joint.receipt(payload['timeline'], payload['measured_timeline'])
                    director.validate_measured_edit(payload, measured)
                    if pacing.enabled(data):
                        director.validate_pacing(payload, artifact(task, 'research'))
                validate_direction(payload, artifact(task, 'research'))
                if development:
                    treatment = artifact(task, 'story-treatment')
                    if payload['narrative']['question'] != treatment['question']:
                        raise ValueError('Formal Blueprint must follow the approved Treatment question')
                    if formal_duration_enabled(data) and payload.get('growth_design') != treatment['growth_design']:
                        raise ValueError('Blueprint must carry the five approved growth decisions')
                    if pacing.enabled(data) and payload.get('pacing_brief') != treatment['pacing_brief']:
                        raise ValueError('Blueprint must carry the approved pacing brief')
                    if mechanism_first(data) and data.get('reference_search_plan'):
                        from .viral import reference_shot_map
                        reference_shot_map(treatment, payload)
        required = (V2_DEPENDENCIES if v2 else LEGACY_DEPENDENCIES).get(name, set())
        if story and name == 'creative-blueprint':
            required = {'diagnostic-animatic'}
        if story and name in {'diagnostic-animatic', 'asset-plan'}:
            required = {'research'} if name == 'diagnostic-animatic' else {'research', 'diagnostic-animatic'}
        if directed and name in {'asset-plan', 'creative-blueprint', 'animation-manifest'}:
            required = required - {'diagnostic-animatic', 'animatic-manifest', 'animatic-qa'}
        if directed_references and name == 'creative-blueprint':
            required = required | {'viral-analysis'}
        technical_handoff = v2 and name in {'animation-manifest', 'timeline'} and require_source_supported_render(task)
        if technical_handoff:
            # These are technical-media handoffs, not fabricated perceptual QA.
            required = ({'research', 'asset-plan', 'cad-model', 'mechanical-diagnostics'}
                        if name == 'animation-manifest' else
                        {'research', 'animation-manifest', 'audio-preparation'})
            config_path = Path(data['config'])
            config = json.loads(config_path.read_text())
            if (data.get('shot_production') and config.get('production_scope') == 'source-supported-film'
                    and config.get('shot_evidence_version') == 1):
                binding = payload.get('config') or {}
                config_matches = (Path(binding.get('path', '')).resolve() == config_path.resolve()
                                  and binding.get('sha256') == filehash(config_path))
            else:
                config_matches = payload.get('config') == data['reference_remake']['production_binding']['config']
            if not config_matches:
                raise ValueError('Technical media handoff requires the exact current film config')
            check_media(payload.get('media'))
        if data.get('reference_policy_version') == 1:
            if name == 'creative-blueprint':
                required = required | {'research', 'asset-plan'}
            elif name == 'content-qa':
                required = {'creative-blueprint', 'research', 'asset-plan'}
                if reference_model_required(data):
                    required.add('reference-model-qa')
        if competition and name in {'asset-plan', 'creative-blueprint'}:
            required = required | {'diagnostic-qa'}
        if development:
            if name == 'story-treatment':
                required = {'research'}
                if mechanism_first(data) and data.get('reference_search_plan'):
                    required.add('viral-analysis')
            elif name == 'story-qa':
                required = {'story-treatment'}
            elif name == 'diagnostic-animatic':
                required = {'research', 'story-treatment', 'story-qa'}
            elif name in {'asset-plan', 'cad-model', 'creative-blueprint'}:
                require_visual_story_review(task)
                required = required | {'diagnostic-qa'}
        if not v2 and name in {'viral-analysis', 'creative-blueprint', 'feasibility',
                               'animatic-manifest', 'animatic-qa',
                               'diagnostic-animatic', 'diagnostic-qa'}:
            raise ValueError('Artifact requires production protocol_version=2')
        if not required <= set(deps):
            raise ValueError('Required dependencies: ' + ', '.join(sorted(required)))
        if set(deps) != required:
            raise ValueError('Only declared DAG dependencies allowed')
        if development:
            validate_development_handoff(Path(task), data, name, payload)
            if name == 'diagnostic-animatic':
                payload = dict(payload, story_content_sha256=digest(
                    treatment_content(artifact(task, 'story-treatment'))))
        if (v2 and name in {'cad-model', 'asset-plan'}
                and data.get('autonomy_policy', {}).get('reference_first')):
            from .viral import validate_viral_analysis
            reference = artifact(task, 'viral-analysis')
            validate_viral_analysis(reference)
            check_research_binding(data, reference)
        if directed_references and name == 'viral-analysis':
            from .viral import validate_directed_analysis
            check_research_binding(data, payload)
            new_reference_path = mechanism_first(data) and bool(data.get('reference_search_plan'))
            validate_directed_analysis(payload, require_techniques=directed_story(data) or new_reference_path,
                                       require_attempts=new_reference_path)
        elif v2 and name in {'viral-analysis', 'creative-blueprint'}:
            from .viral import validate_viral_analysis, validate_creative_blueprint
            (validate_viral_analysis if name == 'viral-analysis'
             else validate_creative_blueprint)(payload)
            if name == 'viral-analysis' and data.get('production_method') == 'reference-recreation':
                check_research_binding(data, payload)
            if name == 'creative-blueprint':
                if directed_references:
                    analysis = artifact(task, 'viral-analysis')
                    selected = set(analysis['selected_ids'])
                    used = {item['reference_id'] for item in payload.get('reference_principles', [])}
                    if used - selected or (selected and not used):
                        raise ValueError('Blueprint must adapt the selected observations in its shots')
                    if directed_story(data):
                        from .viral import match_reference_techniques
                        match_reference_techniques(payload, analysis)
                if data.get('content_policy_version') == 1:
                    from .growth import validate_contract
                    if payload.get('content_policy_version') != 1:
                        raise ValueError('New task requires content_policy_version=1 blueprint')
                    if payload.get('duration_policy_override') != data.get('duration_policy_override'):
                        raise ValueError('Blueprint duration override differs from task authorization')
                    validate_contract(payload, data.get('duration'))
                if not story:
                    selected = set(artifact(task, 'viral-analysis').get('selected_ids', []))
                    used = {item.get('reference_id') for item in payload.get('reference_principles', [])}
                    if not used or not used <= selected:
                        raise ValueError('Blueprint principles must bind selected observed references')
                if data.get('production_method') == 'reference-recreation':
                    check_recreation(task, payload)
        if data.get("reference_policy_version") == 1:
            from . import reference_policy as rp
            from . import visual_narrative as visual
            if name == 'asset-plan':
                from .media_policy import enabled as asset_first
                if asset_first(data) != asset_first(payload):
                    raise ValueError('Asset plan media policy differs from task creation policy')
                if story and (not science_story(payload) or
                              (discovery(data) and contract_version(payload) != contract_version(data))):
                    raise ValueError('Science-story asset plan must declare the current contract')
            if visual.version(data) == visual.VERSION:
                if name == 'research':
                    if not discovery(data):
                        visual.validate_research(payload)
                    from .knowledge_progression import FIELD, enabled
                    plan = {'shots': payload.get('visual_plan', [])}
                    from .media_policy import enabled as asset_first
                    if asset_first(data):
                        plan.update(visual_policy_version=2, media_policy_version=1)
                    if enabled(data):
                        plan[FIELD] = data[FIELD]
                    # New science research precedes asset matching and measured
                    # timing. Its provisional visual ideas are not an executable
                    # frozen plan. Validate the complete plan at Blueprint handoff.
                    if not science_contract(data):
                        visual.validate_plan(plan)
                if name == 'creative-blueprint':
                    visual.match_policy(data, payload)
                    visual.validate_plan(payload)
            if name == "research":
                if not competition or selected_story(payload, allow_unselected=True) is not None:
                    rp.validate_research(payload, policy=data)
                    from .comprehension import enabled, validate_product_research
                    if enabled(data) or (source_policy.enabled(data) and mechanism_first(data)):
                        validate_product_research(payload, policy=data)
            elif name == 'cad-model':
                research = artifact(task, 'research')
                from .comprehension import enabled, validate_product_research
                if enabled(data) or (source_policy.enabled(data) and mechanism_first(data)):
                    validate_product_research(research, policy=data)
                chosen = artifact(task, 'asset-plan')
                rp.validate_asset(research, chosen, policy=data)
                if chosen['strategy'] != 'autonomous-cad':
                    raise ValueError('New CAD requires prior evidence-based asset selection')
                if source_policy.enabled(data):
                    candidate = next(row for row in chosen['candidates']
                                     if row['id'] == chosen['selected_candidate_id'])
                    if source_policy.require_source_ids(payload, candidate['source_ids'], 'CAD inputs') != set(candidate['source_ids']):
                        raise ValueError('CAD source lineage differs from the selected asset')
            elif name == "asset-plan":
                research = artifact(task, 'research')
                from .comprehension import enabled, validate_product_research
                if enabled(data) or (source_policy.enabled(data) and mechanism_first(data)):
                    validate_product_research(research, policy=data)
                rp.validate_asset(research, payload, policy=data)
            elif name == "creative-blueprint":
                from .comprehension import enabled, validate_product_plan
                if enabled(data):
                    if payload.get('product_policy_version') != 1:
                        raise ValueError('Current blueprint requires product_policy_version=1')
                    validate_product_plan(payload, artifact(task, 'research'))
                if data.get('growth_policy_version') == 2 and payload.get('growth_policy_version') != 2:
                    raise ValueError('Current blueprint requires growth_policy_version=2')
                if payload.get('reference_policy_version') != 1:
                    raise ValueError('New blueprint requires reference_policy_version=1')
                rp.validate_plan(payload, artifact(task, "research"), artifact(task, "asset-plan"), policy=data)
                if directed:
                    requested = data.get('duration')
                    if requested is not None and abs(payload['duration_seconds'] - requested) > 1 / 30:
                        raise ValueError('Blueprint differs from requested duration')
                    config_binding = payload.get('production_config', {})
                    config_path = (ROOT / config_binding.get('path', '')).resolve()
                    if not config_path.is_file() or filehash(config_path) != config_binding.get('sha256'):
                        raise ValueError('Blueprint must bind the compiled config')
                    cfg = json.loads(config_path.read_text())
                    if source_policy.enabled(data):
                        validate_production_sources(task, cfg, policy=data, require_reveal=True)
                    visual.match_policy(data, cfg)
                    visual.match_blueprint(payload, cfg)
                    if cfg.get('blueprint_program_sha256') != digest({
                            key: value for key, value in payload.items() if key != 'production_config'}):
                        raise ValueError('Production config was not compiled from this exact frozen Blueprint')
            elif name == "content-qa":
                blueprint = artifact(task, 'creative-blueprint')
                rp.validate_preproduction(blueprint, artifact(task, "research"), artifact(task, "asset-plan"), payload)
                if reference_model_required(data):
                    rp.validate_reference_model(artifact(task, 'reference-model-qa'), artifact(task, 'research')['mechanism_id'])
                reviewer = payload.get("reviewer_thread_id")
                if not reviewer or reviewer in {r["thread_id"] for r in data["agent_runs"] if r["role"] != "QA"}:
                    raise ValueError("Independent content QA reviewer required")
            elif name == "final-qa" and payload.get('checks') and all(
                    value == 'PASS' for value in payload['checks'].values()):
                rp.validate_final_report(payload.get("reference_report", {}), payload.get("media", []))
        if v2 and name == 'feasibility':
            checks = payload.get('checks', {})
            if not production_checks(checks, FEASIBILITY_CHECKS):
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
            draft_plan = json.loads(blueprint_path.read_text())
            if not isinstance(draft_plan, dict):
                raise ValueError('Diagnostic blueprint JSON must be an object')
            if discovery(data) and not directed and draft_plan.get('story_id') != selected_story(artifact(task, 'research'))['id']:
                raise ValueError('Moving draft must address the selected research story')
            from .visual_narrative import scene_direction_enabled, validate_scene_direction
            if scene_direction_enabled(data):
                validate_scene_direction(draft_plan, payload['media'])
            if flexible:
                from .blueprint import validate_story_preview
                treatment = artifact(task, 'story-treatment') if mechanism_first(data) else None
                validate_story_preview(draft_plan, payload['media'], treatment=treatment, task=data)
                if mechanism_first(data) and data.get('reference_search_plan'):
                    from .viral import reference_shot_map
                    reference_shot_map(treatment, draft_plan)
                if pacing.enabled(data):
                    from . import joint_timeline as joint
                    film = next(row for row in payload['media'] if Path(row['path']).suffix.lower() == '.mp4')
                    plan = draft_plan['timeline']
                    measured = joint.receipt(plan, draft_plan['measured_timeline'])
                    inputs = {'blueprint': evidence, 'measured_timeline': draft_plan['measured_timeline']}
                    states = []
                    if 'pacing_states' in draft_plan:
                        inputs['state_manifest'] = draft_plan['pacing_states']
                        states = pacing.load_states(inputs['state_manifest'])
                    payload = dict(payload, pacing_review=pacing.analyze(
                        joint.binding(film['path']), plan, draft_plan['pacing'], measured=measured,
                        inputs=inputs, states=states))
            if competition:
                if any(row['outcome'] == 'RESELECT_STORY' and row['story_id'] == draft_plan['story_id']
                       for row in history):
                    raise ValueError('A vetoed story needs reselection before another moving draft')
                previous_plan = None
                if history and history[-1]['draft']:
                    prior = json.loads((Path(task) / history[-1]['draft']['path']).read_text())
                    if digest({k:v for k,v in prior.items() if k != 'sha256'}) != history[-1]['draft']['sha256']:
                        raise ValueError('Previous creative draft handoff changed')
                    evidence = prior['payload']['blueprint_evidence']
                    if filehash(evidence['path']) != evidence['sha256']:
                        raise ValueError('Previous creative draft plan changed')
                    previous_plan = json.loads(Path(evidence['path']).read_text())
                editorial_policy.validate_revision(draft_plan, payload['media'], history, previous_plan)
            if story:
                from scripts.common import probe
                for item in payload['media']:
                    if Path(item['path']).suffix.lower() == '.mp4' and not any(
                            stream['codec_type'] == 'video' for stream in probe(item['path'])['streams']):
                        raise ValueError('Creative draft MP4 needs a picture track')
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
            from .visual_narrative import scene_direction_enabled, validate_scene_review
            if scene_direction_enabled(data) or (flexible and not development):
                validate_scene_review(payload.get('visual_story_review', {}))
        if v2 and name == 'animation-manifest':
            require_animatic(task)
        verdict = None
        if competition and name in editorial_policy.REVIEW_INPUTS:
            from scripts.common import probe
            check_media(payload.get('media'))
            production = artifact(task, editorial_policy.REVIEW_INPUTS[name])
            check_media(production.get('media'))
            durations = {row['sha256']: float(probe(row['path'])['format']['duration'])
                         for row in production['media'] if Path(row['path']).suffix.lower() == '.mp4'}
            verdict = editorial_policy.validate_review(data, payload, production, durations,
                                                       selected_story(artifact(task, 'research'))['id'])
            if name == 'diagnostic-qa' and (verdict['outcome'] == 'PASS') != (
                    payload['visual_story_review']['status'] == 'PASS'):
                raise ValueError('Picture review and creative decision must agree on PASS')
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
        if name == 'final-qa':
            if any(key in payload for key in ('audio_acceptance_mode', 'audio_technical_status',
                                               'audio_technical_evidence')):
                raise ValueError('Final audio acceptance evidence is generated by the workflow')
            from .audio_acceptance import MODE, verify
            if director_audio.enabled(data):
                from .audio_acceptance import music_review
                film = artifact(task, 'timeline')
                try:
                    evidence = verify(film, artifact(task, 'creative-blueprint'))
                except (OSError, ValueError, RuntimeError, KeyError, TypeError,
                        EOFError, wave.Error, subprocess.SubprocessError) as error:
                    payload.update(audio_technical_status='FAIL', audio_technical_evidence={'reason': str(error)})
                else:
                    payload.update(audio_technical_status='PASS', audio_technical_evidence=evidence)
                mix_check = payload['audio_technical_evidence'].get('mix_check', {})
                require_continuity = bool(mix_check.get('ducking') or mix_check.get('constant_bed_calibration')
                                          or director_audio.fixed_bed(data) and mix_check.get('music_status') == 'READY')
                payload = dict(payload, audio_perceptual_review=music_review(
                    payload, film['media'], require_continuity=require_continuity,
                    require_audibility=((director_audio.contextual_bed(data) or director_audio.fixed_bed(data))
                                        and mix_check.get('music_status') != 'SILENCE_DESIGNED')))
            elif directed and data.get('audio_acceptance_policy') == MODE and payload.get('full_audio_listened') is not True:
                if payload.get('audio_perceptual_review', 'NOT_PERFORMED') != 'NOT_PERFORMED':
                    raise ValueError('Record actual listening results only with the corresponding observations')
                payload = dict(payload, audio_acceptance_mode=MODE, audio_perceptual_review='NOT_PERFORMED')
                try:
                    evidence = verify(artifact(task, 'timeline'), artifact(task, 'creative-blueprint'))
                except (OSError, ValueError, RuntimeError, KeyError, TypeError,
                        EOFError, wave.Error, subprocess.SubprocessError) as error:
                    payload.update(audio_technical_status='FAIL', audio_technical_evidence={'reason': str(error)})
                else:
                    payload.update(audio_technical_status='PASS', audio_technical_evidence=evidence)
        if data.get(video_review.FIELD) and name in {'animation-manifest', 'timeline'}:
            if 'video_review' in payload:
                raise ValueError('Video Review evidence is generated by the workflow')
            films = [row for row in payload.get('media', []) if Path(row['path']).suffix.lower() == '.mp4']
            if len(films) != 1:
                raise ValueError('Video Review requires one complete production MP4')
            config_path = Path(data['config'])
            report = video_review.for_composition(
                films[0], artifact(task, 'creative-blueprint'), artifact(task, 'research'),
                json.loads(config_path.read_text()), ROOT / 'remotion/public')
            payload = dict(payload, video_review=report)
        from .qa_images import handoff_visuals
        visual_evidence = handoff_visuals(payload)
        versions = data.setdefault('creative_handoff_versions', {}) if competition else {}
        version = versions.get(name, data['handoffs'].get(name, {}).get('version', 0)) + 1
        envelope = dict(schema_version=1, role=role, name=name, version=version,
                        dependencies=deps, payload=payload, visual_evidence=visual_evidence)
        if competition and name == 'research' and 'research' in data['handoffs']:
            envelope['previous_research'] = dict(data['handoffs']['research'])
        path, envelope, recovered = prepare_handoff(task, envelope)
        version = envelope['version']
        path = str(path.relative_to(task))
        if data.get('reference_policy_version') == 1 and name == 'asset-plan':
            data['asset_strategy'] = payload['strategy']
        if directed and name == 'creative-blueprint':
            if not data.get('config') or Path(data['config']) != config_path:
                data['route_runs']['3d'] = {'status': 'PENDING', 'outputs': {}}
            data['config'] = str(config_path)
            data['shared_production'].update(timeline=payload['measured_timeline'],
                                             narration=measured['narration_audio'])
        data['handoffs'][name] = dict(path=path, version=version, sha256=envelope['sha256'])
        if competition:
            versions[name] = version
        if verdict and verdict['outcome'] in editorial_policy.STORY_FAILURE:
            retire_creative_direction(data, name, verdict)
        # Journal the sealed version before moving the ledger pointer. If a
        # retry is needed the recovery event shares the same immutable hash.
        event(task, 'handoff', role=role, name=name, version=version,
              sha256=envelope['sha256'], recovered=recovered)
        write(Path(task) / 'task.json', data)
    continuation(task)
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
        if path.suffix.lower() not in {'.mp4', '.png', '.wav', '.jpg', '.jpeg', '.webp', '.m4a'}:
            raise ValueError('Evidence must reference media, not a log')
        if not path.is_file() or filehash(path) != item['sha256']:
            raise ValueError('Media evidence missing or changed')


def technical_audio_review(data, report):
    from .audio_acceptance import MODE
    return (producer_directed(data) and data.get('audio_acceptance_policy') == MODE
            and report.get('audio_acceptance_mode') == MODE)


def check_qa(task, name, *, acceptance=True):
    if name not in {'preview-qa', 'animatic-qa', 'final-qa'}:
        raise ValueError('Diagnostic reports cannot grant production acceptance')
    data = load(task)
    if story_development(data) and name in {'preview-qa', 'final-qa'}:
        require_visual_story_review(task)
    elif skill_driven(data) and name in {'preview-qa', 'final-qa'}:
        draft = artifact(task, 'diagnostic-qa')
        if draft['visual_story_review']['status'] != 'PASS':
            raise ValueError('Independent review of the current story preview must pass before HD')
    if data.get(video_review.FIELD) and name in {'preview-qa', 'final-qa'}:
        production_name = 'animation-manifest' if name == 'preview-qa' else 'timeline'
        production = artifact(task, production_name)
        video_review.require_current(production, pacing_required=pacing.enabled(data))
    directed = producer_directed(data)
    # A Producer preview is a working edit. Final QA reviews the complete film.
    workprint_review = name == 'preview-qa' and directed_story(data)
    if directed and name == 'preview-qa' and not workprint_review and name not in data['handoffs']:
        return None
    if workprint_review:
        acceptance = False
    qa = artifact(task, name)
    technical_audio = name == 'final-qa' and technical_audio_review(data, qa)
    if name == 'final-qa' and acceptance and any(
            issue.get('requires_audio_review') is True and issue.get('status') != 'RESOLVED'
            for issue in qa.get('issues', [])):
        raise ValueError('Unresolved audio issue requires targeted review')
    if editorial_policy.enabled(load(task)) and qa['story_review']['outcome'] != 'PASS':
        raise ValueError('The current moving edit requires an independent creative PASS')
    from .comprehension import enabled, validate_media_qa
    if acceptance and enabled(load(task)):
        review = dict(qa)
        review['production_thread_ids'] = [r['thread_id'] for r in load(task).get('agent_runs', [])
                                          if r['role'] != 'QA']
        validate_media_qa(artifact(task, 'creative-blueprint'), review)
    if name == 'final-qa' and data.get('reference_policy_version') == 1:
        from .reference_policy import validate_final_report
        validate_final_report(qa.get('reference_report', {}), qa.get('media', []))
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
    from . import director_audio
    if name == 'final-qa' and acceptance and director_audio.enabled(data):
        from .audio_acceptance import check_evidence, music_review
        films = [row for row in production['media'] if Path(row['path']).suffix.lower() == '.mp4']
        check_evidence(qa, films, require_music=True)
        mix_check = qa['audio_technical_evidence']['mix_check']
        require_continuity = bool(mix_check.get('ducking') or mix_check.get('constant_bed_calibration')
                                  or director_audio.fixed_bed(data) and mix_check['music_status'] == 'READY')
        if music_review(qa, films, require_continuity=require_continuity,
                        require_audibility=((director_audio.contextual_bed(data) or director_audio.fixed_bed(data))
                                            and mix_check['music_status'] == 'READY')) != 'PASS':
            raise ValueError('Final music and mechanical sound require full independent listening on the exact MP4')
    if mechanism_first(data) and name in {'preview-qa', 'final-qa'}:
        video_review.require_mechanical_positioning(data, qa, production)
    if pacing.enabled(data) and name in {'preview-qa', 'final-qa'}:
        if pacing.review_status(production['video_review']['pacing'], qa) != 'PASS':
            raise ValueError('Independent pacing review requires full timed picture and sound observations')
    from . import joint_timeline as joint
    if joint.integrity(data) and name in {'preview-qa', 'final-qa'}:
        blueprint = artifact(task, 'creative-blueprint')
        if not data.get(video_review.FIELD):
            plan = blueprint['timeline']
            measured = joint.receipt(plan, blueprint['measured_timeline'])
            config = read_input_json(data['config'])
            mix = config.get('audio_mix')
            playback = None
            if mix:
                from .audio_acceptance import verify_mix
                playback, _ = verify_mix(mix, joint.bound(measured['narration_audio']),
                                         plan['frame_count'] * joint.SAMPLES_PER_FRAME, check_masking=False)
            for path, _ in expected:
                joint.validate_rendered_film(path, plan)
                joint.validate_rendered_audio(path, plan, measured, playback, mix=bool(mix))
    from .production_contract import creative_first, science_story, validate_creative_review
    if workprint_review:
        if len(expected) != 1:
            raise ValueError('Workprint review requires the complete edited MP4')
        path, sha = next(iter(expected))
        preview = next(row for row in production['media'] if row['sha256'] == sha
                       and str(Path(row['path']).resolve()) == path)
        durations = {sha: complete_media(data, preview, final=False)['duration']}
        validate_creative_review(qa, durations, acceptance=False, whole_edit=True)
        from .viral import validate_reference_effects
        effects = validate_reference_effects(artifact(task, 'creative-blueprint'), qa, sha)
        if mechanism_first(data) and data.get('reference_search_plan') and 'FAIL' in effects:
            raise ValueError('Repair the failed reference effects on the current workprint')
        from . import director
        if director.enabled(data):
            blueprint = artifact(task, 'creative-blueprint')
            director.preview_evidence(path, blueprint['timeline'], [
                shot['shot_id'] for shot in blueprint['shots'] if shot['mechanical_role'] == 'core'])
            if any(row['status'] == 'FAIL' for row in qa['creative_review'].values()):
                raise ValueError('Repair the failed creative workprint before final rendering')
        if joint.integrity(data):
            from .audio_acceptance import MODE
            from .production_contract import validate_review_observations
            review = dict(qa, production_thread_ids=[r['thread_id'] for r in data['agent_runs'] if r['role'] != 'QA'])
            preview_technical = (data.get('audio_acceptance_policy') == MODE
                                 and qa.get('checks', {}).get('listening') in (None, 'UNKNOWN'))
            validate_review_observations(review, [preview], blueprint, technical_audio=preview_technical, workprint=True)
    if not directed and name in {'animatic-qa', 'final-qa'} and creative_first(data):
        from scripts.common import probe
        durations = {digest: float(probe(path)['format']['duration']) for path, digest in expected}
        story_gate = science_story(load(task)) and name == 'animatic-qa'
        validate_creative_review(qa, durations, acceptance=acceptance or story_gate, whole_edit=story_gate)
    from .production_contract import enabled as science_contract, validate_qa as science_qa
    if science_contract(load(task)) and name == 'final-qa':
        film = [row for row in production['media'] if Path(row['path']).suffix.lower() == '.mp4']
        science_qa(qa, film if technical_audio else production['media'], acceptance=acceptance,
                   blueprint=artifact(task, 'creative-blueprint') if acceptance else None,
                   technical_audio=technical_audio)
        request=load(task).get('revision_request')
        if request and acceptance:
            from .media_revision import revision_claims, validate_report
            for path,sha in expected:
                latest=next((r for r in reversed(load(task)['stages'])
                             if r.get('media',{}).get('sha256')==sha and r.get('revision')),None)
                if latest is None:
                    raise ValueError('An improvement claim requires actual decoded revision evidence')
                ref=latest['revision']
                if filehash(ref['path']) != ref['sha256']:
                    raise ValueError('Revision evidence changed')
                revision_report=read_input_json(ref['path'])
                claimed=revision_claims(revision_report.get('changes', []))
                if claimed != request.get('changes'):
                    raise ValueError('Revision evidence must address the declared defect intervals')
                validate_report(revision_report,path)
    from .media_policy import enabled as asset_first, validate_qa as validate_hybrid_qa, binding as media_binding
    if asset_first(load(task)) and name == 'final-qa':
        task_data = load(task)
        original_inputs = {key: media_binding(Path(task)/task_data['handoffs'][handoff]['path'])
                           for key,handoff in (('research','research'),('script','script'),('blueprint','creative-blueprint'))}
        for path, _ in expected:
            validate_hybrid_qa(qa, Path(path).with_suffix('.media-provenance.json'), acceptance=acceptance,
                               original_inputs=original_inputs, technical_audio=technical_audio)
        production_threads = {r['thread_id'] for r in task_data['agent_runs'] if r['role'] != 'QA'}
        if any(qa[section]['reviewer_thread_id'] in production_threads for section in
               ('copyright_review','original_expression_review')):
            raise ValueError('Copyright and original expression reviewers must be independent of production')
    from . import visual_narrative as visual
    if visual.version(data) == visual.VERSION and not directed:
        blueprint = artifact(task, 'creative-blueprint')
        visual.validate_review(qa.get('visual_checks'), [s['shot_id'] for s in blueprint['shots']],
                               acceptance=acceptance)
        from .knowledge_progression import enabled, validate_media_evidence
        if enabled(blueprint):
            validate_media_evidence(blueprint, qa, {sha: path for path, sha in expected}, acceptance=acceptance)
    if load(task).get('content_policy_version') == 1:
        from .growth import validate_media_checks, check_media_duration
        blueprint = artifact(task, 'creative-blueprint')
        if acceptance:
            validate_media_checks(blueprint, qa)
        check_media_duration(blueprint, production['media'])
    checks = qa.get('checks', {})
    required_checks = ANIMATIC_CHECKS if name == 'animatic-qa' else QA_CHECKS
    from .audio_acceptance import MODE
    pending_preview_audio = (name == 'preview-qa' and directed and data.get('audio_acceptance_policy') == MODE
                             and checks.get('listening') in (None, 'UNKNOWN'))
    if technical_audio or pending_preview_audio:
        # Final audio evidence is evaluated on the delivered MP4, after the optional preview.
        required_checks = required_checks - {'listening'}
        checks = {key: value for key, value in checks.items() if key != 'listening'}
    if (not required_checks <= set(checks) or
            (any(value != 'PASS' for value in checks.values()) if acceptance
             else not production_checks(checks, required_checks,
                 perceptual_extra={'blueprint_fidelity'} if science_contract(load(task)) else ()))):
        raise ValueError('QA FAIL/UNKNOWN or missing checks prevents advancement')
    if not qa.get('independent_reviewer') or not qa.get('reviewer_thread_id'):
        raise ValueError('Independent reviewer identity is required')
    if qa['reviewer_thread_id'] in {r['thread_id'] for r in load(task)['agent_runs']
            if r['role'] in {'Research', 'MechanicalResearch', 'CAD', 'ViralResearch', 'Producer',
                                                    'Asset', 'Animation', 'Editor'}}:
        raise ValueError('QA reviewer also produced this task')
    if any(str(i.get('severity', '')).lower() in {'critical', 'major', 'error'}
           and i.get('status') != 'RESOLVED' for i in qa.get('issues', [])):
        raise ValueError('Unresolved blocking QA defects')
    if name == 'final-qa' and acceptance:
        scoped_media = current_source_supported_film(task, data)
        if scoped_media is not None:
            require_source_supported_review(qa, scoped_media)
        else:
            for media in production['media']:
                reject_superseded_scoped_final(data, media)
    return qa


def check_asset(task):
    asset = artifact(task, 'asset-plan')
    if load(task).get('reference_policy_version') == 1:
        from .reference_policy import validate_asset
        validate_asset(artifact(task, 'research'), asset, policy=load(task))
        if asset['strategy'] == 'existing-media':
            candidate = next(c for c in asset['candidates'] if c.get('id') == asset['selected_candidate_id'])
            check_media(candidate['source_files'])
            return asset
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
    report = read_input_json(files['validation']['path'])
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
    if not production_checks(checks, MECHANICAL_CHECKS):
        raise ValueError('Mechanical FAIL/UNKNOWN or missing checks blocks production')
    reviewer = qa.get('reviewer_thread_id')
    if (qa.get('independent_reviewer') is not True or not reviewer or
            reviewer in {r['thread_id'] for r in data['agent_runs'] if r['role'] != 'QA'}):
        raise ValueError('Independent mechanical reviewer required')
    if any(i.get('severity') in {'critical', 'major', 'error'} for i in qa.get('issues', [])):
        raise ValueError('Unresolved mechanical defects block production')
    return qa


def require_reference_content(task):
    data = load(task)
    if require_source_supported_render(task):
        return
    unresolved = [r for r in data.get('content_repairs', []) if r.get('status') != 'RESOLVED']
    if unresolved:
        raise ValueError('Unresolved content defect blocks production: ' + unresolved[0]['defect_key'])
    from .comprehension import enabled, validate_product_plan
    if enabled(data):
        blueprint = artifact(task, 'creative-blueprint')
        if blueprint.get('product_policy_version') != 1:
            raise ValueError('Product recognition policy missing from current blueprint')
        validate_product_plan(blueprint, artifact(task, 'research'))
    if data.get("reference_policy_version") != 1:
        return
    from .reference_policy import validate_preproduction, validate_reference_model
    if reference_model_required(data):
        report = artifact(task, 'reference-model-qa')
        if report.get('reviewer_thread_id') in {row['thread_id'] for row in data['agent_runs'] if row['role'] != 'QA'}:
            raise ValueError('Reference-model QA reviewer must be independent of production')
        validate_reference_model(report, artifact(task, 'research')['mechanism_id'])
    return validate_preproduction(artifact(task, "creative-blueprint"),
                                 artifact(task, "research"), artifact(task, "asset-plan"),
                                 artifact(task, "content-qa"))


def require_animatic(task):
    """Check full-render prerequisites under the task's pinned workflow."""
    from .production_contract import science_story
    data = load(task)
    require_visual_story_review(task)
    require_current_scheme(data)
    if not science_story(data) and require_source_supported_render(task):
        return
    if protocol_version(data) == 1:
        return
    require_mechanical(task)
    check_production_config(task)
    feasibility = artifact(task, 'feasibility')
    checks = feasibility.get('checks', {})
    if not production_checks(checks, FEASIBILITY_CHECKS):
        raise ValueError('Feasibility requires every check PASS')
    check_asset(task)
    if producer_directed(data):
        return
    return check_qa(task, 'animatic-qa', acceptance=False)


def check_core_motion_inputs(config):
    """Catch constant data tracks before costly renders; this is not motion QA."""
    from .production_contract import enabled
    if not enabled(config):
        return
    for name, shot in config.get('shots', {}).items():
        if (shot.get('visual', {}).get('mechanical_role') != 'core'
                or shot.get('science', {}).get('driver') != 'data_tracks'):
            continue
        changed = False
        for track in shot.get('tracks', []):
            for channel in ('location', 'rotation_euler', 'rotation_quaternion', 'scale'):
                values = [pose[channel] for pose in track['poses'] if channel in pose]
                changed |= bool(values) and any(value != values[0] for value in values[1:])
        for track in shot.get('mesh_tracks', []):
            values = [pose['vertices'] for pose in track['poses']]
            changed |= bool(values) and any(value != values[0] for value in values[1:])
        if not changed:
            raise ValueError('Core shot has constant data tracks; camera motion is not mechanism motion: ' + name)


def check_production_config(task, config=None):
    """Bind approved story decisions to the actual executable config bytes."""
    data = load(task)
    require_current_scheme(data)
    if require_source_supported_render(task, config):
        return
    from .three_d import validate_config
    if config or data.get('config'):
        validate_config(read_input_json(config or data['config']))
    if protocol_version(data) == 1:
        return
    blueprint = artifact(task, 'creative-blueprint')
    require_reference_content(task)
    if data.get('content_policy_version') == 1:
        from .growth import validate_contract
        if blueprint.get('content_policy_version') != 1:
            raise ValueError('New task requires versioned growth blueprint')
        if blueprint.get('duration_policy_override') != data.get('duration_policy_override'):
            raise ValueError('Blueprint duration override differs from task authorization')
        validate_contract(blueprint, data.get('duration'))
        if data.get('growth_policy_version') == 2 and blueprint.get('growth_policy_version') != 2:
            raise ValueError('Current task requires five separately verified growth goals')
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
    compiled = read_input_json(expected)
    if source_policy.enabled(data):
        validate_production_sources(task, compiled, policy=data, require_reveal=True)
    from . import director, joint_timeline as joint
    from . import director_audio
    if not director_audio.policy(data) == director_audio.policy(blueprint) == director_audio.policy(compiled):
        raise ValueError('Executable music direction policy differs from the task')
    if director_audio.enabled(data):
        measured = joint.receipt(compiled['timeline'], compiled['measured_timeline'])
        director_audio.validate_arrangement(compiled, blueprint=blueprint, measured=measured)
    if not director.enabled(data) == director.enabled(blueprint) == director.enabled(compiled):
        raise ValueError('Executable config differs from the task creative direction policy')
    if joint.integrity(data) and (not joint.enabled(compiled) or any(
            compiled.get(field) != blueprint[field] for field in ('timeline', 'measured_timeline', 'narrative'))):
        raise ValueError('Executable config lost the frozen picture, speech or story coverage')
    from .visual_narrative import VERSION, match_blueprint, match_policy, version
    match_policy(data, blueprint)
    match_policy(data, compiled)
    if version(data) == VERSION:
        match_blueprint(blueprint, compiled)
    if data.get('reference_policy_version') == 1:
        for key in ('evidence_map', 'content_timing'):
            if compiled.get(key) != blueprint.get(key):
                raise ValueError('Executable config lost reference evidence: ' + key)
    route = compiled.get('render_route', '3d')
    reference_layers = (data.get('reference_policy_version') == 1
                        and data.get('asset_strategy') == 'existing-media'
                        and route in {'2d', '2.5d'})
    if data.get('asset_strategy') == 'illustrated' or reference_layers:
        asset = check_asset(task)
        if route != asset['render_route'] or data.get('render_route', route) != route:
            raise ValueError('Illustrated route differs from approved asset')
        sources = asset.get('source_files', [])
        if reference_layers:
            sources = next(c['source_files'] for c in asset['candidates']
                           if c.get('id') == asset['selected_candidate_id'])
        approved = {(str((ROOT / f['path']).resolve()), f['sha256']) for f in sources}
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
    check_core_motion_inputs(compiled)


def advance(task, target):
    with lock(Path(task) / '.ledger.lock'):
        data = load(task)
        require_current_scheme(data)
        current = data['state']
        if target in {'FAILED', 'BLOCKED'}:
            pass
        elif NEXT.get(current) != target:
            raise ValueError(f'Illegal transition {current} -> {target}')
        if target == 'ASSET_READY':
            if story_development(data):
                require_visual_story_review(task)
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
            if producer_directed(data):
                for preview in animation['media']:
                    complete_media(data, preview, final=False)
        if target == 'EDITING':
            check_qa(task, 'preview-qa', acceptance=False)
        if target == 'FINAL_CHECKING':
            timeline = artifact(task, 'timeline')
            check_media(timeline.get('media'))
            if data.get(video_review.FIELD):
                video_review.require_current(timeline, pacing_required=pacing.enabled(data))
            if timeline.get('technical_pass') is not True:
                raise ValueError('Technical validation missing')
        if target == 'COMPLETED':
            check_qa(task, 'preview-qa')
            review = check_qa(task, 'final-qa')
            check_requested_routes(task, data)
            reviewed_shots = review.get('shot_acceptance', {})
            for shot_id, record in data.get('shot_production', {}).items():
                if record.get('status') not in {'RENDERED', 'QA_PENDING'}:
                    continue
                scoped = reviewed_shots.get(shot_id, {})
                media = record.get('media')
                if (media and scoped.get('media') == media
                        and all(scoped.get(check) == 'PASS'
                                for check in ('scientific', 'visual', 'comprehension', 'continuous_viewing'))):
                    check_media([media])
                    record.update(status='ACCEPTED', acceptance_handoff=data['handoffs']['final-qa'])
        data['state'] = target
        write(Path(task) / 'task.json', data)
        event(task, 'state', previous=current, state=target)
    continuation(task)


def check_requested_routes(task, data):
    routes = data.get('requested_routes', [])
    scoped_media = current_source_supported_film(task, data)
    if scoped_media is not None:
        require_source_supported_review(artifact(task, 'final-qa'), scoped_media)
    if data.get('three_d_policy_version') == 1:
        if routes != ['3d']:
            raise ValueError('3D-only task route scope changed')
        from .provenance import validate as validate_provenance
        output = scoped_media or data.get('route_runs', {}).get('3d', {}).get('outputs', {})
        from .media_policy import enabled as asset_first, validate_manifest, bound
        if asset_first(data):
            manifest_path = Path(output['path']).with_suffix('.media-provenance.json')
            manifest = validate_manifest(manifest_path, output)
            proof = bound(manifest['build_proof'])
        else:
            proof = Path(task) / '3d-provenance.json'
        from .visual_narrative import VERSION, match_policy, version
        build = json.loads(proof.read_text())['build'] if proof.is_file() else {}
        match_policy(data, build)
        if version(data) == VERSION:
            config = ROOT / data['config']
            if build.get('visual_config') != read_input_json(config):
                raise ValueError('Final provenance differs from the exact approved visual config')
        validate_provenance(proof, output)
    if len(routes) <= 1 and data.get('three_d_policy_version') != 1:
        return  # Existing single-route and historical ledgers keep their gates.
    from .covers import validate as validate_covers
    from .growth_report import validate as validate_growth
    if producer_directed(data) or data.get('content_policy_version') == 1 or (Path(task)/'cover-plan.json').exists():
        validate_covers(task, require_pass=True)
        validate_growth(task)
    report = artifact(task, 'final-qa')
    if producer_directed(data):
        complete_media(data, output)
        if not any(item['sha256'] == output['sha256'] for item in report['media']):
            raise ValueError('Independent final QA must cover the registered full film')
    route_checks = report.get('route_checks', {})
    for route in routes:
        result = route_checks.get(route, {})
        media = result.get('media')
        if not media:
            raise ValueError('Missing route-specific final QA media: ' + route)
        check_media([media])
        from .comprehension import enabled, validate_media_qa
        if enabled(data):
            review = dict(result, media=[media], independent=report.get('independent'),
                          reviewer_role=report.get('reviewer_role'),
                          reviewer_thread_id=report.get('reviewer_thread_id'),
                          production_thread_ids=[r['thread_id'] for r in data.get('agent_runs', [])
                                                 if r['role'] != 'QA'])
            validate_media_qa(artifact(task, 'creative-blueprint'), review, media=[media])
        if data.get('content_policy_version') == 1:
            from .growth import validate_media_checks, check_media_duration
            blueprint = artifact(task, 'creative-blueprint')
            validate_media_checks(blueprint, dict(result, media=[media]))
            check_media_duration(blueprint, [media])
        route_checks_required = QA_CHECKS
        if technical_audio_review(data, report):
            route_checks_required = QA_CHECKS - {'listening'}
            if result.get('checks', {}).get('listening') not in (None, 'UNKNOWN'):
                raise ValueError('Technical audio acceptance cannot claim a route listening result')
        if not all(result.get('checks', {}).get(check) == 'PASS' for check in route_checks_required):
            raise ValueError('Requested route final QA has FAIL/UNKNOWN/missing checks: ' + route)
        recorded = (scoped_media if route == '3d' and scoped_media is not None
                    else data.get('route_runs', {}).get(route, {}).get('outputs', {}))
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
        from .production_contract import science_story
        if science_story(data):
            data['autonomy_policy'].update(reference_first=False, physical_reference_to_cad=False)
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
        if (editorial_policy.enabled(data) and 'diagnostic-animatic' not in data['handoffs']
                and (data.get('creative_history') or ('research' in data['handoffs'] and
                     artifact(task, 'research')['story_exploration']['selected_id'] is None))):
            raise ValueError('Return to the creative selection or moving-draft stage before shot repairs')
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


def require_hd_workprint_request(task, config, *, record=True):
    """Verify explicit native-HD candidate authorization without granting acceptance."""
    data = load(task)
    binding = data.get('hd_workprint_authorization', {})
    source = Path(binding.get('path', ''))
    if not source.is_file() or filehash(source) != binding.get('sha256'):
        raise ValueError('HD workprint requires a bound explicit user request')
    request = read_input_json(source)
    if (request.get('kind') != 'explicit-user-native-hd-candidate'
            or not request.get('user_request', '').strip()
            or request.get('formal_acceptance') is not False
            or request.get('config_sha256') != filehash(config)):
        raise ValueError('HD workprint authorization does not bind this candidate')
    baseline = request.get('baseline_config', {})
    baseline_path = Path(baseline.get('path', ''))
    if not baseline_path.is_file() or filehash(baseline_path) != baseline.get('sha256'):
        raise ValueError('HD workprint source config binding is invalid')
    expected_config = read_input_json(baseline_path)
    expected_config['render']['preview_native'] = True
    # Native frame sampling can change the studio's derived AABB floor anchor.
    # Permit only a small, evidenced scalar correction, never motion/geometry edits.
    for correction in request.get('derived_floor_corrections', []):
        evidence = correction.get('evidence', {})
        evidence_path = Path(evidence.get('path', ''))
        old, new = correction.get('from'), correction.get('to')
        if (not evidence_path.is_file() or filehash(evidence_path) != evidence.get('sha256')
                or not isinstance(old, (int, float)) or not isinstance(new, (int, float))
                or not 0 < abs(new - old) <= .001):
            raise ValueError('Native-HD floor correction requires bounded, hashed evidence')
        lighting = expected_config['shots'][correction['shot_id']]['studio_lighting']
        if lighting.get('floor_gap') != old:
            raise ValueError('Native-HD floor correction source changed')
        lighting['floor_gap'] = new
    candidate_config = read_input_json(config)
    if (candidate_config != expected_config
            or tuple(candidate_config['render'].get(k) for k in ('width', 'height', 'fps')) != (1920, 1080, 30)):
        raise ValueError('HD workprint may only enable native resolution on the reviewed source')
    qa_name = request.get('baseline_qa_handoff', 'animatic-qa')
    if qa_name not in {'animatic-qa', 'hd-workprint-qa'}:
        raise ValueError('HD workprint requires a recognized independent QA handoff')
    qa = artifact(task, qa_name)
    current = data['handoffs'][qa_name]
    if qa_name == 'hd-workprint-qa' and (
            qa.get('independent') is not True or not qa.get('reviewer_thread_id')
            or qa['reviewer_thread_id'] in {row['thread_id'] for row in data.get('agent_runs', []) if row['role'] != 'QA'}
            or qa.get('decision', {}).get('native_hd_unaccepted_workprint_allowed') is not True
            or qa.get('decision', {}).get('formal_final_render_permission') is not False
            or qa.get('decision', {}).get('final_acceptance') is not False):
        raise ValueError('Native workprint requires explicit independent limited QA permission')
    if qa_name == 'hd-workprint-qa':
        inputs = qa.get('input_bindings', [])
        if not inputs or any(not Path(row.get('path', '')).is_file()
                             or filehash(row['path']) != row.get('sha256') for row in inputs):
            raise ValueError('Native workprint QA input binding missing or stale')
        if (str(Path(config).resolve()), filehash(config)) not in {
                (str(Path(row['path']).resolve()), row['sha256']) for row in inputs}:
            raise ValueError('Native workprint QA must bind the exact candidate config')
    if request.get('baseline_animatic_qa_sha256') != current['sha256']:
        raise ValueError('HD workprint baseline QA changed')
    checks = qa.get('checks', {})
    if not checks or any(v not in {'PASS', 'UNKNOWN'} for v in checks.values()):
        raise ValueError('Known failed or invalid QA cannot authorize HD workprint')
    if any(i.get('severity') in {'critical', 'major', 'error'} for i in qa.get('issues', [])):
        raise ValueError('Unresolved major defects block HD workprint')
    media = qa.get('media', [])
    check_media(media)
    if request.get('baseline_media_sha256') not in {m['sha256'] for m in media}:
        raise ValueError('HD workprint must bind the exact reviewed baseline media')
    asset = check_asset(task)
    if (asset.get('qualified') is not True or asset.get('independent_meshes') is not True
            or asset.get('missing_required_parts') != []):
        raise ValueError('HD workprint requires the qualified existing asset')
    if record:
        event(task, 'hd_workprint_authorized', request=binding, config_sha256=filehash(config),
              formal_acceptance=False)


def require_animatic_diagnostic(task, config, qa_path, *, record=True):
    """Authorize only inexpensive raw full-storyboard previews before freeze."""
    data = load(task)
    if story_development(data):
        require_creative_pass(task, 'story-qa')
    if editorial_policy.enabled(data):
        require_visual_story_review(task)
    from .production_contract import enabled as science_contract
    states={'RESEARCHING','ASSET_READY','ANIMATING'} if science_contract(data) else {'RESEARCHING'}
    if active_media_repair(data):
        states.add('REPAIRING')
    if data['state'] not in states or qa_path is None:
        raise ValueError('Low-cost full animatic requires RESEARCHING and independent preproduction QA')
    qa = read_input_json(qa_path)
    if (qa.get('task_id') != data['id'] or qa.get('reviewer_role') != 'QA'
            or qa.get('independent') is not True or not qa.get('reviewer_thread_id')
            or qa['reviewer_thread_id'] in {row['thread_id'] for row in data['agent_runs'] if row['role'] != 'QA'}):
        raise ValueError('Independent task-bound low-cost animatic reviewer required')
    decision = qa.get('decision', {})
    if (decision.get('raw_full_low_cost_dynamic_animatic_allowed') is not True
            or decision.get('expensive_render_allowed') is not False
            or decision.get('final_acceptance') is not False):
        raise ValueError('QA must explicitly allow raw low-cost animatic only, not expensive/final rendering')
    bindings = qa.get('input_bindings', [])
    bound = {}
    for item in bindings:
        path = Path(item['path'])
        if not path.is_file() or filehash(path) != item['sha256']:
            raise ValueError('Stale low-cost animatic QA dependency: ' + str(path))
        bound[str(path.resolve())] = item['sha256']
    if bound.get(str(Path(config).resolve())) != filehash(config):
        raise ValueError('Low-cost animatic QA must bind the exact executable config')
    cfg = read_input_json(config)
    render = cfg.get('render', {})
    if render.get('preview_native') or render.get('framing') != 'fullframe':
        raise ValueError('Animatic diagnostic requires downsampled fullframe preview')
    from fractions import Fraction
    if (render.get('width', 0) // 2 > 960 or render.get('height', 0) // 2 > 540
            or Fraction(str(render.get('fps', 0))) != 30):
        raise ValueError('Animatic diagnostic limited to 960x540/15fps preview')
    selected = cfg.get('local_preview_shots', [])
    required = {row['shot'] for row in cfg.get('storyboard', [])}
    duration = sum(row['seconds'] for row in cfg.get('storyboard', []))
    if not required or set(selected) != required or not 0 < duration <= 300:
        raise ValueError('Full animatic diagnostic must include all authored chapters within 300 seconds')
    assembly_path = Path(cfg.get('assembly_config', ''))
    if bound.get(str(assembly_path.resolve())) != filehash(assembly_path):
        raise ValueError('QA must bind the exact assembly dependencies')
    assembly = read_input_json(assembly_path)
    for item in assembly.get('source_files', []):
        if not Path(item['path']).is_file() or filehash(item['path']) != item['sha256']:
            raise ValueError('Stale assembly source for full animatic: ' + item['path'])
    if record:
        event(task, 'low_cost_full_animatic_authorized', config_sha256=filehash(config),
              qa=dict(path=str(qa_path), sha256=filehash(qa_path)),
              formal_acceptance=False, expensive_render_allowed=False)
        with lock(Path(task) / '.ledger.lock'):
            current = load(task)
            current['low_cost_animatic_approval'] = dict(
                config=dict(path=str(Path(config).resolve()), sha256=filehash(config)),
                qa=dict(path=str(Path(qa_path).resolve()), sha256=filehash(qa_path)))
            write(Path(task) / 'task.json', current)
    return qa


def validate_stage(task, phase, config, *, workprint=False, diagnostic=False,
                   animatic_diagnostic=False, preproduction_qa=None):
    if phase not in {'asset', 'checks', 'keys', 'local', 'preview', 'final'}:
        raise ValueError('Unsupported stage')
    data = load(task)
    if story_development(data):
        if animatic_diagnostic or diagnostic:
            require_creative_pass(task, 'story-qa')
        else:
            require_visual_story_review(task)
    remake_candidate = (data.get('reference_remake', {}).get('old_scheme_status') == 'REJECTED_BY_USER'
                        and phase in {'keys', 'checks', 'local'})
    require_current_scheme(data, candidate_preview=remake_candidate)
    if diagnostic and phase not in {'keys', 'checks', 'local'}:
        raise ValueError('Diagnostic stage only permits candidate keys/checks/local in RESEARCHING')
    from .three_d import validate_config
    if not Path(config).is_file():
        raise ValueError('Actual 3D production config file required')
    cfg = read_input_json(config)
    validate_config(cfg)
    if source_policy.enabled(data) and animatic_diagnostic:
        validate_production_sources(task, cfg, policy=data, require_reveal=True)
    technical_render = require_source_supported_render(task, config)
    scoped_render = cfg.get('production_scope') == 'verified-shots'
    if scoped_render and phase not in {'keys', 'checks', 'local'}:
        raise ValueError('Scoped shots cannot authorize a full film or final acceptance')
    if technical_render:
        remake_candidate = False
    if remake_candidate:
        from .reference_policy import validate_research
        research = artifact(task, 'research')
        validate_research(research)
        asset = check_asset(task)
        if asset.get('mechanism_id') != research.get('mechanism_id'):
            raise ValueError('Candidate asset and research must identify the same mechanism')
        assembly_path = ROOT / cfg['assembly_config']
        assembly = read_input_json(assembly_path)
        sources = assembly.get('source_files', [])
        model = asset['model']
        direct_model = any(Path(row['path']).resolve() == Path(model['path']).resolve()
                           and row['sha256'] == model['sha256'] for row in sources)
        shared_source = assembly.get('model_source') == asset.get('model_source') and bool(asset.get('model_source'))
        if not sources or not (direct_model or shared_source):
            raise ValueError('Candidate render assembly must use the newly verified model')
        if shared_source:
            source = asset['model_source']
            path = Path(source.get('path', ''))
            if not path.is_file() or filehash(path) != source.get('sha256'):
                raise ValueError('Candidate model source missing or changed')
        for row in sources:
            if filehash(ROOT / row['path']) != row['sha256']:
                raise ValueError('Candidate assembly source changed')
        binding = data['reference_remake']['production_binding'].get('config', {})
        if str(Path(binding.get('path', '')).resolve()) != str(Path(config).resolve()) or binding.get('sha256') != filehash(config):
            raise ValueError('Replacement candidate requires its exact new config binding')
        selected = cfg.get('local_preview_shots', [])
        seconds = sum(cfg.get('shots', {}).get(name, {}).get('seconds', 0) for name in selected)
        if not selected or not 10 <= seconds <= 15:
            raise ValueError('Replacement candidate must be a continuous 10-15 second local preview')
        if workprint or animatic_diagnostic or diagnostic:
            raise ValueError('Replacement candidate uses the bounded local preview, not legacy bypass flags')
    native_hd_workprint = False
    native_hd_short_insert = False
    if animatic_diagnostic:
        if phase != 'local' or diagnostic or workprint:
            raise ValueError('Full animatic diagnostic only permits raw low-cost local previews')
        require_animatic_diagnostic(task, config, preproduction_qa, record=False)
    if data.get('reference_policy_version') == 1:
        if phase == 'asset':
            from .comprehension import enabled, validate_product_research
            if enabled(data):
                validate_product_research(artifact(task, 'research'))
            from .reference_policy import validate_asset
            chosen = artifact(task, 'asset-plan')
            validate_asset(artifact(task, 'research'), chosen)
            if chosen['strategy'] != 'autonomous-cad':
                raise ValueError('Asset generation requires evidence-based CAD selection; reuse approved assets directly')
        elif phase in {'preview', 'final'}:
            require_reference_content(task)
        from .production_contract import science_story
        if data.get('asset_strategy') == 'existing-media' and not science_story(data) and not (
                phase != 'asset' and cfg.get('render_route') in {'2d', '2.5d'}):
            raise ValueError('Existing media requires an authored editing route plan; do not invoke CAD rendering')
    if data.get('asset_strategy') == 'autonomous-cad' and phase != 'asset':
        candidate_config = cfg
        if candidate_config.get('render', {}).get('preview_native'):
            if phase == 'local' and workprint and not diagnostic:
                require_hd_workprint_request(task, config, record=False)
                native_hd_workprint = True
                selected = candidate_config.get('local_preview_shots', [])
                storyboard = candidate_config.get('storyboard', [])
                if (len(selected) == 1 and len(storyboard) == 1
                        and storyboard[0].get('shot') == selected[0]
                        and selected[0] in candidate_config.get('shots', {})):
                    seconds = candidate_config['shots'][selected[0]].get('seconds', 0)
                    native_hd_short_insert = (0 < seconds <= 5 and storyboard[0].get('seconds') == seconds)
            elif not remake_candidate and not technical_render:
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
        if editorial_policy.enabled(data) or directed_story(data):
            check_qa(task, 'preview-qa', acceptance=False)
    elif not (technical_render or diagnostic or animatic_diagnostic or remake_candidate or
              (phase == 'final' and active_media_repair(data, final=True)) or
              (native_hd_workprint and data['state'] == 'RESEARCHING')) and data['state'] not in allowed[phase]:
        raise ValueError('Stage lacks verified prerequisites: ' + data['state'])
    if phase in {'preview', 'final'}:
        require_animatic(task)
        check_production_config(task, config)
    if phase == 'final':
        from .director_audio import validate_arrangement
        validate_arrangement(cfg, require_ready=True)
    if phase == 'final' and data.get(video_review.FIELD):
        check_qa(task, 'preview-qa', acceptance=False)
    if phase == 'final' and not technical_render and not (workprint and data['state'] == 'PREVIEW_CHECKING'):
        check_qa(task, 'preview-qa', acceptance=False)
    assembly_path = ROOT / (cfg.get('assembly_config') or 'config/assembly.json')
    if assembly_path.is_file():
        assembly = read_input_json(assembly_path)
        for source in assembly.get('source_files', []):
            if filehash(ROOT / source['path']) != source['sha256']:
                raise ValueError('Assembly source hash mismatch: ' + source['path'])
    return data, technical_render, scoped_render, remake_candidate, native_hd_short_insert


def stage_ledger_identity(data):
    # Progress reporting and receipts do not authorize rendering. Use a separate
    # identity from asset/shot/composition keys.
    progress = {'continuation', 'next_step', 'production_status', 'stages', 'route_runs',
                'candidate_failures', 'delivery_receipt', 'low_cost_animatic_approval'}
    return digest({key: value for key, value in data.items() if key not in progress})


def stage_authorization(task, phase, config, **options):
    files = {}
    token = input_hashes.set(files)
    try:
        config_sha = filehash(config) if Path(config).is_file() else None
        ledger = stage_ledger_identity(load(task))
        validated = validate_stage(task, phase, config, **options)
        if ledger != stage_ledger_identity(load(task)) or config_sha != filehash(config):
            raise ValueError('Production inputs changed during stage validation')
    finally:
        input_hashes.reset(token)
    return validated, dict(task=str(Path(task).resolve()), phase=phase, ledger=ledger,
                           config=str(Path(config).resolve()), files=files)


def verify_stage_authorization(binding, task, phase, config, contents, data):
    path = str(Path(config).resolve())
    if (binding['task'] != str(Path(task).resolve()) or binding['phase'] != phase
            or binding['config'] != path or binding['ledger'] != stage_ledger_identity(data)
            or binding['files'].get(path) != hashlib.sha256(contents).hexdigest()):
        raise ValueError('Stage input differs from the authorized task, phase or config')
    for source, expected in binding['files'].items():
        if source == path:
            continue
        try:
            current = filehash(source)
        except OSError as error:
            raise ValueError('Authorized stage dependency unreadable: ' + source) from error
        if current != expected:
            raise ValueError('Authorized stage dependency changed: ' + source)


def run_stage(task, phase, config, env_file=None, workprint=False, diagnostic=False,
              animatic_diagnostic=False, preproduction_qa=None):
    """Execute existing deterministic script once; serialize all Blender work."""
    options = dict(workprint=workprint, diagnostic=diagnostic,
                   animatic_diagnostic=animatic_diagnostic, preproduction_qa=preproduction_qa)
    _, queued = stage_authorization(task, phase, config, **options)
    # Existing cleanup only removes old completed content-addressed entries,
    # skips protected/task-referenced entries and shares our global lock.
    sys.path.insert(0, str(ROOT / 'scripts'))
    from clean import cleanup
    try:
        cleanup(older_hours=720, apply=True)
    except CleanupBusy as error:
        # Another real renderer owns the global lock. Skip optional cleanup,
        # then queue on that same lock; never fail or delete its live frames.
        event(task, 'cleanup_deferred', reason=str(error))
    with lock(ROOT / 'work/production.lock', wait=True):
        validated, authorized = stage_authorization(task, phase, config, **options)
        if authorized != queued:
            raise ValueError('Authorized production inputs changed while waiting for the production lock')
        data, technical_render, scoped_render, remake_candidate, native_hd_short_insert = validated
        if animatic_diagnostic:
            # Persist only the approval that passed revalidation under the production lock.
            with lock(Path(task) / '.ledger.lock'):
                current = load(task)
                current['low_cost_animatic_approval'] = dict(
                    config=dict(path=authorized['config'], sha256=authorized['files'][authorized['config']]),
                    qa=dict(path=str(Path(preproduction_qa).resolve()),
                            sha256=authorized['files'][str(Path(preproduction_qa).resolve())]))
                write(Path(task) / 'task.json', current)
            event(task, 'low_cost_full_animatic_authorized', **current['low_cost_animatic_approval'],
                  formal_acceptance=False, expensive_render_allowed=False)
        if workprint and data.get('hd_workprint_authorization'):
            event(task, 'hd_workprint_authorized', request=data['hd_workprint_authorization'],
                  config_sha256=authorized['files'][authorized['config']],
                  formal_acceptance=False)
        config_sha = authorized['files'][authorized['config']]
        start = time.time()
        from .production_contract import enabled as science_contract
        previous_media=None
        if phase=='final' and science_contract(data):
            import shutil
            cfg=read_input_json(config)
            target=ROOT/'output'/(cfg['id']+'-final.mp4')
            request=data.get('revision_request',{})
            previous_media=request.get('previous_media') or next(
                (r['media'] for r in reversed(data['stages']) if r.get('phase')=='final' and r.get('media')),None)
            if target.is_file() and not request.get('previous_media'):
                previous_media=dict(path=str(target),sha256=filehash(target))
            if previous_media:
                check_media([previous_media])
                saved=Path(task)/'revisions'/previous_media['sha256']/'previous.mp4'
                saved.parent.mkdir(parents=True,exist_ok=True)
                if not saved.exists():
                    shutil.copy2(previous_media['path'],saved)
                previous_media=dict(path=str(saved.resolve()),sha256=filehash(saved))
                event(task,'previous_media_preserved',media=previous_media)
        args = ['uv', 'run', '--project', str(ROOT), 'python',
                str(ROOT / 'scripts/produce.py'), str(config), '--phase', phase]
        args += ['--task', str(Path(task).resolve())]
        if diagnostic or native_hd_short_insert:
            args += ['--diagnostic']
        if protocol_version(data) == 1 and phase in {'preview', 'final'}:
            args += ['--legacy-workprint']
        if env_file:
            args += ['--env-file', str(env_file)]
        logfile = Path(task) / ('stage-' + phase + '-' + str(time.time_ns()) + '.log')
        authorization_path = logfile.with_suffix('.inputs.json')
        write(authorization_path, authorized)
        args += ['--stage-authorization', str(authorization_path), digest(authorized)]
        try:
            with logfile.open('w') as out:
                subprocess.run(args, cwd=ROOT, stdout=out, stderr=subprocess.STDOUT, check=True)
        except (subprocess.CalledProcessError, OSError):
            isolated_candidate = (diagnostic or animatic_diagnostic or workprint or remake_candidate
                                  or technical_render or active_media_repair(data))
            if isolated_candidate:
                # Preserve independent routes' valid prerequisites after a
                # failed inspectable candidate; retain every failed attempt.
                with lock(Path(task) / '.ledger.lock'):
                    current = load(task)
                    current.setdefault('candidate_failures', []).append(dict(
                        phase=phase, config=str(Path(config).resolve()), config_sha256=config_sha,
                        route=read_input_json(config).get('render_route'),
                        status='REPAIRING', log=str(logfile), epoch=time.time()))
                    write(Path(task) / 'task.json', current)
            else:
                advance(task, 'FAILED')
            event(task, 'stage_failed', phase=phase, seconds=time.time()-start, log=str(logfile),
                  diagnostic=diagnostic or animatic_diagnostic or native_hd_short_insert, animatic_diagnostic=animatic_diagnostic,
                  previous_state=data['state'], isolated_candidate=isolated_candidate,
                  lifecycle='REPAIRING' if isolated_candidate else 'FAILED', config_sha256=config_sha)
            continuation(task)
            raise
        with lock(Path(task) / '.ledger.lock', wait=True):
            data = load(task)
            try:
                config_contents = Path(config).read_bytes()
                verify_stage_authorization(authorized, task, phase, config, config_contents, data)
            except (ValueError, OSError) as error:
                event(task, 'stage_output_rejected', phase=phase, reason=str(error), log=str(logfile),
                      authorization=str(authorization_path), config_sha256=config_sha,
                      command_success=False)
                raise
            observations = []
            for line in logfile.read_text().splitlines():
                try:
                    observation = json.loads(line)
                except ValueError:
                    continue
                if isinstance(observation, dict) and 'cache_hit' in observation:
                    observations.append(observation)
            row = dict(phase=phase, seconds=round(time.time()-start, 3), log=str(logfile),
                       config_sha256=config_sha,
                       command_success=True, quality_accepted=False, unaccepted_workprint=workprint or technical_render,
                       diagnostic=diagnostic or animatic_diagnostic or native_hd_short_insert, animatic_diagnostic=animatic_diagnostic,
                       cache_observations=observations,
                       cache_hit_rate=(sum(r['cache_hit'] for r in observations)/len(observations)
                                       if observations else None),
                       full_shot_renders=sum(r['stage'].startswith('final:') and not r['cache_hit']
                                             for r in observations))
            data['stages'].append(row)
            if phase=='final' and science_contract(data):
                from .media_revision import compare, bind
                cfg=json.loads(config_contents)
                target=ROOT/'output'/(cfg['id']+'-final.mp4')
                row['media']=bind(target)
                if producer_directed(data):
                    media = dict(row['media'], chapter_ids=[shot['id'] for shot in cfg['storyboard']])
                    data['route_runs']['3d'] = {'status': 'TECHNICAL_PASS_UNACCEPTED', 'outputs': media}
                row['previous_media']=previous_media
                request=data.get('revision_request')
                if request:
                    if previous_media is None:
                        raise ValueError('Improvement claim requires the preserved previous actual MP4')
                    result=compare(previous_media['path'],target,request['changes'])
                    revision=Path(task)/'revisions'/('comparison-'+str(time.time_ns())+'.json')
                    write(revision,result)
                    row['revision']=bind(revision)
                    row['upgrade_target_met']=result['status']=='OBSERVABLE_CHANGE_VERIFIED'
            if technical_render and not scoped_render and phase in {'preview', 'final'}:
                cfg = json.loads(config_contents)
                row['source_supported_film'] = bool(data.get('shot_production')
                    and cfg.get('production_scope') == 'source-supported-film'
                    and cfg.get('shot_evidence_version') == 1)
                target = ROOT/'output'/(cfg['id']+'-'+phase+'.mp4')
                row['media'] = dict(path=str(target), sha256=filehash(target))
                check_media([row['media']])
            failure = data.get('production_execution_failure', {})
            command = failure.get('command', [])
            if failure.get('status') == 'OPEN' and '--config' in command:
                failed_config = command[command.index('--config')+1]
                if Path(failed_config).resolve() == Path(config).resolve():
                    failure.update(status='RESOLVED', resolved_epoch=time.time(),
                                   resolution='Corrected inputs/environment; exact stage completed successfully')
            if scoped_render and phase == 'local':
                cfg = json.loads(config_contents)
                receipt = json.loads((ROOT/'output'/cfg['id']/'verified-shots.json').read_text())
                if receipt['config_sha256'] != config_sha:
                    raise ValueError('Scoped render receipt config changed')
                for name, rendered in receipt['shots'].items():
                    check_media([rendered['media']])
                    for name_of_file in ('scene', 'checks'):
                        ref = rendered[name_of_file]
                        if not Path(ref['path']).is_file() or filehash(ref['path']) != ref['sha256']:
                            raise ValueError('Scoped scene/checks missing or stale')
                    data['shot_production'][name].update(rendered, status='QA_PENDING',
                        render_status='RENDERED', perceptual_qa='UNKNOWN')
            for failure in data.get('candidate_failures', []):
                if failure.get('config_sha256') == row['config_sha256'] and failure.get('phase') == phase:
                    failure.update(status='RESOLVED', resolved_epoch=time.time())
            write(Path(task) / 'task.json', data)
            event(task, 'stage', **row)
    continuation(task)
    return logfile


def select_route(task, route, reason):
    """Producer chooses representation before freezing production dependencies."""
    from .three_d import require_route
    require_route(route)
    if not reason.strip():
        raise ValueError('Supported route and reason required')
    with lock(Path(task) / '.ledger.lock'):
        data = load(task)
        if data['state'] not in {'CREATED', 'RESEARCHING'} or any(
                name in data['handoffs'] for name in ('asset-plan', 'creative-blueprint', 'feasibility')):
            raise ValueError('Select route before asset and blueprint handoffs')
        if data.get('reference_policy_version') != 1:
            data['asset_strategy'] = 'autonomous-cad' if route == '3d' else 'illustrated'
        data['render_route'] = route
        write(Path(task) / 'task.json', data)
        event(task, 'route_selected', route=route, reason=reason)
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    from . import pacing
    pacing.opening_arguments(sub.add_parser('opening-analysis', help='Inspect the opening of an actual MP4'))
    p = sub.add_parser('produce', help='Render an authored episode to MP4')
    source = p.add_mutually_exclusive_group(required=True)
    source.add_argument('--episode', type=Path, help='Directory containing the scene, narration and edit')
    source.add_argument('--resume', type=Path, help='Inspect the continuation of an existing ledger task')
    p.add_argument('--work-dir', type=Path, help='Keep reusable picture clips in this directory')
    p.add_argument('--env-file', type=Path, help='Use local speech credentials')
    p.add_argument('--edit', type=Path, help='Alternate edit JSON, relative to the episode directory')
    p.add_argument('--preview-shots', type=int, help='Render a low-cost preview of the first N shots')
    p.add_argument('--allow-short', action='store_true', help='Honor an explicitly requested short episode')
    p = sub.add_parser('migrate-3d', help='Explicit in-place migration of an undelivered task; preserve all assets and history')
    p.add_argument('task',type=Path)
    p.add_argument('--reason',required=True)
    p = sub.add_parser('route-run', help='Resume authored route render plan; no agent impersonation')
    p.add_argument('task', type=Path)
    p.add_argument('--plan', type=Path, required=True, help='Current topic-specific 3D plan; no deprecated default plan')
    p.add_argument('--env-file', type=Path, help='Credentials file forwarded only to opted-in audio step; no secrets in plan')
    p = sub.add_parser('continue', help='Reconcile work; --execute drains approved commands until delivery or native Producer reasoning is needed')
    p.add_argument('task', type=Path)
    p.add_argument('--plan', type=Path)
    p.add_argument('--execute', action='store_true')
    p.add_argument('--animatic-config', type=Path, help='Bind an independently permitted full low-cost storyboard')
    p.add_argument('--preproduction-qa', type=Path)
    p = sub.add_parser('record-delivery', help='Bind files actually provided to the user after independent acceptance')
    p.add_argument('task', type=Path)
    p.add_argument('--file', dest='files', type=Path, action='append', required=True)
    p.add_argument('--reason', required=True)
    p = sub.add_parser('extend-routes', help='Explicitly expand an authorized existing task without recreating it')
    p.add_argument('task', type=Path)
    p.add_argument('--routes', choices=['all', '2d', '2.5d', '3d'], required=True)
    p.add_argument('--reason', required=True)
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
                           help='Explicitly render an unaccepted final workprint, or bound user-authorized native-HD local candidate')
            p.add_argument('--diagnostic', action='store_true',
                           help='Inspect one evidenced candidate shot, at most five seconds; never full production')
            p.add_argument('--animatic-diagnostic', action='store_true', help='QA-bound full low-cost raw dynamic storyboard; never expensive or accepted production')
            p.add_argument('--preproduction-qa', type=Path, help='Independent exact-config low-cost diagnostic permission')
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
            p.add_argument('--seconds', type=float)
            p.add_argument('--tokens', type=int)
            p.add_argument('--model')
            p.add_argument('--reasoning-effort')
            p.add_argument('--task-type')
            p.add_argument('--input-version')
            p.add_argument('--output', action='append', default=[])
            p.add_argument('--cache-hit', action='store_true', default=None)
            p.add_argument('--duplicate', action='store_true', default=None)
            p.add_argument('--cost', type=float)
            p.add_argument('--success', choices=['true', 'false'])
            p.add_argument('--retries', type=int)
    args = parser.parse_args()
    if args.command == 'opening-analysis':
        pacing.run_opening(args)
        return
    if args.command == 'migrate-3d':
        from .three_d import migrate
        migrate(args.task,args.reason)
        print(json.dumps(continuation(args.task),ensure_ascii=False,indent=2))
        return
    if args.command == 'produce':
        if args.resume:
            if args.work_dir or args.env_file or args.edit or args.preview_shots is not None or args.allow_short:
                parser.error('--work-dir, --env-file, --edit, --preview-shots and --allow-short apply to --episode')
            event(args.resume, 'producer_resumed', dispatch_mode='current_native_codex_session')
            print(json.dumps(continuation(args.resume), ensure_ascii=False, indent=2))
        else:
            from .episode import produce

            print(produce(args.episode, work_dir=args.work_dir, env_file=args.env_file,
                          edit_file=args.edit, preview_shots=args.preview_shots, allow_short=args.allow_short))
        return
    if args.command == 'extend-routes':
        from .three_d import require_route
        require_route(args.routes)
        with lock(args.task / '.ledger.lock'):
            data = load(args.task)
            routes = ['2d', '2.5d', '3d'] if args.routes == 'all' else [args.routes]
            previous = data.get('requested_routes', [data.get('render_route', '3d')])
            if not args.reason.strip() or not set(previous) < set(routes):
                raise ValueError('A documented authorization and strict route-scope expansion are required')
            data['requested_routes'] = routes
            for route in routes:
                data.setdefault('route_runs', {}).setdefault(route, {'status': 'PENDING', 'outputs': {}})
            if len(routes) == 3:
                data['production_method'] = 'original-shared-script-three-routes'
            if data['state'] == 'COMPLETED':
                data['state'] = 'FINAL_CHECKING'
            data.pop('delivery_receipt', None)
            write(args.task / 'task.json', data)
            event(args.task, 'route_scope_extended', previous=previous, requested_routes=routes, reason=args.reason)
        print(json.dumps(continuation(args.task), ensure_ascii=False, indent=2))
        return
    if args.command == 'record-delivery':
        print(json.dumps(record_delivery(args.task, args.files, args.reason), ensure_ascii=False, indent=2))
        return
    if args.command == 'continue':
        if args.animatic_config or args.preproduction_qa:
            if not args.animatic_config or not args.preproduction_qa:
                raise ValueError('Both --animatic-config and --preproduction-qa are required')
            require_animatic_diagnostic(args.task, args.animatic_config, args.preproduction_qa)
        if args.plan:
            plan = json.loads(args.plan.read_text())
            data = load(args.task)
            if plan.get('topic') != data['topic'] or set(plan.get('routes', {})) != set(data.get('requested_routes', [])):
                raise ValueError('Continuation plan must match the existing task topic and requested routes')
            with lock(args.task / '.ledger.lock'):
                data = load(args.task)
                data['production_plan'] = dict(path=str(args.plan.resolve()), sha256=filehash(args.plan))
                write(args.task / 'task.json', data)
                event(args.task, 'production_plan_bound', **data['production_plan'])
        result = continuation(args.task)
        if args.execute:
            result = continue_production(args.task)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    if args.command == 'route-run':
        from .multiroute import prepare, run_plan
        data = load(args.task)
        if data.get('reference_policy_version') == 1:
            require_animatic(args.task)
        plan_data = json.loads(args.plan.read_text())
        if plan_data.get('topic') and plan_data['topic'] != data['topic']:
            raise ValueError('Adapter topic does not match task; arbitrary topics require their own production plan')
        if data.get('requested_routes') and set(data['requested_routes']) != set(plan_data['routes']):
            raise ValueError('Plan route scope must match task requested_routes; single-route tasks use their assigned production stages')
        folder = (Path(data.get('shared_production', {}).get('render_directory') or args.task / '3d')
                  if data.get('three_d_policy_version') == 1 else
                  Path(data.get('shared_production', {}).get('comparison_directory') or args.task / 'multiroute'))
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
            report_binding = {'report': str(folder / 'report.json'),
                              'sha256': filehash(folder / 'report.json'), 'status': report['status']}
            data['three_d_build' if data.get('three_d_policy_version') == 1 else 'route_comparison'] = report_binding
            data['multiroute_status'] = report['status']
            data['next_step'] = 'Current Producer dispatches independent exact-media route QA; UNKNOWN prevents completion.'
            for route, media in report['routes'].items():
                if producer_directed(data):
                    current = data['route_runs'].get(route, {}).get('outputs', {})
                    if current.get('sha256') == media['sha256']:
                        media = current | media
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
                only_3d = data.get('three_d_policy_version') == 1
                if (set(route_paths) == ({'3d'} if only_3d else {'2d','2.5d','3d'})
                        and all(path.is_file() for path in route_paths.values())
                        and (only_3d or (folder / 'compare.mp4').is_file())):
                    from .growth_report import generate as generate_growth_report
                    growth = generate_growth_report(args.task, route_paths, None if only_3d else folder / 'compare.mp4')
                    data['growth_report'] = {'path': str(args.task / 'growth-report.json'),
                                             'sha256': filehash(args.task / 'growth-report.json'),
                                             'status': growth['status']}
            write(args.task / 'task.json', data)
            event(args.task, 'three_d_build_generated' if data.get('three_d_policy_version') == 1 else
                  'route_comparison_generated', report=report_binding)
        continuation(args.task)
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
        print(run_stage(args.task, args.phase, args.config, args.env_file, args.workprint, args.diagnostic,
                        args.animatic_diagnostic, args.preproduction_qa))
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
                check_qa(args.task,'preview-qa', acceptance=False)
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
                check_qa(args.task, 'preview-qa', acceptance=target == 'COMPLETED')
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
            row.update(model=args.model, reasoning_effort=args.reasoning_effort,
                       task_type=args.task_type, input_version=args.input_version,
                       outputs=args.output, cache_hit=args.cache_hit,
                       duplicate=args.duplicate, cost=args.cost,
                       success=None if args.success is None else args.success == 'true',
                       retries=args.retries)
            data['agent_runs'].append(row)
            write(args.task / 'task.json', data)
            event(args.task, 'agent_run', **row)
        continuation(args.task)
