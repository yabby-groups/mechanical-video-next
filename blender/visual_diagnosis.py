"""Replay selected poses and inspect their geometry in a scratch Blender process."""

import json
from pathlib import Path
import runpy
import sys

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector


DIRECTIONS = {'front': (0, -1, 0), 'side': (1, 0, 0), 'top': (0, 0, 1)}


def corners(obj, graph):
    evaluated = obj.evaluated_get(graph)
    return [evaluated.matrix_world @ Vector(point) for point in evaluated.bound_box]


def bounds(points):
    return [[min(axis) for axis in zip(*points)], [max(axis) for axis in zip(*points)]]


def largest_faces(evaluated):
    """Show major contact surfaces on an explicitly selected evaluated mesh."""
    mesh = evaluated.data
    matrix = evaluated.matrix_world
    linear = matrix.to_3x3()
    normal_matrix = linear.inverted_safe().transposed()
    volume_scale = abs(linear.determinant())
    faces = []
    for polygon in mesh.polygons:
        normal = normal_matrix @ polygon.normal
        area = polygon.area * volume_scale * normal.length
        if area > 0:
            faces.append((area, polygon.index, normal.normalized()))
    return [
        {'area': area, 'face': index, 'center': list(matrix @ mesh.polygons[index].center),
         'normal': list(normal)}
        for area, index, normal in sorted(faces, key=lambda row: (-row[0], row[1]))[:8]
    ]


def describe(scene, graph, region, names):
    camera = scene.camera.evaluated_get(graph) if scene.camera else None
    rows = []
    for obj in scene.objects:
        if obj.type not in {'MESH', 'CURVE', 'SURFACE', 'FONT', 'META'} and obj.name not in names:
            continue
        evaluated = obj.evaluated_get(graph)
        world = corners(obj, graph)
        box = None
        if camera and camera.data.type in {'PERSP', 'ORTHO'}:
            points = [world_to_camera_view(scene, camera, point) for point in world]
            if all(p.z > 0 for p in points):
                lower, upper = bounds([(p.x, 1-p.y) for p in points])
                box = lower + upper
        if obj.name not in names and region is not None:
            # Bounds alone do not establish visibility or exclude occluded objects.
            if box is None or box[0] >= region[2] or box[1] >= region[3] or box[2] <= region[0] or box[3] <= region[1]:
                continue
        animation = obj.animation_data
        row = {
            'name': obj.name, 'parent': obj.parent.name if obj.parent else None,
            'geometry': obj.data.name if obj.data else None, 'type': obj.type,
            'evaluated_vertices': len(evaluated.data.vertices) if obj.type == 'MESH' else None,
            'world_bounds': bounds(world), 'world_matrix': [list(row) for row in evaluated.matrix_world],
            'production_camera_bounds': box, 'hide_render': obj.hide_render,
            'modifiers': [{'name': item.name, 'type': item.type} for item in obj.modifiers],
            'constraints': [{'name': item.name, 'type': item.type,
                             'target': item.target.name if getattr(item, 'target', None) else None}
                            for item in obj.constraints],
            'action': animation.action.name if animation and animation.action else None,
            'drivers': [driver.data_path for driver in animation.drivers] if animation else [],
        }
        if obj.name in names and obj.type == 'MESH':
            row['largest_world_faces'] = largest_faces(evaluated)
        rows.append(row)
    return rows


def orthographic_camera(scene, view, points):
    direction = Vector(DIRECTIONS[view])
    low, high = (Vector(point) for point in bounds(points))
    center = (low + high) / 2
    size = max((high - low).length, 0.01)
    camera = bpy.data.objects.new('Visual diagnosis camera', bpy.data.cameras.new('Visual diagnosis camera'))
    scene.collection.objects.link(camera)
    camera.location = center + direction * (size * 2)
    rotation = (-direction).to_track_quat('-Z', 'Y')
    camera.rotation_euler = rotation.to_euler()
    extent = [rotation.inverted() @ (point - center) for point in points]
    camera.data.type = 'ORTHO'
    camera.data.ortho_scale = 2.3 * max(max(abs(p.x), abs(p.y)) for p in extent) + 0.001
    camera.data.clip_end = max(100, size * 4)
    return camera


def render_poses(scene, seek, request, directory):
    originals = []
    names = set(request['objects'])
    hidden = set(request['hide'])
    unknown = (names | hidden) - set(scene.objects.keys())
    if unknown:
        raise ValueError(f'Unknown scene objects: {sorted(unknown)}')
    view = request['view']
    orthographic = view in DIRECTIONS
    if (view == 'camera' or request['region']) and scene.camera is None:
        raise ValueError('This scene has no original camera')
    if orthographic and not names:
        raise ValueError('Name the parts to frame in an orthographic view')
    framing = []
    for frame in request['frames']:
        graph = seek(frame)
        originals.append({'frame': frame, 'image': None,
                          'objects': describe(scene, graph, request['region'], names)})
        if orthographic:
            for name in names:
                framing.extend(corners(scene.objects[name], graph))
    if view == 'objects':
        return originals

    diagnostic_camera = orthographic_camera(scene, view, framing) if orthographic else None
    resolution = request['resolution']
    for row in originals:
        seek(row['frame'])
        if diagnostic_camera:
            scene.camera = diagnostic_camera
        for obj in scene.objects:
            if obj.name in hidden or (request['isolate'] and obj.type not in {'CAMERA', 'LIGHT'}
                                      and obj.name not in names):
                obj.hide_render = True
        render = scene.render
        render.use_border = view == 'camera' and request['region'] is not None
        render.use_crop_to_border = render.use_border
        if render.use_border:
            x, y, right, bottom = request['region']
            render.border_min_x, render.border_max_x = x, right
            render.border_min_y, render.border_max_y = 1-bottom, 1-y
        render.resolution_percentage = 100
        if orthographic:
            render.resolution_x = render.resolution_y = resolution
            render.pixel_aspect_x = render.pixel_aspect_y = 1
        else:
            # Match the original aspect. For a detail crop, spend the pixel budget there.
            width, height = render.resolution_x, render.resolution_y
            extent = max(width, height)
            if render.use_border:
                extent = max(width * (right-x), height * (bottom-y), extent / 4)
            render.resolution_x = max(4, round(resolution * width / extent))
            render.resolution_y = max(4, round(resolution * height / extent))
        if orthographic or request['xray']:
            render.engine = 'BLENDER_WORKBENCH'
            shading = scene.display.shading
            shading.light = 'STUDIO'
            shading.color_type = 'MATERIAL'
            shading.show_xray = request['xray']
            shading.xray_alpha = 0.45
        elif render.engine == 'BLENDER_EEVEE':
            scene.eevee.taa_render_samples = 4
        elif render.engine == 'CYCLES':
            scene.cycles.samples = min(scene.cycles.samples, 8)
        render.use_compositing = False
        render.use_sequencer = False
        render.image_settings.file_format = 'PNG'
        row['image'] = f"frame-{row['frame']:06d}.png"
        render.filepath = str(directory / row['image'])
        bpy.ops.render.render(write_still=True)
        if view == 'camera':
            render.resolution_x, render.resolution_y = width, height
    return originals


def main():
    directory, = sys.argv[sys.argv.index('--')+1:]
    directory = Path(directory)
    request = json.loads((directory / 'request.json').read_text())
    result = None

    def replay(scene, pose=None):
        def seek(frame):
            scene.frame_set(frame)
            if pose is not None:
                pose(frame / 30)
            bpy.context.view_layer.update()
            return bpy.context.evaluated_depsgraph_get()
        return render_poses(scene, seek, request, directory)

    if 'script' in request:
        # Use the same scene setup and pose callback as production. A failing
        # contact check should still be inspectable at the failing pose.
        def check(scene, pose, count, measure, *, model, substeps=2):
            nonlocal result
            if result is not None or request['frame_count'] != count or max(request['frames']) >= count:
                raise ValueError('Scene setup differs from the bound production shot')
            result = replay(scene, pose)
            return True

        counts = [0] * request['shot'] + [request['frame_count']]
        timing = directory / 'timing.json'
        timing.write_text(json.dumps(counts))
        sys.argv[sys.argv.index('--')+1:] = [
            '--timing', str(timing), '--directory', str(directory), '--shot', str(request['shot'])]
        source = Path(request['script'])
        sys.path[:0] = [str(source.parent), str(Path(__file__).parent)]
        runpy.run_path(str(source), run_name='__main__', init_globals={'check_mechanics': check})
        if result is None:
            raise ValueError('Scene did not expose its production pose callback')
    else:
        result = replay(bpy.context.scene)
    (directory / 'poses.json').write_text(json.dumps(result, allow_nan=False, indent=2) + '\n')


if __name__ == '__main__':
    main()
