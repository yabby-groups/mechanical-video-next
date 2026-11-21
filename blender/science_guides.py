"""Opt-in camera staging and evidence-linked geometry guides, not CAD parts."""

import bpy
from mathutils import Euler, Vector

from science_scene import marker_center, target


def stage(scene, parts, spec):
    if 'stage_rotation' not in spec:
        return
    root = bpy.data.objects.new('Editorial stage', None)
    scene.collection.objects.link(root)
    for part in parts:
        if part.parent is None:
            part.parent = root
    root.rotation_euler = Euler(spec['stage_rotation'])


def camera_motion(scene, camera, poses, count, linear_action, followed=None, framing=(), rig_spec=None,
                  parts=(), lock_scale=False):
    if rig_spec:
        return camera_rig_motion(scene, camera, poses, count, linear_action, rig_spec, parts)
    if followed is not None:
        scene.frame_set(1)
        origin = followed.matrix_world.translation.copy()
    index = 0
    fitted = []
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
            if lock_scale:
                fitted.append((rotation, center, *camera_bounds(rotation, framing), width))
                continue
            center, width, distance = fit_camera(scene, rotation, framing, center, width)
        camera.location = center + direction * distance
        camera.rotation_euler = rotation.to_euler('XYZ', camera.rotation_euler)
        camera.data.ortho_scale = width
        camera.keyframe_insert('location', frame=frame)
        camera.keyframe_insert('rotation_euler', frame=frame)
        camera.data.keyframe_insert('ortho_scale', frame=frame)
    if lock_scale:
        aspect = scene.render.resolution_x / scene.render.resolution_y
        envelope = max(framing_width(high - low, offset, aspect)
                       for _, offset, low, high, _ in fitted)
        for frame, (rotation, offset, low, high, padding) in enumerate(fitted, 1):
            center, scale, distance = framing_pose(scene, rotation, offset, envelope * padding, low, high)
            camera.location = center + rotation @ Vector((0, 0, distance))
            camera.rotation_euler = rotation.to_euler('XYZ', camera.rotation_euler)
            camera.data.ortho_scale = scale
            camera.keyframe_insert('location', frame=frame)
            camera.keyframe_insert('rotation_euler', frame=frame)
            camera.data.keyframe_insert('ortho_scale', frame=frame)
    linear_action(camera.animation_data)
    linear_action(camera.data.animation_data)
    scene.frame_set(1)
    return {'frame_envelope_width': envelope, 'frames_evaluated': count,
            'scope': 'Authored padding changes scale against a fixed evaluated envelope'} if lock_scale else None


def camera_rig_motion(scene, previous, poses, count, linear_action, spec, parts):
    """Small adapter to the official rig; the existing camera_path owns staging."""
    import addon_utils
    from bpy_extras.object_utils import world_to_camera_view

    addon_utils.enable('add_camera_rigs', default_set=True, persistent=False)
    bpy.ops.object.select_all(action='DESELECT')
    bpy.ops.object.build_camera_rig(mode=spec['mode'])
    rig, camera = bpy.context.object, scene.camera
    camera.name = 'ShotCamera.Cinematic'
    previous.hide_render = True
    camera.data.clip_start, camera.data.clip_end = spec['clip']
    camera.data.sensor_width = 36
    camera.data.dof.use_dof = False  # Keep both contacting surfaces legible.
    rig.pose.bones['Camera']['lens'] = spec['lens_mm']
    controls = []
    for name, bone in [('DollyCart', 'Camera'), ('ContactAim', 'Aim')]:
        control = bpy.data.objects.new(name, None)
        scene.collection.objects.link(control)
        constraint = rig.pose.bones[bone].constraints.new('COPY_LOCATION')
        constraint.target = control
        constraint.owner_space = constraint.target_space = 'WORLD'
        # Location must be solved before the add-on's target-facing rotation.
        rig.pose.bones[bone].constraints.move(len(rig.pose.bones[bone].constraints)-1, 0)
        controls.append(control)
    cart, aim = controls
    camera.data.dof.focus_object = aim
    followed = target(parts, spec['follow']['object']) if spec.get('follow') else None
    scene.frame_set(1)
    if followed:
        initial = marker_center(followed)
    index = 0
    rows, previous_matrix, previous_markers, travel = [], None, {}, {}
    for frame in range(1, count + 1):
        scene.frame_set(frame)
        progress = (frame - 1) / max(1, count - 1)
        while index < len(poses)-2 and progress > poses[index+1]['progress']:
            index += 1
        start, end = poses[index:index+2]
        blend = (progress-start['progress']) / (end['progress']-start['progress'])
        blend = blend*blend*(3-2*blend)
        center = Vector(start['target']).lerp(Vector(end['target']), blend)
        if followed:
            center += (marker_center(followed)-initial)*spec['follow']['weight']
        direction = Vector(start['direction']).normalized().lerp(Vector(end['direction']).normalized(), blend).normalized()
        width = start['width']*(1-blend) + end['width']*blend
        # Perspective dolly, fixed focal length; width is at the aim plane.
        cart.location = center + direction * width * spec['lens_mm'] / camera.data.sensor_width
        aim.location = center
        cart.keyframe_insert('location', frame=frame)
        aim.keyframe_insert('location', frame=frame)
        bpy.context.view_layer.update()
        matrix = camera.matrix_world.copy()
        projected = world_to_camera_view(scene, camera, center)
        # Inspect actual evaluated geometry, not an invented contact coordinate.
        markers = {}
        for name in spec.get('inspect_markers', []):
            obj = target(parts, name)
            position = marker_center(obj)
            screen = world_to_camera_view(scene, camera, position)
            before = previous_markers.get(name, position)
            travel[name] = travel.get(name, 0) + (position-before).length
            projected_before = world_to_camera_view(scene, camera, before)
            delta = position - matrix.translation
            nearest, first = delta.length + .00001, None
            graph = bpy.context.evaluated_depsgraph_get()
            for surface in parts:
                if surface.hide_render or surface.type != 'MESH':
                    continue
                evaluated = surface.evaluated_get(graph)
                inverse = evaluated.matrix_world.inverted()
                local_origin = inverse @ matrix.translation
                local_direction = inverse.to_3x3() @ delta.normalized()
                hit, hit_position, _, _ = evaluated.ray_cast(local_origin, local_direction)
                if hit:
                    distance = (evaluated.matrix_world @ hit_position-matrix.translation).length
                    if distance < nearest:
                        nearest, first = distance, surface
            markers[name] = {'world': list(position), 'screen': [screen.x, 1-screen.y],
                             'path_m': travel[name],
                             'surface_step_screen': [screen.x-projected_before.x, projected_before.y-screen.y],
                             'in_frame': screen.z > 0 and 0 < screen.x < 1 and 0 < screen.y < 1,
                             'first_rendered_geometry_candidate': first.name if first else None}
            previous_markers[name] = position
        rows.append({'frame': frame, 'time': (frame-1)/scene.render.fps,
                     'camera': list(matrix.translation), 'aim': list(center),
                     'aim_in_frame': projected.z > 0 and 0 < projected.x < 1 and 0 < projected.y < 1,
                     'step_m': 0 if previous_matrix is None else (matrix.translation-previous_matrix.translation).length,
                     'rotation_step_radians': 0 if previous_matrix is None else matrix.to_quaternion().rotation_difference(previous_matrix.to_quaternion()).angle,
                     'markers': markers})
        previous_matrix = matrix
    for control in controls:
        linear_action(control.animation_data)
    scene.frame_set(1)
    return {'addon': 'add_camera_rigs', 'version': '1.9.2', 'mode': spec['mode'],
            'lens_mm': spec['lens_mm'], 'rig': rig.name, 'camera': camera.name,
            'frames': rows, 'scope': 'Every-frame evaluated camera and marker projection; ray candidates do not establish visual clarity, transparent occlusion or continuous viewing'}


def evaluated_bounds(objects):
    graph = bpy.context.evaluated_depsgraph_get()
    for obj in objects:
        evaluated = obj.evaluated_get(graph)
        for corner in evaluated.bound_box:
            yield evaluated.matrix_world @ Vector(corner)


def camera_bounds(rotation, objects):
    inverse = rotation.inverted()
    points = [inverse @ point for point in evaluated_bounds(objects)]
    low = Vector(tuple(min(point[i] for point in points) for i in range(3)))
    high = Vector(tuple(max(point[i] for point in points) for i in range(3)))
    return low, high


def framing_width(span, offset, aspect):
    return max(span.x / (.97 - 2 * abs(offset.x)),
               span.y * aspect / (.97 - 2 * abs(offset.y)), 1e-6)


def framing_pose(scene, rotation, offset, width, low, high):
    aspect = scene.render.resolution_x / scene.render.resolution_y
    center = (low + high) / 2
    center -= Vector((offset.x * width, offset.y * width / aspect, 0))
    distance = max(scene.camera.data.clip_start * 2, (high.z - low.z) / 2 + width * 2)
    return rotation @ center, width / min(1, aspect), distance


def fit_camera(scene, rotation, objects, offset, padding):
    low, high = camera_bounds(rotation, objects)
    aspect = scene.render.resolution_x / scene.render.resolution_y
    width = framing_width(high - low, offset, aspect) * padding
    return framing_pose(scene, rotation, offset, width, low, high)


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
