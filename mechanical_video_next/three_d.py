"""Validate the Blender route and the policies pinned by existing ledgers."""
from pathlib import Path
import copy
import json

POLICY_VERSION = 1


def require_route(route):
    if route != '3d':
        raise ValueError('The 3D-only Blender route requires 3d; use episode graphics or a supporting picture for explanations')


def validate_config(config):
    from .source_policy import validate_sources
    from .science_shots import validate as validate_science_shot
    from .visual_narrative import VERSION, validate_execution, validate_plan, version
    from .knowledge_progression import FIELD, enabled
    from .production_contract import FIELD as CONTRACT_FIELD, flexible_story
    from .joint_timeline import FIELD as TIMELINE_FIELD, enabled as joint_timeline
    visual_version = version(config)
    from .media_policy import enabled as asset_first, validate_document
    hybrid = asset_first(config)
    validate_sources(config, policy=config)
    progression = enabled(config)
    if progression and visual_version != VERSION:
        raise ValueError('Knowledge progression requires visual policy 2')
    require_route(config.get('render_route', '3d'))
    if config.get('requested_routes', ['3d']) != ['3d']:
        raise ValueError('3D-only production requires requested_routes=["3d"]')
    if config.get('asset_strategy') == 'illustrated':
        raise ValueError('Illustrated mechanical subjects are not 3D')
    shots = config.get('shots', {})
    picture = ({row['id']: row for row in config['timeline']['shots']}
               if isinstance(shots, dict) and joint_timeline(config) else {})
    for name, shot in shots.items() if isinstance(shots, dict) else enumerate(shots):
        if not isinstance(shot, dict):
            raise ValueError('Executable 3D shots must be structured objects')
        require_route(shot.get('render_route', '3d'))
        if shot.get('template') == 'layered' or shot.get('layers'):
            raise ValueError('Layered mechanical imagery cannot replace a real 3D scene')
        if isinstance(shots, dict) and visual_version == VERSION and shots:
            validate_execution(shot, progression=progression, hybrid=hybrid,
                               flexible=flexible_story(config), picture=picture.get(name))
        elif visual_version != VERSION and (shot.get('template') == 'editorial' or {'visual', 'graphic', 'footage'} & shot.keys()):
            raise ValueError('Editorial shots require the versioned visual production policy')
        # Blueprint rows are declarative mappings. Their complete executable
        # science program is copied from the bound base and checked after
        # compilation; requiring tracks here makes science templates impossible
        # to compile without duplicating their source of truth.
        if isinstance(shots, dict) or shot.get('science'):
            validate_science_shot(shot)
        if (config.get('production_scope') != 'verified-shots'
                and shot.get('evidence_status') == 'RESEARCH_REQUIRED'):
            raise ValueError('Unverified mechanism shot cannot enter the full film')
    if any(shot.get('science') for shot in (shots.values() if isinstance(shots, dict) else shots)):
        if config.get('storyboard') and (config.get('presentation') != 'mechanism-fullframe'
                or config.get('render', {}).get('framing') != 'fullframe'):
            raise ValueError('Science compositions require fullframe Blender and Remotion framing')
    if visual_version == VERSION and isinstance(shots, dict) and shots:
        rows = config.get('storyboard', [])
        if not rows or {row['shot'] for row in rows} != set(shots):
            raise ValueError('Visual execution requires complete storyboard coverage')
        validate_plan({**({'visual_policy_version': 2, 'media_policy_version': 1} if hybrid else {}),
            **{key: config[key] for key in (CONTRACT_FIELD, 'production_contract', 'production_method',
                                           'producer_direction_version', 'subject_kind', TIMELINE_FIELD)
               if key in config},
            **({FIELD: config[FIELD]} if progression else {}), 'shots': [
            dict(shots[row['shot']]['visual'], shot_id=row['id'], narration=row['narration'],
                 **{k: shots[row['shot']][k] for k in ('graphic','footage') if k in shots[row['shot']]})
            for row in rows
        ]})
        if config.get('presentation') != 'mechanism-fullframe' or [
                config.get('render', {}).get(k) for k in ('width', 'height', 'fps', 'framing')
        ] != [1920, 1080, 30, 'fullframe']:
            raise ValueError('Visual production requires the native 1920x1080/30 fullframe format')
    validate_document(config)
    if picture:
        from . import director, joint_timeline as joint
        if joint.integrity(config['timeline']):
            plan = joint.validate(config['timeline'])
            expected = [(row['id'], row['end_frame'] - row['start_frame']) for row in plan['shots']]
            actual = [(row['id'], joint.frame_number(row['seconds'])) for row in config['storyboard']]
            if expected != actual:
                raise ValueError('Compiled storyboard differs from the complete joint picture track')
            director.validate_action_programs(config)


def migrate(task, reason):
    """Explicit, idempotent in-place scope change, retaining every old record."""
    from .workflow import load, write, lock, event, sync_producer_prompt
    task = Path(task)
    with lock(task / '.ledger.lock'):
        data = load(task)
        if data.get('delivery_receipt') or data.get('delivered') or data['state'] == 'COMPLETED':
            raise ValueError('Completed/delivered history must not be migrated')
        if data.get('three_d_policy_version') == POLICY_VERSION:
            sync_producer_prompt(task, data)
            return data
        data.setdefault('route_scope_history', []).append({
            'reason': reason, 'requested_routes': copy.deepcopy(data.get('requested_routes')),
            'render_route': data.get('render_route'),
            'route_runs': copy.deepcopy(data.get('route_runs', {})),
            'continuation': copy.deepcopy(data.get('continuation'))})
        data.update(three_d_policy_version=POLICY_VERSION, requested_routes=['3d'], render_route='3d',
                    production_method='reference-grounded-3d')
        for route, run in data.get('route_runs', {}).items():
            if route != '3d':
                run['retired_from_delivery'] = True
                run['schedule_production'] = False
        data.pop('delivery_receipt', None)
        write(task / 'task.json', data)
        sync_producer_prompt(task, data)
        event(task, 'three_d_only_migration', reason=reason, preserved_assets=True)
    return data
