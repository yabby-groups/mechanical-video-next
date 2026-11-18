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
