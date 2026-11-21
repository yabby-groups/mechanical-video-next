"""Native Blender reconstruction of the return path in US 7,900,978 B2, figs. 1–5."""
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Vector

output = Path(sys.argv[sys.argv.index('--') + 1]).resolve()
output.mkdir(parents=True, exist_ok=True)
TAU = math.tau
STEP = math.radians(30)
TOP, BOTTOM = map(math.radians, (111, 249))
RADIUS, COIL, WIRE = 1.68, 0.149, 0.034
SHAFT_HALF = 0.276
DEPTH = -0.19
STEEL = (0.37, 0.52, 0.54)
GOLD = (0.88, 0.51, 0.15)
BLUE = (0.10, 0.55, 0.72)
MINT = (0.46, 0.83, 0.59)
SILVER = (0.78, 0.81, 0.74)
INK = (0.055, 0.10, 0.11)
DOOR = (0.31, 0.18, 0.115)
FPS = 30

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene


def material(obj, color):
    obj.color = (*color, 1)
    return obj


def empty(name, parent=None):
    obj = bpy.data.objects.new(name, None)
    scene.collection.objects.link(obj)
    obj.parent = parent
    return obj


def mesh(name, vertices, faces, color, parent=None):
    data = bpy.data.meshes.new(name)
    data.from_pydata(vertices, [], faces)
    data.update()
    obj = bpy.data.objects.new(name, data)
    scene.collection.objects.link(obj)
    obj.parent = parent
    return material(obj, color)


def bevel(obj, width):
    mod = obj.modifiers.new('Machined edges', 'BEVEL')
    mod.width = width
    mod.segments = 3
    obj.modifiers.new('Face normals', 'WEIGHTED_NORMAL')


def box(name, location, dimensions, color, parent=None, edge=.04):
    bpy.ops.mesh.primitive_cube_add(size=1)
    obj = bpy.context.object
    obj.name, obj.parent, obj.location, obj.dimensions = name, parent, location, dimensions
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if edge:
        bevel(obj, edge)
    return material(obj, color)


def profile(name, angles, inner, outer, low_y, high_y, color, parent=None, closed=True):
    count = len(angles)
    vertices = [(radius(a) * math.cos(a), depth, radius(a) * math.sin(a))
                for depth in (low_y, high_y) for radius in (outer, inner) for a in angles]
    faces = []
    for i in range(count if closed else count - 1):
        j = (i + 1) % count
        faces.extend(((i, j, 2*count+j, 2*count+i),
                      (count+i, 3*count+i, 3*count+j, count+j),
                      (i, count+i, count+j, j),
                      (2*count+i, 2*count+j, 3*count+j, 3*count+i)))
    if not closed:
        faces.extend((i, 2*count+i, 3*count+i, count+i) if i == 0
                     else (i, count+i, 3*count+i, 2*count+i) for i in (0, count-1))
    obj = mesh(name, vertices, faces, color, parent)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode='OBJECT')
    obj.select_set(False)
    return obj


def circle(value):
    return lambda angle: value


FULL = [TAU * i / 192 for i in range(192)]


def ring(name, inside, outside, y0, y1, color, parent=None):
    inner = inside if callable(inside) else circle(inside)
    return profile(name, FULL, inner, circle(outside), y0, y1, color, parent)


def arc(name, a0, a1, inside, outside, y0, y1, color, parent=None):
    angles = [a0 + (a1-a0)*i/64 for i in range(65)]
    return profile(name, angles, circle(inside), circle(outside), y0, y1, color, parent, False)


def square_radius(angle):
    return SHAFT_HALF / max(abs(math.sin(angle)), abs(math.cos(angle)))


def sweep_square(angle, low, high):
    directions = [low, high]
    for corner in range(-5, 6):
        candidate = angle - (math.pi/4 + corner*math.pi/2)
        if low <= candidate <= high:
            directions.append(candidate)
    return max(square_radius(angle - local) for local in directions)


def frame(seconds):
    return round(seconds * FPS) + 1


def keys(obj, field, poses):
    for time, value in poses:
        setattr(obj, field, value)
        obj.keyframe_insert(data_path=field, frame=frame(time))


def visibility(objects, outside):
    for obj in objects:
        keys(obj, 'hide_render', [(0, not outside), (5.3, outside), (33, not outside)])


driver = empty('34 active flat spring driver')
stationary = empty('32 opposite flat spring driver')
shaft = empty('66 square drive spindle')
lever = empty('Lever handle')
housing = empty('12 housing and flange')
cover = empty('58 cover plate')

# Clearances use the angular envelope of the square spindle, not a round surrogate.
hub = ring('48 hub with actual square opening', lambda a: square_radius(a)+.012,
           .53, -.56, -.38, SILVER, shaft)
box('66 continuous square spindle', (0, -.03, 0), (.552, 1.98, .552), SILVER, shaft, .006)
box('Lever shank', (0, -.86, 0), (.59, .65, .58), GOLD, lever, .14)
box('Lever grip', (1.61, -1.10, 0), (3.20, .39, .37), GOLD, lever, .13)
bevel(ring('Housing face', .49, 2.07, .35, .54, STEEL, housing), .024)
bevel(arc('Annular spring channel, outer wall', math.radians(98), math.radians(262),
          1.90, 2.01, -.34, .38, STEEL, housing), .018)
bevel(arc('Annular spring channel, inner wall', TOP + .06, BOTTOM - .06,
          1.31, 1.39, .135, .36, INK, housing), .016)
arc('Stationary driver stop', TOP-.21, TOP-.095, 1.48, 1.87, -.36, .109, INK, housing)
arc('Moving driver home stop', BOTTOM+.095, BOTTOM+.21, 1.48, 1.87, -.36, .109, INK, housing)
bevel(ring('Cover plate with spindle opening', .54, 2.065, -.528, -.46, STEEL, cover), .024)

bevel(ring('Opposite driver with swept square aperture', lambda a: sweep_square(a, -STEP, 0)+.012,
           .83, .014, .109, BLUE, stationary), .016)
bevel(ring('Moving driver with swept square aperture', lambda a: sweep_square(a, 0, STEP)+.012,
           .91, -.17, -.065, GOLD, driver), .016)
arc('Stationary radial arm and stop face', TOP-.093, TOP, .67, 1.86, -.045, .109, BLUE, stationary)
arc('Stationary spring seat', TOP-.095, TOP, 1.48, 1.88, -.375, .109, BLUE, stationary)
arc('Driven radial arm', BOTTOM, BOTTOM+.093, .73, 1.85, -.17, -.065, GOLD, driver)
arc('Moving spring seat', BOTTOM, BOTTOM+.095, 1.48, 1.88, -.375, -.065, GOLD, driver)


def spring_points(angle):
    extent = (BOTTOM - angle) - TOP
    sections, sides, turns = 300, 10, 15
    result = []
    for index in range(sections+1):
        t = index / sections
        # Match each end to the planar radial seat, using closed turns and a round wire.
        phase = TAU*turns*t
        radius = RADIUS + COIL*math.cos(phase)
        phi = TOP + t * extent
        axis = Vector((radius*math.cos(phi), DEPTH + COIL*math.sin(phase), radius*math.sin(phi)))
        # Sweep an actual tube in the radial/axial plane, perpendicular to the arc tangent.
        for side in range(sides):
            roll = TAU*side/sides
            radial = math.cos(roll)*WIRE
            result.append((axis.x + radial*math.cos(phi), axis.y + math.sin(roll)*WIRE,
                           axis.z + radial*math.sin(phi)))
    return result


vertices = spring_points(0)
sides = 10
faces = [(i*sides+j, (i+1)*sides+j, (i+1)*sides+(j+1)%sides, i*sides+(j+1)%sides)
         for i in range(len(vertices)//sides-1) for j in range(sides)]
faces.extend((tuple(range(sides)), tuple(reversed(range(len(vertices)-sides,len(vertices))))))
spring = mesh('30 continuous wire arc spring', vertices, faces, MINT)
for polygon in spring.data.polygons:
    polygon.use_smooth = True
spring.shape_key_add(name='Neutral')
shapes = []
for index in range(1, 16):
    layer = spring.shape_key_add(name=f'{index*2} degrees')
    for vertex, xyz in zip(layer.data, spring_points(STEP * index/15)):
        vertex.co = xyz
    shapes.append(layer)

# A bored door panel. The preview isolates the return unit, so the door stays stationary.
door = box('Door panel with a through bore', (0, .885, 0), (15, .69, 11), DOOR, edge=0)
bpy.ops.mesh.primitive_cylinder_add(vertices=128, radius=2.025, depth=2.05,
                                   location=(0,.94,0), rotation=(math.pi/2,0,0))
cutter = bpy.context.object
bpy.context.view_layer.objects.active = door
mod = door.modifiers.new('Through bore for trim and assembly', 'BOOLEAN')
mod.operation, mod.object = 'DIFFERENCE', cutter
bpy.ops.object.modifier_apply(modifier=mod.name)
bpy.data.objects.remove(cutter, do_unlink=True)
bevel(door, .022)
inset = box('Door stile', (4.91, .57, .05), (.055, .015, 11), (.48,.28,.16))
background = box('Studio backdrop', (0, 5.05, 0), (70, .12, 70), INK, edge=0)
visibility([door, inset], True)
visibility([spring, *driver.children, *stationary.children], False)
# The cover reappears as an exploded layer, then moves out of the observation window.
for obj in cover.children:
    keys(obj, 'hide_render', [(0,False), (11.9,False), (13.3,True), (33,False)])
keys(cover, 'location', [(0,(0,0,0)), (5.3,(0,0,0)), (8.9,(0,1.50,0)),
                         (11.9,(0,1.50,0)), (13.1,(0,3.0,0)), (33,(0,0,0))])
for part, offset in ((driver,.54), (stationary,.94), (housing,1.35),
                     (shaft,-.62), (lever,-1.02), (spring,1.07)):
    keys(part, 'location', [(0,(0,0,0)), (5.3,(0,0,0)), (8.9,(0,offset,0)),
                            (11,(0,offset,0)), (13.7,(0,0,0))])
motion = [(0,0), (.75,0), (1.7,28), (2.20,28), (3.15,0), (13.9,0),
          (15.65,0), (21.00,28), (24.35,28), (29.4,0), (34,0),
          (35.70,28), (36.35,28), (37.50,0), (40.50,0)]
for obj in (shaft, lever, driver):
    keys(obj, 'rotation_euler', [(t,(0,math.radians(a),0)) for t,a in motion])

# Bake the wire geometry from the same evaluated shaft clock into the portable blend.
for i in range(1, frame(40.5)):
    scene.frame_set(i)
    sample = driver.rotation_euler.y / (STEP / 15)
    for index, shape in enumerate(shapes, 1):
        shape.value = max(0, 1 - abs(sample - index))
        shape.keyframe_insert('value', frame=i)


def camera(name, poses):
    data = bpy.data.cameras.new(name)
    obj = bpy.data.objects.new(name, data)
    scene.collection.objects.link(obj)
    data.type = 'ORTHO'
    for time, position, target, size in poses:
        obj.location = position
        obj.rotation_euler = (Vector(target)-obj.location).to_track_quat('-Z','Y').to_euler()
        for field in ('location','rotation_euler'):
            obj.keyframe_insert(data_path=field, frame=frame(time))
        data.ortho_scale = size
        data.keyframe_insert(data_path='ortho_scale', frame=frame(time))
    marker = scene.timeline_markers.new(name, frame=frame(poses[0][0]))
    marker.camera = obj
    return obj


scene.camera = camera('01 Handle in use', [(0,(4,-12,4),(.75,0,.03),10.25),
                       (5.2,(4,-12,4),(.75,0,.03),9.4)])
camera('02 Exploded assembly', [(5.3,(8,-11,5),(.22,0,.0),9.9),
       (10.8,(8,-11,5),(.22,0,.0),9.9), (13.9,(1,-12,1),(.32,0,-.04),8.8)])
camera('03 Press and return on one clock', [(14,(1,-12,1),(.32,0,-.04),8.75),
       (22.7,(1.0,-12,.7),(.05,0,-.07),7.8), (32.9,(1.0,-12,.7),(.05,0,-.07),7.8)])
camera('04 Back to the door', [(33,(4,-12,4),(.70,0,.03),9.4),
       (40.4,(4,-12,4),(.70,0,.03),10.1)])

scene.render.engine = 'BLENDER_WORKBENCH'
scene.render.resolution_x, scene.render.resolution_y = 768,432
scene.render.fps = FPS
scene.frame_start, scene.frame_end = 1, frame(40.5)-1
scene.render.image_settings.file_format = 'JPEG'
scene.render.image_settings.quality = 90
scene.display.render_aa = '8'
shading = scene.display.shading
shading.light, shading.color_type, shading.cavity_type = 'STUDIO','OBJECT','BOTH'
shading.show_cavity = shading.show_shadows = shading.show_specular_highlight = True
scene.view_settings.view_transform = 'Standard'
scene.view_settings.exposure = .43

# Native pose trace and minimum coil-body gap. Every rendered motion frame is sampled.
rows = []
for current in range(frame(14), frame(33)):
    scene.frame_set(current)
    graph = bpy.context.evaluated_depsgraph_get()
    angle = driver.evaluated_get(graph).rotation_euler.y
    evaluated = spring.evaluated_get(graph)
    wire = evaluated.to_mesh()
    points = wire.vertices
    min_pitch = min((points[i].co - points[i+200].co).length for i in range(len(points)-200))
    length = RADIUS*(BOTTOM - TOP - angle)
    first_ring = sum((point.co for point in points[:10]), Vector()) / 10
    end_ring = sum((point.co for point in points[-10:]), Vector()) / 10
    start_angle = math.atan2(first_ring.z, first_ring.x) % TAU
    end_angle = math.atan2(end_ring.z, end_ring.x) % TAU
    position_error = RADIUS * max(abs(start_angle-TOP), abs(end_angle-(BOTTOM-angle)))
    evaluated.to_mesh_clear()
    assert abs(shaft.rotation_euler.y-angle) < 1e-6 and abs(stationary.rotation_euler.y) < 1e-6
    assert min_pitch > WIRE*2 and length > 0 and position_error < .002
    rows.append(dict(frame=current, spindle_degrees=math.degrees(angle),
                     driven_arm_degrees=math.degrees(angle), opposing_arm_degrees=0,
                     spring_arc_length=length, minimum_same_phase_pitch=min_pitch,
                     maximum_end_to_seat_error=position_error))
(output/'motion.json').write_text(json.dumps(dict(samples=rows, wire_diameter=2*WIRE,
    contact_scope='Sampled poses and coil pitch for the modeled return mechanism',
    physical_simulation=False, latchbolt_shown=False), indent=2)+'\n')
scene.frame_set(1)
scene.render.filepath = str(output / 'frames' / 'frame-')
Path(scene.render.filepath).parent.mkdir(exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=str(output / 'door-handle-return.blend'))
bpy.ops.render.render(animation=True)
