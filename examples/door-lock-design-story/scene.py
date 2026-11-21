"""Original low-cost storyboard plates for 把钥匙放进口袋. Run inside Blender."""
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Vector

HERE = Path(__file__).resolve().parent
args = sys.argv[sys.argv.index('--') + 1:]
output = Path(args[0]).resolve()
output.mkdir(parents=True, exist_ok=True)
edit = json.loads((HERE / 'edit.json').read_text())
BLUE = (0.12, 0.56, 0.83)
GOLD = (0.98, 0.63, 0.19)
BRASS = (0.80, 0.57, 0.29)
TEAL = (0.13, 0.29, 0.29)
CREAM = (0.73, 0.68, 0.56)
INK = (0.077, 0.10, 0.13)
STEEL = (0.31, 0.44, 0.51)
WHITE = (0.93, 0.92, 0.81)
WOOD = (0.31, 0.145, 0.075)


def color(obj, rgb):
    obj.color = (*rgb, 1)
    return obj


def box(name, center, dims, rgb, bevel=0.035, parent=None):
    bpy.ops.mesh.primitive_cube_add(size=1)
    obj = bpy.context.object
    obj.name, obj.parent, obj.location, obj.dimensions = name, parent, center, dims
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if bevel:
        mod = obj.modifiers.new('Rounded edges', 'BEVEL')
        mod.width, mod.segments = bevel, 3
        obj.modifiers.new('Weighted normals', 'WEIGHTED_NORMAL')
    return color(obj, rgb)


def cyl(name, center, radius, depth, rgb, axis='Z', parent=None):
    bpy.ops.mesh.primitive_cylinder_add(vertices=40, radius=radius, depth=depth)
    obj = bpy.context.object
    obj.name, obj.parent, obj.location = name, parent, center
    if axis == 'X':
        obj.rotation_euler.y = math.pi / 2
    if axis == 'Y':
        obj.rotation_euler.x = math.pi / 2
    for poly in obj.data.polygons:
        poly.use_smooth = len(poly.vertices) == 4
    return color(obj, rgb)


def empty(name, center=(0, 0, 0), parent=None):
    obj = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(obj)
    obj.parent, obj.location = parent, center
    return obj


def mesh(name, vertices, faces, rgb, parent=None):
    data = bpy.data.meshes.new(name)
    data.from_pydata(vertices, [], faces)
    data.update()
    obj = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(obj)
    obj.parent = parent
    return color(obj, rgb)


def text(title, center, size, rgb, angle=math.pi / 2, parent=None):
    font = bpy.data.curves.new(title, 'FONT')
    font.body, font.size, font.align_x, font.align_y = title, size, 'CENTER', 'CENTER'
    obj = bpy.data.objects.new(title, font)
    bpy.context.collection.objects.link(obj)
    obj.parent, obj.location, obj.rotation_euler.x = parent, center, angle
    return color(obj, rgb)


def key_motion(obj, attribute, values):
    for seconds, value in values:
        setattr(obj, attribute, value)
        obj.keyframe_insert(data_path=attribute, frame=start + round(seconds * 30))


def camera(center, focus, width, move=None, zoom=()):
    obj = bpy.data.objects.new('Camera', bpy.data.cameras.new('Orthographic camera'))
    bpy.context.collection.objects.link(obj)
    obj.data.type, obj.data.ortho_scale = 'ORTHO', width
    bpy.context.scene.camera = obj
    for seconds, point, target in [(0, center, focus), *([move] if move else [])]:
        obj.location = point
        obj.rotation_euler = (Vector(target) - obj.location).to_track_quat('-Z', 'Y').to_euler()
        for attr in ('location', 'rotation_euler'):
            obj.keyframe_insert(data_path=attr, frame=start + round(seconds * 30))
    for seconds, scale in ((0, width), *zoom):
        obj.data.ortho_scale = scale
        obj.data.keyframe_insert(data_path='ortho_scale', frame=start + round(seconds * 30))


def blade(parent, rgb, teeth):
    # Profile is extruded along Y. The shoulder remains outside the cutaway.
    outline = [(0.25, -0.48), (2.60, -0.48), *reversed(reader_profile(teeth))]
    vertices = [(x, y, z) for y in (-0.09, 0.09) for x, z in outline]
    count = len(outline)
    sides = [(i, (i + 1) % count, (i + 1) % count + count, i + count)
             for i in range(count)]
    mesh('Cut edge of key', vertices,
         [tuple(reversed(range(count))), tuple(range(count, 2 * count)), *sides], BRASS, parent)
    box('Key head', (-0.21, 0, -0.32), (1.0, 0.19, 0.80), rgb, 0.14, parent)
    cyl('Key head rivet', (-0.44, -0.105, -0.32), 0.10, 0.035, INK, 'Y', parent)


def reader_profile(teeth):
    return [(0.25, -0.12), (0.54, teeth[0]), (0.83, teeth[0]),
            (1.13, teeth[1]), (1.53, teeth[1]), (1.90, -0.16), (2.60, -0.20)]


def hallway(success):
    box('Terrazzo floor', (0, 1, -0.14), (16, 11, 0.25), STEEL)
    box('Left wall', (-4.12, 0.15, 2.35), (4, 0.45, 4.7), CREAM)
    box('Right wall', (3.96, 0.15, 2.35), (5, 0.45, 4.7), CREAM)
    box('Header', (-0.25, 0.18, 4.26), (3.1, 0.42, 1.0), CREAM)
    box('Interior wall', (-0.1, 2.85, 2.30), (12, 0.1, 4.6), TEAL)
    for x in (-1.82, 1.40):
        box('Jamb', (x, -0.07, 1.89), (0.24, 0.40, 3.78), INK)
    hinge = empty('Door hinge', (1.29, 0.02, 0))
    box('Wood door', (-1.48, 0, 1.88), (2.97, 0.23, 3.73), WOOD, 0.04, hinge)
    box('Inset door panel', (-1.48, -0.126, 2.33), (2.49, 0.06, 2.57), (0.42, 0.23, 0.12),
        0.07, hinge)
    box('Number plaque', (-1.48, -0.16, 3.12), (0.72, 0.07, 0.28), INK, 0.025, hinge)
    text('203', (-1.48, -0.208, 3.12), 0.18, WHITE, parent=hinge)
    cyl('Cylinder escutcheon', (-2.53, -0.18, 1.82), 0.20, 0.13, BRASS, 'Y', hinge)
    box('Key entrance', (-2.53, -0.252, 1.82), (0.04, 0.027, 0.135), INK, 0.01, hinge)
    cyl('Handle', (-2.53, -0.25, 1.47), 0.13, 0.34, INK, 'Y', hinge)
    box('Lever', (-2.28, -0.42, 1.47), (0.56, 0.13, 0.13), BRASS, 0.04, hinge)

    actor = empty('Person in terracotta coat', (-3.05, -1.65, 0))
    coat = (0.50, 0.21, 0.115)
    skin = (0.72, 0.48, 0.33)
    for x in (-0.19, 0.19):
        box('Trouser leg', (x, 0, 0.68), (0.30, 0.37, 1.31), INK, 0.12, actor)
        box('Boot', (x, 0.08, 0.13), (0.36, 0.54, 0.25), INK, 0.09, actor)
    box('Coat', (0, 0, 1.69), (0.87, 0.55, 1.02), coat, 0.23, actor)
    box('Pocket front', (0.21, -0.405, 1.46), (0.39, 0.055, 0.34), (0.32, 0.13, 0.09),
        0.03, actor)
    box('Pocket lining', (0.21, -0.331, 1.29), (0.35, 0.14, 0.065),
        (0.32, 0.13, 0.09), 0.025, actor)
    cyl('Neck', (0, 0, 2.24), 0.15, 0.18, skin, parent=actor)
    bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=12, radius=0.29)
    head = bpy.context.object
    head.parent, head.location, head.scale = actor, (0, 0, 2.48), (1, 0.84, 1.15)
    color(head, skin)
    cyl('Cap', (0, 0, 2.72), 0.29, 0.12, INK, parent=actor)
    arm = box('Sleeve', (0, 0, 0), (0.24, 0.24, 1), coat, 0.075)
    hand = empty('Wrist and keyring')
    box('Hand', (-0.07, -0.14, 0), (0.19, 0.20, 0.17), skin, 0.055, hand)
    keyring = empty('Ring carried by the wrist', parent=hand)
    key = empty('Inserted key', (0, 0.115, 0), keyring)
    key.rotation_euler.z = math.pi / 2
    key.scale = (0.16, 0.16, 0.16)
    blade(key, GOLD if success else BLUE, (-0.04, 0.12) if success else (0.12, -0.04))
    spare = empty('Other key', (-0.03, 0.078, -0.11) if success else (0.12, -0.09, -0.095),
                  keyring)
    spare.rotation_euler.y = 1.0
    spare.scale = (0.118, 0.118, 0.118)
    blade(spare, BLUE if success else GOLD, (0.12, -0.04) if success else (-0.04, 0.12))
    # Move wrist, key and sleeve on the same pose clock.
    reached = (-1.24, -0.665, 1.865)
    poses = [(0, (-2.02, -1.29, 1.78), 0),
             (1.5, (-1.24, -0.98, 1.865), 0), (2.1, reached, 0),
             (2.8, reached, 0.40 if success else 0.035)]
    if success:
        poses += [(3.1, (-1.24, -1.01, 1.865), 0),
                  (4.15, (-2.84, -1.95, 2.00), 0), (4.70, (-2.84, -1.95, 1.64), 0),
                  (5.15, (-2.82, -2.03, 1.56), 0), (5.62, (-2.68, -2.04, 1.72), 0)]
        key_motion(keyring, 'rotation_euler', [(0, (0, 0, 0)), (3.15, (0, 0, 0)),
                                                  (4.15, (-math.pi / 2, 0, 0))])
        key_motion(keyring, 'location', [(0, (0, 0, 0)), (4.7, (0, 0, 0)),
                                             (5.15, (-0.02, 0.05, -0.095))])
        for obj in keyring.children_recursive:
            obj.hide_render = False
            obj.keyframe_insert(data_path='hide_render', frame=start + round(5.10 * 30))
            obj.hide_render = True
            obj.keyframe_insert(data_path='hide_render', frame=start + round(5.15 * 30))
        key_motion(hinge, 'rotation_euler', [(0, (0, 0, 0)), (3.1, (0, 0, 0)),
                                                  (5.1, (0, 0, -1.06))])
        key_motion(actor, 'location', [(0, (-3.05, -1.65, 0)), (5.62, (-3.05, -1.65, 0)),
                                              (6.5, (-0.75, -1.29, 0)), (7.8, (-0.23, 0.83, 0))])
        poses += [(6.5, (-0.50, -1.55, 1.43), 0), (7.8, (0.02, 0.55, 1.43), 0)]
    else:
        poses += [(3.8, reached, 0), (4.6, (-1.65, -1.23, 1.78), 0),
                  (6.3, (-1.84, -1.40, 1.83), -0.55)]
    key_motion(hand, 'location', [(s, p) for s, p, _ in poses])
    key_motion(hand, 'rotation_euler', [(s, (0, r, 0)) for s, _, r in poses])
    for seconds, wrist, _ in poses:
        shoulder = (-2.69, -1.62, 2.02)
        if success and seconds >= 6.5:
            shoulder = (-0.39, -1.26, 2.02) if seconds == 6.5 else (0.13, 0.86, 2.02)
        delta = Vector(wrist) - Vector(shoulder)
        arm.location = (Vector(wrist) + Vector(shoulder)) / 2
        arm.scale.z = delta.length
        arm.rotation_euler = delta.to_track_quat('Z', 'Y').to_euler()
        for attr in ('location', 'scale', 'rotation_euler'):
            arm.keyframe_insert(data_path=attr, frame=start + round(seconds * 30))
    if success:
        camera((-4.2, -6.8, 3.45), (-1.74, -0.20, 1.82), 5.1,
               (7.7, (-3.9, -7.6, 3.72), (-1.31, 0, 1.72)),
               zoom=((3.1, 5.1), (4.8, 4.25), (5.5, 4.25), (7.7, 5.3)))
    else:
        camera((-4.0, -6.7, 3.45), (-1.54, -0.40, 1.90), 4.75,
               (6.2, (-2.9, -6.0, 2.92), (-1.43, -0.48, 1.88)))


def safe():
    box('Stone floor', (0, 0, -0.14), (15, 12, 0.25), WOOD)
    box('Workshop wall', (0, 2.2, 2.3), (15, 0.30, 5), (0.28, 0.24, 0.21))
    box('Safe housing', (0, 0.5, 2.02), (4.1, 1.4, 4.03), INK, 0.11)
    box('Rebated door', (0, -0.33, 2.06), (3.72, 0.37, 3.53), STEEL, 0.07)
    box('Safe panel', (0, -0.54, 2.08), (3.21, 0.10, 3.03), TEAL, 0.055)
    for z in (0.93, 3.23):
        cyl('Safe hinge', (1.75, -0.58, z), 0.16, 0.49, BRASS)
    cyl('Lock hardware', (-0.27, -0.67, 2.05), 0.61, 0.19, BRASS, 'Y')
    cyl('Lock face', (-0.27, -0.78, 2.05), 0.49, 0.13, INK, 'Y')
    box('Lock opening', (-0.27, -0.868, 2.05), (0.10, 0.03, 0.31), BRASS)
    for z in (-0.81, 0.81):
        for x in (-1.43, 1.43):
            cyl('Rivet', (x, -0.62, 2.09 + z), 0.08, 0.08, BRASS, 'Y')
    text('BANK SAFE', (-0.24, -0.61, 2.91), 0.235, BRASS)
    camera((-4.0, -8, 3.45), (0, -0.36, 1.99), 7.1,
           (5.8, (-0.6, -7, 2.63), (-0.24, -0.63, 2.0)))


def transition():
    box('Domestic door section', (0, 0.35, 1.91), (6.5, 0.57, 4.2), WOOD, 0.05)
    box('Varnished inset', (0, 0, 2.05), (5.86, 0.19, 3.19), (0.47, 0.25, 0.13))
    cyl('Small escutcheon', (-0.27, -0.15, 2.05), 0.53, 0.15, BRASS, 'Y')
    cyl('Lock face', (-0.27, -0.25, 2.05), 0.44, 0.10, INK, 'Y')
    box('Key entrance', (-0.27, -0.309, 2.05), (0.075, 0.025, 0.28), BRASS)
    prop = empty('Yale-style flat key, original illustration', (-1.8, -0.64, 1.1))
    prop.rotation_euler.y = -0.22
    blade(prop, GOLD, (-0.05, 0.14))
    key_motion(prop, 'location', [(0, (-1.8, -0.64, 0.67)), (4.2, (-1.1, -0.80, 1.64)),
                                  (6.8, (-1.1, -0.80, 1.64))])
    camera((-0.6, -7, 2.63), (-0.24, -0.12, 2.0), 7.1,
           (6.7, (-2.0, -5.7, 3.42), (0, -0.42, 1.83)))


def door_adaptation():
    box('Display table', (0, 0.2, -0.30), (12, 7, 0.35), TEAL)
    for index, (x, depth) in enumerate(((-1.68, 0.28), (1.65, 1.20))):
        slab = empty('Door sample from a common front datum', (x, 0, 0))
        box('Board edge', (0, depth / 2, 1.18), (1.50, depth, 2.38),
            (WOOD, (0.56, 0.32, 0.14))[index], 0.035, slab)
        cyl('Outer lock face', (0, -0.045, 1.43), 0.29, 0.15, BRASS, 'Y', slab)
        box('Key entrance', (0, -0.129, 1.43), (0.06, 0.034, 0.21), INK, 0.015, slab)
        for y in (0.0, depth):
            box('Board thickness endpoint', (0.85, y, 0.08), (0.11, 0.08, 0.25),
                WHITE, 0.012, slab)
        box('Board depth reference', (0.85, depth / 2, 0.05), (0.052, depth, 0.06),
            WHITE, 0.01, slab)
        key_motion(slab, 'rotation_euler', [(0, (0, 0, 0)), (5.7, (0, 0, -0.68))])
    key = empty('Same size flat key', (-0.50, -1.08, 1.45))
    key.scale = (0.34, 0.34, 0.34)
    blade(key, GOLD, (-0.04, 0.12))
    key_motion(key, 'location', [(0, (-1.99, -0.65, 1.48)),
                                 (2.2, (-0.50, -1.25, 1.54)),
                                 (4.3, (1.25, -1.08, 1.48))])
    camera((2.6, -7.5, 4.3), (0.05, 0.15, 1.19), 6.5,
           (6.8, (3.8, -7.3, 5), (0.15, 0.18, 1.18)))


def desk(pattern):
    box('Workshop test table', (0, 0.55, -0.64), (10, 5.7, 0.48), WOOD, 0.12)
    box('Felt work mat', (0, 0.18, -0.37), (6.1, 3.0, 0.08), TEAL, 0.18)
    for row, offset in enumerate((-0.76, 0.76)):
        rgb = (BLUE, GOLD)[row]
        teeth = ((0.13, -0.06), (-0.06, 0.13))[row] if pattern else (-0.05, -0.05)
        prop = empty('Comparison key', (-1.7, offset, -0.26))
        prop.rotation_euler.x = math.pi / 2
        if pattern:
            blade(prop, rgb, teeth)
        else:
            box('Plain metal blank', (1.12, 0, -0.31), (2.45, 0.17, 0.43), rgb, 0.06, prop)
        key_motion(prop, 'location', [(0, (-3.6, offset, -0.26)),
                                      (1.35, (-1.7, offset, -0.26))])
        for index, x in enumerate((-1.02, -0.39)):
            probe = empty('Sliding feeler', (x, offset - 0.41, 0.70))
            cyl('Touch point', (0, 0, 0), 0.085, 0.28, WHITE, 'Y', probe)
            cyl('Readout marker', (0, 0.02, 0.16), 0.17, 0.07, rgb, 'Z', probe)
            target = offset - teeth[index] - 0.14
            key_motion(probe, 'location', [(0, (x, offset - 0.58, 0.04)),
                                           (1.5, (x, offset - 0.58, 0.04)),
                                           (2.65, (x, target, 0.04))])
        box('Guide rail', (-0.69, offset - 0.68, -0.04), (1.14, 0.10, 0.13), INK, 0.03)
    camera((0.5, -5.4, 7.3), (-0.29, 0.35, -0.05), 6.35,
           (4.8, (0, -4.2, 7.1), (-0.50, 0.37, -0.06)))


def half_tube(name, radius, inner, x0, x1, rgb, parent=None):
    points = [(math.cos(math.pi * i / 28), math.sin(math.pi * i / 28)) for i in range(29)]
    vertices = [(x, r * z, r * y) for x in (x0, x1) for r in (radius, inner) for y, z in points]
    faces = []
    count = len(points)
    for i in range(count - 1):
        j = i + 1
        faces.extend(((i, j, 2 * count + j, 2 * count + i),
                      (count + i, 3 * count + i, 3 * count + j, count + j),
                      (i, count + i, count + j, j),
                      (2 * count + i, 2 * count + j, 3 * count + j, 3 * count + i)))
    for i in (0, count - 1):
        faces.append((i, 2 * count + i, 3 * count + i, count + i))
    return mesh(name, vertices, faces, rgb, parent)


def spring(name, parent, lo, hi):
    wire = bpy.data.curves.new(name, 'CURVE')
    wire.dimensions, wire.bevel_depth, wire.bevel_resolution = '3D', 0.026, 2
    spline = wire.splines.new('POLY')
    spline.points.add(72)
    for i, point in enumerate(spline.points):
        point.co = (0.119 * math.cos(i * math.pi / 6), 0.119 * math.sin(i * math.pi / 6),
                    lo + (hi - lo) * i / 72, 1)
    obj = bpy.data.objects.new(name, wire)
    bpy.context.collection.objects.link(obj)
    obj.parent = parent
    return obj


def cutaway(success):
    rotor = empty('Rotating cylinder')
    box('Display base', (0.0, 0, -1.33), (16, 8, 0.25), TEAL)
    half_tube('Stationary housing, rear section', 1.04, 0.755, -0.80, 2.68, STEEL)
    half_tube('Plug, rear section', 0.75, 0.43, -0.76, 2.64, BRASS, rotor)
    cyl('Fixed housing rear end', (2.68, 0, 0), 1.04, 0.10, STEEL, 'X')
    key = empty('Key in section', (-3.25, 0, 0), rotor)
    teeth = (-0.04, 0.12) if success else (0.12, -0.04)
    blade(key, GOLD if success else BLUE, teeth)
    profile = reader_profile(teeth)
    positions = []
    for frame in range(46):
        progress = frame / 45
        ease = progress * progress * (3 - 2 * progress)
        positions.append((frame / 30, -3.25 + 3.28 * ease))
    key_motion(key, 'location', [(seconds, (x, 0, 0)) for seconds, x in positions])
    for i, x in enumerate((0.70, 1.46)):
        correct = (-0.04, 0.12)[i]
        length = 0.75 - correct
        seam = empty('Key pin at {:.2f}'.format(x), (x, 0, 0.48), rotor)
        cyl('Lower pin', (0, 0, -length / 2), 0.126, length, GOLD, parent=seam)
        driver = empty('Driver at {:.2f}'.format(x), (x, 0, 0.48))
        cyl('Upper pin', (0, 0, 0.22), 0.126, 0.44, STEEL, parent=driver)
        coil = spring('Spring', driver, 0.455, 1.03)
        # Fix the upper seat in the stationary housing while the spring compresses.
        coil.location.z = 0.455
        for p in coil.data.splines[0].points:
            p.co.z -= 0.455
        def spring_scale(seam_z):
            return (1.79 - seam_z - 0.455) / 0.575
        lifts = []
        for seconds, key_x in positions:
            at = x - key_x
            seam_z = 0.42
            for (left, low), (right, high) in zip(profile, profile[1:]):
                if left <= at <= right:
                    seam_z = max(seam_z, length + low + (high - low) * (at - left) / (right - left))
                    break
            lifts.append((seconds, seam_z))
        for obj in (seam, driver):
            key_motion(obj, 'location', [(seconds, (x, 0, z)) for seconds, z in lifts])
        key_motion(coil, 'scale', [(seconds, (1, 1, spring_scale(z))) for seconds, z in lifts])
        box('Spring chamber, cutaway back', (x, 0.24, 1.29), (0.35, 0.13, 0.97), STEEL)
        box('Fixed spring cap', (x, 0.085, 1.79), (0.37, 0.34, 0.10), INK)
    for left, right in ((-0.73, 0.51), (0.90, 1.27), (1.65, 2.63)):
        box('Shear plane marker', ((left + right) / 2, -0.065, 0.75),
            (right - left, 0.020, 0.022), WHITE, 0.005)
    if success:
        key_motion(rotor, 'rotation_euler', [(0, (0, 0, 0)), (4.3, (0, 0, 0)),
                                                   (5.5, (-0.72, 0, 0))])
    if success:
        camera((0.11, -8, 0.43), (0.11, 0, 0.43), 6.1,
               (6.7, (0.27, -8, 0.50), (0.27, 0, 0.50)))
    else:
        camera((0.11, -8, 0.43), (0.11, 0, 0.43), 6.1,
               (4.8, (0.27, -8, 0.50), (0.27, 0, 0.50)))


renderers = {'hall_fail': lambda: hallway(False), 'hall_pass': lambda: hallway(True),
             'door_adaptation': door_adaptation,
             'safe': safe, 'transition': transition, 'blank': lambda: desk(False),
             'pattern': lambda: desk(True), 'mismatch': lambda: cutaway(False),
             'match': lambda: cutaway(True)}
start = 1
for shot in edit['shots']:
    end = start + round(shot['seconds'] * 30) - 1
    if len(args) == 1 or shot['id'] == args[1]:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        scene = bpy.context.scene
        scene.render.engine = 'BLENDER_WORKBENCH'
        scene.render.resolution_x, scene.render.resolution_y = 768, 432
        scene.render.fps = 30
        scene.render.image_settings.file_format = 'JPEG'
        scene.render.image_settings.quality = 84
        scene.display.render_aa = '8'
        shading = scene.display.shading
        shading.light, shading.color_type = 'STUDIO', 'OBJECT'
        shading.background_type, shading.background_color = 'WORLD', INK
        shading.show_shadows = True
        shading.show_cavity = True
        shading.cavity_type = 'BOTH'
        shading.show_specular_highlight = True
        scene.world = bpy.data.worlds.new('Dark studio background')
        scene.world.color = INK
        scene.view_settings.view_transform = 'Standard'
        scene.view_settings.exposure = 0.44
        renderers[shot['scene']]()
        scene.frame_start, scene.frame_end = start, end
        scene.render.filepath = str(output / 'frame-')
        bpy.ops.render.render(animation=True)
    start = end + 1
