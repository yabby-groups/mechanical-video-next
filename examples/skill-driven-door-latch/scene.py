"""Original Blender plates for the door-latch story preview."""
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parent
OUT = Path(sys.argv[sys.argv.index("--") + 1]).resolve()
STORY = json.loads((ROOT / "story.json").read_text())


def color(value):
    rgb = [int(value[i:i+2], 16) / 255 for i in (0, 2, 4)]
    return tuple(x / 12.92 if x < .04045 else ((x + .055) / 1.055) ** 2.4 for x in rgb) + (1,)


def paint(obj, hexcolor):
    obj.color = color(hexcolor)
    return obj


def box(name, position, size, shade, bevel=.035):
    bpy.ops.mesh.primitive_cube_add(size=1, location=position)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if bevel:
        modifier = obj.modifiers.new("Soft edge", 'BEVEL')
        modifier.width = bevel
        modifier.segments = 2
    return paint(obj, shade)


def pivot(name, position):
    obj = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(obj)
    obj.location = position
    return obj


def child(obj, parent):
    obj.parent = parent
    return obj


def ball(name, position, scale, shade, parent=None):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=8, location=position)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    for polygon in obj.data.polygons:
        polygon.use_smooth = True
    return child(paint(obj, shade), parent)


def tube(name, a, b, radius, shade, parent=None):
    vector = Vector(b) - Vector(a)
    bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=radius, depth=vector.length,
                                       location=(Vector(a) + Vector(b)) / 2)
    obj = bpy.context.object
    obj.name = name
    obj.rotation_euler = vector.to_track_quat('Z', 'Y').to_euler()
    return child(paint(obj, shade), parent)


def camera(position, target, size):
    obj = scene.camera
    obj.location = position
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat('-Z', 'Y').to_euler()
    obj.data.ortho_scale = size


def room():
    box("Wall left", (-2.65, .12, 1.48), (2.2, .22, 2.95), "DCCBB2")
    box("Wall right", (1.93, .12, 1.48), (1.45, .22, 2.95), "DCCBB2")
    box("Lintel", (-.12, .12, 2.74), (2.95, .22, .43), "DCCBB2")
    box("Floor", (0, -.5, -.09), (8, 6, .16), "A87850")
    box("Hall backdrop", (-.45, 1.67, 1.5), (5, .2, 3), "526C72")
    box("Mat", (-.12, -.78, .004), (2.12, 1.02, .02), "774942", .02)
    for i in range(7):
        box("Mat stripe", (-1.0 + .3*i, -.78, .02), (.092, .92, .012), "BF8B63", .003)
    for x in (-1.50, 1.16):
        box("Frame stile", (x, -.035, 1.25), (.13, .27, 2.52), "755545")
    box("Frame header", (-.17, -.035, 2.51), (2.78, .27, .13), "755545")
    door = pivot("Door hinge", (-1.43, 0, 0))
    child(box("Painted door", (1.25, 0, 1.23), (2.50, .10, 2.44), "41645F"), door)
    for z, h in ((1.72, .74), (.65, .84)):
        child(box("Recessed panel trim", (1.25, -.057, z), (2.13, .037, h), "2C514F"), door)
        child(box("Recessed panel", (1.25, -.075, z), (1.99, .022, h-.14), "587D72"), door)
    handle = pivot("Handle axis", (2.26, -.135, 1.18))
    handle.parent = door
    child(box("Fixed brass plate", (2.26, -.094, 1.18), (.13, .036, .23), "C69C56"), door)
    child(box("Lever", (-.14, -.045, 0), (.36, .075, .065), "E4BC6F"), handle)
    box("Console", (1.87, -.18, .88), (.92, .46, .11), "553D35")
    box("Console base", (1.87, -.13, .46), (.80, .27, .86), "987053")
    box("Frame", (1.86, -.025, 1.94), (.71, .10, .71), "70513C")
    box("Print", (1.86, -.085, 1.94), (.61, .035, .61), "F3D9AD")
    ball("Sun print", (1.86, -.11, 1.94), (.20, .018, .20), "BC5440")
    box("Plant pot", (1.88, -.19, 1.07), (.30, .28, .26), "C26B49", .067)
    for i in range(5):
        tip = (1.60 + i*.13, -.20, 1.41 + .13*math.sin(i*math.pi/4))
        tube("Stem", (1.88,-.19,1.13), tip, .015, "426745")
        ball("Leaf", tip, (.10,.045,.068), "779456")
    actor = pivot("Occupant", (0, 0, 0))
    ball("Sweater", (0, 0, 1.37), (.29, .22, .42), "BC6246", actor)
    ball("Head", (.015, 0, 1.93), (.185, .169, .222), "D4986D", actor)
    ball("Hair", (-.025, .025, 2.018), (.176, .157, .147), "46312D", actor)
    ball("Nose", (.175, -.039, 1.932), (.055, .052, .055), "D4986D", actor)
    eye = ball("Eye", (.117, -.126, 1.967), (.025, .017, .015), "302623", actor)
    eye.name = "Visible eye"
    for x in (-.128, .128):
        tube("Trouser leg", (x,0,.95), (x+.025,0,.20), .115, "373B4C", actor)
        ball("Shoe", (x+.08,-.015,.14), (.171,.122,.083), "6A473A", actor)
    bag = child(box("Paper grocery bag", (.25,-.25,1.22), (.42,.34,.54), "C69555"), actor)
    for x, z, shade in ((.09,1.57,"6D8647"),(.25,1.56,"CE7741"),(.40,1.57,"D6AB55")):
        ball("Grocery", (x,-.25,z), (.11,.11,.15), shade, actor)
    arm = tube("Visible arm", (0,-.18,1.52), (.20,-.33,1.20), .09, "A6533D", actor)
    hand = ball("Visible hand", (.23,-.36,1.20), (.09,.075,.07), "D4986D", actor)
    tube("Supporting arm", (0,.13,1.48), (.51,-.11,1.25), .08, "BB694F", actor)
    return door, handle, actor, arm, hand, bag


def rig():
    box("Lab background", (0, -.65, -.55), (11, 10, .10), "172E40", 0)
    for i in range(-8, 9):
        box("Grid X", (i*.50, 0, -.485), (.008, 8, .008), "254458", 0)
        box("Grid Y", (0, i*.50, -.478), (10, .008, .008), "254458", 0)
    box("Jamb", (1.48, -.63, -.175), (1.22, 4.50, .20), "5B7482")
    box("Strike near edge", (.695, -.86, .02), (.43, 1.72, .21), "B8CCD0", 0)
    box("Strike far edge", (.695, 1.58, .02), (.43, 1.24, .21), "B8CCD0", 0)
    box("Strike back rail", (.94, .48, .02), (.06, .96, .21), "7995A0", 0)
    door = pivot("Local tangential door axis", (0, 0, 0))
    child(box("Door cut edge", (-1.03, 0, -.135), (1.51, 1.51, .25), "38736F"), door)
    child(box("Guide rail left", (-.27, -.46, .04), (.42, .17, .20), "639893"), door)
    child(box("Guide rail right", (-.27, .46, .04), (.42, .17, .20), "639893"), door)
    coords = [(-.88,-.36),(.88,-.36),(.21,.36),(-.88,.36)]
    mesh = bpy.data.meshes.new("Asymmetric latch geometry")
    mesh.from_pydata([(x,y,z) for z in (-.055,.165) for x,y in coords], [],
                     [(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)])
    mesh.update()
    bolt = bpy.data.objects.new("Latch with beveled and retaining faces", mesh)
    bpy.context.collection.objects.link(bolt)
    child(paint(bolt, "F9BB61"), door)
    return door, bolt


def ease(frame, start, stop):
    t = min(1, max(0, (frame-start)/(stop-start)))
    return t*t*(3-2*t)


def lerp(a, b, t):
    return a+(b-a)*t


def room_pose(frame, objects):
    door, handle, actor, arm, hand, _ = objects
    if frame < 330:
        door.rotation_euler.z = math.radians(-26 * (1-ease(frame, 54, 139)) - .7*(ease(frame, 234, 257)-ease(frame, 264, 294)))
        actor.location = (.25 + .10*ease(frame, 19, 81) + .15*ease(frame, 187, 245),
                          -1.52+.53*ease(frame,56,140), 0)
        actor.rotation_euler.z = -.12 + .18*ease(frame, 144, 215)
        target = (.42, -.31, 1.53) if frame < 210 else (.64, -.34, 1.42)
        camera((3.7,-8.3,4.12) if frame < 210 else (3.0,-7.3,3.25), target, 5.63 if frame < 210 else 4.25)
        reach = ease(frame, 210, 243) - ease(frame, 273, 301)
    else:
        handle.rotation_euler.y = -.46*(ease(frame, 990, 1035)-ease(frame,1053,1084))
        door.rotation_euler.z = math.radians(-62 * ease(frame, 1036, 1114))
        actor.location = (.50 + .17*ease(frame,1040,1090) + .09*ease(frame,1105,1170),
                          -.99-.45*ease(frame,1036,1087)+2.30*ease(frame,1090,1190), 0)
        actor.rotation_euler.z = -.08+.95*ease(frame,1109,1183)
        camera((3.65,-8.2,4.03), (.46,-.30,1.42), 5.45)
        reach = ease(frame, 968, 1018) - ease(frame, 1048, 1080)
    grip = handle.location + Matrix.Rotation(handle.rotation_euler.y, 3, 'Y') @ Vector((-.20,-.07,.014))
    grip = door.location + Matrix.Rotation(door.rotation_euler.z, 3, 'Z') @ grip
    local_grip = Matrix.Rotation(-actor.rotation_euler.z, 3, 'Z') @ (grip-actor.location)
    beginning = Vector((0,-.18,1.51))
    finish = Vector((.27,-.35,1.22)).lerp(local_grip, reach)
    arm.location = (beginning+finish)/2
    arm.rotation_euler = (finish-beginning).to_track_quat('Z','Y').to_euler()
    arm.scale.z = (finish-beginning).length / (Vector((.20,-.33,1.20))-Vector((0,-.18,1.52))).length
    hand.location = finish


def rig_pose(frame, objects):
    door, bolt = objects
    if frame < 570:
        y = lerp(-2.51, .52, ease(frame, 354, 527))
        if y+.36 > -1.72 and y-.36 < 0:
            local_y = max(-.36, -1.72-y)
            depth = max(0, .88-(local_y+.36)*(.67/.72)-.48)
        elif y >= .36:
            depth = .40*(1-ease(y,.36,.48))
        else:
            depth = 0
    elif frame < 770:
        y = lerp(.52, .36, ease(frame, 610, 670))
        depth = 0
    else:
        depth = .52*ease(frame, 801, 844)
        y = lerp(.36,-2.05,ease(frame, 850, 943))
    door.location.y = y
    bolt.location.x = -depth
    camera((-.38,-.47,9), (-.38,-.47,0), 7.4)
    return y, depth


bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
cam_data = bpy.data.cameras.new("Shot camera")
scene.camera = bpy.data.objects.new("Shot camera", cam_data)
bpy.context.collection.objects.link(scene.camera)
cam_data.type = 'ORTHO'
scene.render.engine = 'BLENDER_WORKBENCH'
scene.display.shading.light = 'STUDIO'
scene.display.shading.studiolight_rotate_z = .45
scene.display.shading.color_type = 'OBJECT'
scene.display.shading.show_shadows = True
scene.display.shading.show_cavity = True
scene.display.shading.cavity_type = 'BOTH'
scene.display.shading.show_object_outline = True
scene.display.shading.object_outline_color = (.055,.07,.075)
scene.display.shading.background_type = 'WORLD'
scene.world = bpy.data.worlds.new("Warm studio")
scene.world.color = (.12,.09,.065)
scene.view_settings.view_transform = 'Standard'
scene.render.resolution_x = 768
scene.render.resolution_y = 432
scene.render.resolution_percentage = 100
scene.render.fps = 30
scene.render.image_settings.file_format = 'JPEG'
scene.render.image_settings.quality = 89
scene.display.render_aa = 'FXAA'
OUT.mkdir(parents=True, exist_ok=True)
scene.frame_start, scene.frame_end = 1, 1200
room_objects = room()
room_names = set(bpy.context.scene.objects.keys()) - {scene.camera.name}
rig_objects = rig()
rig_names = set(bpy.context.scene.objects.keys()) - room_names - {scene.camera.name}
measurements = []


def frame_change(_, *args):
    frame = scene.frame_current - 1
    lab = 330 <= frame < 960
    scene.display.shading.show_shadows = not lab
    for name in room_names:
        bpy.data.objects[name].hide_render = lab
    for name in rig_names:
        bpy.data.objects[name].hide_render = not lab
    if lab:
        rig_pose(frame, rig_objects)
    else:
        room_pose(frame, room_objects)


for frame in range(330, 960):
    y, depth = rig_pose(frame, rig_objects)
    overlap_y = max(-1.72, y-.36)
    overlap = overlap_y < min(0, y+.36)
    overrun = .88-(overlap_y-y+.36)*(.67/.72)-depth-.48 if overlap else 0
    if overrun > 1e-9:
        raise ValueError(f"Strike penetration at {frame}: {overrun}")
    measurements.append(dict(frame=frame, door_tangential=y, retract=depth, clearance_checked=True))
(OUT / 'kinematics.json').write_text(json.dumps(measurements, indent=2))
bpy.app.handlers.frame_change_pre.append(frame_change)
scene.render.filepath = str(OUT / 'frame-')
if len(sys.argv) > sys.argv.index("--") + 2:
    for frame in map(int, sys.argv[sys.argv.index("--")+2:]):
        scene.frame_set(frame)
        frame_change(scene)
        scene.render.filepath = str(OUT / f"frame-{frame:04d}.jpg")
        bpy.ops.render.render(write_still=True)
else:
    bpy.ops.render.render(animation=True)
