"""Reusable teaching asset and thin EAS adapter, not a geometry solver.

Run through scripts/produce.py. Blender must exit nonzero for any failed assertion.
"""
import argparse
import json
import math
import hashlib
from pathlib import Path
import sys
import time
import subprocess
import bisect

import bpy
import bmesh
from mathutils import Vector, Matrix, Quaternion
from mathutils.bvhtree import BVHTree
from bpy_extras.object_utils import world_to_camera_view

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'blender/vendor'))
import exploded_assembly_studio as eas
from exploded_assembly_studio import core
from add_mesh_gears import add_gear


def savejson(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2))


def render_chunked(scene, selected, args):
    """Encode bounded owned PNG batches within this single Blender process.

    Each successful block is fully decoded before its exact PNG list is removed.
    Failed blocks, encoded files and command logs remain as diagnostic evidence.
    """
    if args.chunk_frames < 1 or args.video_output is None:
        raise ValueError('Chunk rendering requires positive --chunk-frames and --video-output')
    session = args.out / ('chunk-run-' + str(time.time_ns()))
    session.mkdir(parents=True, exist_ok=False)
    selected = list(selected)
    chunks = []
    state = {'status': 'RUNNING', 'chunk_frames': args.chunk_frames,
             'requested_frames': len(selected), 'chunks': [], 'scope': 'Technical encode/decode only'}

    def command(argv, log):
        with log.open('w') as stream:
            stream.write(json.dumps([str(v) for v in argv]) + '\n')
            stream.flush()
            subprocess.run([str(v) for v in argv], stdout=stream, stderr=subprocess.STDOUT, check=True)

    try:
        for start in range(0, len(selected), args.chunk_frames):
            block = selected[start:start+args.chunk_frames]
            owned = []
            for f in block:
                scene.frame_set(f)
                path = session / f'{f:05d}.png'
                scene.render.filepath = str(path)
                bpy.ops.render.render(write_still=True)
                owned.append(path)
            chunk = session / f'chunk-{len(chunks):05d}.mp4'
            command(['ffmpeg', '-v', 'error', '-y', '-framerate', args.fps,
                     '-start_number', block[0], '-i', session/'%05d.png', '-frames:v', len(block),
                     '-vf', 'pad=ceil(iw/2)*2:ceil(ih/2)*2', '-c:v', 'libx264', '-preset', 'fast',
                     '-crf', '19', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', chunk],
                    chunk.with_suffix('.encode.log'))
            command(['ffmpeg', '-v', 'error', '-xerror', '-i', chunk, '-f', 'null', '-'],
                    chunk.with_suffix('.decode.log'))
            chunks.append(chunk)
            state['chunks'].append({'file': str(chunk), 'first_frame': block[0],
                                    'frame_count': len(block), 'decode': 'PASS'})
            savejson(session/'report.json', state)
            for path in owned:
                path.unlink()
        concat = session/'concat.txt'
        concat.write_text(''.join("file '" + str(p.resolve()).replace("'", "'\\''") + "'\n" for p in chunks))
        args.video_output.parent.mkdir(parents=True, exist_ok=True)
        command(['ffmpeg', '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', concat,
                 '-c', 'copy', '-movflags', '+faststart', args.video_output], session/'concat.log')
        command(['ffmpeg', '-v', 'error', '-xerror', '-i', args.video_output, '-f', 'null', '-'],
                session/'final-decode.log')
        probe = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-select_streams', 'v:0',
                         '-show_entries', 'stream=nb_frames,width,height', '-of', 'json', str(args.video_output)]))
        stream = probe['streams'][0]
        assert int(stream['nb_frames']) == len(selected), probe
        assert int(stream['width']) == args.width and int(stream['height']) == args.height, probe
        state.update(status='PASS', output=str(args.video_output), probe=probe, final_decode='PASS')
        savejson(session/'report.json', state)
        savejson(args.out/'chunk-result.json', dict(state, evidence_directory=str(session)))
        # Only this session's individually decoded chunks, after final decode.
        for chunk in chunks:
            chunk.unlink()
    except Exception as exc:
        state.update(status='FAIL', error=repr(exc))
        savejson(session/'report.json', state)
        raise


def material(name, color, metal=0.3, roughness=0.32, preserve_surface=False):
    m = bpy.data.materials.new(name)
    m.diffuse_color = (*color, 1)
    m.use_nodes = True
    p = m.node_tree.nodes.get('Principled BSDF')
    p.inputs['Base Color'].default_value = (*color, 1)
    p.inputs['Metallic'].default_value = metal
    p.inputs['Roughness'].default_value = roughness
    m['studio_preserve_surface'] = preserve_surface
    return m


def finish(obj, name, mat, location=(0,0,0)):
    obj.name = name
    obj.location = location
    obj.data.materials.append(mat)
    obj.color = mat.diffuse_color
    for col in list(obj.users_collection):
        col.objects.unlink(obj)
    bpy.data.collections['Assembly'].objects.link(obj)
    return obj


def cylinder(name, radius, depth, z, mat):
    bpy.ops.mesh.primitive_cylinder_add(vertices=96, radius=radius, depth=depth, location=(0,0,z))
    return finish(bpy.context.object, name, mat, (0,0,z))


def gear(name, teeth, radius, mat, base=0.4):
    # Upstream add_gear supports negative radius for inward-facing teeth.
    verts, faces, _, _ = add_gear(teeth, radius, 0.08, 0.10, base, math.radians(20), width=0.16)
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    return finish(obj, name, mat)


def make_asset(cfg, out):
    if cfg.get('kind') == 'source-mesh-assembly-v1':
        return make_source_asset(cfg, out)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    eas.register()
    scene = bpy.context.scene
    col = bpy.data.collections.new('Assembly')
    scene.collection.children.link(col)
    gold = material('INPUT | amber', (0.98,0.51,0.10))
    blue = material('PLANETS | ice blue', (0.12,0.64,0.85))
    steel = material('FIXED | silver', (0.49,0.59,0.68))
    green = material('OUTPUT | mint', (0.13,0.82,0.60))
    dark = material('HOUSING | graphite', (0.16,0.22,0.29))
    rs = cfg['sun_teeth'] * cfg['module'] / 2
    rp = cfg['planet_teeth'] * cfg['module'] / 2
    rr = cfg['ring_teeth'] * cfg['module'] / 2
    sun = gear('Sun', cfg['sun_teeth'], rs, gold, 0.50)
    ring = gear('Ring', cfg['ring_teeth'], -rr, steel, 0.34)
    # Align the simple upstream tooth pattern (tooth centre starts at half pitch).
    # Geometric contact is explicitly outside this teaching asset's claim.
    for i in range(cfg['planet_count']):
        a = i * 2 * math.pi / cfg['planet_count']
        p = gear(f'Planet_{i+1}', cfg['planet_teeth'], rp, blue, 0.47)
        p.location = ((rs+rp)*math.cos(a), (rs+rp)*math.sin(a), 0)
        p.rotation_euler.z = math.pi / cfg['planet_teeth']
    carrier = cylinder('Carrier', 2.18, 0.15, -0.43, green)
    cylinder('Housing_lower', 3.19, 0.22, -0.82, dark)
    cylinder('Housing_upper', 3.19, 0.22, 0.82, dark)
    cylinder('Input_shaft', 0.20, 1.30, 0.20, gold)
    # Orientation markers are separate meshes but grouped with their parent part by prefix.
    for i in range(3):
        a = i * 2 * math.pi / 3
        pin = cylinder(f'Carrier|pin{i+1}', 0.12, 0.60, -0.05, green)
        pin.location.x, pin.location.y = (rs+rp)*math.cos(a), (rs+rp)*math.sin(a)
    marker = cylinder('Sun|marker', 0.075, 0.045, 0.19, dark)
    marker.location.x = 0.52
    bpy.context.view_layer.update()
    props = scene.eas
    props.source = 'COLLECTION'
    props.collection = col
    props.group_mode = 'PREFIX'
    props.group_separator = '|'
    props.skip_child_parts = False
    assert bpy.ops.eas.set_assembly_position() == {'FINISHED'}
    inventory = []
    for o in col.objects:
        inventory.append({'name':o.name, 'vertices':len(o.data.vertices), 'faces':len(o.data.polygons),
                          'matrix':list(core.matrix_to_flat(o.matrix_world)), 'bounds':[list(v) for v in o.bound_box]})
    assert set(cfg['required_parts']) <= {o.name for o in col.objects}
    bpy.ops.wm.save_as_mainfile(filepath=str(out))
    savejson(out.with_suffix('.inventory.json'), {'parts': inventory, 'count':len(inventory), 'independent_meshes':True})


def make_source_asset(cfg, out):
    """Import licensed independent source meshes; no inferred hidden geometry."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    eas.register()
    col = bpy.data.collections.new('Assembly')
    bpy.context.scene.collection.children.link(col)
    palette = {name:material(name, spec['color'], spec.get('metallic', 0.6),
                            spec.get('roughness', 0.32), spec.get('preserve_surface', False))
               for name,spec in cfg['materials'].items()}
    for name, spec in cfg['materials'].items():
        if spec.get('fabric_weave'):
            nodes=palette[name].node_tree.nodes
            links=palette[name].node_tree.links
            coordinates=nodes.new('ShaderNodeTexCoord')
            waves=[]
            for direction in ('X','Y'):
                wave=nodes.new('ShaderNodeTexWave')
                wave.bands_direction=direction
                wave.inputs['Scale'].default_value=spec.get('weave_scale', 1200)
                links.new(coordinates.outputs['Object'],wave.inputs['Vector'])
                waves.append(wave)
            mix=nodes.new('ShaderNodeMath')
            mix.operation='MULTIPLY'
            links.new(waves[0].outputs['Fac'],mix.inputs[0])
            links.new(waves[1].outputs['Fac'],mix.inputs[1])
            bump=nodes.new('ShaderNodeBump')
            bump.inputs['Strength'].default_value=0.22
            bump.inputs['Distance'].default_value=spec.get('weave_depth', 0.00012)
            links.new(mix.outputs[0],bump.inputs['Height'])
            links.new(bump.outputs['Normal'],nodes.get('Principled BSDF').inputs['Normal'])
    for index, spec in enumerate(cfg.get('source_files', [])):
        source = ROOT/spec['path']
        assert hashlib.sha256(source.read_bytes()).hexdigest() == spec['sha256']
        assert source.suffix.lower() == '.stl', 'Explicitly supported source format required'
        bpy.ops.object.select_all(action='DESELECT')
        bpy.ops.wm.stl_import(filepath=str(source), global_scale=spec.get('scale', 1.0))
        if spec.get('split_loose', True):
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.select_all(action='SELECT')
            bpy.ops.mesh.separate(type='LOOSE')
            bpy.ops.object.mode_set(mode='OBJECT')
        imported = list(bpy.context.selected_objects)
        def sort_key(obj):
            points = [obj.matrix_world @ Vector(v) for v in obj.bound_box]
            lo,hi = core.bounds_of(points)
            return tuple(round(v, 6) for v in (*lo,*hi))
        imported.sort(key=sort_key)
        for part_index,obj in enumerate(imported):
            if 'parts' in spec and part_index not in spec['parts']:
                bpy.data.objects.remove(obj,do_unlink=True)
                continue
            name = f'source{index}_{part_index:03d}'
            if spec.get('cap_boundaries'):
                bm=bmesh.new()
                bm.from_mesh(obj.data)
                boundary=[e for e in bm.edges if e.is_boundary]
                if boundary:
                    bmesh.ops.holes_fill(bm,edges=boundary,sides=0)
                bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
                assert not [e for e in bm.edges if not e.is_manifold], 'Source cut did not close'
                bm.to_mesh(obj.data)
                bm.free()
            if spec.get('origin'):
                obj.data.transform(Matrix.Translation(-Vector(spec['origin'])))
            # Keep original author coordinates; changing origin must not move vertices.
            position = obj.location.copy()
            finish(obj,name,palette[cfg.get('part_materials',{}).get(name,'steel')],position)
    for spec in cfg.get('instances', []):
        source=bpy.data.objects[spec['source']]
        obj=source.copy()
        col.objects.link(obj)
        obj.name=spec['name']
        obj.location=spec.get('location',[0,0,0])
        obj.rotation_euler=spec.get('rotation_euler',[0,0,0])
    for spec in cfg.get('meshes', []):
        mesh=bpy.data.meshes.new(spec['name'])
        mesh.from_pydata(spec['vertices'],[],spec['faces'])
        mesh.update()
        obj=bpy.data.objects.new(spec['name'],mesh)
        bpy.context.scene.collection.objects.link(obj)
        finish(obj,spec['name'],palette[spec.get('material','steel')],
               spec.get('location', [0, 0, 0]))
        obj.rotation_euler = spec.get('rotation_euler', [0, 0, 0])
    for name in cfg.get('remove_prototypes', []):
        bpy.data.objects.remove(bpy.data.objects[name],do_unlink=True)
    parts = list(col.objects)
    for obj in parts:
        spec=cfg['materials'].get(obj.active_material.name,{})
        if spec.get('bevel_width',0)>0:
            bevel=obj.modifiers.new('Source edge finish','BEVEL')
            bevel.width=spec['bevel_width']
            bevel.segments=3
            bevel.use_clamp_overlap=True
            bevel.harden_normals=True
    assert len(parts)>=2, 'A single mesh is not an independent assembly'
    assert set(cfg['required_parts']) <= {o.name for o in parts}
    props=bpy.context.scene.eas
    props.source='COLLECTION'
    props.collection=col
    props.group_mode='PREFIX'
    props.group_separator='|'
    assert bpy.ops.eas.set_assembly_position() == {'FINISHED'}
    inventory=[]
    for obj in parts:
        points=[obj.matrix_world @ Vector(v) for v in obj.bound_box]
        lo,hi=core.bounds_of(points)
        inventory.append({'name':obj.name,'vertices':len(obj.data.vertices),
                          'faces':len(obj.data.polygons),'bounds':[list(lo),list(hi)],
                          'matrix':list(core.matrix_to_flat(obj.matrix_world))})
        bm=bmesh.new()
        bm.from_mesh(obj.data)
        inventory[-1]['boundary_edges']=sum(e.is_boundary for e in bm.edges)
        inventory[-1]['nonmanifold_edges']=sum(not e.is_manifold for e in bm.edges)
        bm.free()
    bpy.ops.wm.save_as_mainfile(filepath=str(out))
    savejson(out.with_suffix('.inventory.json'),{'parts':inventory,'count':len(parts),
             'independent_meshes':True,'source_files':cfg['source_files'],
             'scope':'Independent source components; identity and motion require review'})


def linear_action(animation_data):
    """Explicit interpolation for legacy and Blender 4.4+ layered actions."""
    if animation_data is None or animation_data.action is None:
        return
    action = animation_data.action
    curves = list(getattr(action, 'fcurves', []))
    for layer in getattr(action, 'layers', []):
        for strip in layer.strips:
            for bag in getattr(strip, 'channelbags', []):
                curves.extend(bag.fcurves)
    for curve in curves:
        curve.extrapolation = 'CONSTANT'
        for key in curve.keyframe_points:
            key.interpolation = 'LINEAR'


def verify_mesh_tracks(shot, count):
    """Compare evaluated Blender vertices against authored source interpolation.

    Before Boolean section modifiers: vertex identity must still match source.
    This verifies prescribed motion import, not physical material/contact behavior.
    """
    rows = []
    scene = bpy.context.scene
    frames = sorted({1, count, *[1+round(i*(count-1)/8) for i in range(9)]})
    for track in shot.get('mesh_tracks', []):
        obj = bpy.data.objects[track['object']]
        poses = track['poses']
        progress = [p['progress'] for p in poses]
        for frame in frames:
            scene.frame_set(frame)
            bpy.context.view_layer.update()
            t = (frame-1)/(count-1)
            hi = min(len(poses)-1, max(1, bisect.bisect_left(progress, t)))
            lo = hi-1
            w = (t-progress[lo])/(progress[hi]-progress[lo])
            evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
            mesh = evaluated.to_mesh()
            try:
                assert len(mesh.vertices) == len(poses[lo]['vertices'])
                error = max((vertex.co-Vector(tuple(a*(1-w)+b*w for a,b in zip(v0,v1)))).length
                            for vertex,v0,v1 in zip(mesh.vertices,poses[lo]['vertices'],poses[hi]['vertices']))
            finally:
                evaluated.to_mesh_clear()
            keys = obj.data.shape_keys.key_blocks
            total = sum(key.value for key in list(keys)[1:])
            rows.append({'object': obj.name, 'frame': frame, 'source_progress': t,
                         'maximum_vertex_error_m': error, 'relative_weight_sum': total})
            assert error < 2e-7 and abs(total-1) < 2e-5, rows[-1]
    return {'status': 'PASS', 'frames': frames, 'samples': rows,
            'maximum_vertex_error_m': max([r['maximum_vertex_error_m'] for r in rows]+[0]),
            'scope': 'Evaluated pre-section Blender vertices versus source pose interpolation; finite frames only'}


def prepare_data_tracks(shot, count):
    """Apply explicit, source-reviewed rigid transforms, never solve contacts."""
    seen=set()
    for track in shot.get('tracks', []):
        obj=bpy.data.objects[track['object']]
        for pose in track['poses']:
            frame=1+pose['progress']*(count-1)
            assert 1<=frame<=count
            for channel in ['location','rotation_euler','scale']:
                if channel in pose:
                    setattr(obj,channel,pose[channel])
                    obj.keyframe_insert(channel,frame=frame)
        linear_action(obj.animation_data)
        seen.add(obj.name)
    # Shape-key samples are authored vertex positions, not a geometry solver.
    for track in shot.get('mesh_tracks', []):
        obj=bpy.data.objects[track['object']]
        obj.shape_key_add(name='Basis')
        poses=track['poses']
        for i,pose in enumerate(poses):
            assert len(pose['vertices'])==len(obj.data.vertices)
            key=obj.shape_key_add(name=f'pose_{i:04d}')
            for v,co in zip(key.data,pose['vertices']): v.co=co
            frame=1+pose['progress']*(count-1)
            key.value=0
            if i>0: key.keyframe_insert('value',frame=1+poses[i-1]['progress']*(count-1))
            key.value=1
            key.keyframe_insert('value',frame=frame)
            key.value=0
            if i+1<len(poses): key.keyframe_insert('value',frame=1+poses[i+1]['progress']*(count-1))
        linear_action(obj.data.shape_keys.animation_data)
        seen.add(obj.name)
    return {'template':'data-keyframes-v1','tracked_objects':sorted(seen),
            'evaluated_mesh_alignment': verify_mesh_tracks(shot, count),
            'scope':'Explicit source-reviewed transforms; no contact/force simulation'}


def setup_render(width, height, fps):
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_WORKBENCH'
    s = scene.display.shading
    s.light = 'STUDIO'
    s.studiolight_rotate_z = 0.5
    s.color_type = 'MATERIAL'
    s.show_shadows = True
    s.show_cavity = True
    s.cavity_type = 'BOTH'
    s.curvature_ridge_factor = 1.4
    s.curvature_valley_factor = 1.1
    s.show_specular_highlight = True
    s.background_type = 'WORLD'
    scene.world = bpy.data.worlds.new('Background') if scene.world is None else scene.world
    scene.world.color = (0.026,0.037,0.059)
    scene.render.resolution_x = width
    scene.render.resolution_y = height
    scene.render.resolution_percentage = 100
    scene.render.fps = fps
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGB'
    scene.display.render_aa = '8'
    scene.view_settings.view_transform = 'Standard'
    scene.render.film_transparent = False
    scene.render.threads_mode = 'FIXED'
    scene.render.threads = 4


def configure_explosion(shot, count):
    p = bpy.context.scene.eas
    p.source = 'COLLECTION'
    p.collection = bpy.data.collections['Assembly']
    p.direction = 'WORLD_AXIS'
    p.axis = 'Z'
    p.distance = shot.get('distance', 1.8)
    p.magnitude = 'UNIFORM'
    p.use_sequence = True
    p.order_mode = 'MANUAL'
    p.overlap = 0.25
    p.group_mode = 'PREFIX'
    p.group_separator = '|'
    p.use_rotation = False
    p.use_phases = False
    p.use_camera = False
    p.replace_animation = True
    p.frame_start = 1
    p.frame_end = count
    for obj in p.collection.objects:
        obj.eas.exclude = obj.name in ['Sun', 'Sun|marker', 'Input_shaft'] or obj.name.startswith('Planet')
        obj.eas.distance_multiplier = {'Housing_upper':2.1,'Housing_lower':-1.4,'Ring':0.65,'Carrier':-0.65}.get(obj.name, -0.65)
        obj.eas.order = {'Housing_upper':0,'Housing_lower':1,'Ring':2,'Carrier':3}.get(obj.name,3)


def camera_region_points(region):
    """World-space editorial focus box; it never clips or changes the mesh."""
    lo, hi = region['min'], region['max']
    if len(lo) != 3 or len(hi) != 3 or any(a >= b for a, b in zip(lo, hi)):
        raise ValueError('camera_focus_region requires increasing 3D min/max')
    return [Vector((x, y, z)) for x in (lo[0], hi[0])
            for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]


def add_teaching_nail(shot, count):
    """Two editorial nail segments, not CAD inventory or fracture simulation."""
    spec = shot.get('teaching_nail')
    if not spec:
        return None
    edge = float(spec.get('cutting_edge_x', .050))
    y = float(spec.get('center_y', -.0045))
    width = float(spec.get('width', .0039))
    thickness = float(spec.get('thickness', .0004))
    surface = material('Teaching nail | warm ivory', (.78, .53, .39), 0, .48)
    objects = []
    for name, start, end in [('TeachingNail_Held', edge, edge+.0082),
                             ('TeachingNail_Offcut', edge-.0018, edge)]:
        bpy.ops.mesh.primitive_cube_add(size=1, location=((start+end)/2, y, 0))
        obj = bpy.context.object
        obj.name = name
        obj.dimensions = (end-start, width, thickness)
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        obj.data.materials.append(surface)
        obj['teaching_prop'] = True
        objects.append(obj)
    offcut = objects[1]
    base = offcut.location.copy()
    # Move towards the open front edge before dropping, so the fragment does
    # not visually pass down through the lower steel plate. Prescribed only.
    for progress, dy, dz, tilt in [(0,0,0,0),(.20,0,0,0),(.32,-.004,-.00025,.10),
                                   (.65,-.006,-.0025,.35),(1,-.007,-.003,.55)]:
        offcut.location = base + Vector((0,dy,dz))
        offcut.rotation_euler = (tilt, tilt*.6, 0)
        offcut.keyframe_insert('location', frame=1+progress*(count-1))
        offcut.keyframe_insert('rotation_euler', frame=1+progress*(count-1))
    linear_action(offcut.animation_data)
    return {'status': 'TEACHING_PROP', 'objects': [o.name for o in objects],
            'cutting_edge_x_m': edge, 'held_segment': 'Outside x >= cutting edge',
            'offcut': 'Inner tip x < cutting edge; prescribed forward release and fall after closure',
            'scope': 'Illustrated nail and prescribed separation; not fracture/contact/material simulation; excluded from mechanical inventory'}


def frame_camera(objects, frames, top=False, direction=None, roll=0, focus_region=None):
    scene = bpy.context.scene
    bpy.ops.object.camera_add()
    cam = bpy.context.object
    cam.name = 'ShotCamera'
    cam.data.type = 'ORTHO'
    direction = Vector(direction or ((0,-0.01,1) if top else (7,-11,10))).normalized()
    points = []
    for f in frames:
        scene.frame_set(f)
        bpy.context.view_layer.update()
        points.extend(o.matrix_world @ Vector(v) for o in objects for v in o.bound_box)
    if focus_region:
        points = camera_region_points(focus_region)
    lo, hi = core.bounds_of(points)
    center = (lo+hi)*0.5
    cam.location = center + direction * 30
    cam.rotation_euler = (center-cam.location).to_track_quat('-Z','Y').to_euler()
    if roll:
        cam.rotation_euler=(cam.rotation_euler.to_quaternion() @ Quaternion((0,0,1),math.radians(roll))).to_euler()
    bpy.context.view_layer.update()
    inv = cam.matrix_world.inverted()
    xy = [inv @ v for v in points]
    # World bounding-box centre is not necessarily the projected box centre
    # for an asymmetric imported assembly. Centre the actual screen bounds.
    offset = Vector(((min(v.x for v in xy)+max(v.x for v in xy))*0.5,
                     (min(v.y for v in xy)+max(v.y for v in xy))*0.5,0))
    cam.location += cam.matrix_world.to_quaternion() @ offset
    aspect = scene.render.resolution_x / scene.render.resolution_y
    # ortho_scale is camera width when aspect >=1, otherwise height.
    w = max(v.x for v in xy)-min(v.x for v in xy)
    h = max(v.y for v in xy)-min(v.y for v in xy)
    cam.data.ortho_scale = (max(w, h*aspect) if aspect >= 1 else max(h, w/aspect)) * 1.14
    scene.camera = cam
    return cam


def validate_motion(cfg):
    s,p,r = (cfg[k] for k in ['sun_teeth','planet_teeth','ring_teeth'])
    assert r == s+2*p, 'Coaxial centre distance constraint'
    assert (s+r) % cfg['planet_count'] == 0, 'Equal spacing assembly constraint'
    ws = cfg['motion']['sun_revolutions_per_second'] * 2*math.pi
    wc = ws*s/(s+r)
    wp = wc-(ws-wc)*s/p
    assert abs(s*(ws-wc)+r*(0-wc)) < 1e-10
    assert abs(s*(ws-wc)+p*(wp-wc)) < 1e-10
    return ws,wc,wp


def prepare_motion(cfg, count, fps):
    scene = bpy.context.scene
    ws,wc,wp = validate_motion(cfg)
    for o in bpy.data.collections['Assembly'].objects:
        if o.name.startswith('Housing'):
            o.hide_render = True
    # Formula-based channels sampled every frame; no physics/contact claims.
    for f in range(1,count+1):
        t = (f-1)/fps
        for name in ['Sun','Sun|marker','Input_shaft']:
            o = bpy.data.objects[name]
            if name == 'Sun|marker':
                o.location.x, o.location.y = 0.52*math.cos(ws*t),0.52*math.sin(ws*t)
                o.keyframe_insert('location',frame=f)
            o.rotation_euler.z = ws*t
            o.keyframe_insert('rotation_euler',frame=f)
        for i in range(3):
            a = i*2*math.pi/3+wc*t
            for name in [f'Planet_{i+1}',f'Carrier|pin{i+1}']:
                o = bpy.data.objects[name]
                o.location.x,o.location.y = 1.8*math.cos(a),1.8*math.sin(a)
                o.keyframe_insert('location',frame=f)
                if name.startswith('Planet'):
                    o.rotation_euler.z = math.pi/18+wp*t
                    o.keyframe_insert('rotation_euler',frame=f)
        carrier = bpy.data.objects['Carrier']
        carrier.rotation_euler.z = wc*t
        carrier.keyframe_insert('rotation_euler',frame=f)
    return {'sun_rad_s':ws,'carrier_rad_s':wc,'planet_rad_s':wp,'ratio':ws/wc,
            'willis_residual':abs(cfg['sun_teeth']*(ws-wc)-cfg['ring_teeth']*wc)}


def render_shot(args):
    eas.register()
    bpy.ops.wm.open_mainfile(filepath=str(args.asset))
    cfg = json.loads(args.assembly_config.read_text())
    shot_bytes = args.shot.read_bytes()
    shot = json.loads(shot_bytes)
    count = max(2,round(shot['seconds']*args.fps))
    setup_render(args.width,args.height,args.fps)
    scene = bpy.context.scene
    parts = list(bpy.data.collections['Assembly'].objects)
    if shot.get('visible_parts'):
        assert set(shot['visible_parts']) <= {o.name for o in parts}
        for obj in parts:
            obj.hide_render=obj.name not in shot['visible_parts']
    original = {o.name:o.matrix_world.copy() for o in parts}
    report = {'shot': {k: v for k, v in shot.items() if k not in {'tracks', 'mesh_tracks'}},
              'source_shot': {'path': str(args.shot), 'sha256': hashlib.sha256(shot_bytes).hexdigest()},
              'checks':{},'unverified':cfg['unverified']}
    template = shot['template']
    if template in ['explode','assemble','exploded']:
        configure_explosion(shot,count)
        assert bpy.ops.eas.animate(mode='EXPLODE') == {'FINISHED'}
        scene.frame_set(count)
        bpy.context.view_layer.update()
        # Axial bounding boxes of the moved rigid groups must be genuinely separated.
        def zb(name):
            o = bpy.data.objects[name]
            v = [o.matrix_world @ Vector(c) for c in o.bound_box]
            return min(c.z for c in v),max(c.z for c in v)
        pairs = [('Housing_upper','Ring'),('Ring','Sun'),('Sun','Carrier'),('Carrier','Housing_lower')]
        gaps = {a+' / '+b:zb(a)[0]-zb(b)[1] for a,b in pairs}
        assert min(gaps.values()) > 0.05, gaps
        report['checks']['exploded_axial_gaps'] = gaps
        assert bpy.ops.eas.animate(mode='ASSEMBLE') == {'FINISHED'}
        scene.frame_set(count)
        bpy.context.view_layer.update()
        residual = max(abs(o.matrix_world[i][j]-original[o.name][i][j]) for o in parts for i in range(4) for j in range(4))
        assert residual < 1e-5, residual
        report['checks']['reassembly_max_matrix_error'] = residual
        assert bpy.ops.eas.animate(mode='EXPLODE' if template != 'assemble' else 'ASSEMBLE') == {'FINISHED'}
    elif template == 'motion':
        report['checks']['motion'] = (prepare_data_tracks(shot,count)
            if cfg.get('kind')=='source-mesh-assembly-v1' else prepare_motion(cfg,count,args.fps))
    elif template == 'detail':
        for o in parts:
            if o.name.startswith('Housing'):
                o.hide_render = True
    elif template != 'overall':
        raise ValueError('Unknown shot template: '+template)
    visible = [o for o in parts if not o.hide_render]
    if shot.get('section_plane'):
        # An explicit local teaching section, applied after deformation. It is
        # geometry removal, not transparency or an asserted disassembly path.
        plane = shot['section_plane']
        if plane.get('axis') != 'y' or plane.get('side') not in {'negative', 'positive'}:
            raise ValueError('Section supports an explicit +/-Y half-space only')
        offset = float(plane.get('offset', 0))
        sign = -1 if plane['side'] == 'negative' else 1
        bpy.ops.mesh.primitive_cube_add(size=1, location=(0, offset + sign * .5, 0))
        cutter = bpy.context.object
        cutter.name = 'TeachingSectionCutter'
        cutter.hide_render = True
        for obj in visible:
            modifier = obj.modifiers.new('Teaching longitudinal section', 'BOOLEAN')
            modifier.operation = 'DIFFERENCE'
            modifier.solver = 'EXACT'
            modifier.object = cutter
        report['section'] = dict(plane, method='Boolean difference after prescribed deformation')
    frames = sorted(set([1,count//2,count])) if template in ['explode','assemble','exploded','motion'] else [1]
    cam = frame_camera(visible, frames, top=template in ['motion','detail'] and shot.get('camera_view')!='oblique',
                       direction=shot.get('camera_direction'),roll=shot.get('camera_roll',0),
                       focus_region=shot.get('camera_focus_region'))
    if shot.get('check_pairs'):
        overlaps=[]
        checked_frames=range(1,count+1) if shot.get('check_all_frames') else frames
        for f in checked_frames:
            scene.frame_set(f)
            bpy.context.view_layer.update()
            trees={}
            for name in {n for pair in shot['check_pairs'] for n in pair}:
                obj=bpy.data.objects[name]
                trees[name]=BVHTree.FromPolygons([obj.matrix_world @ v.co for v in obj.data.vertices],
                                [list(p.vertices) for p in obj.data.polygons],all_triangles=False)
            for a,b in shot['check_pairs']:
                hits=trees[a].overlap(trees[b])
                if hits: overlaps.append({'frame':f,'pair':[a,b],'triangle_pairs':len(hits)})
        report['checks']['surface_overlap_candidates']=overlaps
        report['checks']['surface_overlap_frame_count']=len(checked_frames)
        report['checks']['surface_overlap_scope']='Sampled source triangle overlaps; contact and force are not inferred'
    if shot.get('visual_profile'):
        sys.path.insert(0,str(ROOT/'blender'))
        import studio_style
        report['visual_style'] = studio_style.apply(shot['visual_profile'],visible,frames,cam,
                                                   shot.get('studio_lighting'))
    # Projection only: this does not prove lack of occlusion or visual comprehension.
    margin = 1
    for f in range(1,count+1):
        scene.frame_set(f)
        focus = shot.get('camera_focus_region')
        projected = ([('editorial_focus_region', point) for point in camera_region_points(focus)]
                     if focus else [(o.name, o.matrix_world @ Vector(v))
                                    for o in visible for v in o.bound_box])
        for name, point in projected:
            p = world_to_camera_view(scene,cam,point)
            margin = min(margin,p.x,p.y,1-p.x,1-p.y)
            assert p.z > 0 and 0.01 <= p.x <= 0.99 and 0.01 <= p.y <= 0.99, (name,f,list(p))
    report['checks']['min_projected_margin'] = margin
    report['checks']['projection_scope'] = ('Editorial focus region only; surrounding assembly intentionally extends outside detail framing'
                                            if shot.get('camera_focus_region') else 'Whole assembly bounding boxes')
    if shot.get('camera_focus_region'):
        report['camera_focus_region'] = shot['camera_focus_region']
    teaching_nail = add_teaching_nail(shot, count)
    if teaching_nail:
        report['teaching_nail'] = teaching_nail
    args.out.mkdir(parents=True,exist_ok=True)
    savejson(args.out/'checks.json',report)
    if args.checks_only:
        return
    # Keyframes/short-motion previews are independently inspectable before full rendering.
    if args.keys:
        selected = frames
    elif template in ['overall','detail','exploded']:
        selected = [count if template == 'exploded' else 1]
    else:
        selected = range(1,count+1)
    if args.chunk_frames and not args.keys:
        render_chunked(scene, selected, args)
        return
    for f in selected:
        scene.frame_set(f)
        scene.render.filepath = str(args.out/f'{f:05d}.png')
        bpy.ops.render.render(write_still=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command',choices=['asset','shot'])
    parser.add_argument('--asset',type=Path)
    parser.add_argument('--assembly-config',type=Path,default=ROOT/'config/assembly.json')
    parser.add_argument('--shot',type=Path)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--width',type=int,default=540)
    parser.add_argument('--height',type=int,default=625)
    parser.add_argument('--fps',type=int,default=15)
    parser.add_argument('--keys',action='store_true')
    parser.add_argument('--checks-only',action='store_true')
    parser.add_argument('--chunk-frames', type=int, default=0)
    parser.add_argument('--video-output', type=Path)
    args = parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    if args.command == 'asset':
        make_asset(json.loads(args.assembly_config.read_text()),args.out)
    else:
        render_shot(args)

if __name__ == '__main__':
    main()
