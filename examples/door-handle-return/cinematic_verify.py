"""Verify the reused authored motion in every frame of each exact scene."""
import fcntl
import json
from pathlib import Path
import sys

import bpy
from mathutils.bvhtree import BVHTree

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from common import filehash

paths = [Path(arg).resolve() for arg in sys.argv[sys.argv.index('--') + 1:]]
source, *targets, output = paths
names = ['Lever handle', '66 square drive spindle', '34 active flat spring driver',
         '32 opposite flat spring driver']
wire = '30 continuous wire arc spring'


def read_motion(path, *, contact=False):
    bpy.ops.wm.open_mainfile(filepath=str(path))
    scene = bpy.context.scene
    parts = [scene.objects[name] for name in names]
    spring = scene.objects[wire]
    states, gaps = [], []
    for frame in range(1, 1216):
        scene.frame_set(frame)
        rotations = [tuple(obj.rotation_euler) for obj in parts]
        weights = [key.value for key in spring.data.shape_keys.key_blocks]
        states.append([rotations, weights])
        if contact and frame in (470, 535, 605, 631, 751, 809, 885, 971):
            graph = bpy.context.evaluated_depsgraph_get()
            evaluated = spring.evaluated_get(graph)
            mesh = evaluated.to_mesh()
            points = [evaluated.matrix_world @ vertex.co for vertex in mesh.vertices]
            tips = [points[:10], points[-10:]]
            mm = []
            for tip, name in zip(tips, ['Stationary spring seat', 'Moving spring seat']):
                seat = scene.objects[name].evaluated_get(graph)
                seat_mesh = seat.to_mesh()
                tree = BVHTree.FromPolygons(
                    [seat.matrix_world @ v.co for v in seat_mesh.vertices],
                    [tuple(p.vertices) for p in seat_mesh.polygons])
                mm.append(min(tree.find_nearest(p)[3] for p in tip))
                seat.to_mesh_clear()
            evaluated.to_mesh_clear()
            gaps.append({'frame': frame, 'seat_surface_gaps_scene_units': mm})
    mesh = spring.data
    basis = [tuple(v.co) for v in mesh.vertices]
    return states, basis, gaps


with (ROOT / 'work/production.lock').open('a') as handle:
    fcntl.flock(handle, fcntl.LOCK_EX)
    reference, wire_basis, _ = read_motion(source)
    reports = []
    for path in targets:
        states, mesh, gaps = read_motion(path, contact=True)
        if states != reference or mesh != wire_basis:
            raise ValueError(f'Authored mechanical rotation or spring geometry changed in {path}')
        if max(max(row['seat_surface_gaps_scene_units']) for row in gaps) > .002:
            raise ValueError(f'Spring end departed from its seat in {path}')
        reports.append({'file': str(path), 'sha256': filehash(path),
                        'exact_source_pose_frames': len(states), 'sampled_seat_gaps': gaps})
    output.write_text(json.dumps({
        'source': str(source), 'source_sha256': filehash(source),
        'objects': names + [wire], 'results': reports,
        'scope': 'Exact local rotation and spring key-weight comparisons. Eight evaluated geometric spring-seat samples. Prescribed motion, no measured forces.'
    }, indent=2) + '\n')
