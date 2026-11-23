"""Opt-in science templates built on the existing Blender shot and camera."""

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector


def target(parts, name):
    obj = next((part for part in parts if part.name == name and not part.hide_render), None)
    if obj is None:
        raise ValueError(f'Science target must be a visible assembly part: {name}')
    return obj


def anchor_world(obj, anchor):
    if anchor.get('evaluated_center') is True:
        return marker_center(obj)
    return obj.matrix_world @ Vector(anchor['local'])


def marker_center(obj):
    """Centroid of the evaluated native mesh, including animated shape keys."""
    mesh = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    if mesh.type != 'MESH' or not mesh.data.vertices:
        raise ValueError(f'Evaluated center requires a nonempty mesh: {obj.name}')
    center = sum((vertex.co for vertex in mesh.data.vertices), Vector()) / len(mesh.data.vertices)
    return mesh.matrix_world @ center


def curve(scene, points, radius, material, label):
    data = bpy.data.curves.new(label, 'CURVE')
    data.dimensions = '3D'
    data.bevel_depth = radius
    data.bevel_resolution = 3
    path = data.splines.new('POLY')
    path.points.add(len(points) - 1)
    for control, position in zip(path.points, points):
        control.co = (*position, 1)
    obj = bpy.data.objects.new(label, data)
    scene.collection.objects.link(obj)
    data.materials.append(material)
    return obj


def add_curves(shot, scene, count, parts, linear_action):
    template, spec = shot['template'], shot['science']
    paths = spec.get('paths', [])
    if template == 'motion_trace':
        anchor = spec['anchors'][spec['trace']]
        obj = target(parts, anchor['object'])
        trace = []
        for frame in range(1, count + 1):
            scene.frame_set(frame)
            trace.append(anchor_world(obj, anchor))
        if max((point - trace[0]).length for point in trace) <= 1e-7:
            raise ValueError('Motion trace anchor does not move')
        paths = [trace]
    material = bpy.data.materials.new('Science | evidence visualization')
    material.diffuse_color = (*spec['color'], 1)
    material.use_nodes = True
    nodes = material.node_tree.nodes
    shader = nodes.get('Principled BSDF')
    shader.inputs['Base Color'].default_value = material.diffuse_color
    shader.inputs['Emission Color'].default_value = material.diffuse_color
    shader.inputs['Emission Strength'].default_value = .35
    for index, points in enumerate(paths):
        guide = curve(scene, points, spec['radius'], material, f'SciencePath.{index:02d}')
        if template == 'motion_trace':
            guide.data.bevel_factor_end = 0
            guide.data.keyframe_insert('bevel_factor_end', frame=1)
            guide.data.bevel_factor_end = 1
            guide.data.keyframe_insert('bevel_factor_end', frame=count)
            linear_action(guide.data.animation_data)
        if template == 'flow_visualization':
            bpy.ops.mesh.primitive_uv_sphere_add(segments=12, ring_count=8, radius=spec['radius'] * 3)
            marker = bpy.context.object
            marker.name = f'ScienceFlow.{index:02d}'
            marker.data.materials.append(material)
            distances = [0]
            for start, end in zip(points, points[1:]):
                distances.append(distances[-1] + (Vector(end) - Vector(start)).length)
            for point, distance in zip(points, distances):
                marker.location = point
                marker.keyframe_insert('location', frame=1 + (count - 1) * distance / distances[-1])
            linear_action(marker.animation_data)
    return {'paths': len(paths), 'point_counts': [len(path) for path in paths]}


def follow_camera(scene, camera, parts, name, count, linear_action):
    obj = target(parts, name)
    scene.frame_set(1)
    origin, location = obj.matrix_world.translation.copy(), camera.location.copy()
    for frame in range(1, count + 1):
        scene.frame_set(frame)
        camera.location = location + obj.matrix_world.translation - origin
        camera.keyframe_insert('location', frame=frame)
    linear_action(camera.animation_data)


def project(scene, camera, parts, anchors, count):
    objects = {key: target(parts, anchor['object']) for key, anchor in anchors.items()}
    samples = {key: [] for key in anchors}
    for frame in range(1, count + 1):
        scene.frame_set(frame)
        for key, anchor in anchors.items():
            position = anchor_world(objects[key], anchor)
            point = world_to_camera_view(scene, camera, position)
            valid = point.z > 0 and 0 <= point.x <= 1 and 0 <= point.y <= 1
            samples[key].append([round(point.x, 6), round(1 - point.y, 6)] if valid else None)
    return {'version': 1, 'fps': scene.render.fps, 'frame_count': count, 'samples': samples,
            'scope': 'Evaluated camera projection, not occlusion or readability QA'}


def observation_projection(projected, window):
    first, last = window['progress']
    count = projected['frame_count']
    frames = [i for i in range(count) if first <= i / max(1, count - 1) <= last]
    if not frames:
        raise ValueError('Observation window contains no evaluated output frames')
    results = {}
    for name in window['anchors']:
        points = projected['samples'][name]
        missing = [i for i in frames if points[i] is None]
        results[name] = {'offscreen_frames': len(missing), 'first_offscreen_frame': missing[0] + 1 if missing else None}
    return {'frame_range': [frames[0] + 1, frames[-1] + 1], 'anchors': results,
            'status': 'FAIL' if any(row['offscreen_frames'] for row in results.values()) else 'PASS',
            'scope': 'Frustum inclusion of the declared datums; occlusion, overlays and comprehension require separate review'}


def retime_data(shot, parts, count):
    """Compose the same monotone clock with each rigid and deforming F-curve."""
    from mechanical_video_next.science_shots import retimed_progress_keys, source_progress
    mapping = shot['science'].get('time_map')
    if not mapping:
        return
    objects = {obj.name: obj for obj in parts}
    owners = [objects[track['object']] for track in shot.get('tracks', [])]
    owners += [objects[track['object']].data.shape_keys for track in shot.get('mesh_tracks', [])]
    seen = set()
    for owner in owners:
        animation = owner.animation_data
        if animation is None or animation.action is None:
            continue
        action = animation.action
        curves = list(getattr(action, 'fcurves', []))
        for layer in getattr(action, 'layers', []):
            for strip in layer.strips:
                for bag in getattr(strip, 'channelbags', []):
                    curves.extend(bag.fcurves)
        for fcurve in curves:
            # A shared action can be reached by more than one owner.
            pointer = fcurve.as_pointer()
            if pointer in seen:
                continue
            seen.add(pointer)
            times = retimed_progress_keys(mapping, [(key.co.x - 1)/(count - 1)
                                                    for key in fcurve.keyframe_points])
            samples = [(1 + progress*(count - 1),
                        fcurve.evaluate(1 + source_progress(mapping, progress)*(count - 1)))
                       for progress in times]
            fcurve.keyframe_points.clear()
            fcurve.keyframe_points.add(len(samples))
            for key, sample in zip(fcurve.keyframe_points, samples):
                key.co = sample
                key.interpolation = 'LINEAR'
            fcurve.extrapolation = 'CONSTANT'
            fcurve.update()


def disassembly(scene, parts, plan, count):
    """Animate editorial offsets from the existing installed mesh transforms."""
    from mechanical_video_next.science_shots import disassembly_frames

    scene.frame_set(1)
    anchor = target(parts, plan['anchor'])
    moved = [target(parts, name) for name in plan['parts']]
    for obj in [anchor, *moved]:
        parent = obj
        while parent is not None:
            if parent.animation_data or parent.constraints or (parent is not obj and parent in moved):
                raise ValueError('Disassembly needs a static assembly pose with independent moved parts')
            parent = parent.parent
    program = disassembly_frames(plan)
    for obj in moved:
        installed = obj.location.copy()
        displacement = Vector(plan['parts'][obj.name])
        for progress, amount in program:
            frame = 1 + progress * (count - 1)
            obj.location = installed + amount * displacement
            obj.keyframe_insert('location', frame=frame)
    frames = sorted({1, count, *(round(1 + t * (count - 1)) for t, _ in program)})
    samples = []
    for frame in frames:
        scene.frame_set(frame)
        samples.append({'frame': frame, 'anchor': list(anchor.matrix_world.translation),
                        'relative_positions': {obj.name: list(obj.matrix_world.translation
                                                             - anchor.matrix_world.translation)
                                               for obj in moved}})
    scene.frame_set(1)
    return {'operation': plan['operation'], 'anchor': anchor.name,
            'parts': [obj.name for obj in moved], 'frames': frames, 'samples': samples,
            'scope': 'Editorial separation relative to the installed pose'}


def check_disassembly_targets(scene, camera, parts, plan, frames):
    """Check declared retained-part datums against evaluated render geometry."""
    targets = plan.get('reveal_targets', {})
    if not targets:
        return []
    reveal_frames = frames[-1:] if plan['operation'] == 'disassemble' else frames[1:-1]
    if not reveal_frames:
        return []
    results = []
    for frame in reveal_frames:
        scene.frame_set(frame)
        depsgraph = bpy.context.evaluated_depsgraph_get()
        camera_pos = camera.matrix_world.translation
        view_axis = camera.matrix_world.to_quaternion() @ Vector((0, 0, -1))
        for name, local in targets.items():
            obj = target(parts, name)
            point = obj.matrix_world @ Vector(local)
            screen = world_to_camera_view(scene, camera, point)
            if not (screen.z > 0 and 0 <= screen.x <= 1 and 0 <= screen.y <= 1):
                raise ValueError(f'Disassembly target {name} is outside the frame at {frame}')
            origin = point - view_axis * screen.z if camera.data.type == 'ORTHO' else camera_pos
            ray = point - origin
            hit, _, _, _, blocker, _ = scene.ray_cast(depsgraph, origin, ray.normalized(),
                                                       distance=max(0, ray.length - 1e-5))
            if hit and blocker != obj and not blocker.hide_render:
                raise ValueError(f'Disassembly target {name} is occluded by {blocker.name} at {frame}')
            results.append({'frame': frame, 'part': name, 'projection': [screen.x, screen.y]})
    return results


def opacity_tracks(parts, tracks, count, linear_action):
    """Copy per-object shaders; preserve approved material shading underneath."""
    receipts = []
    for track in tracks:
        obj = target(parts, track['object'])
        if not obj.material_slots:
            raise ValueError('Opacity target requires an existing material')
        for slot in obj.material_slots:
            if slot.material is None or not slot.material.use_nodes:
                raise ValueError('Opacity target requires node-based material slots')
            material = slot.material.copy()
            material.name = obj.name + ' | editorial opacity'
            # OBJECT assignment avoids changing a mesh shared with another part.
            slot.link = 'OBJECT'
            slot.material = material
            if hasattr(material, 'surface_render_method'):
                material.surface_render_method = 'DITHERED'
            else:
                material.blend_method = 'HASHED'
            nodes, links = material.node_tree.nodes, material.node_tree.links
            output = next((node for node in nodes if node.type == 'OUTPUT_MATERIAL'
                           and node.is_active_output), None)
            if output is None or not output.inputs['Surface'].is_linked:
                raise ValueError('Opacity target needs an active connected surface shader')
            previous = output.inputs['Surface'].links[0].from_socket
            transparent = nodes.new('ShaderNodeBsdfTransparent')
            mix = nodes.new('ShaderNodeMixShader')
            links.new(transparent.outputs[0], mix.inputs[1])
            links.new(previous, mix.inputs[2])
            links.new(mix.outputs[0], output.inputs['Surface'])
            for progress, value in track['keys']:
                mix.inputs[0].default_value = value
                mix.inputs[0].keyframe_insert('default_value', frame=1 + progress*(count - 1))
            linear_action(material.node_tree.animation_data)
        receipts.append({'object': obj.name, 'keys': track['keys']})
    return {'objects': receipts, 'clock': 'screen progress; independent of mechanism retiming',
            'scope': 'Editorial transparency; not material transmission, optical simulation or occlusion QA'}


def check_joint(kind, points, item, frame):
    from math import atan2, isfinite

    offset = len(points) // 2
    a, b = points[:2]
    c, d = points[offset:offset+2]
    reference, moving = b - a, d - c
    if min(reference.length, moving.length) <= max(1e-12, item.get('tolerance', 0)):
        raise ValueError(f'Degenerate {kind} axis at frame {frame}')
    reference.normalize()
    moving.normalize()
    angle = atan2(reference.cross(moving).length, reference.dot(moving))
    delta = c - a
    axial = delta.dot(reference)
    error = delta.length if kind == 'hinge' else (delta - axial * reference).length
    tolerance = item.get('tolerance', 0)
    if (not all(map(isfinite, (angle, error, axial))) or angle > item['max_axis_angle']
            or error > tolerance):
        raise ValueError(f'{kind} joint alignment failed at frame {frame}: offset {error}, angle {angle}')
    if kind == 'slider':
        transverse = points[2] - a
        transverse -= reference * transverse.dot(reference)
        follower_side = points[-1] - c
        follower_side -= moving * follower_side.dot(moving)
        if min(transverse.length, follower_side.length) <= max(1e-12, tolerance):
            raise ValueError(f'Degenerate slider clocking datum at frame {frame}')
        transverse.normalize()
        follower_side.normalize()
        twist = atan2(transverse.cross(follower_side).length, transverse.dot(follower_side))
        if not isfinite(twist) or twist > item['max_axis_angle']:
            raise ValueError(f'Slider clocking failed at frame {frame}: angular offset {twist}')
        angle = max(angle, twist)
        lo, hi = item['range']
        if not lo - tolerance <= axial <= hi + tolerance:
            raise ValueError(f'Slider travel failed at frame {frame}: axis position {axial}')
    return error, angle, axial


def check_constraints(scene, parts, constraints, count):
    """Check declared output-frame kinematics; never solve dynamics or contact."""
    import math
    from science_guides import point
    if type(count) is not int or count < 1:
        raise ValueError('Constraint evaluation requires a positive output frame count')
    receipts = []
    for item in constraints:
        kind = item['kind']
        if kind in {'motion', 'rotation_ratio'} and count < 2:
            raise ValueError('Motion constraints require at least two evaluated frames')
        objects = {ref['object']: target(parts, ref['object']) for ref in item['points']}
        for ref in item['points']:
            if 'vertex' in ref and ref['vertex'] >= len(objects[ref['object']].data.vertices):
                raise ValueError('Constraint vertex outside source mesh')
            if 'vertex' in ref and objects[ref['object']].modifiers:
                raise ValueError('Vertex constraints require stable topology without modifiers')
        values = []
        joint_angles, joint_positions, driver_angles = [], [], []
        tolerance = item.get('tolerance', 0)
        previous = None
        initial_angles = None
        driver_travel = 0
        driver_excursion = follower_excursion = 0
        hits = [None] * len(item.get('events', []))
        for frame in range(1, count + 1):
            scene.frame_set(frame)
            bpy.context.view_layer.update()
            depsgraph = bpy.context.evaluated_depsgraph_get()
            if kind == 'rotation_ratio':
                angles = []
                for ref in item['points']:
                    source = objects[ref['object']]
                    if source.parent is not None:
                        raise ValueError('Rotation ratio requires unparented objects; parent transforms are outside the local Euler check')
                    if source.constraints:
                        raise ValueError('Rotation ratio cannot infer constrained transforms from local Euler channels')
                    obj = source.evaluated_get(depsgraph)
                    if obj.rotation_mode not in {'XYZ', 'XZY', 'YXZ', 'YZX', 'ZXY', 'ZYX'}:
                        raise ValueError('Rotation ratio requires local Euler rotation channels')
                    angle = obj.rotation_euler[ref['axis']]
                    if not math.isfinite(angle):
                        raise ValueError(f'Nonfinite rotation constraint at frame {frame}')
                    angles.append(angle)
                if initial_angles is None:
                    initial_angles = angles
                driver_angles.append(angles[0])
                driver_excursion = max(driver_excursion, abs(angles[0] - initial_angles[0]))
                follower_excursion = max(follower_excursion, abs(angles[1] - initial_angles[1]))
                if previous is not None:
                    driver_travel += abs(angles[0] - previous[0])
                value = (angles[1] - initial_angles[1]) - item['ratio'] * (angles[0] - initial_angles[0])
                if not math.isfinite(value) or abs(value) > tolerance:
                    raise ValueError(f'Rotation ratio constraint failed at frame {frame}: residual {value}')
                previous = angles
            else:
                points = [point(ref, objects, depsgraph) for ref in item['points']]
                if kind in {'hinge', 'slider'}:
                    value, angle, position = check_joint(kind, points, item, frame)
                    joint_angles.append(angle)
                    joint_positions.append(position)
                elif kind == 'motion':
                    value = 0 if previous is None else (points[0] - previous).length
                    if not math.isfinite(value) or value > item['max_step'] + tolerance:
                        raise ValueError(f'Motion frame step failed at frame {frame}: {value}')
                    previous = points[0].copy()
                else:
                    value = sum((a - b).length for a, b in zip(points, points[1:]))
                    lo, hi = item['range']
                    if not math.isfinite(value) or not lo - tolerance <= value <= hi + tolerance:
                        raise ValueError(f'Distance constraint ({kind}) failed at frame {frame}: {value} outside {item["range"]}')
                    progress = (frame - 1) / (count - 1) if count > 1 else 0
                    for index, event in enumerate(item.get('events', [])):
                        start, end = event['progress']
                        lower, upper = event['range']
                        if start <= progress <= end and lower - tolerance <= value <= upper + tolerance:
                            hits[index] = frame if hits[index] is None else hits[index]
            values.append(value)
        receipt = {'kind': kind, 'points': item['points'], 'tolerance': tolerance,
                   'minimum': min(values), 'maximum': max(values)}
        # Existing numerical measurements, in native render-frame order.
        # Retain signed joint or driver movement for edit review.
        if kind == 'rotation_ratio':
            receipt['review_unit'] = 'radians'
            receipt['review_samples'] = driver_angles
        elif kind in {'hinge', 'slider'}:
            receipt['review_unit'] = 'scene units'
            receipt['review_samples'] = joint_positions
        else:
            receipt['review_unit'] = 'scene units'
            receipt['review_samples'] = values
        if kind == 'rotation_ratio':
            if driver_travel < item['minimum_driver_travel']:
                raise ValueError('Rotation ratio driver is static or has insufficient travel')
            if (abs(item['ratio'])*driver_excursion <= tolerance or follower_excursion <= tolerance):
                raise ValueError('Rotation ratio tolerance masks expected or observed follower motion')
            receipt.update(ratio=item['ratio'], driver_travel=driver_travel,
                           driver_excursion=driver_excursion, follower_excursion=follower_excursion,
                           maximum_residual=max(map(abs, values)))
        elif kind == 'motion':
            total = sum(values)
            lo, hi = item['range']
            if total <= tolerance:
                raise ValueError('Motion travel is indistinguishable from zero at the declared tolerance')
            if not lo - tolerance <= total <= hi + tolerance:
                raise ValueError(f'Motion travel constraint failed: {total} outside {item["range"]}')
            receipt.update(range=item['range'], total_travel=total, max_step=item['max_step'])
        elif kind in {'hinge', 'slider'}:
            receipt.update(level='M2', max_axis_angle=max(joint_angles),
                           axis_angle_limit=item['max_axis_angle'],
                           axial_position_range=[min(joint_positions), max(joint_positions)])
            if kind == 'slider':
                receipt['range'] = item['range']
        else:
            if any(hit is None for hit in hits):
                raise ValueError(f'Missing constraint event windows: {[i for i, hit in enumerate(hits) if hit is None]}')
            receipt.update(range=item['range'])
            if hits:
                receipt['events'] = [dict(event, observed_frame=hit)
                                     for event, hit in zip(item['events'], hits)]
        receipts.append(receipt)
    return {'status': 'PASS', 'physics_status': 'KINEMATIC_ONLY',
            'frame_count': count, 'samples': receipts,
            'scope': 'Declared evaluated output-frame points, axes and local Euler channels only; '
                     'not a constraint solver, subframe, collision/contact, force or physical simulation proof'}
