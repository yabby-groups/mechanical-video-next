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
    return obj.matrix_world @ Vector(anchor['local'])


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


def check_constraints(scene, parts, constraints, count):
    """Check supplied distances in every evaluated output frame; never solve them."""
    from science_guides import point
    receipts = []
    for item in constraints:
        objects = {ref['object']: target(parts, ref['object']) for ref in item['points']}
        for ref in item['points']:
            if 'vertex' in ref and ref['vertex'] >= len(objects[ref['object']].data.vertices):
                raise ValueError('Constraint vertex outside source mesh')
            if 'vertex' in ref and objects[ref['object']].modifiers:
                raise ValueError('Vertex constraints require stable topology without modifiers')
        distances = []
        lo, hi = item['range']
        tolerance = item.get('tolerance', 0)
        for frame in range(1, count + 1):
            scene.frame_set(frame)
            bpy.context.view_layer.update()
            depsgraph = bpy.context.evaluated_depsgraph_get()
            a, b = [point(ref, objects, depsgraph) for ref in item['points']]
            distance = (a - b).length
            if not lo - tolerance <= distance <= hi + tolerance:
                raise ValueError(f'Distance constraint failed at frame {frame}: {distance} outside {item["range"]}')
            distances.append(distance)
        receipts.append({'kind': 'distance', 'points': item['points'], 'range': item['range'],
                         'tolerance': tolerance, 'minimum': min(distances), 'maximum': max(distances)})
    return {'status': 'PASS', 'frame_count': count, 'samples': receipts,
            'scope': 'Evaluated frame distances only; not a constraint solver, subframe, contact or force proof'}
