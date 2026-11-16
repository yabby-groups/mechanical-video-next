"""Run inside Blender against the actual saved render scene, never a JSON claim."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import bpy
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view


def inspect_scene(scene, collection='Assembly'):
    group = bpy.data.collections.get(collection)
    if group is None or scene.camera is None:
        raise ValueError('Mechanical collection and three-dimensional camera required')
    objects = [o for o in group.all_objects if o.type == 'MESH' and not o.hide_render]
    geometry, positions, bounds = [], {}, {}
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
    frames = sorted({scene.frame_start, round((scene.frame_start+scene.frame_end)/2), scene.frame_end})
    for frame in frames:
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        deps = bpy.context.evaluated_depsgraph_get()
        positions[str(frame)] = {
            o.name: {'matrix': [v for row in o.matrix_world for v in row],
                     'geometry': hashlib.sha256(b''.join(
                         str(tuple(v.co)).encode() for v in o.evaluated_get(deps).data.vertices)).hexdigest()}
            for o in objects}
        projected=[world_to_camera_view(scene,scene.camera,o.matrix_world @ Vector(c))
                   for o in objects for c in o.bound_box]
        bounds[str(frame)]=[max(0,min(p.x for p in projected)),
                            max(0,1-max(p.y for p in projected)),
                            min(1,max(p.x for p in projected)),
                            min(1,1-min(p.y for p in projected))]
    moved = any(positions[str(f)] != positions[str(frames[0])] for f in frames[1:])
    return dict(geometry=geometry, camera={'type':scene.camera.data.type,
                'matrix':[v for row in scene.camera.matrix_world for v in row],
                'lens':scene.camera.data.lens, 'ortho_scale':scene.camera.data.ortho_scale},
                motion_samples=positions, subject_bounds=bounds, spatial_motion=moved, frame_range=frames,
                engine=scene.render.engine, resolution=[scene.render.resolution_x,scene.render.resolution_y],
                fps=scene.render.fps / scene.render.fps_base)


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True)
    p.add_argument('--frames',type=int,nargs='*');p.add_argument('--render-dir',type=Path)
    a=p.parse_args(sys.argv[sys.argv.index('--')+1:])
    report=inspect_scene(bpy.context.scene)
    if a.render_dir:
        a.render_dir.mkdir(parents=True,exist_ok=True)
        for f in a.frames or report['frame_range']:
            bpy.context.scene.frame_set(f)
            bpy.context.scene.render.filepath=str(a.render_dir/f'{f:05d}.png')
            bpy.ops.render.render(write_still=True)
    a.output.write_text(json.dumps(report,indent=2)+'\n')


if __name__ == '__main__':
    main()
