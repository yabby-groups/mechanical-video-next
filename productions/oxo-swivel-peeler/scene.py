"""OXO 20081 swivel peeler, with a rigid carrier and a separately rolling blade."""
import argparse
from bisect import bisect_left
from array import array
import json
import math as m
import os
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys

import bpy
from mathutils import Vector

spec = spec_from_file_location(
    "studio", Path(__file__).resolve().parents[1] / "quarter-turn-faucet" / "scene.py"
)
studio = module_from_spec(spec)
spec.loader.exec_module(studio)
camera = studio.camera
ease = studio.ease
group = studio.group
material = studio.material
pipe = studio.pipe
surface = studio.surface

R = 1.75
CZ = 1.66
TIP = 1.12
INNER = .068
FRONT = -.19
GUIDE_HEIGHT = -.081
CUTTING_HEIGHT = -.122
GUIDES = ((FRONT, GUIDE_HEIGHT), (-FRONT, GUIDE_HEIGHT))
PEEL_DEPTH = .038
PEEL_HALF_WIDTH = .325
START = .30
END = .98


def shaped_material(name, color, dark, scale, roughness):
    finish = material(name, color, roughness=roughness)
    nodes = finish.node_tree.nodes
    links = finish.node_tree.links
    shader = nodes.get("Principled BSDF")
    noise = nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = scale
    noise.inputs["Detail"].default_value = 2.6
    ramp = nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = .20
    ramp.color_ramp.elements[0].color = (*dark, 1)
    ramp.color_ramp.elements[1].position = .80
    ramp.color_ramp.elements[1].color = (*color, 1)
    links.new(noise.outputs["Fac"], ramp.inputs[0])
    links.new(ramp.outputs["Color"], shader.inputs["Base Color"])
    grain = nodes.new("ShaderNodeTexNoise")
    grain.inputs["Scale"].default_value = 122
    bump = nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = .19
    bump.inputs["Distance"].default_value = .017
    links.new(grain.outputs["Fac"], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], shader.inputs["Normal"])
    return finish


def skin_material():
    finish = material("Striped apple skin with lenticels", (.38, .017, .008), roughness=.41)
    nodes = finish.node_tree.nodes
    links = finish.node_tree.links
    shader = nodes.get("Principled BSDF")

    def ramp(signal, stops):
        node = nodes.new("ShaderNodeValToRGB")
        colors = node.color_ramp
        for i, (position, color) in enumerate(stops):
            element = colors.elements[i] if i < 2 else colors.elements.new(position)
            element.position, element.color = position, color
        links.new(signal, node.inputs[0])
        return node.outputs["Color"]

    coord = nodes.new("ShaderNodeAttribute")
    coord.attribute_name = "uncut_position"
    position = coord.outputs["Vector"]
    stretch = nodes.new("ShaderNodeVectorMath")
    stretch.operation = "MULTIPLY"
    stretch.inputs[1].default_value = (2.7, 2.7, .36)
    links.new(position, stretch.inputs[0])

    def noise(vector, scale, detail):
        node = nodes.new("ShaderNodeTexNoise")
        node.inputs["Scale"].default_value = scale
        node.inputs["Detail"].default_value = detail
        links.new(vector, node.inputs["Vector"])
        return node.outputs["Fac"]

    bands = noise(stretch.outputs["Vector"], 4.2, 2.4)
    pigment = ramp(bands, [
        (.18, (.065, .0028, .003, 1)), (.88, (.57, .065, .013, 1)),
        (.43, (.22, .008, .006, 1)), (.62, (.43, .027, .006, 1)),
        (.74, (.51, .092, .016, 1)),
    ])
    distance = nodes.new("ShaderNodeVectorMath")
    distance.operation = "DISTANCE"
    distance.inputs[1].default_value = (-.13, .12, 3.28)
    links.new(position, distance.inputs[0])
    distance_scale = nodes.new("ShaderNodeMath")
    distance_scale.operation = "MULTIPLY"
    distance_scale.inputs[1].default_value = .63
    links.new(distance.outputs["Value"], distance_scale.inputs[0])
    stem_color = ramp(distance_scale.outputs[0], [
        (.03, (.7, .7, .7, 1)), (.68, (0, 0, 0, 1)),
        (.25, (.46, .46, .46, 1)),
    ])
    blush = nodes.new("ShaderNodeMixRGB")
    blush.inputs[2].default_value = (.45, .32, .047, 1)
    links.new(stem_color, blush.inputs[0])
    links.new(pigment, blush.inputs[1])

    pores = nodes.new("ShaderNodeTexVoronoi")
    pores.inputs["Scale"].default_value = 37
    links.new(position, pores.inputs["Vector"])
    speckle = ramp(pores.outputs["Distance"], [
        (.046, (.68, .68, .68, 1)), (.125, (0, 0, 0, 1)),
    ])
    skin_color = nodes.new("ShaderNodeMixRGB")
    skin_color.inputs[2].default_value = (.61, .41, .13, 1)
    links.new(speckle, skin_color.inputs[0])
    links.new(blush.outputs[0], skin_color.inputs[1])
    links.new(skin_color.outputs[0], shader.inputs["Base Color"])

    pores_bump = nodes.new("ShaderNodeBump")
    pores_bump.inputs["Strength"].default_value = .24
    pores_bump.inputs["Distance"].default_value = .009
    links.new(noise(position, 61, 2), pores_bump.inputs["Height"])
    links.new(pores_bump.outputs["Normal"], shader.inputs["Normal"])
    shader.inputs["Specular IOR Level"].default_value = .32
    shader.inputs["Coat Weight"].default_value = .055
    shader.inputs["Coat Roughness"].default_value = .38
    shader.inputs["Subsurface Weight"].default_value = .032
    return finish


def finishes():
    return {
        "apple": skin_material(),
        "flesh": shaped_material("Fresh apple flesh", (.90, .74, .39),
                                 (.70, .54, .22), 16, .48),
        "grip": shaped_material("Soft satin elastomer", (.024, .027, .033),
                                (.012, .014, .018), 8.4, .47),
        "frame": material("Molded black carrier", (.022, .027, .035), .15, .36),
        "steel": material("Brushed stainless", (.48, .57, .62), .76, .25),
        "edge": material("Polished cutting bevel", (.68, .75, .76), .65, .20),
        "axis": material("Blue axis overlay", (.07, .61, 1), .19, .25, .78),
        "force": material("Amber contact overlay", (1, .43, .064), .17, .28, .76),
        "grip_mark": material("Ivory fixed reference", (.90, .94, .96), .08, .29, .28),
        "stage": material("Slate blue work surface", (.028, .087, .114), .05, .54),
        "stem": shaped_material("Fibrous dry stem", (.19, .095, .029), (.065, .028, .010), 35, .62),
    }


def section_mesh(name, rows, finish, parent, *, end_caps=True, smooth=False):
    columns = len(rows[0])
    count = len(rows)
    faces = [
        (i*columns + j, i*columns + (j+1) % columns,
         (i+1)*columns + (j+1) % columns, (i+1)*columns + j)
        for i in range(count-1) for j in range(columns)
    ]
    if end_caps:
        faces.extend([tuple(reversed(range(columns))),
                      tuple((count-1)*columns + j for j in range(columns))])
    return surface(name, [p for row in rows for p in row], faces, finish, parent, smooth)


def grip(root, parts):
    profiles = [
        (-4.48, .04, .04), (-4.41, .28, .23), (-4.27, .39, .30),
        (-3.91, .43, .32), (-3.33, .44, .33), (-2.76, .45, .34),
        (-2.22, .46, .35), (-1.86, .40, .32), (-1.63, .33, .28),
        (-1.42, .27, .24), (-1.34, .24, .21),
    ]
    body = section_mesh("Rounded Good Grips handle", [
        [(x, ry*m.cos(k*m.tau/64), .27 + rz*m.sin(k*m.tau/64)) for k in range(64)]
        for x, ry, rz in profiles
    ], parts["grip"], root, smooth=True)
    # The hanging hole in the tail passes through the original solid grip.
    bpy.ops.mesh.primitive_cylinder_add(vertices=64, radius=.152, depth=1.2,
                                      location=(-4.11, 0, .29))
    cutter = bpy.context.object
    modifier = body.modifiers.new("Hanging hole", "BOOLEAN")
    modifier.operation = "DIFFERENCE"
    modifier.object = cutter
    bpy.context.view_layer.objects.active = body
    bpy.ops.object.modifier_apply(modifier=modifier.name)
    bpy.data.objects.remove(cutter, do_unlink=True)
    studio.bevel(body, .032)
    for i in range(9):
        x = -2.54 + .094*i
        for sign in (-1, 1):
            path = [(x, sign*(.409-.008*i)*m.cos(a), .26+.308*m.sin(a))
                    for a in (-.68, -.35, 0, .35, .68)]
            pipe("Grip ribs", path, .037, parts["grip"], root, bezier=True)


def blade_geometry(root, parts, half=TIP, full=True):
    # The tool travels in -Y. The front shoulder rides on the fruit and
    # the trailing rail's sharp edge faces -Y, into the opening.
    for name, profile in (
        ("Leading guide", ((-.231, .008), (-.211, -.056), (FRONT, GUIDE_HEIGHT),
                           (-INNER, -.070), (-.096, -.019), (-.211, .039))),
        ("Trailing cutting edge", ((INNER, CUTTING_HEIGHT), (.107, -.064), (.219, -.026),
                                   (.233, .016), (.202, .043), (.115, .021), (.084, -.018))),
    ):
        mesh = section_mesh(name, [[(x, y, z) for y, z in profile]
                                   for x in (-half, half)], parts["steel"], root)
        mesh.data.materials.append(parts["edge"])
        mesh.data.polygons[0 if name == "Trailing cutting edge" else 2].material_index = 1
        studio.bevel(mesh, .005)
    if full:
        for sign in (-1, 1):
            studio.block("Folded steel end tab", (sign*(TIP-.067), 0, -.015),
                         (.144, .46, .119), parts["steel"], root, edge=.049)
            pin = studio.cylinder("Blade journal, schematic", .062, .225, 0,
                                  parts["steel"], root, edge=.008)
            pin.rotation_euler.y = m.pi/2
            pin.location.x = sign*(TIP+.063)


def peeler(parts):
    tool = group("Peeler carriage")
    blade = group("Blade pivots around its local X axis", parent=tool)
    carrier = group("Fixed black carrier", parent=tool)
    grip(carrier, parts)
    # Side spine bridges the journals above and behind the open strip.
    sections = [
        (-1.51, .00, .13, .28, .47), (-1.36, .05, .24, -.11, .49),
        (-1.19, .12, .26, -.09, .55), (-.97, .26, .15, .22, .56),
        (.83, .26, .15, .22, .53), (1.04, .20, .20, .13, .49),
        (1.19, .10, .25, -.11, .40), (1.35, .03, .21, -.13, .22),
        (1.50, 0, .085, -.05, .07),
    ]
    profile = [(-1,-.73), (-.76,-1), (.76,-1), (1,-.73),
               (1,.73), (.76,1), (-.76,1), (-1,.73)]
    spine = section_mesh("Open carrier and distal eye tip", [
        [(x, cy + dy*y, (z0+z1)/2 + (z1-z0)*z/2) for y, z in profile]
        for x, cy, dy, z0, z1 in sections
    ], parts["frame"], carrier, smooth=True)
    studio.bevel(spine, .025)
    blade_geometry(blade, parts)
    return tool, carrier, blade


def apple_point(x, theta):
    """Parametrize a lobed fruit with a sloped crown and recessed stem."""
    section = m.sqrt(max(0, R*R - x*x))
    y, z = -section*m.sin(theta), section*m.cos(theta)
    level = z/R
    azimuth = m.atan2(y, x)
    lobes = m.cos(5*azimuth+.55)
    crown = .10*m.exp(-((level-.64)/.25)**2)
    taper = .12*ease(-level, .16, .84)
    shoulder = .035*lobes*ease(abs(level), .26, .87)
    reach = 1 + crown - taper + shoulder + .031*m.cos(2*azimuth+.70)
    px, py = x*reach+.084*level, y*reach-.039*level
    well = m.exp(-(((px+.10)/.41)**2+((py-.11)/.40)**2))
    if level > 0:
        z = z - .37*well + .052*lobes*ease(level,.40,.85)*(1-well)
    else:
        z = z + .13*well + .03*lobes*ease(-level,.56,.96)*(1-well)
    z += .043*px - .028*py
    return px, py, CZ + .946*z


def color_coordinates(obj, coords):
    attr = obj.data.attributes.get("uncut_position")
    if attr is None:
        attr = obj.data.attributes.new("uncut_position", "FLOAT_VECTOR", "POINT")
    attr.data.foreach_set("vector", coords)


def track_width(theta):
    return PEEL_HALF_WIDTH*(1+.048*m.sin(44*theta)+.028*m.sin(97*theta))


def apple(parts, *, cut=False):
    columns = 256
    xs = [R*m.sin(i*m.pi/240) for i in range(-119, 120)]
    angles = [j*m.tau/columns for j in range(columns)]
    rows = [[apple_point(x, theta) for theta in angles] for x in xs]
    obj = section_mesh("Apple with stem cavity, broad shoulders and five lobes",
                       rows, parts["apple"], None, smooth=True)
    color_coordinates(obj, array("f", (v for row in rows for point in row for v in point)))

    stem = pipe("Bent stem rising from the stem well",
                ((-.07,.105,3.00), (-.09,.11,3.22), (-.16,.14,3.37), (-.23,.13,3.49)),
                .043, parts["stem"], bezier=True)
    stem.data.bevel_resolution = 4
    if not cut:
        return None

    depth = obj.data.attributes.new("peeled", "FLOAT", "POINT")
    finish = parts["apple"]
    nodes = finish.node_tree.nodes
    links = finish.node_tree.links
    shader = nodes.get("Principled BSDF")
    skin_color = shader.inputs["Base Color"].links[0].from_socket
    flesh_color = nodes.new("ShaderNodeTexNoise")
    flesh_color.inputs["Scale"].default_value = 48
    flesh_color.inputs["Detail"].default_value = 2
    coords = next(node for node in nodes
                  if node.type == "ATTRIBUTE" and node.attribute_name == "uncut_position")
    links.new(coords.outputs["Vector"], flesh_color.inputs["Vector"])
    flesh_ramp = nodes.new("ShaderNodeValToRGB")
    flesh_ramp.color_ramp.elements[0].color = (.53, .37, .143, 1)
    flesh_ramp.color_ramp.elements[1].color = (.91, .79, .42, 1)
    links.new(flesh_color.outputs["Fac"], flesh_ramp.inputs[0])
    mask = nodes.new("ShaderNodeAttribute")
    mask.attribute_name = "peeled"
    mix = nodes.new("ShaderNodeMixRGB")
    links.new(mask.outputs["Fac"], mix.inputs[0])
    links.new(skin_color, mix.inputs[1])
    links.new(flesh_ramp.outputs["Color"], mix.inputs[2])
    links.new(mix.outputs[0], shader.inputs["Base Color"])

    band = [(i*columns+j, x, theta, rows[i][j])
            for i, x in enumerate(xs) if abs(x) < .40
            for j, theta in enumerate(angles) if .12 < theta < 1.21]
    values = array("f", [0]) * len(obj.data.vertices)

    def update(start, stop):
        for index, x, theta, point in band:
            width = track_width(theta)
            # The cut grows behind the edge, along the same surface as the skin.
            end = stop - .037*(x/width)**2
            first = start + .028*(x/width)**2
            span = min((width-abs(x))/.023, (end-theta)/.025, (theta-first)/.026)
            amount = ease(span, 0, 1)
            px, py, pz = point
            inset = amount * PEEL_DEPTH
            obj.data.vertices[index].co = (px, py + m.sin(theta)*inset,
                                           pz - m.cos(theta)*inset)
            values[index] = amount
        depth.data.foreach_set("value", values)
        obj.data.update()

    return update


SURFACE_ANGLES = tuple(i/900 for i in range(1301))
SURFACE_SECTION = tuple(apple_point(0, theta) for theta in SURFACE_ANGLES)
SURFACE_DEPTHS = tuple(-point[1] for point in SURFACE_SECTION)


def roll_yz(y, z, angle):
    return y*m.cos(angle)-z*m.sin(angle), y*m.sin(angle)+z*m.cos(angle)


def surface_at(y):
    """Return height and path phase of the fruit in the cutting plane."""
    index = max(1, min(bisect_left(SURFACE_DEPTHS, -y), len(SURFACE_DEPTHS)-1))
    near, far = SURFACE_DEPTHS[index-1:index+1]
    amount = max(0, min(1, (-y-near)/(far-near)))
    z0, z1 = SURFACE_SECTION[index-1][2], SURFACE_SECTION[index][2]
    return z0 + (z1-z0)*amount, (index-1+amount)/900


def y_on_path(theta):
    return apple_point(0, theta)[1]


def contact_height(y, angle):
    offsets = [roll_yz(a, b, angle) for a, b in GUIDES]
    heights = [surface_at(y+dy)[0]-dz for dy, dz in offsets]
    index = max(range(len(heights)), key=heights.__getitem__)
    return heights[index], offsets[index]


def set_contact(tool, blade, theta, roll, gap=0):
    y = y_on_path(theta)
    height, (dy, dz) = contact_height(y, roll)
    tool.location = (0, y, height+gap)
    blade.rotation_euler.x = roll
    return Vector((0, y+dy, height+dz))


def aligned_roll(theta):
    y = y_on_path(theta)
    low, high = .0, 1.48
    for _ in range(23):
        angle = (low+high)/2
        front, back = [roll_yz(dy, dz, angle) for dy, dz in GUIDES]
        dz_front = surface_at(y+front[0])[0]-front[1]
        dz_back = surface_at(y+back[0])[0]-back[1]
        if dz_front > dz_back:
            high = angle
        else:
            low = angle
    return (low+high)/2


def ribbon(parts):
    length_rows, width_cols = 58, 21
    faces = [(i*width_cols+j, (i+1)*width_cols+j, (i+1)*width_cols+j+1, i*width_cols+j+1)
             for i in range(length_rows-1) for j in range(width_cols-1)]
    strip = surface("Thin apple peel lifted through the open slot",
                    [(0,0,0)]*(length_rows*width_cols), faces, parts["apple"], smooth=True)
    strip.data.materials.append(parts["flesh"])
    thickness = strip.modifiers.new("Skin and pale underside", "SOLIDIFY")
    thickness.thickness = .013
    thickness.material_offset = 1
    thickness.material_offset_rim = 1
    thickness.offset = -.45

    def update(tool, roll, first, phase):
        length = max(0, (phase-first)*1.86)
        strip.hide_render = length < .022
        if strip.hide_render:
            return
        pigment = array("f")
        for i in range(length_rows):
            u = length*i/(length_rows-1)
            age = phase - (phase-first)*i/(length_rows-1)
            # Rise through the slot, clear the leading rail, then bend under gravity.
            local_y = INNER - .82*u + .105*ease(u, .39, .95)
            local_z = CUTTING_HEIGHT + .34*(1-m.exp(-6.8*u))
            sag = .49*max(0, u-.28)**1.51
            dy, dz = roll_yz(local_y, local_z, roll)
            for j in range(width_cols):
                q = 2*j/(width_cols-1)-1
                width = track_width(age)*(.95-.15*ease(u, .15, 1.14))
                twist = .083*m.sin(7.1*u)*ease(u, .12, .55)
                x = q*width+.061*m.sin(3.4*u)*u
                y = tool.location.y + dy - sag*.50 - .035*q*q*ease(u, .04, .25)
                z = tool.location.z + dz - sag + twist*q - .086*q*q
                # Sag starts after the strip is in free air beyond the fruit.
                z = max(z, surface_at(y)[0]+.024) if u > .25 and y > -1.78 else z
                strip.data.vertices[i*width_cols+j].co = (x, y, z)
                pigment.extend(apple_point(q*width, age))
        color_coordinates(strip, pigment)
        strip.data.update()

    return update


def arrow(name, origin, tip, width, finish, parent=None):
    a, b = Vector(origin), Vector(tip)
    direction = (b-a).normalized()
    side = Vector((0, direction.z, -direction.y))
    if side.length < .01:
        side = Vector((0, 0, 1))
    side.normalize()
    base = b-direction*width*3.0
    return (pipe(name, (a, base), width*.29, finish, parent),
            pipe(name+" head", (base+side*width, b, base-side*width),
                 width*.29, finish, parent))


def show(objects, visible):
    for obj in objects:
        obj.hide_render = not visible


def axis_markers(parts, parent, *, near=TIP+.16):
    dots = [studio.bead("Projected center of blade journal", (sign*near, -.255, 0), .083,
                        parts["axis"], parent) for sign in (-1, 1)]
    return [*dots, *(pipe("Axis overlay", ((x,0,0),(x+.115,0,0)), .02,
                           parts["axis"], parent)
                     for x in (-.94, -.71, -.48, -.25, -.02, .21, .44, .67, .90))]


def in_use(cam, parts, shot, duration):
    expose = apple(parts, cut=True)
    peel = ribbon(parts)
    tool, carrier, blade = peeler(parts)
    markers = axis_markers(parts, tool)
    moving = pipe("Moving cutting rail", ((-.83,.177,-.023), (.83,.177,-.023)),
                  .016, parts["force"], blade)
    fixed = pipe("Reference fixed to handle", ((-2.64,-.27,.54), (-2.25,-.27,.54)),
                 .016, parts["grip_mark"], carrier)
    first = surface_at(y_on_path(START)+roll_yz(INNER, CUTTING_HEIGHT, aligned_roll(START))[0])[1]

    def pose(t):
        f = t/duration
        gap = 0
        if shot == 0:
            gap = .17*(1-ease(t, .02, .60))
            theta = START + (END-START)*ease(t, .73, 3.60)
            roll = aligned_roll(theta)+.20*(1-ease(t, .60, 1.03))
            camera(cam, (-1.12, -.39, 1.94), (2.8, -8.4, 5.5), 7.92)
            markers_visible = t >= 3.86
            show(markers, markers_visible)
            show((moving, fixed), t >= .43)
        elif shot == 3:
            theta = START + .035 + (END-START-.035)*ease(f, .16, .82)
            roll = aligned_roll(theta)
            push = ease(f,.21,.84)
            camera(cam, (-.25,-.45,2.73-.25*push), (2.8,-6.6,6.6), 4.31-.32*push)
            show([*markers, moving, fixed], False)
        else:
            theta = START + .087*ease(f,.065,.24) + (END-START-.087)*ease(f,.46,.74)
            roll = aligned_roll(theta)
            camera(cam, (-1.07,-.39,1.90), (3.0,-8.1,5.7), 7.96)
            markers_visible = f >= .37
            show(markers, markers_visible)
            show((moving, fixed), True)
        set_contact(tool, blade, theta, roll, gap)
        dy, _ = roll_yz(INNER, CUTTING_HEIGHT, roll)
        phase = surface_at(tool.location.y+dy)[1] if gap < .003 else first
        expose(first, max(first, phase))
        peel(tool, roll, first, phase)
        if shot == 3:
            return theta, push
        return theta, roll, gap, markers_visible, t >= .43

    return pose


def assembly(cam, parts, duration):
    tool, carrier, blade = peeler(parts)
    marks = axis_markers(parts, tool)
    fixed = pipe("Fixed carriage reference", ((-2.66,-.28,.54), (-2.28,-.28,.54)),
                 .021, parts["grip_mark"], carrier)
    moving = pipe("Moving lip reference", ((-.39,.177,-.023),(.37,.177,-.023)),
                  .025, parts["force"], blade)
    guides = [pipe("Assembly guide", ((x,0,0),(x,0,.56)), .018, parts["axis"], tool)
              for x in (-TIP,TIP)]

    def pose(t):
        f = t/duration
        apart = ease(f, .27, .42)*(1-ease(f, .55, .69))
        blade.location.z = -.54*apart
        for guide in guides:
            guide.location.z = -.54*apart
        blade.rotation_euler.x = .07 + .55*ease(f,.71,.85) - .70*ease(f,.86,.98)
        show(guides, apart > .04)
        show(marks, f > .38)
        show((fixed, moving), f > .67)
        push = ease(f, .08, .59)
        camera(cam, (-1.38+1.20*push, .03, .07), (2.1,-7,6.0), 7.18-3.04*push)
        tool.location.z = .78
        return apart, blade.rotation_euler.x, push, f > .38, f > .67

    return pose


def end_view(cam, parts, duration):
    apple(parts)
    tool = group("End-on section carriage")
    blade = group("Short representative cross section of the steel blade", parent=tool)
    blade_geometry(blade, parts, half=.31, full=False)
    studio.bead("Axis seen end-on", (.38,0,0), .041, parts["axis"], tool)
    section_ref = pipe("Handle's fixed direction", ((.60,.28,.15),(.60,.73,.15)),
                       .024, parts["grip_mark"], tool)
    section_ref.data.bevel_resolution = 2
    force = group("Contact normal indicator")
    arrow("Local upward contact", (.41, 0, -.02), (.41, 0, .34), .063, parts["force"], force)
    studio.bead("First contact", (.41,0,0), .047, parts["force"], force)

    def pose(t):
        f = t/duration
        theta = .43 + .51*ease(f,.64,.93)
        touch = ease(f,.27,.42)
        roll = aligned_roll(theta)+.28*(1-ease(f,.43,.61))
        contact = set_contact(tool, blade, theta, roll, .28*(1-touch))
        force.location = contact
        slope = (surface_at(contact.y+.012)[0]-surface_at(contact.y-.012)[0])/.024
        force.rotation_euler.x = m.atan(slope)
        force_visible = .42 <= f < .61
        show(force.children, force_visible)
        camera(cam, (0,-.86,2.77), (9,-.66,1.04), 3.81)
        return theta, roll, touch, force_visible

    return pose


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--timing", type=Path, required=True)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--shot", type=int, required=True)
    parser.add_argument("--preview", action="store_true")
    args = parser.parse_args(sys.argv[sys.argv.index("--")+1:])
    frames = json.loads(args.timing.read_text())[args.shot]
    scene, cam = studio.setup(args.shot)
    scene.eevee.taa_render_samples = 6 if args.preview else 12
    scene.eevee.shadow_ray_count = 2
    if args.shot != 1:
        bpy.data.lights["Window"].energy *= .82
        bpy.data.lights["Rim strip"].energy *= .58
        bpy.data.lights["Front fill"].energy *= .64
    scene.render.resolution_percentage = 30 if args.preview else 100
    parts = finishes()
    floor_top = -.02 if args.shot == 1 else .075
    studio.block("Seamless blue table", (0,0,floor_top-1),
                 (180,180,2), parts["stage"], edge=0)
    duration = frames / 30
    if args.shot == 1:
        pose = assembly(cam, parts, duration)
    elif args.shot == 2:
        pose = end_view(cam, parts, duration)
    else:
        pose = in_use(cam, parts, args.shot, duration)
    directory = args.directory / f"shot-{args.shot}"
    directory.mkdir(parents=True, exist_ok=True)
    scene.frame_start, scene.frame_end = 0, frames-1
    previous_pose = None
    previous_frame = None
    for i in range(0, frames, 5 if args.preview else 1):
        destination = directory / f"{i:05}.jpg"
        scene.frame_set(i)
        current_pose = pose(i/30)
        if not destination.is_file():
            if current_pose == previous_pose:
                os.link(previous_frame, destination)
            else:
                scene.render.filepath = str(destination)
                bpy.ops.render.render(write_still=True)
        previous_pose = current_pose
        previous_frame = destination


if __name__ == "__main__":
    main()
