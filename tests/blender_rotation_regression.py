"""Native Blender regression: Euler wrapping must not reverse a rigid rotor.

Run with Blender --background --python-exit-code 1 --python tests/blender_rotation_regression.py.
This uses real Blender animation evaluation, never mocks or perception scores.
"""
from pathlib import Path
import math
import runpy
import json

import bpy
from mathutils import Euler

ROOT = Path(__file__).resolve().parents[1]
scene_module = runpy.run_path(str(ROOT/'blender/scene.py'), run_name='rotation_regression')
prepare = scene_module['prepare_data_tracks']
bpy.ops.wm.read_factory_settings(use_empty=True)


def sample(name, quaternion):
    bpy.ops.mesh.primitive_cube_add(size=.01)
    obj = bpy.context.object
    obj.name = name
    shot = dict(tracks=[dict(object=name, poses=[
        dict(progress=0, rotation_euler=[math.radians(179), 0, 0]),
        dict(progress=1, rotation_euler=[math.radians(-179), 0, 0])])])
    if quaternion:
        shot['rotation_interpolation'] = 'quaternion-shortest-path'
    prepare(shot, 2)
    errors = []
    for fraction in [0, .25, .5, .75, 1]:
        bpy.context.scene.frame_set(1, subframe=fraction)
        bpy.context.view_layer.update()
        actual = obj.evaluated_get(bpy.context.evaluated_depsgraph_get()).matrix_world.to_quaternion()
        expected = Euler([math.radians(179+2*fraction), 0, 0], 'XYZ').to_quaternion()
        angle = actual.rotation_difference(expected).angle
        errors.append(min(angle, abs(2*math.pi-angle)))
    return errors


legacy = sample('legacy_rotor', False)
fixed = sample('quaternion_rotor', True)
assert legacy[2] > 3, legacy
assert max(fixed) < .001, fixed
task = ROOT/'output/tasks/hand-crank-pencil-sharpener-20261116'
config = json.loads((task/'editor/boston-film-v5/production.json').read_text())
chapter = config['shots']['combined']
dense_errors = []
for track in chapter['tracks']:
    obj = bpy.data.objects.new(track['object'], None)
    bpy.context.scene.collection.objects.link(obj)
prepare(dict(tracks=chapter['tracks'], rotation_interpolation='quaternion-shortest-path'),
        round(chapter['seconds']*30))
for frame in [1, 83, 84, 85, 166, 250, 251, 252, 330]:
    bpy.context.scene.frame_set(frame, subframe=.5)
    bpy.context.view_layer.update()
    for track in chapter['tracks']:
        poses = track['poses']
        if frame >= len(poses):
            continue
        q0 = Euler(poses[frame-1]['rotation_euler'], 'XYZ').to_quaternion()
        q1 = Euler(poses[frame]['rotation_euler'], 'XYZ').to_quaternion()
        expected = q0.slerp(q1, .5)
        actual = bpy.data.objects[track['object']].evaluated_get(
            bpy.context.evaluated_depsgraph_get()).matrix_world.to_quaternion()
        angle = actual.rotation_difference(expected).angle
        dense_errors.append(min(angle, abs(2*math.pi-angle)))
assert max(dense_errors) < .001, max(dense_errors)
report = dict(status='PASS', legacy_max_error_radians=max(legacy),
              fixed_max_error_radians=max(fixed), real_blender=True,
              actual_combined_subframe_samples=len(dense_errors),
              actual_combined_max_error_radians=max(dense_errors),
              scope='Native rigid rotation at endpoints and subframes; no mechanical/perceptual acceptance')
out = ROOT/'output/tasks/hand-crank-pencil-sharpener-20261116/editor/boston-film-v5/rotation-regression.json'
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps(report))
