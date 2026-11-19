"""Blender-only audit of actual saved comparison scenes, without editing them."""
import hashlib
import json
import math
from pathlib import Path
import bpy
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'output/camera-study'
baseline=ROOT/'output/tasks/workflow-acceptance-20261118/repairs/scenes-v4/3947031e9a2082d48501914ea3a9c11f5fdfc40d76fde3d251d43c3a0881abc1-1795005709947925000.blend'
sources={'A':baseline}
for version in ('B','C'):
    receipt=json.loads((OUT/f'{version}-final.json').read_text())
    checks=json.loads(Path(receipt['checks']).read_text())
    sources[version]=Path(checks['scene_artifact']['path'])
reports={}
for version,path in sources.items():
    bpy.ops.wm.open_mainfile(filepath=str(path))
    scene=bpy.context.scene
    parts=[o for o in bpy.data.collections['Assembly'].objects if not o.hide_render and o.type=='MESH']
    rows=[]
    previous=None
    for frame in range(1,374):
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        graph=bpy.context.evaluated_depsgraph_get()
        cam=scene.camera.evaluated_get(graph)
        camera=cam.matrix_world.translation.copy()
        minimum=float('inf')
        for obj in parts:
            obj=obj.evaluated_get(graph)
            corners=[obj.matrix_world@Vector(v) for v in obj.bound_box]
            low=[min(v[i] for v in corners) for i in range(3)]
            high=[max(v[i] for v in corners) for i in range(3)]
            minimum=min(minimum,math.sqrt(sum(max(low[i]-camera[i],0,camera[i]-high[i])**2 for i in range(3))))
        markers={}
        for name in ('Supply_witness','Belt_witness'):
            obj=bpy.data.objects[name].evaluated_get(graph)
            center=obj.matrix_world@(sum((v.co for v in obj.data.vertices),Vector())/len(obj.data.vertices))
            point=world_to_camera_view(scene,cam,center)
            markers[name]=dict(screen=[point.x,1-point.y],depth=point.z,
                               in_frame=point.z>0 and .01<point.x<.99 and .01<point.y<.99)
        matrix=cam.matrix_world.copy()
        rows.append(dict(frame=frame,time=(frame-1)/30,camera=list(camera),
                         clearance_from_visible_mesh_world_aabbs_m=minimum,markers=markers,
                         translation_step_m=0 if previous is None else (camera-previous.translation).length,
                         rotation_step_radians=0 if previous is None else matrix.to_quaternion().rotation_difference(previous.to_quaternion()).angle))
        previous=matrix
    reports[version]=dict(scene=str(path),scene_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                          camera_type=scene.camera.data.type,frame_count=len(rows),
                          all_marker_centers_in_frame=all(m['in_frame'] for r in rows for m in r['markers'].values()),
                          min_camera_aabb_clearance_m=min(r['clearance_from_visible_mesh_world_aabbs_m'] for r in rows),
                          maximum_translation_step_m=max(r['translation_step_m'] for r in rows),
                          maximum_rotation_step_radians=max(r['rotation_step_radians'] for r in rows),frames=rows)
(OUT/'engineering-scenes.json').write_text(json.dumps(dict(blender=bpy.app.version_string,versions=reports,
    scope='Every-frame saved-scene engineering evaluation; positive AABB clearance proves camera outside all visible assembly mesh AABBs, not contact-force correctness or visual quality. Marker-center projection does not establish whole-surface visibility, reading or listening.'),indent=2))
