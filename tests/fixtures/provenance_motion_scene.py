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
report = dict(loop=loop, trimmed=trimmed, camera_only=camera_only, offscreen=offscreen, one_frame=one_frame)
if '--render-clipped-witness' in sys.argv:
    from render_preflight import render_frame

    scene.render.engine = 'BLENDER_EEVEE'
    scene.render.image_settings.file_format = 'PNG'
    camera.rotation_euler = (0, 0, 0)
    camera.data.lens = 35
    camera.data.clip_start = 1
    camera.data.clip_end = 3
    for frame, height in ((1, .35), (8, 0), (9, 0)):
        camera.location = (0, 0, height)
        camera.keyframe_insert('location', frame=frame)
    subject.location = (-.24, 0, -1.02)
    subject.scale = (.45, .52, .8)
    subject.name = 'Clipped part'
    other = subject.copy()
    other.name = 'Fixed part'
    other.data = subject.data.copy()
    group.objects.link(other)
    other.location = (.38, 0, -1.8)
    other.scale = (.4, .5, .4)

    def emissive(obj, color):
        material = bpy.data.materials.new(obj.name + ' fixture')
        material.use_nodes = True
        tree = material.node_tree
        emission = tree.nodes.new('ShaderNodeEmission')
        emission.inputs['Color'].default_value = color
        tree.links.new(emission.outputs[0], tree.nodes.get('Material Output').inputs['Surface'])
        obj.data.materials.clear()
        obj.data.materials.append(material)

    emissive(subject, (1, 0, 0, 1))
    emissive(other, (0, 1, 0, 1))
    for frame, hidden in ((1, False), (8, False), (9, True)):
        subject.hide_render = hidden
        subject.keyframe_insert('hide_render', frame=frame)
    scene.frame_set(1)
    report['clipped'] = inspect_scene(scene, witnesses=[1, 8, 9], intervals=[(1, 10)])
    render_frame(scene, 8, out.parent/'witness.png', preflight=True)
    render_frame(scene, 8, out.parent/'repeat.png')
    render_frame(scene, 9, out.parent/'replacement.png')
    scene.frame_set(8)
    subject.animation_data_clear()
    camera.data.type = 'ORTHO'
    camera.data.ortho_scale = 2
    subject.location, subject.scale = (.3, 0, -2), (.25, .25, .25)
    other.location, other.scale = (.3, 0, -1.5), (.6, .6, .6)
    report['occluded'] = inspect_scene(scene, witnesses=[8], intervals=[(8, 9)])
out.write_text(json.dumps(report))
