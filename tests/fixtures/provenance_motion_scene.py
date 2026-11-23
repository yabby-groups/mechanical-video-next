"""Run with Blender's embedded Python through the serial host runner."""
import json
from pathlib import Path
import sys

import bpy
from mathutils import Vector

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root / 'blender'))
from provenance_audit import inspect_scene

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.frame_start, scene.frame_end = 1, 31
scene.render.resolution_x, scene.render.resolution_y = 640, 360
group = bpy.data.collections.new('Assembly')
scene.collection.children.link(group)
bpy.ops.mesh.primitive_cube_add(size=0.5)
subject = bpy.context.object
for collection in list(subject.users_collection):
    collection.objects.unlink(subject)
group.objects.link(subject)
bpy.ops.object.camera_add(location=(0, -8, 0))
camera = bpy.context.object
camera.rotation_euler = Vector((0, 1, 0)).to_track_quat('-Z', 'Y').to_euler()
scene.camera = camera

for frame, offset in ((1, 0), (8, 2), (16, 0), (23, -2), (31, 0)):
    subject.location.x = offset
    subject.keyframe_insert('location', frame=frame)
loop = inspect_scene(scene, witnesses=[1, 16, 31])
trimmed = inspect_scene(scene, witnesses=[7, 9, 11], intervals=[(7, 12)])
subject.animation_data_clear()
subject.location.x = 0
for frame, offset in ((1, 0), (8, 2), (31, 0)):
    camera.location.x = offset
    camera.keyframe_insert('location', frame=frame)
camera_only = inspect_scene(scene, witnesses=[1, 8, 31])
camera.animation_data_clear()
subject.location.x = 50
offscreen = inspect_scene(scene, witnesses=[1, 8, 31])
one_frame = inspect_scene(scene, witnesses=[8], intervals=[(8, 9)])
out = Path(sys.argv[sys.argv.index('--') + 1])
out.write_text(json.dumps(dict(loop=loop, trimmed=trimmed, camera_only=camera_only,
                               offscreen=offscreen, one_frame=one_frame)))
