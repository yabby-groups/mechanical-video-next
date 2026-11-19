"""Run inside Blender: exercise the unmodified official Dolly and Crane API."""
import json
import sys
from pathlib import Path

import bpy
import addon_utils

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'blender/vendor'))
addon_utils.enable('add_camera_rigs', default_set=True, persistent=False)
rows = []
for mode in ('DOLLY', 'CRANE'):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    # Factory settings clear preferences; enable again in this disposable process.
    addon_utils.enable('add_camera_rigs', default_set=True, persistent=False)
    assert bpy.ops.object.build_camera_rig(mode=mode) == {'FINISHED'}
    rig, camera = bpy.context.object, bpy.context.scene.camera
    for frame, x in ((1, 0), (180, .025), (360, .03)):
        rig.pose.bones['Camera'].location.x = x
        rig.pose.bones['Camera'].keyframe_insert('location', frame=frame)
        rig.pose.bones['Aim'].location.x = x / 2
        rig.pose.bones['Aim'].keyframe_insert('location', frame=frame)
    bpy.context.scene.frame_set(180)
    bpy.context.view_layer.update()
    out = ROOT / 'output/camera-study' / (mode.lower() + '-probe.blend')
    bpy.ops.wm.save_as_mainfile(filepath=str(out))
    rows.append({'mode': mode, 'scene': str(out), 'bones': list(rig.pose.bones.keys()),
                 'camera': camera.name, 'constraints': [c.type for c in rig.pose.bones['Camera'].constraints],
                 'evaluated_matrix': [list(row) for row in camera.matrix_world]})
(ROOT / 'output/camera-study/rig-probe.json').write_text(json.dumps({
    'blender': bpy.app.version_string, 'addon_version': '1.9.2',
    'background': bpy.app.background, 'results': rows}, indent=2))
