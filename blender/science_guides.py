"""Opt-in camera staging and evidence-linked geometry guides, not CAD parts."""

import bpy
from mathutils import Euler, Vector

from science_scene import target


def stage(scene, parts, spec):
    if 'stage_rotation' not in spec:
        return
    root = bpy.data.objects.new('Editorial stage', None)
    scene.collection.objects.link(root)
    for part in parts:
        if part.parent is None:
            part.parent = root
    root.rotation_euler = Euler(spec['stage_rotation'])


def camera_motion(scene, camera, poses, count, linear_action, followed=None, framing=()):
    if followed is not None:
        scene.frame_set(1)
        origin = followed.matrix_world.translation.copy()
    index = 0
    for frame in range(1, count + 1):
        progress = (frame - 1) / max(1, count - 1)
        while progress > poses[index+1]['progress']:
            index += 1
        start, end = poses[index:index+2]
        mix = (progress - start['progress']) / (end['progress'] - start['progress'])
        mix = mix * mix * (3 - 2 * mix)
        center = Vector(start['target']).lerp(Vector(end['target']), mix)
        if followed is not None:
            scene.frame_set(frame)
            weight = start.get('follow_weight', 0) * (1 - mix) + end.get('follow_weight', 0) * mix
            center += (followed.matrix_world.translation - origin) * weight
        direction = Vector(start['direction']).normalized().lerp(Vector(end['direction']).normalized(), mix).normalized()
        rotation = (-direction).to_track_quat('-Z', 'Y')
        width = start['width'] * (1 - mix) + end['width'] * mix
        distance = 30
        if framing:
            scene.frame_set(frame)
            center, width, distance = fit_camera(scene, rotation, framing, center, width)
        camera.location = center + direction * distance
        camera.rotation_euler = rotation.to_euler('XYZ', camera.rotation_euler)
        camera.data.ortho_scale = width
        camera.keyframe_insert('location', frame=frame)
        camera.keyframe_insert('rotation_euler', frame=frame)
        camera.data.keyframe_insert('ortho_scale', frame=frame)
    linear_action(camera.animation_data)
    linear_action(camera.data.animation_data)
    scene.frame_set(1)


def evaluated_bounds(objects):
    graph = bpy.context.evaluated_depsgraph_get()
    for obj in objects:
        evaluated = obj.evaluated_get(graph)
        for corner in evaluated.bound_box:
            yield evaluated.matrix_world @ Vector(corner)


def fit_camera(scene, rotation, objects, offset, padding):
    inverse = rotation.inverted()
    points = [inverse @ point for point in evaluated_bounds(objects)]
    low = Vector(tuple(min(point[i] for point in points) for i in range(3)))
    high = Vector(tuple(max(point[i] for point in points) for i in range(3)))
    span = high - low
    aspect = scene.render.resolution_x / scene.render.resolution_y
    width = max(span.x / (.97 - 2 * abs(offset.x)),
                span.y * aspect / (.97 - 2 * abs(offset.y)), 1e-6) * padding
    center = (low + high) / 2
    center -= Vector((offset.x * width, offset.y * width / aspect, 0))
    distance = max(scene.camera.data.clip_start * 2, span.z / 2 + width * 2)
    return rotation @ center, width / min(1, aspect), distance


def point(ref, objects, depsgraph):
    obj = objects[ref['object']].evaluated_get(depsgraph)
    local = (obj.data.vertices[ref['vertex']].co.copy() if 'vertex' in ref else Vector((0, 0, 0)))
    local += Vector(ref.get('local', (0, 0, 0)))
    return obj.matrix_world @ local


def ink(color):
    material = bpy.data.materials.new('Guide ink')
    material.diffuse_color = (*color, 1)
    material.use_nodes = True
    nodes = material.node_tree.nodes
    emission = nodes.new('ShaderNodeEmission')
    emission.inputs['Color'].default_value = material.diffuse_color
    material.node_tree.links.new(emission.outputs[0], nodes.get('Material Output').inputs['Surface'])
    return material


def primitive(kind, radius, material):
    if kind == 'line':
        bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=radius, depth=1)
    elif kind == 'tip':
        bpy.ops.mesh.primitive_cone_add(vertices=16, radius1=radius * 2.2, depth=1)
    else:
        bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=8, radius=radius)
    obj = bpy.context.object
    obj.name = 'Editorial ' + kind
    obj.data.materials.append(material)
    obj.rotation_mode = 'QUATERNION'
    return obj


def place(obj, start, end, frame):
    delta = end - start
    obj.location = (start + end) / 2
    if delta.length > 1e-9:
        rotation = delta.normalized().to_track_quat('Z', 'Y')
        if obj.rotation_quaternion.dot(rotation) < 0:
            rotation.negate()
        obj.rotation_quaternion = rotation
    obj.scale.z = delta.length
    for channel in ('location', 'rotation_quaternion', 'scale'):
        obj.keyframe_insert(channel, frame=frame)


def add_guides(scene, parts, items, count, linear_action):
    active_frames = []
    for item in items:
        refs = item['points']
        objects = {ref['object']: target(parts, ref['object']) for ref in refs}
        for ref in refs:
            if 'vertex' in ref and ref['vertex'] >= len(objects[ref['object']].data.vertices):
                raise ValueError('Guide vertex outside source mesh')
        material = ink(item['color'])
        radius = item['width']
        kind = item['kind']
        if kind == 'marker':
            geometry = [primitive('marker', radius, material)]
        elif kind == 'dashed':
            geometry = [primitive('line', radius, material) for _ in range(8)]
        else:
            geometry = [primitive('line', radius, material), primitive('tip', radius, material)]
        first, last = (1 + round(progress * (count - 1)) for progress in item.get('window', [0, 1]))
        for obj in geometry:
            for frame, hidden in ((first - 1, True), (first, False), (last, False), (last + 1, True)):
                obj.hide_render = hidden
                obj.keyframe_insert('hide_render', frame=frame)
        for frame in range(first, last + 1):
            scene.frame_set(frame)
            depsgraph = bpy.context.evaluated_depsgraph_get()
            points = [point(ref, objects, depsgraph) for ref in refs]
            if kind == 'marker':
                geometry[0].location = points[0]
                geometry[0].keyframe_insert('location', frame=frame)
            elif kind == 'dashed':
                for index, obj in enumerate(geometry):
                    place(obj, points[0].lerp(points[1], index / 8), points[0].lerp(points[1], (index + .57) / 8), frame)
            else:
                length = (points[1] - points[0]).length
                middle = points[1].lerp(points[0], min(.48, 5 * radius / max(length, 1e-9)))
                place(geometry[0], points[0], middle, frame)
                place(geometry[1], middle, points[1], frame)
        for obj in geometry:
            linear_action(obj.animation_data)
        active_frames.append({'kind': kind, 'first_frame': first, 'last_frame': last})
    return {'guides': active_frames, 'scope': 'Illustrative geometry anchored to evaluated poses; not mechanical parts or force vectors'}


def add_print(parts, marks):
    for mark in marks:
        surface = target(parts, mark['object'])
        data = bpy.data.curves.new('Editorial print', 'FONT')
        data.body = mark['text']
        data.size = mark['size']
        data.materials.append(ink(mark['color']))
        obj = bpy.data.objects.new('Editorial print', data)
        bpy.context.scene.collection.objects.link(obj)
        obj.parent = surface
        obj.location = mark['local']
        obj.rotation_euler = mark['rotation_euler']
