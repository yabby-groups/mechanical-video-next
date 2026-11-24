"""Original Blender geometry and motion for the quarter-turn faucet episode."""

import argparse
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Vector

FPS = 30
TAU = math.tau
TRAVEL = math.pi / 2
PORT_HALF = math.radians(35)
HOT_X = -2.12


def material(name, color, metal=0, roughness=.32, glow=0):
    item = bpy.data.materials.new(name)
    item.diffuse_color = (*color, 1)
    item.use_nodes = True
    shader = item.node_tree.nodes.get("Principled BSDF")
    shader.inputs["Base Color"].default_value = (*color, 1)
    shader.inputs["Metallic"].default_value = metal
    shader.inputs["Roughness"].default_value = roughness
    shader.inputs["Emission Color"].default_value = (*color, 1)
    shader.inputs["Emission Strength"].default_value = glow
    return item


def surface(name, vertices, faces, finish, parent=None, smooth=False):
    data = bpy.data.meshes.new(name)
    data.from_pydata(vertices, [], faces)
    data.update()
    obj = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(obj)
    obj.parent = parent
    if finish:
        data.materials.append(finish)
    if smooth:
        for face in data.polygons:
            face.use_smooth = True
    return obj


def group(name, location=(0, 0, 0), parent=None):
    obj = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(obj)
    obj.parent = parent
    obj.location = location
    return obj


def bevel(obj, width):
    if width:
        modifier = obj.modifiers.new("Machined edge", "BEVEL")
        modifier.width = width
        modifier.segments = 3
        modifier.angle_limit = .3
        normal = obj.modifiers.new("Face normals", "WEIGHTED_NORMAL")
        normal.keep_sharp = True
    return obj


def cylinder(name, radius, depth, z, finish, parent=None, sides=64, edge=.03):
    obj = ring(name, ((0, z-depth/2), (radius, z-depth/2),
                      (radius, z+depth/2), (0, z+depth/2)), finish, parent, sides=sides)
    return bevel(obj, edge)


def ring(name, profile, finish, parent=None, *, start=0, end=TAU, sides=96):
    """Revolve a closed cross-section, with capped faces on a sectional cut."""
    full = math.isclose(end-start, TAU)
    columns = sides if full else sides+1
    vertices = []
    for i in range(columns):
        angle = start + (end-start)*i/sides
        vertices.extend((r*math.cos(angle), r*math.sin(angle), z) for r, z in profile)
    rows = len(profile)
    faces = [
        (i*rows+j, ((i+1) % columns)*rows+j, ((i+1) % columns)*rows+(j+1) % rows,
         i*rows+(j+1) % rows)
        for i in range(sides) for j in range(rows)
    ]
    if not full:
        faces.extend([tuple(reversed(range(rows))), tuple(range(sides*rows, columns*rows))])
    obj = surface(name, vertices, faces, finish, parent)
    for face in obj.data.polygons[:sides*rows]:
        bottom = profile[face.index % rows]
        top = profile[(face.index+1) % rows]
        face.use_smooth = bottom[1] != top[1] and (bottom[0] > 0 or top[0] > 0)
    return obj


def block(name, location, size, finish, parent=None, edge=.035):
    x, y, z = (dim/2 for dim in size)
    vertices = [(-x,-y,-z),(x,-y,-z),(x,y,-z),(-x,y,-z),
                (-x,-y,z),(x,-y,z),(x,y,z),(-x,y,z)]
    faces = [(3,2,1,0),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]
    obj = surface(name, vertices, faces, finish, parent)
    obj.location = location
    return bevel(obj, edge)


def pipe(name, points, radius, finish, parent=None, *, bezier=False):
    data = bpy.data.curves.new(name, "CURVE")
    data.dimensions = "3D"
    data.resolution_u = 12
    data.bevel_depth = radius
    data.bevel_resolution = 5
    data.use_fill_caps = True
    spline = data.splines.new("BEZIER" if bezier else "POLY")
    if bezier:
        spline.bezier_points.add(len(points)-1)
        for point, xyz in zip(spline.bezier_points, points, strict=True):
            point.co = xyz
            point.handle_left_type = point.handle_right_type = "AUTO"
    else:
        spline.points.add(len(points)-1)
        for point, xyz in zip(spline.points, points, strict=True):
            point.co = (*xyz, 1)
    obj = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(obj)
    obj.parent = parent
    data.materials.append(finish)
    return obj


def bead(name, location, radius, finish, parent=None):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=12, ring_count=6, radius=radius)
    obj = bpy.context.object
    obj.name = name
    obj.parent = parent
    obj.location = location
    obj.data.materials.append(finish)
    for face in obj.data.polygons:
        face.use_smooth = True
    return obj


def look(obj, target):
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat("-Z", "Y").to_euler()


def setup(shot):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.eevee.taa_render_samples = 12 if shot in (0, 6) else 16
    scene.eevee.shadow_ray_count = 3
    scene.render.resolution_x = 1920
    scene.render.resolution_y = 1080
    scene.render.fps = FPS
    scene.render.image_settings.file_format = "JPEG"
    scene.render.image_settings.quality = 93
    scene.view_settings.view_transform = "AgX"
    scene.world = bpy.data.worlds.new("Neutral studio")
    scene.world.use_nodes = True
    scene.world.node_tree.nodes["Background"].inputs[0].default_value = (.24, .32, .36, 1)
    scene.world.node_tree.nodes["Background"].inputs[1].default_value = .45

    for name, position, color, power, size in (
        ("Window", (-4,-4,8), (1,.89,.73), 1900, 6.0),
        ("Rim strip", (4,3,6), (.67,.85,1), 2600, 5.0),
        ("Front fill", (2,-7,3), (1,.96,.87), 620, 4.6),
    ):
        light = bpy.data.lights.new(name, "AREA")
        light.energy, light.color, light.shape, light.size = power, color, "DISK", size
        obj = bpy.data.objects.new(name, light)
        bpy.context.collection.objects.link(obj)
        obj.location = position
        look(obj, (0,0,.4))

    cam = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
    bpy.context.collection.objects.link(cam)
    cam.data.type = "ORTHO"
    scene.camera = cam
    return scene, cam


def camera(cam, target, direction, scale):
    cam.location = Vector(target) + Vector(direction).normalized()*18
    look(cam, target)
    cam.data.ortho_scale = scale


def ease(t, start, end):
    x = min(1, max(0, (t-start)/(end-start)))
    return x*x*(3-2*x)


def show_tree(root, enabled):
    for obj in root.children_recursive:
        obj.hide_render = not enabled


def finishes():
    return {
        "chrome": material("Brushed nickel", (.48,.56,.59), .88, .24),
        "dark": material("Dark polymer", (.029,.048,.052), .12, .38),
        "brass": material("Machined brass", (.69,.36,.091), .76, .29),
        "cut": material("Exposed brass", (.83,.51,.18), .45, .38),
        "moving": material("Moving ceramic, ivory", (.88,.83,.65), 0, .19),
        "fixed": material("Fixed ceramic, slate blue", (.25,.42,.51), 0, .25),
        "mark": material("Moving reference mark", (.85,.26,.048), .2, .27),
        "basin": material("Glazed porcelain", (.79,.84,.82), .06, .2),
        "stone": material("Warm limestone", (.39,.34,.26), 0, .61),
        "wall": material("Matte moss", (.052,.13,.12), 0, .66),
        "water": material("Water illustration", (.009,.36,.72), .20, .18, .23),
        "spark": material("Water highlights", (.18,.74,.94), .17, .22, .32),
        "hot": material("Hot-side index", (.57,.13,.071), .15, .31),
    }


def lever(name, parent, finish, index):
    cylinder(name+" hub", .36, .4, .03, finish, parent)
    ring(name+" domed top", ((0,.23),(.31,.23),(.33,.25),(.28,.31),(0,.33)), finish, parent)
    pipe(name+" grip", [(-.13,0,.15),(-.51,0,.19),(-1.08,0,.25),(-1.37,0,.26)],
         .13, finish, parent, bezier=True)
    bead(name+" rounded end", (-1.37,0,.26), .13, finish, parent)
    cylinder(name+" colored index", .104, .022, .338, index, parent, edge=.008)


def basin(f):
    # The profile runs from the drain to the countertop, forming a continuous bowl.
    profile = [
        (.14,.12,-1.14),(.24,.16,-1.15),(.44,.32,-1.12),
        (1.38,1.04,-1.06),(2.30,1.55,-.79),(2.64,1.81,-.43),
        (2.77,1.88,-.15),(2.85,1.92,-.03),(2.98,1.99,.02),(3.10,2.05,.01),
    ]
    vertices = [(rx*math.cos(i*TAU/96), -2.10+ry*math.sin(i*TAU/96), z)
                for i in range(96) for rx,ry,z in profile]
    n = len(profile)
    obj = surface("Inset porcelain basin", vertices, [
        (i*n+j,i*n+j+1,((i+1)%96)*n+j+1,((i+1)%96)*n+j)
        for i in range(96) for j in range(n-1)], f["basin"], smooth=True)
    outer = [(3.10*math.cos(i*TAU/96), -2.10+2.05*math.sin(i*TAU/96), .01)
             for i in range(96)]
    far = [((15/max(abs(math.cos(a)),abs(math.sin(a))))*math.cos(a),
            -2.10+(15/max(abs(math.cos(a)),abs(math.sin(a))))*math.sin(a), .01)
           for a in (i*TAU/96 for i in range(96))]
    surface("Limestone worktop", outer+far, [
        (i,i+96,(i+1)%96+96,(i+1)%96) for i in range(96)], f["stone"])
    drain = group("Drain in bowl", (0,-2.10,0))
    cylinder("Drain flange", .24, .028, -1.13, f["chrome"], drain)
    cylinder("Drain strainer", .145, .031, -1.115, f["dark"], drain)


def spout(f, parent=None):
    cylinder("Spout mounting flange", .65, .19, .105, f["chrome"], parent)
    ring("Spout flare", ((0,.18),(.57,.18),(.53,.28),(.44,.40),(.41,.61),(0,.61)),
         f["chrome"], parent)
    pipe("High-arc spout", [(0,0,.40),(0,0,1.50),(0,-.18,2.63),
                           (0,-.83,3.25),(0,-1.70,3.25),(0,-2.10,2.73),(0,-2.10,2.52)],
         .21, f["chrome"], parent, bezier=True)
    nozzle = group("Aerator assembly", (0,-2.10,0), parent)
    cylinder("Aerator ring", .232, .28, 2.52, f["chrome"], nozzle)
    cylinder("Aerator outlet mesh", .187, .018, 2.37, f["dark"], nozzle, edge=.005)


def bonnet(f, parent, *, section=False):
    limits = {"start": .05, "end": math.pi-.05} if section else {}
    return ring("Handle escutcheon", ((.30,.025),(.73,.025),(.71,.14),(.53,.23),
                                     (.43,.34),(.39,.63),(.30,.63)), f["chrome"], parent, **limits)


def faucet(f):
    basin(f)
    block("Tiled backsplash", (0,2.0,2.8), (28,.2,7), f["wall"], edge=0)
    for i in range(-5,6):
        block("Vertical grout", (i*2.0,1.895,2.5), (.024,.014,5), f["dark"], edge=0)
    for i in range(1,4):
        block("Horizontal grout", (0,1.893,i*1.35), (25,.014,.023), f["dark"], edge=0)
    spout(f)
    hot = group("Hot side lever", (HOT_X,0,.79))
    lever("Hot", hot, f["chrome"], f["hot"])
    cold = group("Cold side lever", (-HOT_X,0,.79))
    cold.rotation_euler.z = math.pi
    lever("Cold", cold, f["chrome"], f["fixed"])
    bonnet(f, group("Hot escutcheon", (HOT_X,0,0)))
    bonnet(f, group("Cold escutcheon", (-HOT_X,0,0)))
    stream = exterior_water(f)
    return hot, stream


def exterior_water(f):
    # Each parcel retains its earlier flow at the nozzle, so shutoff travels downstream.
    root = group("Water from aerator")
    count = 42
    vertices = [(0,0,0)]*(count*8)
    faces = [(i*8+j,i*8+(j+1)%8,(i+1)*8+(j+1)%8,(i+1)*8+j)
             for i in range(count-1) for j in range(8)]
    ribbon = surface("Falling stream", vertices, faces, f["water"], root, smooth=True)
    droplets = [bead("Splash", (0,0,0), .035, f["spark"], root) for _ in range(18)]
    ripples = [ring("Ripples", ((.98,0),(1.015,0),(1.008,.012),(.99,.012)),
                    f["spark"], root, sides=54) for _ in range(3)]

    def pose(time, flow_at):
        for i in range(count):
            u = i/(count-1)
            lag = .64*math.sqrt(u)
            flow = flow_at(time-lag)
            z = 2.375-u*3.48
            radius = (.108-.05*u)*math.sqrt(max(flow,0))
            for j in range(8):
                angle = j*TAU/8
                turb = 1+.11*math.sin(31*u-19*time+angle*2)
                ribbon.data.vertices[i*8+j].co = (
                    radius*turb*math.cos(angle)+.021*u*math.sin(time*26+u*19),
                    -2.10+radius*turb*math.sin(angle), z)
        ribbon.data.update()
        impact = flow_at(time-.64)
        for i, item in enumerate(droplets):
            phase = (time*(2.5+(i%5)*.13)+i*.217)%1
            angle = i*2.39996+time*.33
            distance = (.1+.46*phase)*math.sqrt(impact)
            item.hide_render = impact < .02
            item.location = (distance*math.cos(angle), -2.1+distance*math.sin(angle),
                             -1.10+.33*math.sin(math.pi*phase)*impact)
            item.scale = (1,.8,1.1+.4*phase)
        for i, item in enumerate(ripples):
            phase = (time*1.75+i/3)%1
            item.hide_render = impact < .05
            item.location = (0,-2.10,-1.10+phase*.056+(.003*i))
            diameter = (.11+.51*phase)*impact
            item.scale = (diameter,diameter,1)

    return pose


def overlap(angle):
    return max(0, 2*PORT_HALF-abs(angle))


def outside_pose(cam, f, shot, duration):
    hot, water = faucet(f)

    def closed(t):
        if shot == 0:
            return ease(t,.23,1.08)
        return 1-ease(t,.32,1.23)+ease(t,duration*.39,duration*.57)

    def pose(t):
        hot.rotation_euler.z = TRAVEL*(1-closed(t))
        water(t, lambda time: overlap(TRAVEL*closed(time))/(2*PORT_HALF))
        move = ease(t, 0, duration)
        camera(cam, (-.34-.20*move,-.76,.92), (4.1-.6*move,-9.9,5.6),
               9.5-.55*move)
    return pose


def cartridge_shell(f, parent, section=True):
    limits = {"start": 0, "end": math.pi} if section else {}
    ring("Brass cartridge shell", (
        (.94,.68),(1.04,.68),(1.06,1.22),(1.01,1.62),(.86,1.80),
        (.78,2.18),(.52,2.18),(.50,1.80),(.75,1.62),(.91,1.19),(.94,.87),
    ), f["brass"], parent, **limits)
    ring("Brass hex wrench flats", ((.79,1.70),(1.18,1.70),(1.22,1.76),(1.22,2.03),
         (1.14,2.12),(.75,2.12)), f["brass"], parent,
         sides=3 if section else 6, **limits)
    for i in range(6):
        z = 1.14+i*.073
        ring("Mounting thread crest", ((1.01,z),(1.105,z+.024),(1.105,z+.043),
             (1.01,z+.057)), f["brass"], parent, **limits)
    ring("Lower seat seal", ((.63,.34),(.97,.34),(1.02,.40),(1.01,.49),(.64,.49)),
         f["dark"], parent, **limits)


def stem(f, parent):
    cylinder("Splined brass stem", .32, 1.40, 1.96, f["brass"], parent)
    for i in range(20):
        angle = i*TAU/20
        spline = block("Spline tooth", (.318*math.cos(angle),.318*math.sin(angle),2.48),
                       (.075,.054,.41), f["brass"], parent, edge=.011)
        spline.rotation_euler.z = angle
    cylinder("Drive carrier", .60, .21, 1.30, f["brass"], parent)
    for side in (-1,1):
        block("Ceramic drive lug", (side*.56,0,1.16), (.18,.23,.16), f["brass"], parent, .018)


def disc(name, z, finish, parent):
    # Two opposed sector holes between invariant solid inner and outer rings.
    height = .19
    inner, outer, radius = .27, .77, .95
    ring(name+" outer ring", ((outer,z),(radius,z),(radius,z+height),
         (outer,z+height)), finish, parent)
    cylinder(name+" inner hub", inner, height, z+height/2, finish, parent, edge=0)
    for base in (0,math.pi):
        ring(name+" solid web", ((inner,z),(outer,z),(outer,z+height),(inner,z+height)),
             finish, parent, start=base+PORT_HALF, end=base+math.pi-PORT_HALF, sides=35)


def plate_set(f, root):
    fixed = group("Fixed disc keyed to valve body", parent=root)
    moving = group("Rotating ceramic disc", parent=root)
    disc("Lower fixed ceramic", .50, f["fixed"], fixed)
    disc("Upper rotating ceramic", .69, f["moving"], moving)
    for y in (-1,1):
        block("Fixed disc locating tab", (0,y*.96,.595), (.20,.13,.19), f["fixed"], fixed, .015)
    for x in (-1,1):
        block("Moving disc index", (x*.856,0,.887), (.125,.09,.022), f["mark"], moving, .008)
    return fixed, moving


def main_cartridge_pose(cam, f, duration):
    root = group("Hot valve inside mounting position", (HOT_X,0,.12))
    cold = group("Cold lever remains installed", (-HOT_X,0,.79))
    lever("Cold", cold, f["chrome"], f["fixed"])
    cold.rotation_euler.z = math.pi
    bonnet(f, group("Cold faucet collar", (-HOT_X,0,0)))
    spout(f)
    basin(f)
    block("Wall", (0,2.0,2.8), (28,.2,7), f["wall"], edge=0)
    housing = group("Handle bonnet removed axially", (HOT_X,0,0))
    bonnet(f, housing)
    handle = group("Handle removed from splines", (HOT_X,0,.81))
    lever("Hot", handle, f["chrome"], f["hot"])
    cartridge = group("GP77005-RP-style cartridge outside profile", parent=root)
    cartridge_shell(f, cartridge, section=False)
    driver = group("Valve stem", parent=cartridge)
    stem(f, driver)
    cartridge.scale = (.34,.34,.34)
    cartridge.location.z = -.32
    cylinder("Installed valve base", .39,.17,.12,f["chrome"],root)

    def pose(t):
        take_handle = ease(t,.65,2.48)
        take_bonnet = ease(t,1.33,3.50)
        take_valve = ease(t,4.75,7.28)
        watch = ease(t,0,duration*.89)
        handle.location = (HOT_X-.68*take_handle,.56*take_handle,.81+1.08*take_handle)
        handle.rotation_euler.z = .18*math.sin(min(1,t/1.32)*math.pi)
        housing.location = (HOT_X+.79*take_bonnet,.43*take_bonnet,.60*take_bonnet)
        cartridge.location.z = -.32+1.37*take_valve
        target = (-.47-1.15*watch,-.08,.88+.49*take_valve+.11*take_handle)
        camera(cam,target,(4.1-1.7*watch,-9.9,4.6+1.1*watch),8.2-3.05*watch)
    return pose


def wet_ports(f, root, *, tall=False):
    """Make geometry only for angular intersection of each pair of openings."""
    bottom = .46 if tall else .485
    top = .92 if tall else .895
    parts = [ring("Open area shared by both discs", ((.31,bottom),(.735,bottom),
        (.735,top),(.31,top)), f["water"], root, start=-PORT_HALF,
        end=PORT_HALF, sides=28) for _ in range(2)]

    def update(angle):
        low = max(-PORT_HALF, -PORT_HALF-angle)
        span = overlap(angle)
        for i, item in enumerate(parts):
            item.hide_render = span < math.radians(.15)
            if item.hide_render:
                continue
            for j in range(29):
                a = low+span*j/28+i*math.pi
                for k,(r,z) in enumerate(((.31,bottom),(.735,bottom),(.735,top),(.31,top))):
                    item.data.vertices[j*4+k].co = (r*math.cos(a),r*math.sin(a),z)
            item.data.update()
    return update


def cutaway(cam, f, shot, duration):
    floor_z = -.76 if shot == 3 else -.07
    block("Studio sweep", (0,0,floor_z), (180,180,.12), f["wall"], edge=0)
    root = group("Valve and discs on shared axis", (-.28,0,.12))
    fixed, moving = plate_set(f, root)
    shell = group("Cartridge body", parent=root)
    cartridge_shell(f, shell)
    driver = group("Stem rotates with upper disc", parent=root)
    stem(f, driver)
    grip = group("Same handle axis", (0,0,2.82), root)
    lever("Indexed handle", grip, f["chrome"], f["hot"])
    wet = wet_ports(f, root, tall=shot == 3)
    lower = group("Inlet centered below discs", parent=root)
    tube = ring("Cutaway inlet", ((.68,-.55),(.97,-.55),(.97,.34),(.68,.34)),
                f["brass"], lower, start=0,end=math.pi)
    inlet = pipe("Water supply below fixed ceramic", [(.52,0,-.55),(.52,0,.50)],
                 .10, f["water"], lower)
    outlet = pipe("Side outlet toward spout", [(.52,0,.87),(.61,-.01,1.06),
                   (1.13,-.06,1.13),(1.76,-.10,1.13)], .10, f["water"], lower, bezier=True)
    for part in (tube, inlet,outlet):
        part.hide_render = shot != 3
    drops = [bead("Water direction marker", (0,0,0), .067, f["spark"], lower) for _ in range(9)]
    next_cue = duration * {2: .61, 3: .495, 4: .463, 5: .446}[shot]
    turn_start = .24

    def pose(t):
        angle = 0
        if shot == 2:
            separate = ease(t, next_cue-.7, next_cue+1.35)
            angle = TRAVEL*.42*(ease(t,3.02,4.13)-ease(t,4.83,5.69))
            moving.location.z = .65*separate
            driver.location.z = .65*separate
            shell.location.z = .20*separate
            # Swing the shell section to one side in the exploded view.
            shell.location.x = .91*separate
            show_tree(grip, False)
            axis = (.20,-7,4.1+2.7*separate)
            camera(cam,(.03,0,1.28+.17*separate),axis,5.65-.24*separate)
        elif shot == 3:
            show_tree(grip, False)
            separate = 1-ease(t,.05,1.55)
            moving.location.z = .65*separate
            driver.location.z = .65*separate
            shell.location.z = .20*separate
            shell.location.x = .91*separate
            flow_view = ease(t, next_cue-1.1, next_cue+.75)
            camera(cam,(.11,0,1.37+.09*separate-.38*flow_view),
                   (.52,-7,3.25+2.7*separate-1.67*flow_view),5.28+.61*flow_view)
        else:
            # Establish the shared axis from the side, then match the view to the faces.
            dive = ease(t,.94,2.34) if shot == 4 else 1
            if shot == 4:
                angle = TRAVEL*ease(t,turn_start, next_cue+.88)
            else:
                angle = TRAVEL*(1-ease(t,.42,min(2.20,next_cue-.15)))
                angle += TRAVEL*.49*ease(t,next_cue+.16,next_cue+1.36)
                angle -= TRAVEL*.49*ease(t,next_cue+1.86,next_cue+3.17)
            show_tree(shell, dive < .43)
            show_tree(driver, dive < .43)
            show_tree(grip, dive < .43)
            direction = (.08,-6.2*(1-dive)-.008,4.0+9*dive)
            camera(cam,(-.28,0,1.60-.80*dive),direction,6.5-2.61*dive)

        for obj in (moving, driver, grip):
            obj.rotation_euler.z = -angle
        wet(angle)
        enable_flow = shot == 3 and t > next_cue-.35
        for obj in root.children:
            if obj.name.startswith("Open area shared"):
                obj.hide_render |= shot == 2 or (shot == 3 and not enable_flow)
        inlet.hide_render = outlet.hide_render = not enable_flow
        for i,dot in enumerate(drops):
            dot.hide_render = not enable_flow
            p = (t*.64+i/len(drops))%1
            if p < .59:
                dot.location = (.52,0,-.55+1.48*p/.59)
            else:
                progress = (p-.59)/.41
                dot.location = (.52+1.24*progress,-.10*progress,
                                .93+.20*ease(progress,0,.42))
            dot.scale = (1,1,1.16)
    return pose


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--timing", type=Path, required=True)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--shot", type=int, choices=range(7), required=True)
    parser.add_argument("--preview", action="store_true")
    args = parser.parse_args(sys.argv[sys.argv.index("--")+1:])
    counts = json.loads(args.timing.read_text())
    count = counts[args.shot]
    duration = count/FPS
    shot = args.shot
    scene, cam = setup(shot)
    f = finishes()
    if shot in (0,6):
        pose = outside_pose(cam,f,shot,duration)
    elif shot == 1:
        pose = main_cartridge_pose(cam,f,duration)
    else:
        pose = cutaway(cam,f,shot,duration)
    folder = args.directory/f"shot-{shot}"
    folder.mkdir(parents=True,exist_ok=True)
    scene.render.resolution_percentage = 38 if args.preview else 100
    step = 10 if args.preview else 1
    for frame in range(0,count,step):
        path = folder/f"{frame:05}.jpg"
        if path.is_file():
            continue
        pose(frame/FPS)
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)


if __name__ == "__main__":
    main()
