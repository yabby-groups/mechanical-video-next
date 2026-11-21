"""Validation for opt-in, evidence-bound 3D shot programs."""

import math
from pathlib import Path

from scripts.common import ROOT, filehash


TEMPLATES = {
    'exploded_view', 'cutaway', 'micro_zoom', 'motion_trace',
    'field_visualization', 'flow_visualization', 'state_transition',
    'measurement', 'camera_follow',
}
MODE_LABEL = {
    'conceptual': '原理示意', 'mathematical': '数学模型',
    'physical_simulation': '物理仿真回放',
}


def number(value):
    return type(value) in (float, int) and math.isfinite(value)


def vector(value, length):
    return isinstance(value, list) and len(value) == length and all(map(number, value))


def name(value):
    return isinstance(value, str) and bool(value.strip())


def source_binding(row):
    if not isinstance(row, dict) or not all(name(row.get(key)) for key in ('path', 'sha256', 'position')):
        raise ValueError('Science evidence requires file, SHA256 and location')
    path = ROOT / row['path']
    if not path.is_file() or filehash(path) != row['sha256']:
        raise ValueError(f'Science evidence file missing or stale: {row["path"]}')


def validate(shot, *, files=False):
    template = shot.get('template')
    spec = shot.get('science')
    if spec is None and template not in TEMPLATES:
        return
    if not isinstance(spec, dict) or spec.get('version') != 1:
        raise ValueError('Science templates require science.version=1')
    if template not in TEMPLATES | {'overall', 'detail', 'motion', 'explode', 'assemble', 'exploded'}:
        raise ValueError('Unknown science shot template')
    mode = spec.get('mode')
    if mode not in MODE_LABEL or not name(spec.get('scope')) or not spec.get('basis'):
        raise ValueError('Science shot requires mode, stated limits and located basis')
    if mode == 'physical_simulation':
        raise ValueError('This renderer does not verify solver outputs; physical_simulation is not supported')
    for binding in spec['basis']:
        if not isinstance(binding, dict) or not all(name(binding.get(key)) for key in ('path', 'sha256', 'position')):
            raise ValueError('Science evidence requires file, SHA256 and location')
        if files:
            source_binding(binding)
    driver = spec.get('driver', 'static')
    if driver not in {'static', 'asset_motion', 'data_tracks'}:
        raise ValueError('Unknown science motion driver')
    if (template not in TEMPLATES and driver != 'static'
            or template in {'exploded_view', 'state_transition'} and driver != 'data_tracks'
            or template == 'motion_trace' and driver == 'static'):
        raise ValueError('Motion driver does not match the template')
    if driver == 'data_tracks' and not (shot.get('tracks') or shot.get('mesh_tracks')):
        raise ValueError('Data tracks require prescribed poses')
    if template == 'exploded_view' and mode != 'conceptual':
        raise ValueError('An editorial exploded view must be marked as conceptual')
    if template == 'cutaway' and not shot.get('section_plane'):
        raise ValueError('Cutaway requires an explicit section plane')
    if 'offset_keys' in shot.get('section_plane', {}):
        plane = shot['section_plane']
        keys = plane['offset_keys']
        if (not isinstance(keys,list) or not 2 <= len(keys) <= 16
                or any(not vector(key,2) for key in keys) or keys[0][0] != 0 or keys[-1][0] != 1
                or keys[0][1] != plane.get('offset',0)
                or any(not 0 <= a[0] < b[0] <= 1 for a,b in zip(keys,keys[1:]))
                or not plane.get('parts')):
            raise ValueError('Animated section requires explicit parts and ordered finite offset keys covering the shot')
    if template == 'micro_zoom' and not shot.get('camera_focus_region'):
        raise ValueError('Micro zoom requires an authored focus region')
    if template == 'camera_follow' and not name(spec.get('follow')):
        raise ValueError('Camera follow requires a named asset object')
    if template == 'camera_follow' and shot.get('camera_focus_region'):
        raise ValueError('Camera follow cannot use a static focus region')
    anchors = spec.get('anchors', {})
    if not isinstance(anchors, dict) or len(anchors) > 16:
        raise ValueError('At most sixteen screen anchors per shot')
    for anchor_id, anchor in anchors.items():
        if not name(anchor_id) or not isinstance(anchor, dict) or not name(anchor.get('object')):
            raise ValueError('Anchor requires a named object')
        if 'evaluated_center' in anchor:
            if anchor['evaluated_center'] is not True or 'local' in anchor:
                raise ValueError('Choose either an evaluated mesh center or a local XYZ anchor')
        elif not vector(anchor.get('local'), 3):
            raise ValueError('Anchor requires a local XYZ triple or evaluated mesh center')
    if 'observation_window' in spec:
        validate_observation_window(spec['observation_window'])
        if not set(spec['observation_window']['anchors']) <= anchors.keys():
            raise ValueError('Observation window requires existing science anchors')
    if template == 'motion_trace' and spec.get('trace') not in anchors:
        raise ValueError('Motion trace requires a named object anchor')
    if template in {'motion_trace', 'field_visualization', 'flow_visualization'}:
        if not vector(spec.get('color'), 3) or not all(0 <= channel <= 1 for channel in spec['color']):
            raise ValueError('Curves require a linear RGB color in [0,1]')
        radius = spec.get('radius')
        if not number(radius) or radius <= 0:
            raise ValueError('Curves require a positive radius in scene units')
    if template in {'field_visualization', 'flow_visualization'}:
        paths = spec.get('paths')
        if not isinstance(paths, list) or not 1 <= len(paths) <= 64 or any(
            not isinstance(path, list) or not 2 <= len(path) <= 1024
            or not all(vector(point, 3) for point in path)
            or any(start == end for start, end in zip(path, path[1:])) for path in paths
        ):
            raise ValueError('Field and flow require bounded, nondegenerate XYZ polylines')
    if template == 'camera_follow' and {'camera_path_follow', 'camera_framing', 'camera_rig'} & spec.keys():
        raise ValueError('Blended tracking and the fixed follow template cannot drive the same camera')
    validate_editorial_geometry(spec)
    validate_motion_program(shot)


def validate_observation_window(window):
    if not isinstance(window, dict):
        raise ValueError('Observation window requires an object')
    anchors, progress = window.get('anchors'), window.get('progress')
    if (not isinstance(anchors, list) or not 1 <= len(anchors) <= 16
            or not all(map(name, anchors)) or len(set(anchors)) != len(anchors)
            or not vector(progress, 2) or not 0 <= progress[0] < progress[1] <= 1):
        raise ValueError('Observation window needs unique anchors and a positive normalized progress interval')


def validate_motion_program(shot):
    """Bound editorial visibility, synchronized time and numerical invariants."""
    spec = shot['science']
    if 'time_map' in spec:
        mapping = spec['time_map']
        if (spec.get('driver') != 'data_tracks' or not isinstance(mapping, list)
                or not 2 <= len(mapping) <= 64
                or any(not vector(key, 2) for key in mapping)
                or mapping[0] != [0, 0] or mapping[-1] != [1, 1]
                or any(not (0 <= a[0] < b[0] <= 1 and 0 <= a[1] <= b[1] <= 1)
                       for a, b in zip(mapping, mapping[1:]))):
            raise ValueError('Time map requires data tracks and monotone [screen, source] endpoints [0,0] to [1,1]')
    opacity = spec.get('opacity_tracks', [])
    if not isinstance(opacity, list) or len(opacity) > 32:
        raise ValueError('At most 32 object opacity tracks')
    seen = set()
    for track in opacity:
        if not isinstance(track, dict) or not name(track.get('object')) or track['object'] in seen:
            raise ValueError('Opacity tracks require unique assembly objects')
        seen.add(track['object'])
        keys = track.get('keys')
        if (not isinstance(keys, list) or not 2 <= len(keys) <= 64
                or any(not vector(key, 2) or not 0 <= key[1] <= 1 for key in keys)
                or keys[0][0] != 0 or keys[-1][0] != 1
                or any(a[0] >= b[0] for a, b in zip(keys, keys[1:]))):
            raise ValueError('Opacity keys require ordered [screen progress, opacity] in [0,1] with endpoints')
    constraints = spec.get('constraints', [])
    if not isinstance(constraints, list) or len(constraints) > 32:
        raise ValueError('At most 32 numerical constraints')
    for constraint in constraints:
        if not isinstance(constraint, dict):
            raise ValueError('Numerical constraint requires an object')
        kind = constraint.get('kind')
        if kind not in {'distance', 'path_length', 'motion', 'rotation_ratio', 'hinge', 'slider'}:
            raise ValueError('Unknown numerical constraint kind')
        if not number(constraint.get('tolerance', 0)) or constraint.get('tolerance', 0) < 0:
            raise ValueError('Numerical constraint requires a nonnegative finite tolerance')
        bounds = constraint.get('range')
        if kind in {'distance', 'motion', 'path_length'} and (not vector(bounds, 2) or not 0 <= bounds[0] <= bounds[1]):
            raise ValueError('Distance constraint or motion/path length requires a nonnegative range')
        refs = constraint.get('points')
        expected = {'distance': 2, 'motion': 1, 'rotation_ratio': 2, 'hinge': 4, 'slider': 6}.get(kind)
        if (not isinstance(refs, list)
                or (not 2 <= len(refs) <= 256 if kind == 'path_length' else len(refs) != expected)
                or any(not isinstance(ref, dict) or not name(ref.get('object'))
                       or not vector(ref.get('local', [0, 0, 0]), 3)
                       or ('vertex' in ref and (type(ref['vertex']) is not int or ref['vertex'] < 0))
                       for ref in refs)):
            raise ValueError('Distance constraint or motion/path length requires evaluated object points')
        if kind == 'rotation_ratio':
            if (any(type(ref.get('axis')) is not int or not 0 <= ref['axis'] <= 2
                    or 'vertex' in ref or 'local' in ref for ref in refs)
                    or not number(constraint.get('ratio')) or constraint['ratio'] == 0
                    or not number(constraint.get('minimum_driver_travel'))
                    or constraint['minimum_driver_travel'] <= 0):
                raise ValueError('Rotation ratio requires two local Euler axes, a signed nonzero ratio and positive driver travel')
        if kind == 'motion' and (bounds[0] <= 0
                or not number(constraint.get('max_step')) or constraint['max_step'] <= 0):
            raise ValueError('Motion requires positive minimum travel and maximum frame step')
        if kind == 'motion' and constraint.get('tolerance', 0) >= bounds[0]:
            raise ValueError('Motion tolerance must be smaller than the positive minimum travel')
        if kind in {'hinge', 'slider'}:
            owners = [ref['object'] for ref in refs]
            angle = constraint.get('max_axis_angle')
            half = len(owners) // 2
            if (len(set(owners[:half])) != 1 or len(set(owners[half:])) != 1 or owners[0] == owners[-1]
                    or not number(angle) or not 0 <= angle < math.pi / 2):
                raise ValueError('Joint requires two ordered datums on each of two distinct parts and a bounded axis angle')
            if kind == 'slider' and (not vector(bounds, 2) or bounds[0] > bounds[1]
                                     or bounds[1] - bounds[0] <= constraint.get('tolerance', 0)):
                raise ValueError('Slider requires a signed travel range wider than its tolerance')
        events = constraint.get('events', [])
        if not isinstance(events, list) or len(events) > 32 or (events and kind not in {'distance', 'path_length'}):
            raise ValueError('Event windows require distance/path length constraints; at most 32 events')
        for event in events:
            if (not isinstance(event, dict) or not vector(event.get('progress'), 2)
                    or not 0 <= event['progress'][0] <= event['progress'][1] <= 1
                    or not vector(event.get('range'), 2)
                    or not 0 <= event['range'][0] <= event['range'][1]):
                raise ValueError('Event requires a normalized output progress window and nonnegative range')


def source_progress(mapping, progress):
    """One bounded piecewise linear clock for every interacting data channel."""
    if not number(progress) or not 0 <= progress <= 1:
        raise ValueError('Output progress must stay inside the validated [0,1] interval')
    if not mapping:
        return progress
    for a, b in zip(mapping, mapping[1:]):
        if progress <= b[0]:
            mix = (progress - a[0]) / (b[0] - a[0])
            return a[1] + mix * (b[1] - a[1])
    return mapping[-1][1]


def retimed_progress_keys(mapping, source_keys):
    """Composition breakpoints, preserving source corners and authored holds.

    Evaluating the original linear F-curve at these source times gives the exact
    composition, including raw quaternion components and shape-key weights.
    """
    progress = {key[0] for key in mapping}
    for a, b in zip(mapping, mapping[1:]):
        if b[1] == a[1]:
            continue
        for key in source_keys:
            if a[1] <= key <= b[1]:
                progress.add(a[0] + (key - a[1]) * (b[0] - a[0]) / (b[1] - a[1]))
    return sorted(progress)


def centerline_strip(points, width, normal):
    """Author a zero-thickness ribbon from an evidenced winding/deformation path.

    Returns mesh vertices and quad topology for the existing asset/mesh_tracks
    interface. No tension, contact, thickness, arc-length or force is solved.
    All poses must use the same number/order of source centerline samples.
    """
    if (not isinstance(points, list) or not 2 <= len(points) <= 4096
            or not all(vector(point, 3) for point in points)
            or not number(width) or width <= 0 or not vector(normal, 3)
            or not any(normal)):
        raise ValueError('Ribbon requires finite centerline samples, positive width and nonzero normal')
    vertices = []
    for i, point in enumerate(points):
        before, after = points[max(0, i - 1)], points[min(len(points) - 1, i + 1)]
        tangent = [b - a for a, b in zip(before, after)]
        side = [tangent[1]*normal[2] - tangent[2]*normal[1],
                tangent[2]*normal[0] - tangent[0]*normal[2],
                tangent[0]*normal[1] - tangent[1]*normal[0]]
        length = math.hypot(*side)
        if length <= 1e-12 or (i and point == points[i-1]):
            raise ValueError('Ribbon samples must be distinct with a tangent transverse to the normal')
        for sign in (-1, 1):
            vertices.append([p + sign*width*s/(2*length) for p, s in zip(point, side)])
    faces = [[2*i, 2*i+1, 2*i+3, 2*i+2] for i in range(len(points)-1)]
    return {'vertices': vertices, 'faces': faces}


def validate_editorial_geometry(spec):
    if 'camera_rig' in spec:
        rig = spec['camera_rig']
        if (not isinstance(rig, dict) or rig.get('version') != 1
                or rig.get('mode') not in {'DOLLY', 'CRANE'} or not spec.get('camera_path')
                or 'camera_framing' in spec or 'camera_path_follow' in spec
                or not number(rig.get('lens_mm')) or not 18 <= rig['lens_mm'] <= 150
                or not vector(rig.get('clip'), 2) or not 0 < rig['clip'][0] < rig['clip'][1]):
            raise ValueError('Camera rig v1 requires official Dolly/Crane, existing path, focal length and clip range; no competing camera controller')
        if rig.get('follow') and (not isinstance(rig['follow'], dict)
                or not name(rig['follow'].get('object')) or not number(rig['follow'].get('weight'))
                or not 0 <= rig['follow']['weight'] <= 1):
            raise ValueError('Rig tracking requires an evaluated object and weight in [0,1]')
        if not isinstance(rig.get('inspect_markers', []), list) or any(not name(x) for x in rig.get('inspect_markers', [])):
            raise ValueError('Rig marker inspection requires named objects')
    if 'camera_framing' in spec:
        framing = spec['camera_framing']
        if (not isinstance(framing, dict) or type(framing.get('version')) is not int
                or framing['version'] != 1 or not isinstance(framing.get('parts'), list)
                or not framing['parts'] or not all(map(name, framing['parts']))
                or len(set(framing['parts'])) != len(framing['parts'])
                or framing.get('scale_mode', 'per_frame') not in ('per_frame', 'locked')
                or not spec.get('camera_path') or 'camera_path_follow' in spec):
            raise ValueError('Camera framing v1 requires unique parts and an unblended camera path')
    if 'camera_clip' in spec:
        clip = spec['camera_clip']
        if not vector(clip, 2) or not 0 < clip[0] < clip[1]:
            raise ValueError('Camera clip requires positive increasing near/far distances')
    if 'stage_rotation' in spec and not vector(spec['stage_rotation'], 3):
        raise ValueError('Stage rotation requires a finite XYZ Euler triple')
    if 'camera_path_follow' in spec and (
            not name(spec['camera_path_follow']) or not spec.get('camera_path')):
        raise ValueError('Blended tracking requires a named part and an authored camera path')
    if 'camera_path' in spec:
        path = spec['camera_path']
        if (not isinstance(path, list) or not 2 <= len(path) <= 16 or any(
                not isinstance(pose, dict) or not number(pose.get('progress'))
                or not vector(pose.get('target'), 3) or not vector(pose.get('direction'), 3)
                or not any(pose['direction']) or not number(pose.get('width')) or pose['width'] <= 0
                for pose in path) or path[0]['progress'] != 0 or path[-1]['progress'] != 1
                or any(a['progress'] >= b['progress'] for a, b in zip(path, path[1:]))):
            raise ValueError('Camera path requires ordered endpoints, aim, direction and orthographic width')
        for start, end in zip(path, path[1:]):
            a, b = start['direction'], end['direction']
            if sum(x*y for x,y in zip(a,b))/(math.hypot(*a)*math.hypot(*b)) < -.95:
                raise ValueError('Add an intermediate camera key for oppositely directed views')
            if start.get('easing_to_next', 'smoothstep') not in ('smoothstep', 'ease_out_cubic'):
                raise ValueError('Unknown camera segment easing')
        if 'easing_to_next' in path[-1]:
            raise ValueError('Camera easing requires a following pose')
        for pose in path:
            if 'camera_framing' in spec and (
                    pose['width'] < 1 or any(abs(v) > .4 for v in pose['target'][:2])
                    or pose['target'][2] != 0):
                raise ValueError('Relative framing requires width >= 1 and normalized XY screen offsets')
            if 'follow_weight' in pose and (
                    not spec.get('camera_path_follow') or not number(pose['follow_weight'])
                    or not 0 <= pose['follow_weight'] <= 1):
                raise ValueError('Camera follow weights require a tracked part and values from zero to one')
    for key in ('guides', 'print_marks'):
        items = spec.get(key, [])
        if not isinstance(items, list) or len(items) > 16:
            raise ValueError(f'At most sixteen {key} per shot')
        for item in items:
            if (not isinstance(item, dict) or not vector(item.get('color'), 3)
                    or not all(0 <= c <= 1 for c in item['color'])):
                raise ValueError('Editorial mark requires linear RGB')
            if key == 'print_marks':
                if (not name(item.get('object')) or not name(item.get('text')) or len(item['text']) > 80
                        or not number(item.get('size')) or item['size'] <= 0 or not vector(item.get('local'), 3)
                        or not vector(item.get('rotation_euler'), 3)):
                    raise ValueError('Printed marks require a surface object, local placement, text and scale')
                continue
            kind = item.get('kind')
            points = item.get('points')
            active = item.get('window', [0, 1])
            if (kind not in {'arrow','dashed','marker'} or not number(item.get('width')) or item['width'] <= 0
                    or not vector(active, 2) or not 0 <= active[0] < active[1] <= 1
                    or not isinstance(points, list) or len(points) != (1 if kind == 'marker' else 2)
                    or any(not isinstance(ref, dict) or not name(ref.get('object'))
                           or not vector(ref.get('local', [0,0,0]), 3)
                           or ('vertex' in ref and (type(ref['vertex']) is not int or ref['vertex'] < 0))
                           for ref in points)):
                raise ValueError('Guide requires evaluated object points, visible time and positive width')


def referenced_parts(shot):
    spec = shot.get('science', {})
    parts = {anchor['object'] for anchor in spec.get('anchors', {}).values()}
    parts.update(point['object'] for guide in spec.get('guides', []) for point in guide['points'])
    parts.update(mark['object'] for mark in spec.get('print_marks', []))
    parts.update(track['object'] for track in spec.get('opacity_tracks', []))
    parts.update(ref['object'] for row in spec.get('constraints', []) for ref in row['points'])
    parts.update(spec.get('camera_framing', {}).get('parts', []))
    parts.update(spec.get('camera_rig', {}).get('inspect_markers', []))
    if spec.get('camera_rig', {}).get('follow'):
        parts.add(spec['camera_rig']['follow']['object'])
    if spec.get('follow'):
        parts.add(spec['follow'])
    if spec.get('camera_path_follow'):
        parts.add(spec['camera_path_follow'])
    if shot.get('section_plane'):
        parts.update(shot['section_plane'].get('parts', []))
    return parts


def validate_asset(assembly, mechanism_id=None):
    reuse = assembly.get('reuse')
    if reuse is None:
        return
    if (not isinstance(reuse, dict) or reuse.get('version') != 1
            or not all(name(reuse.get(key)) for key in ('mechanism_id', 'license', 'scope', 'units'))
            or not reuse.get('sources') or not reuse.get('limitations')):
        raise ValueError('Reusable asset requires exact mechanism, units, rights, scope, source and limits')
    if mechanism_id is not None and reuse['mechanism_id'] != mechanism_id:
        raise ValueError('Reusable asset belongs to a different implementation')
    for row in reuse['sources']:
        source_binding(row)
    if 'generator' in reuse:
        source_binding(reuse['generator'])
    parts = reuse.get('parts', {})
    if not isinstance(parts, dict) or set(parts) != set(assembly['required_parts']):
        raise ValueError('Reusable asset must describe every required part exactly')
    for part, record in parts.items():
        parent = record.get('parent')
        if parent is not None and (parent not in parts or parent == part):
            raise ValueError('Unknown or self-parented reusable part')
        visited = {part}
        while parent is not None:
            if parent in visited or parent not in parts:
                raise ValueError('Invalid reusable part hierarchy')
            visited.add(parent)
            parent = parts[parent].get('parent')
        if not name(record.get('material')):
            raise ValueError('Reusable parts require material descriptions')
    controls = reuse.get('controls', {})
    if not isinstance(controls, dict):
        raise ValueError('Reusable asset controls must be keyed by name')
    for control in controls.values():
        if (control.get('driver') not in {'asset_motion', 'data_tracks'}
                or not control.get('parts') or not set(control['parts']) <= set(parts)
                or not name(control.get('constraint')) or not name(control.get('dof'))):
            raise ValueError('Control requires known parts, executable driver, constraint and degrees of freedom')


def validate_assembly_shot(shot, assembly):
    spec = shot.get('science')
    if not spec:
        return
    validate(shot, files=True)
    if spec.get('camera_rig'):
        rig = spec['camera_rig']
        names = set(rig.get('inspect_markers', []))
        if rig.get('follow'):
            names.add(rig['follow']['object'])
        available = set(shot.get('visible_parts') or assembly.get('required_parts', []))
        available.update(assembly.get('reuse', {}).get('parts', {}))
        if not names <= available:
            raise ValueError('Camera rig requires visible assembly targets: ' + ', '.join(sorted(names-available)))
    if spec.get('driver') == 'asset_motion':
        control = assembly.get('reuse', {}).get('controls', {}).get(spec.get('control'))
        if not control or control['driver'] != 'asset_motion':
            raise ValueError('Asset motion requires a declared reusable control')
        if assembly.get('kind') == 'source-mesh-assembly-v1':
            raise ValueError('Imported assembly motion requires explicit data tracks')
