"""The current production contract; historical ledgers remain readable."""
from pathlib import Path
import copy
import json

POLICY_VERSION = 1


def require_route(route):
    if route != '3d':
        raise ValueError('3D-only production: 2d, 2.5d, all and illustrated/layered substitutes are permanently retired')


def validate_config(config):
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
