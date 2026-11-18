"""The current production contract; historical ledgers remain readable."""
from pathlib import Path
import copy
import json

POLICY_VERSION = 1


def require_route(route):
    if route != '3d':
        raise ValueError('3D-only production: 2d, 2.5d, all and illustrated/layered substitutes are permanently retired')


def validate_config(config):
    from .science_shots import validate as validate_science_shot
    from .visual_narrative import VERSION, validate_execution, validate_plan, version
    from .knowledge_progression import FIELD, enabled
    visual_version = version(config)
    from .media_policy import enabled as asset_first, validate_document
    hybrid = asset_first(config)
    progression = enabled(config)
    if progression and visual_version != VERSION:
        raise ValueError('Knowledge progression requires visual policy 2')
    require_route(config.get('render_route', '3d'))
    if config.get('requested_routes', ['3d']) != ['3d']:
        raise ValueError('3D-only production requires requested_routes=["3d"]')
    if config.get('asset_strategy') == 'illustrated':
        raise ValueError('Illustrated mechanical subjects are not 3D')
    shots = config.get('shots', {})
    for shot in shots.values() if isinstance(shots, dict) else shots:
        if not isinstance(shot, dict):
            raise ValueError('Executable 3D shots must be structured objects')
        require_route(shot.get('render_route', '3d'))
        if shot.get('template') == 'layered' or shot.get('layers'):
            raise ValueError('Layered mechanical imagery cannot replace a real 3D scene')
        if isinstance(shots, dict) and visual_version == VERSION and shots:
            validate_execution(shot, progression=progression, hybrid=hybrid)
        elif visual_version != VERSION and (shot.get('template') == 'editorial' or {'visual', 'graphic', 'footage'} & shot.keys()):
            raise ValueError('Editorial shots require the versioned visual production policy')
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
