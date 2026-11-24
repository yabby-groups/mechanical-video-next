"""Product topology carried by the existing assembly configuration."""

from .science_shots import name, vector

VERSION = 1
RELATIONS = ('connections', 'joints', 'constraints', 'actuators', 'transmissions', 'outputs', 'resets')


def validate(graph, objects, *, source_ids=None, model=None):
    if graph.get('version') != VERSION:
        raise ValueError('Unsupported product assembly version')
    product = graph.get('product', {})
    identity = product.get('model')
    if not name(identity) or (model is not None and identity != model):
        raise ValueError('Assembly product model must match the researched model')
    assemblies = graph.get('assemblies', {})
    parts = graph.get('parts', {})
    if not assemblies or not parts or set(objects) != {row.get('object') for row in parts.values()}:
        raise ValueError('Product assembly must address the native part inventory')
    if len(parts) != len(objects):
        raise ValueError('Each native part requires one product part ID')
    for key, part in parts.items():
        if (part.get('assembly') not in assemblies or not name(part.get('name'))
                or part.get('model') != identity or not isinstance(part.get('geometry'), dict)
                or not isinstance(part.get('dimensions'), dict)):
            raise ValueError('Incomplete assembly part: ' + key)
        if not vector(part['geometry'].get('installed_matrix'), 16):
            raise ValueError('Part needs its installed world transform: ' + key)
        if source_ids is not None and not (part.get('source_ids') and set(part['source_ids']) <= source_ids):
            raise ValueError('Part evidence must match the researched product: ' + key)
    for kind in RELATIONS:
        records = graph.get(kind, {})
        if not isinstance(records, dict):
            raise ValueError('Assembly relations must be keyed by ID: ' + kind)
        for key, row in records.items():
            linked = row.get('parts', [])
            if not linked or len(set(linked)) != len(linked) or not set(linked) <= parts.keys():
                raise ValueError('Unknown or duplicate parts in relation: ' + key)
            if source_ids is not None and not (row.get('source_ids') and set(row['source_ids']) <= source_ids):
                raise ValueError('Relation evidence must match the researched product: ' + key)
    connections = graph.get('connections', {})
    removable = set()
    for key, row in connections.items():
        if 'removal' not in row:
            continue
        removal = row['removal']
        moving = removal.get('parts', [])
        path = removal.get('path')
        blockers = removal.get('after', [])
        if (not moving or not set(moving) < set(row['parts']) or set(moving) & removable
                or not isinstance(path, list) or not 1 <= len(path) <= 8
                or any(not vector(offset, 3) or not any(offset) for offset in path)
                or not set(blockers) <= connections.keys() or key in blockers):
            raise ValueError('Invalid installed connection or removal path: ' + key)
        removable.update(moving)
    return graph


def reveal_plan(graph, request):
    """Resolve prerequisite connections and compile a reversible native path."""
    parts = graph['parts']
    connections = graph.get('connections', {})
    ordered, visiting = {}, set()

    def visit(key):
        if key in ordered:
            return
        if key in visiting or key not in connections or 'removal' not in connections[key]:
            raise ValueError('Unresolved removal prerequisite: ' + key)
        visiting.add(key)
        removal = connections[key]['removal']
        for blocker in removal.get('after', []):
            visit(blocker)
        ordered[key] = removal
        visiting.remove(key)

    for key in request['connections']:
        visit(key)
    if not {request['anchor'], *request['targets']} <= parts.keys():
        raise ValueError('Assembly reveal references an unknown part')
    paths = {parts[part]['object']: row['path'] for row in ordered.values() for part in row['parts']}
    targets = {parts[part]['object']: point for part, point in request['targets'].items()}
    groups = [[parts[part]['object'] for part in row['parts']] for row in ordered.values()]
    return dict(operation=request.get('operation', 'cycle'), anchor=parts[request['anchor']]['object'],
                parts={part: path[-1] for part, path in paths.items()}, paths=paths,
                groups=groups, reveal_targets=targets)


def path_clock(plan):
    """Installed hold, ordered removal, observation and reversed restoration."""
    groups = plan['groups']
    operation = plan['operation']
    begin, end = (.08, .40) if operation == 'cycle' else (.08, .78)
    step = (end - begin) / len(groups)
    clock = {}
    for index, group in enumerate(groups):
        start = begin + index * step
        for part in group:
            path = plan['paths'][part]
            keys = [(0, [0, 0, 0]), (start, [0, 0, 0])]
            keys += [(start + step * i / len(path), point) for i, point in enumerate(path, 1)]
            if operation == 'cycle':
                keys += [(1 - time, value) for time, value in reversed(keys)]
            else:
                keys.append((1, path[-1]))
                if operation == 'reassemble':
                    keys = [(1 - time, value) for time, value in reversed(keys)]
            clock[part] = keys
    return clock


def compile_reveal(shot, assembly):
    spec = shot.get('science', {})
    request = spec.get('assembly_reveal')
    if request is None:
        return shot
    graph = validate(assembly.get('product_assembly', {}), assembly['required_parts'])
    plan = reveal_plan(graph, request)
    focus = request.get('focus_parts', [])
    if not set(focus) <= graph['parts'].keys():
        raise ValueError('Reveal focus references an unknown assembly part')
    framing = {'focus_parts': [graph['parts'][part]['object'] for part in focus]} if focus else {}
    directions = request.get('camera_directions', [[5, -7, 4], [-5, -7, 4], [5, 7, 6], [-5, 7, 6]])
    return dict(shot, science=dict(spec, disassembly=plan,
                reveal_views=[{'direction': direction, **framing} for direction in directions]))
