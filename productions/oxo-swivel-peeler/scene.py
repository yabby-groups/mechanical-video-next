"""OXO 20081 swivel peeler, with a rigid carrier and a separately rolling blade."""
import argparse
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

R = 1.79
CZ = 1.79
TIP = 1.12
INNER = .068
LEADING = -.19
GUIDE_HEIGHT = -.081
CUTTING_HEIGHT = -.113
GUIDES = ((LEADING, GUIDE_HEIGHT), (-LEADING, GUIDE_HEIGHT))
AXIS_RADIUS = m.sqrt(R*R - LEADING*LEADING) - GUIDE_HEIGHT
PEEL_DEPTH = .041
PEEL_HALF_WIDTH = m.sqrt(R*R - (R-PEEL_DEPTH)**2)


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


def finishes():
    return {
        "apple": shaped_material("Crimson mottled apple skin", (.60, .036, .015),
                                 (.17, .005, .008), 6.2, .36),
        "flesh": shaped_material("Fresh apple flesh", (.97, .80, .36),
                                 (.69, .45, .17), 12, .49),
        "grip": shaped_material("Soft satin elastomer", (.024, .027, .033),
                                (.012, .014, .018), 8.4, .47),
        "frame": material("Molded black carrier", (.022, .027, .035), .15, .36),
        "steel": material("Brushed stainless", (.48, .57, .62), .76, .25),
        "edge": material("Polished cutting bevel", (.68, .75, .76), .65, .20),
        "axis": material("Blue axis overlay", (.07, .61, 1), .19, .25, .78),
        "force": material("Amber contact overlay", (1, .43, .064), .17, .28, .76),
        "grip_mark": material("Ivory fixed reference", (.90, .94, .96), .08, .29, .28),
        "stage": material("Slate blue work surface", (.028, .087, .114), .05, .54),
        "stem": material("Stem", (.13, .063, .018), 0, .62),
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
    lip_height = CUTTING_HEIGHT if full else -.067
    for name, profile in (
        ("Cutting lip", ((-.231, .006), (-.206, -.067), (LEADING, GUIDE_HEIGHT),
                         (-INNER, lip_height), (-.093, -.056), (-.207, .043))),
        ("Trailing lip", ((INNER, -.019), (.102, .023), (.206, .047),
                          (.232, .010), (.216, -.055), (-LEADING, GUIDE_HEIGHT))),
    ):
        mesh = section_mesh(name, [[(x, y, z) for y, z in profile]
                                   for x in (-half, half)], parts["steel"], root)
        mesh.data.materials.append(parts["edge"])
        mesh.data.polygons[3 if name == "Cutting lip" else 0].material_index = 1
        studio.bevel(mesh, .008)
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


def apple_point(x, theta, offset=0):
    radial = m.sqrt(max(0, R*R - x*x)) + offset
    return (x, -radial*m.sin(theta), CZ+radial*m.cos(theta))


def apple(parts):
    rows = [[apple_point(R*m.cos(a), b)
             for b in (j*m.tau/128 for j in range(128))]
            for a in (i*m.pi/96 for i in range(96, -1, -1))]
    for row in rows:
        for j, (x, y, z) in enumerate(row):
            base = 1 - ease(z, .12, 1.06)
            stem_dimple = .13*m.exp(-((x+.38)**2+(y-.80)**2)/.062) if z > 3 else 0
            row[j] = (x*(1+.16*base), y*(1+.16*base),
                      z+.07*base-stem_dimple)
    section_mesh("Apple body", rows, parts["apple"], None, end_caps=False, smooth=True)
    stem = pipe("Short hooked apple stem", ((-.38,.80,3.18), (-.40,.82,3.32),
                                          (-.44,.83,3.48), (-.40,.84,3.55)),
                .047, parts["stem"], bezier=True)
    stem.data.bevel_resolution = 3


def skin_track(parts):
    rows, cols = 32, 20
    faces = [(i*cols+j, (i+1)*cols+j, (i+1)*cols+j+1, i*cols+j+1)
             for i in range(rows-1) for j in range(cols-1)]
    patch = surface("Newly exposed apple track", [(0,0,0)] * (rows*cols),
                    faces, parts["flesh"], smooth=True)

    def update(start, stop):
        patch.hide_render = stop - start < .005
        for i in range(rows):
            f = i/(rows-1)
            theta = start + (stop-start)*f
            for j in range(cols):
                q = 2*j/(cols-1)-1
                width = PEEL_HALF_WIDTH*(.965+.035*m.sin(7*theta))
                phase = theta - .072*q*q*(.1+.9*f)
                patch.data.vertices[i*cols+j].co = apple_point(width*q, phase, .008)
        patch.data.update()

    return update


def roll_yz(y, z, angle):
    return y*m.cos(angle)-z*m.sin(angle), y*m.sin(angle)+z*m.cos(angle)


def contact_height(y, angle):
    # The two outer guides set the support height. The inner cutting edge
    # extends below them so that it can shave a thin layer from the track.
    offsets = [roll_yz(a, b, angle) for a, b in GUIDES]
    heights = [CZ+m.sqrt(max(0, R*R-(y+dy)**2))-dz for dy, dz in offsets]
    index = max(range(len(heights)), key=heights.__getitem__)
    return heights[index], offsets[index]


def set_contact(tool, blade, theta, roll, gap=0):
    y = -R*m.sin(theta)
    height, (dy, dz) = contact_height(y, roll)
    tool.location = (0, y, height+gap)
    blade.rotation_euler.x = roll
    return Vector((0, y+dy, height+dz))


def aligned_roll(theta):
    return m.asin(R*m.sin(theta)/AXIS_RADIUS)


def ribbon(parts):
    length_rows, width_cols = 46, 15
    faces = [(i*width_cols+j, i*width_cols+j+1, (i+1)*width_cols+j+1, (i+1)*width_cols+j)
             for i in range(length_rows-1) for j in range(width_cols-1)]
    strip = surface("Apple peel exits through the blade slot",
                    [(0,0,0)]*(length_rows*width_cols), faces, parts["apple"], smooth=True)
    strip.data.materials.append(parts["flesh"])
    thickness = strip.modifiers.new("Peel thickness and flesh side", "SOLIDIFY")
    thickness.thickness = .025
    thickness.material_offset = 1
    thickness.material_offset_rim = 1
    thickness.offset = -.35

    def update(tool, roll, amount):
        strip.hide_render = amount < .012
        for i in range(length_rows):
            u = amount*i/(length_rows-1)
            y = -INNER + .24*u + .35*u*u + .21*m.sin(u*2.5)
            z = CUTTING_HEIGHT + .69*(1-m.exp(-8*u)) + .27*m.sin(u*3.4) - .33*u*u
            dy, dz = roll_yz(y, z, roll)
            for j in range(width_cols):
                q = 2*j/(width_cols-1)-1
                # Crosswise curl narrows the ribbon just as it clears the slot.
                point = (q*(PEEL_HALF_WIDTH-.08*u) + .09*u*u,
                         tool.location.y+dy+.095*q*q*u,
                         tool.location.z+dz+.105*q*q*u)
                strip.data.vertices[i*width_cols+j].co = point
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
    apple(parts)
    expose = skin_track(parts)
    peel = ribbon(parts)
    tool, carrier, blade = peeler(parts)
    markers = axis_markers(parts, tool)
    moving = pipe("Moving side of blade", ((-.88,-.244,.043), (.86,-.244,.043)),
                  .027, parts["force"], blade)
    fixed = pipe("Reference fixed to handle", ((-2.64,-.27,.54), (-2.25,-.27,.54)),
                 .021, parts["grip_mark"], carrier)

    def pose(t):
        f = t/duration
        gap = 0
        if shot == 0:
            approach = ease(t, .10, .49)
            gap = .16*(1-approach)
            amount = ease(t, .49, 1.98)
            late = ease(f, .54, .91)
            theta = -.13 + .53*amount + .17*late
            roll = aligned_roll(theta)-.23*(1-ease(t,.49,.90))
            camera(cam, (-1.06, -.12, 2.40), (2.3, -8.5, 5.35), 8.42)
            markers_visible = t >= 2.52
            show(markers, markers_visible)
            show((moving, fixed), True)
        elif shot == 3:
            theta = .29 + .29*ease(f, .19, .78)
            roll = aligned_roll(theta)
            push = ease(f,.15,.83)
            camera(cam, (.02,-.46,3.24), (2.7,-6,5.8), 4.12-.26*push)
            show([*markers, moving, fixed], False)
        else:
            start = ease(f,.05,.26)
            slide = ease(f,.43,.72)
            theta = -.24 + .15*start + .62*slide
            roll = aligned_roll(theta)
            camera(cam, (-1.06,-.19,2.37), (2.0,-8,5.02), 8.40)
            markers_visible = f >= .71
            show(markers, markers_visible)
            show((moving, fixed), True)
        set_contact(tool, blade, theta, roll, gap)
        start_theta = -.084 if shot == 0 else .08 if shot == 3 else -.25
        dy, dz = roll_yz(-INNER, CUTTING_HEIGHT, roll)
        edge_theta = m.atan2(-tool.location.y-dy, tool.location.z+dz-CZ)
        expose(start_theta, edge_theta)
        if shot == 3:
            peel(tool, roll, min(1, max(0, (theta-.274)*3.6)))
        else:
            peel(tool, roll, min(.46, max(0, (theta-start_theta)*.78)))
        if shot == 3:
            return theta, push
        return theta, roll, gap, markers_visible

    return pose


def assembly(cam, parts, duration):
    tool, carrier, blade = peeler(parts)
    marks = axis_markers(parts, tool)
    fixed = pipe("Fixed carriage reference", ((-2.66,-.28,.54), (-2.28,-.28,.54)),
                 .021, parts["grip_mark"], carrier)
    moving = pipe("Moving lip reference", ((-.39,-.210,.016),(.37,-.210,.016)),
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
        theta = .36 + .39*ease(f,.64,.93)
        touch = ease(f,.27,.42)
        roll = aligned_roll(theta)-.30*(1-ease(f,.43,.61))
        contact = set_contact(tool, blade, theta, roll, .25*(1-touch))
        force.location = contact
        force.rotation_euler.x = m.atan2(-contact.y, contact.z-CZ)
        force_visible = .415 <= f < .61
        show(force.children, force_visible)
        camera(cam, (0,-.76,3.24), (9,-.78,1.14), 3.60)
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
    scene.render.resolution_percentage = 30 if args.preview else 100
    parts = finishes()
    studio.block("Seamless blue table", (0,0,-1.02),
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
