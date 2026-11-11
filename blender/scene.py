"""Reusable teaching asset and thin EAS adapter, not a geometry solver.

Run through scripts/produce.py. Blender must exit nonzero for any failed assertion.
"""
import argparse
import json
import math
from pathlib import Path
import sys
import time

import bpy
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'blender/vendor'))
import exploded_assembly_studio as eas
from exploded_assembly_studio import core
from add_mesh_gears import add_gear


def savejson(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2))


def material(name, color, metal=0.3):
    m = bpy.data.materials.new(name)
    m.diffuse_color = (*color, 1)
    m.use_nodes = True
    p = m.node_tree.nodes.get('Principled BSDF')
    p.inputs['Base Color'].default_value = (*color, 1)
    p.inputs['Metallic'].default_value = metal
    p.inputs['Roughness'].default_value = 0.32
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


def frame_camera(objects, frames, top=False):
    scene = bpy.context.scene
    bpy.ops.object.camera_add()
    cam = bpy.context.object
    cam.name = 'ShotCamera'
    cam.data.type = 'ORTHO'
    direction = Vector((0,-0.01,1) if top else (7,-11,10)).normalized()
    points = []
    for f in frames:
        scene.frame_set(f)
        bpy.context.view_layer.update()
        points.extend(o.matrix_world @ Vector(v) for o in objects for v in o.bound_box)
    lo, hi = core.bounds_of(points)
    center = (lo+hi)*0.5
    cam.location = center + direction * 30
    cam.rotation_euler = (center-cam.location).to_track_quat('-Z','Y').to_euler()
    bpy.context.view_layer.update()
    inv = cam.matrix_world.inverted()
    xy = [inv @ v for v in points]
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
    cfg = json.loads((ROOT/'config/assembly.json').read_text())
    shot = json.loads(args.shot.read_text())
    count = max(2,round(shot['seconds']*args.fps))
    setup_render(args.width,args.height,args.fps)
    scene = bpy.context.scene
    parts = list(bpy.data.collections['Assembly'].objects)
    original = {o.name:o.matrix_world.copy() for o in parts}
    report = {'shot':shot,'checks':{},'unverified':cfg['unverified']}
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
        report['checks']['motion'] = prepare_motion(cfg,count,args.fps)
    elif template == 'detail':
        for o in parts:
            if o.name.startswith('Housing'):
                o.hide_render = True
    elif template != 'overall':
        raise ValueError('Unknown shot template: '+template)
    visible = [o for o in parts if not o.hide_render]
    frames = sorted(set([1,count//2,count])) if template in ['explode','assemble','exploded','motion'] else [1]
    cam = frame_camera(visible, frames, top=template in ['motion','detail'])
    # Projection only: this does not prove lack of occlusion or visual comprehension.
    margin = 1
    for f in range(1,count+1):
        scene.frame_set(f)
        for o in visible:
            for v in o.bound_box:
                p = world_to_camera_view(scene,cam,o.matrix_world @ Vector(v))
                margin = min(margin,p.x,p.y,1-p.x,1-p.y)
                assert p.z > 0 and 0.01 <= p.x <= 0.99 and 0.01 <= p.y <= 0.99, (o.name,f,list(p))
    report['checks']['min_projected_margin'] = margin
    args.out.mkdir(parents=True,exist_ok=True)
    savejson(args.out/'checks.json',report)
    # Keyframes/short-motion previews are independently inspectable before full rendering.
    if args.keys:
        selected = frames
    elif template in ['overall','detail','exploded']:
        selected = [count if template == 'exploded' else 1]
    else:
        selected = range(1,count+1)
    for f in selected:
        scene.frame_set(f)
        scene.render.filepath = str(args.out/f'{f:05d}.png')
        bpy.ops.render.render(write_still=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command',choices=['asset','shot'])
    parser.add_argument('--asset',type=Path)
    parser.add_argument('--shot',type=Path)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--width',type=int,default=540)
    parser.add_argument('--height',type=int,default=625)
    parser.add_argument('--fps',type=int,default=15)
    parser.add_argument('--keys',action='store_true')
    args = parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    if args.command == 'asset':
        make_asset(json.loads((ROOT/'config/assembly.json').read_text()),args.out)
    else:
        render_shot(args)

if __name__ == '__main__':
    main()
