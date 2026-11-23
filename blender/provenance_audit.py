"""Run inside Blender against the actual saved render scene, never a JSON claim."""
import argparse
import hashlib
from itertools import combinations
import json
import math
from pathlib import Path
import sys
import bpy
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view


def matrix_values(obj):
    return tuple(value for row in obj.matrix_world for value in row)


def mesh_digest(obj):
    digest = hashlib.sha256()
    for vertex in obj.data.vertices:
        digest.update(str(tuple(vertex.co)).encode())
    return digest.hexdigest()


def renderable_objects(layer):
    if layer.exclude or layer.collection.hide_render:
        return
    yield from layer.collection.objects
    for child in layer.children:
        yield from renderable_objects(child)


def convex_hull(points):
    def chain(ordered):
        boundary = []
        for point in ordered:
            while len(boundary) >= 2:
                a, b = boundary[-2:]
                cross = (b[0] - a[0]) * (point[1] - a[1]) - (b[1] - a[1]) * (point[0] - a[0])
                if cross > 0:
                    break
                boundary.pop()
            boundary.append(point)
        return boundary

    ordered = sorted(set(points))
    return chain(ordered)[:-1] + chain(reversed(ordered))[:-1]


def clip_to_picture(points):
    """Intersect the projected hull with the normalized picture rectangle."""
    for axis, limit, sign in ((0, 0, 1), (0, 1, -1), (1, 0, 1), (1, 1, -1)):
        if not points:
            break
        clipped = []
        for a, b in zip(points[-1:] + points[:-1], points, strict=True):
            inside_a = sign * (a[axis] - limit) >= 0
            inside_b = sign * (b[axis] - limit) >= 0
            if inside_a != inside_b:
                fraction = (limit - a[axis]) / (b[axis] - a[axis])
                other = a[1-axis] + fraction * (b[1-axis] - a[1-axis])
                clipped.append((limit, other) if axis == 0 else (other, limit))
            if inside_b:
                clipped.append(b)
        points = clipped
    return points


def project_object_bounds(scene, camera, view, obj, near, far):
    corners = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    depths = [-(view @ corner).z for corner in corners]
    if (len(corners) != 8 or not all(math.isfinite(depth) for depth in depths)
            or any(not all(map(math.isfinite, corner)) for corner in corners)):
        raise ValueError(f'Cannot determine finite witness bounds for {obj.name}')
    if max(depths) < near or min(depths) > far:
        return None
    visible = [corner for corner, depth in zip(corners, depths, strict=True) if near <= depth <= far]
    if len(visible) < len(corners):
        # The pairs include every box edge. Diagonal intersections stay inside
        # the clipped convex box and avoid relying on Blender's corner order.
        for (a, depth_a), (b, depth_b) in combinations(zip(corners, depths, strict=True), 2):
            for plane in (near, far):
                if min(depth_a, depth_b) < plane < max(depth_a, depth_b):
                    visible.append(a.lerp(b, (plane - depth_a) / (depth_b - depth_a)))
    pixels = [world_to_camera_view(scene, camera, corner) for corner in visible]
    if not pixels or any(not all(map(math.isfinite, point)) or point.z <= 0 for point in pixels):
        raise ValueError(f'Cannot determine finite witness projection for {obj.name}')
    hull = convex_hull([(point.x, 1 - point.y) for point in pixels])
    if len(hull) < 3:
        return None
    picture = clip_to_picture(hull)
    if len(picture) < 3:
        return None
    x, y = zip(*picture)
    left, top, right, bottom = min(x), min(y), max(x), max(y)
    if left < right and top < bottom:
        return left, top, right, bottom
    return None


def projected_regions(scene, camera, objects):
    near, far = camera.data.clip_start, camera.data.clip_end
    if camera.data.type not in {'PERSP', 'ORTHO'} or not (math.isfinite(far) and 0 < near < far):
        raise ValueError('Witness bounds need a perspective or orthographic camera with finite clipping planes')
    view = camera.matrix_world.normalized().inverted()
    return {obj.name: project_object_bounds(scene, camera, view, obj, near, far)
            for obj in objects}


def union_bounds(regions):
    projected = [bounds for bounds in regions if bounds is not None]
    if not projected:
        return None
    return [min(row[0] for row in projected), min(row[1] for row in projected),
            max(row[2] for row in projected), max(row[3] for row in projected)]


def witness_bounds(scene, camera, objects):
    return union_bounds(projected_regions(scene, camera, objects).values())


def witness_regions(scene, camera, objects, deps):
    projected = projected_regions(scene, camera, objects)
    view_frame = camera.data.view_frame(scene=scene)
    x_min, x_max = min(v.x for v in view_frame), max(v.x for v in view_frame)
    y_min, y_max = min(v.y for v in view_frame), max(v.y for v in view_frame)
    matrix = camera.matrix_world.normalized()
    near, far = camera.data.clip_start, camera.data.clip_end
    grid = 12
    regions = {}
    for obj in objects:
        bounds = projected[obj.name]
        if bounds is None:
            regions[obj.name] = dict(status='INSUFFICIENT_EVIDENCE', reason='Outside camera frustum')
            continue
        left, top, right, bottom = bounds
        dx, dy = (right - left) / grid, (bottom - top) / grid
        hits = []
        # The clipped projection can include geometry hidden by another mesh.
        # Sample actual first surface hits between the camera clipping planes.
        for j in range(grid):
            for i in range(grid):
                x = x_min + (left + (i + .5) * dx) * (x_max - x_min)
                y = y_max - (top + (j + .5) * dy) * (y_max - y_min)
                if camera.data.type == 'PERSP':
                    ray = Vector((x, y, view_frame[0].z)) / -view_frame[0].z
                    start, end = matrix @ (ray * near), matrix @ (ray * far)
                else:
                    start, end = matrix @ Vector((x, y, -near)), matrix @ Vector((x, y, -far))
                direction = end - start
                hit, _, _, _, surface, _ = scene.ray_cast(deps, start, direction.normalized(),
                                                           distance=direction.length)
                if hit and surface.original == obj.original:
                    hits.append((i, j))
        if not hits:
            regions[obj.name] = dict(status='INSUFFICIENT_EVIDENCE', projected_bounds=bounds,
                                     reason='No visible surface in camera-ray samples')
            continue
        xs, ys = zip(*hits)
        regions[obj.name] = dict(status='VISIBLE', projected_bounds=bounds, visible_samples=len(hits),
            bounds=[left + min(xs) * dx, top + min(ys) * dy,
                    min(right, left + (max(xs) + 1) * dx), min(bottom, top + (max(ys) + 1) * dy)])
    return union_bounds(projected.values()), regions


def inspect_scene(scene, collection='Assembly', *, witnesses=None, intervals=None, motion_frames=()):

    group = bpy.data.collections.get(collection)
    if group is None or scene.camera is None:
        raise ValueError('Mechanical collection and three-dimensional camera required')
    visible = set(renderable_objects(bpy.context.view_layer.layer_collection))
    objects = [obj for obj in group.all_objects if obj.type == 'MESH' and not obj.hide_render and obj in visible]
    geometry, positions, bounds, regions = [], {}, {}, {}
    for obj in objects:
        vertices = [v.co for v in obj.data.vertices]
        if len(vertices) < 4:
            continue
        origin = vertices[0]
        axis = max((v-origin for v in vertices), key=lambda v: v.length)
        normal = max((axis.cross(v-origin) for v in vertices), key=lambda v: v.length)
        span = max((v-origin).length for v in vertices)
        # Affine dimension, not thickness or volume: curved thin shells count,
        # real sheet parts can be planar when the rest of the assembly is 3D.
        depth = max(abs(normal.normalized().dot(v-origin)) for v in vertices) if normal.length else 0
        textures = any(n.type == 'TEX_IMAGE' for m in obj.data.materials if m and m.use_nodes
                       for n in m.node_tree.nodes)
        geometry.append(dict(name=obj.name, vertices=len(vertices), polygons=len(obj.data.polygons),
                             spatial=depth > max(span * 1e-6, 1e-10), affine_depth=depth,
                             textured=textures, dimensions=list(obj.dimensions)))
    if not geometry or not any(o['spatial'] for o in geometry):
        raise ValueError('Pseudo-3D: mechanical subject is planar')
    if any(o['textured'] and not o['spatial'] for o in geometry):
        raise ValueError('Mechanical image-textured planes are not accepted as 3D subjects')
    first, last = scene.frame_start, scene.frame_end
    witnesses = sorted(set(witnesses or (first, round((first + last) / 2), last)))
    intervals = intervals or [(first, last + 1)]
    if any(not first <= start < stop <= last + 1 for start, stop in intervals):
        raise ValueError('Motion interval outside actual scene timeline')
    spans = []
    for start, stop in sorted(intervals):
        if spans and start <= spans[-1][1]:
            spans[-1][1] = max(stop, spans[-1][1])
        else:
            spans.append([start, stop])
    origins = {frame: start for start, stop in spans for frame in range(start, stop)}
    clock = list(origins)
    starts = {start for start, _ in spans}
    if not set(witnesses) <= set(clock):
        raise ValueError('Render witness outside actual scene timeline or source intervals')

    # Rigid tracks and inherited/constraint transforms are cheap to inspect at
    # native frame times. Shape keys use evaluated meshes when weights change.
    # Modifiers with external dependencies are sampled at witnesses and
    # numerical states, with bounded additional mesh evaluations.
    local_modifiers = {'BEVEL', 'WEIGHTED_NORMAL', 'EDGE_SPLIT', 'TRIANGULATE', 'SUBSURF'}
    modifiers = {obj.name for obj in objects if any(
        modifier.show_render and (modifier.type not in local_modifiers
                                  or obj.animation_data is not None)
        for modifier in obj.modifiers)}
    modifier_frames = set(witnesses) | starts | (set(motion_frames) & set(clock))
    modifier_frames.update(clock[round(i * (len(clock) - 1) / 15)] for i in range(16))
    clock_order = list(dict.fromkeys([*sorted(starts), *sorted(modifier_frames), *clock]))
    references, shape_cache = {}, {}
    moved = False
    for frame in clock_order:
        if moved and frame not in witnesses:
            continue
        scene.frame_set(frame)
        deps = bpy.context.evaluated_depsgraph_get()
        evaluated = [obj.evaluated_get(deps) for obj in objects]
        if frame in witnesses:
            camera = scene.camera.evaluated_get(deps)
            try:
                bounds[str(frame)], regions[str(frame)] = witness_regions(
                    scene, camera, [obj for obj in evaluated if not obj.hide_render], deps)
            except ValueError as error:
                raise ValueError(f'Witness frame {frame}: {error}') from error
        snapshot = {}
        for original, obj in zip(objects, evaluated, strict=True):
            transform = matrix_values(obj)
            geometry_hash = None
            if original.name in modifiers:
                if frame in modifier_frames:
                    geometry_hash = mesh_digest(obj)
            elif original.data.shape_keys:
                keys = original.data.shape_keys
                weights = tuple(key.value for key in keys.key_blocks) if keys.use_relative else (keys.eval_time,)
                shape_key = (original.name, weights)
                if shape_key not in shape_cache:
                    shape_cache[shape_key] = mesh_digest(obj)
                geometry_hash = shape_cache[shape_key]
            snapshot[obj.name] = {'matrix': transform, 'geometry': geometry_hash}
        changed = False
        if frame in starts:
            references[frame] = snapshot
        else:
            reference = references[origins[frame]]
            changed = any(row['matrix'] != reference[name]['matrix']
                          or (row['geometry'] is not None and row['geometry'] != reference[name]['geometry'])
                          for name, row in snapshot.items())
        if frame in witnesses or frame in starts or (changed and not moved):
            positions[str(frame)] = snapshot
        moved |= changed
    if moved:
        motion_status = 'MOTION_FOUND'
    elif not any(stop - start >= 2 for start, stop in spans):
        motion_status = 'INSUFFICIENT_SAMPLES'
    elif modifiers and not set(clock) <= modifier_frames:
        motion_status = 'NO_CHANGE_IN_SAMPLES'
    else:
        motion_status = 'STATIC_ON_RENDERED_FRAMES'
    camera = scene.camera
    resolution = [pixels * scene.render.resolution_percentage // 100
                  for pixels in (scene.render.resolution_x, scene.render.resolution_y)]
    return dict(geometry=geometry, camera={'type': camera.data.type, 'matrix': matrix_values(camera),
                'lens': camera.data.lens, 'ortho_scale': camera.data.ortho_scale},
                motion_samples=positions, subject_bounds=bounds, subject_regions=regions, spatial_motion=moved,
                motion_status=motion_status, frame_range=[first, last],
                engine=scene.render.engine, resolution=resolution,
                fps=scene.render.fps / scene.render.fps_base)


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True)
    p.add_argument('--frames',type=int,nargs='*');p.add_argument('--render-dir',type=Path)
    p.add_argument('--interval', nargs=2, type=int, action='append')
    p.add_argument('--motion-frames', type=int, nargs='*', default=[])
    a=p.parse_args(sys.argv[sys.argv.index('--')+1:])
    report=inspect_scene(bpy.context.scene, witnesses=a.frames, intervals=a.interval, motion_frames=a.motion_frames)
    if a.render_dir:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from render_preflight import render_frame
        a.render_dir.mkdir(parents=True,exist_ok=True)
        for i, frame in enumerate(a.frames or sorted(map(int, report['subject_bounds']))):
            render_frame(bpy.context.scene, frame, a.render_dir/f'{frame:05d}.png', preflight=i == 0)
    a.output.write_text(json.dumps(report,indent=2)+'\n')


if __name__ == '__main__':
    main()
