"""Consistent quarter-turn cartridge for the section, water route and replay."""

import argparse
import math
from pathlib import Path
import sys

import bmesh
import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mechanism_revision_scene import STILL_INTERVALS, extraction, hot_handle, mounting_thread
from scene import (
    FPS, PORT_HALF, TAU, TRAVEL, bead, bevel, block, camera, ease, finishes,
    group, material, overlap, pipe, ring, setup, show_tree, surface,
)

FIXED_Z = .50
CONTACT_Z = .69
MOVING_TOP = .88
PORT_INNER = .27
PORT_OUTER = .77
DISC_RADIUS = .95
OUTLET_Z = 1.067
WINDOW_ANGLE = math.radians(24)
WINDOW_WIDTH = .68
WINDOW_HEIGHT = .33
STEM_BOTTOM = 1.29
PLAN_DIRECTION = (0, -.001, 1)
SECTION_DIRECTION = (2.5, -8, 4.5)
COUNTS = {"opening-ports": 60, "opening-body": 90, "extract": 289, "plates": 319, "flow": 327,
          "closure": 264, "reopen": 283, "replay-ports": 240}


def orient_mesh(obj):
    mesh = bmesh.new()
    mesh.from_mesh(obj.data)
    bmesh.ops.recalc_face_normals(mesh, faces=list(mesh.faces))
    mesh.to_mesh(obj.data)
    mesh.free()
    return obj


def cut(obj, tool, operation="DIFFERENCE"):
    bpy.context.view_layer.objects.active = obj
    modifier = obj.modifiers.new("Machined geometry", "BOOLEAN")
    modifier.operation = operation
    modifier.object = tool
    bpy.ops.object.modifier_apply(modifier=modifier.name)
    bpy.data.objects.remove(tool, do_unlink=True)


def axis_cylinder(name, radius, depth, z, finish, parent):
    bpy.ops.mesh.primitive_cylinder_add(vertices=64, radius=radius, depth=depth)
    obj = bpy.context.object
    obj.name = name
    obj.parent = parent
    obj.location.z = z
    if finish:
        obj.data.materials.append(finish)
    for face in obj.data.polygons:
        face.use_smooth = len(face.vertices) == 4
    return obj


def ceramic_blank(name, low, high, finish, parent):
    # A single closed mesh. Adjacent solid cells share vertices and faces;
    # the two empty cells leave ports all the way through the ceramic.
    boundaries = (-PORT_HALF, PORT_HALF, math.pi - PORT_HALF,
                  math.pi + PORT_HALF, TAU - PORT_HALF)
    angles, ports = [], []
    for segment, (start, end) in enumerate(zip(boundaries, boundaries[1:])):
        for step in range(32):
            angles.append(start + (end - start) * step / 32)
            ports.append(segment % 2 == 0)
    radii = (0, PORT_INNER, PORT_OUTER, DISC_RADIUS)
    vertices = []
    indices = {}

    def vertex(column, row, top):
        key = (column % len(angles) if row else 0, row, top)
        if key not in indices:
            angle = angles[column % len(angles)]
            radius = radii[row]
            indices[key] = len(vertices)
            vertices.append((radius * math.cos(angle), radius * math.sin(angle), high if top else low))
        return indices[key]

    def solid(column, row):
        return 0 <= row < 3 and (row != 1 or not ports[column % len(angles)])

    faces = []
    for column in range(len(angles)):
        for row in range(3):
            if not solid(column, row):
                continue
            corners = ((column, row), (column, row + 1),
                       (column + 1, row + 1), (column + 1, row))
            bottom = [vertex(*point, False) for point in corners]
            top = [vertex(*point, True) for point in corners]
            faces.extend((tuple(dict.fromkeys(reversed(bottom))), tuple(dict.fromkeys(top))))
            neighbors = ((column - 1, row), (column, row + 1),
                         (column + 1, row), (column, row - 1))
            for side, cell in enumerate(neighbors):
                following = (side + 1) % 4
                if bottom[side] != bottom[following] and not solid(*cell):
                    faces.append((bottom[side], bottom[following], top[following], top[side]))
    return orient_mesh(surface(name, vertices, faces, finish, parent))


def ceramic_pair(f, root, *, section=False):
    fixed = group("Stationary ceramic", parent=root)
    moving = group("Rotating ceramic", parent=root)
    lower = ceramic_blank("Fixed ceramic with two through ports", FIXED_Z, CONTACT_Z, f["fixed"], fixed)
    upper = ceramic_blank("Rotating ceramic with two through ports", CONTACT_Z, MOVING_TOP, f["moving"], moving)
    for direction in (-1, 1):
        tab = block("Ceramic locating ear", (0, direction * .960, .60), (.19, .144, .177),
                    None, fixed, edge=0)
        cut(lower, tab, "UNION")
    pocket = block("Blind drive socket", (0, 0, .875), (.182, .406, .154), None, moving, edge=0)
    cut(upper, pocket)
    if section:
        moving.rotation_euler.z = -TRAVEL
        for obj in (lower, upper):
            cut(obj, block("Cut plane", (0, -1.50, .68), (4, 3, .6), None, root, edge=0))
    for obj in (lower, upper):
        bevel(obj, .004)
    return fixed, moving


def cartridge_body(f, parent, *, section=True):
    end = math.pi if section else TAU
    upper = orient_mesh(ring("Brass shell around the outlet chamber", (
        (.963, .43), (1.055, .43), (1.055, 1.57), (.86, 1.80), (.77, 2.18),
        (.348, 2.18), (.348, 1.64), (.76, 1.64), (.963, 1.49),
    ), f["brass"], parent, end=end))
    # The service photograph shows a window through the side of the cartridge.
    window = block("Mill through cartridge wall",
                   (math.cos(WINDOW_ANGLE), math.sin(WINDOW_ANGLE), OUTLET_Z),
                   (.65, WINDOW_WIDTH, WINDOW_HEIGHT), None, parent, edge=.025)
    window.rotation_euler.z = WINDOW_ANGLE
    bpy.context.view_layer.objects.active = window
    bpy.ops.object.modifier_apply(modifier=window.modifiers[0].name)
    cut(upper, window)
    for sign in (-1, 1):
        notch = block("Locating groove for the fixed disc",
                      (0, sign * .972, .58), (.204, .146, .24), None, parent, edge=0)
        cut(upper, notch)
    bevel(upper, .013)
    ring("Stem seal within the valve shell",
         ((.32, 1.90), (.348, 1.90), (.348, 1.97), (.32, 1.97)),
         f["dark"], parent, end=end)
    bevel(ring("Hexagonal wrench flats", ((.765, 1.70), (1.18, 1.70), (1.22, 1.76),
         (1.22, 2.03), (1.14, 2.12), (.765, 2.12)), f["brass"], parent,
         sides=3 if section else 6, end=end), .017)
    mounting_thread(f, parent, section=section)


def valve_body(f, parent):
    """Schematic valve body collecting water outside the cartridge window."""
    finish = material("Sectioned valve body", (.31, .38, .40), .48, .36)
    collector = orient_mesh(ring("Sectioned valve body and outlet gallery", (
        (1.056, .75), (1.47, .75), (1.47, 1.238), (1.066, 1.238),
        (1.066, 1.223), (1.29, 1.223), (1.29, .88), (1.056, .88),
    ), finish, parent, end=math.pi))
    bore = axis_cylinder("Bore into the valve body gallery", .131, .75, OUTLET_Z, None, parent)
    bore.location.x = 1.44
    bore.rotation_euler.y = math.pi / 2
    cut(collector, bore)
    bevel(collector, .010)
    branch = orient_mesh(block("Side of the faucet valve body", (1.69, .22, OUTLET_Z),
                               (.64, .44, .53), finish, parent, edge=0))
    bore = axis_cylinder("Passage through the valve body", .131, .76, OUTLET_Z, None, parent)
    bore.location.x = 1.69
    bore.rotation_euler.y = math.pi / 2
    cut(branch, bore)
    bevel(branch, .014)
    for z in (.837, 1.213):
        ring("Seal between cartridge and valve body",
             ((1.050, z-.027), (1.083, z-.021), (1.090, z),
              (1.083, z+.021), (1.050, z+.027)),
             f["dark"], parent, end=math.pi)


def intact_cartridge(f, root, *, section):
    section_finishes(f)
    cartridge_body(f, root, section=section)
    fixed, moving = ceramic_pair(f, root)
    driver = group("Stem engaged in rotating plate", parent=root)
    drive(f, driver)
    seal_end = math.pi if section else TAU
    ring("Open bottom gasket", ((.81, .38), (1.015, .38), (1.043, .45),
         (1.001, FIXED_Z), (.81, FIXED_Z)), f["dark"], fixed, end=seal_end)
    return fixed, moving, driver


def drive(f, parent):
    bevel(axis_cylinder("Splined stem", .32, 2.68 - STEM_BOTTOM,
                        (2.68 + STEM_BOTTOM) / 2, f["brass"], parent), .026)
    for tooth in range(20):
        angle = tooth * TAU / 20
        spline = block("Stem spline", (.319 * math.cos(angle), .319 * math.sin(angle), 2.48),
                       (.075, .052, .36), f["brass"], parent, edge=.011)
        spline.rotation_euler.z = angle
    # The rectangular tongue reaches into the blind pocket. Its sides bear on
    # the slot walls, and the water goes around the stem in the annular chamber.
    block("Drive tongue fitted into the upper ceramic", (0, 0, 1.057), (.178, .397, .501),
          f["cut"], parent, edge=.005)


def inlet(f, root):
    seat = group("Lower inlet seat and gasket", parent=root)
    ring("Inlet bore", ((.81, -.35), (1.035, -.35), (1.035, .355), (.81, .355)),
         f["brass"], seat, end=math.pi)
    ring("Compression seal beneath the bottom ceramic",
         ((.81, .354), (1.012, .354), (1.045, .420), (1.001, FIXED_Z), (.81, FIXED_Z)),
         f["dark"], seat, end=math.pi)
    return seat


def inlet_water(f, parent):
    return ring("Water in the shared inlet chamber",
                ((.001, 0), (.80, 0), (.80, FIXED_Z + .33), (.001, FIXED_Z + .33)),
                f["water"], parent, end=math.pi)


def common_opening(f, root):
    profile = ((PORT_INNER+.005, FIXED_Z), (PORT_OUTER-.006, FIXED_Z),
               (PORT_OUTER-.006, MOVING_TOP-.010), (PORT_INNER+.005, MOVING_TOP-.010))
    objects = [ring("Water visible only in the common opening", profile, f["water"], root,
                    start=-PORT_HALF, end=PORT_HALF, sides=32) for _ in range(2)]

    def paint(turn):
        # A clockwise turn puts the moving port at -turn. The intersection
        # begins at the fixed port's left boundary and ends at the moving edge.
        width = overlap(turn)
        for index, obj in enumerate(objects):
            obj.hide_render = width < .003
            for column in range(33):
                angle = (index * math.pi - PORT_HALF + .001
                         + max(0, width - .002) * column / 32)
                for corner, (radius, z) in enumerate(profile):
                    obj.data.vertices[column*4+corner].co = (radius*math.cos(angle),
                                                            radius*math.sin(angle), z)
            obj.data.update()

    return paint


def flowing_water(f, root):
    # Both fixed openings rise from a common inlet. Above the faces one
    # branch travels around the drive tongue. The two join at the wall window.
    # The joint stream goes around the cartridge in the gallery and leaves
    # through the passage in the surrounding valve body.
    outlet = [(radius * math.cos(angle), radius * math.sin(angle), OUTLET_Z)
              for radius, angle in ((1.112, WINDOW_ANGLE), (1.173, .26),
                                    (1.181, .12), (1.22, .028))]
    right = [(.55, .035, FIXED_Z-.006), (.55, .035, .66), (.55, .035, .94),
             (.60, .088, OUTLET_Z), (.70, .24, OUTLET_Z), (.83, .36, OUTLET_Z),
             (1.004, .43, OUTLET_Z), *outlet,
             (1.31, .018, OUTLET_Z), (1.50, .015, OUTLET_Z), (1.99, .015, OUTLET_Z)]
    left = [(-.55, .035, FIXED_Z-.006), (-.55, .035, .66), (-.55, .052, .94),
            (-.45, .26, OUTLET_Z), (-.23, .47, OUTLET_Z), (.04, .54, OUTLET_Z),
            (.43, .46, OUTLET_Z), (.68, .34, OUTLET_Z), (.83, .36, OUTLET_Z)]
    paths = []
    for index, points in enumerate((right, left)):
        stream = pipe("Water through the ceramic and outlet", points, .056 if index == 0 else .046,
                      f["water"], root, bezier=True)
        stream.data.bevel_factor_mapping_end = "SPLINE"
        lengths = [0]
        for start, end in zip(points, points[1:]):
            lengths.append(lengths[-1] + (Vector(end) - Vector(start)).length)
        dots = [bead("Moving water highlight", (0, 0, 0), .019, f["spark"], root) for _ in range(6)]
        paths.append((stream, points, lengths, dots, stream.data.bevel_depth))

    def paint(t, fill, turn=0):
        opening = overlap(turn) / (2 * PORT_HALF)
        for stream, points, lengths, dots, radius in paths:
            stream.hide_render = fill <= 0 or opening <= 0
            stream.data.bevel_depth = radius * math.sqrt(opening)
            stream.data.bevel_factor_end = fill
            positions = [Vector(point) for point in points]
            if turn:
                for point in positions:
                    angle = -.5 * turn * (1-ease(point.z, .88, OUTLET_Z))
                    x, y = point.x, point.y
                    point.x = x * math.cos(angle) - y * math.sin(angle)
                    point.y = x * math.sin(angle) + y * math.cos(angle)
            for point, location in zip(stream.data.splines[0].bezier_points, positions, strict=True):
                point.co = location
            for index, dot in enumerate(dots):
                position = ((t * .88 + index / len(dots) * lengths[-1]) % lengths[-1])
                dot.hide_render = stream.hide_render or position >= (fill - .035)*lengths[-1]
                if not dot.hide_render:
                    span = next(i for i in range(1, len(lengths)) if lengths[i] >= position)
                    portion = (position-lengths[span-1]) / (lengths[span]-lengths[span-1])
                    dot.location = positions[span-1].lerp(positions[span], portion)
    return paint


def studio(f, floor):
    block("Studio floor", (0, 0, floor - .06), (60, 60, .12), f["wall"], edge=0)


def section_end(f, root):
    ceramic_pair(f, root, section=True)
    inlet(f, root)
    water = inlet_water(f, root)
    water.location.z = -.33
    for start, end in ((0, PORT_HALF-.005), (math.pi - PORT_HALF+.005, math.pi)):
        ring("Pressurized inlet water stopped at the contact plane",
             ((PORT_INNER+.005, FIXED_Z), (PORT_OUTER-.006, FIXED_Z),
              (PORT_OUTER-.006, CONTACT_Z), (PORT_INNER+.005, CONTACT_Z)),
             f["water"], root, start=start, end=end, sides=28)


def section_finishes(f):
    f["fixed"] = material("Stationary ceramic, warm grey", (.33, .30, .24), 0, .29)
    f["moving"] = material("Rotating ceramic, porcelain", (.89, .87, .78), 0, .25)
    f["water"] = material("Water, cyan blue", (.004, .22, .67), 0, .29, .29)


def pose_for(view, cam, f):
    if view == "extract":
        return extraction(cam, f, cartridge_builder=intact_cartridge, lifted_rotation=1.31)
    section_finishes(f)
    studio(f, -1.27 if view in ("plates", "flow") else -.57)
    root = group("Ceramic cartridge")
    fixed, moving = ceramic_pair(f, root)
    wet = common_opening(f, root)
    indicator = block("Flush brass drive tongue for the overhead view", (0, 0, .852),
                      (.172, .388, .053), f["cut"], moving, edge=.004)
    if view in ("opening-ports", "reopen", "replay-ports"):
        def plan(t):
            if view == "opening-ports":
                turn = TRAVEL * ease(t, .23, 1.08)
            elif view == "replay-ports":
                turn = TRAVEL * ease(t, 1.40, 3.43)
            else:
                turn = TRAVEL * (1-ease(t, .28, 2.58))
                turn += .53 * TRAVEL * (ease(t, 4.16, 5.33)-ease(t, 6.05, 7.48))
            moving.rotation_euler.z = -turn
            wet(turn)
            camera(cam, (0, -.03, CONTACT_Z), PLAN_DIRECTION, 4.98 if view.endswith("-ports") else 4.25)
        return plan

    shell = group("Cartridge housing", parent=root)
    cartridge_body(f, shell)
    collector = group("Valve body surrounding the cartridge", parent=root) if view in ("flow", "closure") else None
    if collector:
        valve_body(f, collector)
    driver = group("Stem engaged in rotating plate", parent=root)
    drive(f, driver)
    seat = inlet(f, root)
    entry = inlet_water(f, seat)
    entry.location.z = -.33
    paint_flow = flowing_water(f, shell)
    closed_section = group("Section through the stopped inlet")
    grip = group("Handle fitted onto splined stem", (0, 0, 2.775), driver)
    hot_handle(f, grip)
    grip.scale = (1.75, 1.75, 1.35)
    socket = next(obj for obj in grip.children if obj.name.startswith("Handle hub"))
    for vertex in socket.data.vertices:
        if math.hypot(vertex.co.x, vertex.co.y) < .12:
            vertex.co.x *= .361 / (1.75 * .116)
            vertex.co.y *= .361 / (1.75 * .116)
    grip.rotation_euler.z = TRAVEL
    if view == "closure":
        section_end(f, closed_section)
    else:
        show_tree(grip, view == "opening-body")

    def pose(t):
        angle, drop, fill, supply = 0, 0, 0, 0
        assembly, overhead, sealed = True, False, False
        if view == "opening-body":
            angle = TRAVEL
            push = ease(t, 0, 2.55)
            camera(cam, (-.43, 0, 1.68), (1.75-.75*push, -8, 3.02+1.12*push), 7.25-.35*push)
        elif view == "plates":
            angle = TRAVEL * (1-ease(t, 2.34, 4.40))
            emphasis = ease(t, 4.70, 5.55)
            drop = ease(t, 6.60, 8.52)
            camera(cam, (.18+.05*drop, -.26*drop, 1.39-.16*emphasis-.26*drop),
                   (2.20-1.5*emphasis-.20*drop, -8, 3.65+1.7*emphasis+.7*drop),
                   5.85-.28*emphasis+.54*drop)
        elif view == "flow":
            drop = 1-ease(t, .09, 1.93)
            supply = ease(t, 5.39, 5.95)
            fill = .20*ease(t, 5.95, 6.78) + .33*ease(t, 6.78, 8.39) + .47*ease(t, 8.39, 9.86)
            if t < 5.24:
                camera(cam, (.23, -.26*drop, 1.23-.26*drop),
                       (1.04, -8, 5.35+.7*drop), 5.75+.54*drop)
            else:
                follow = ease(t, 5.24, 9.86)
                camera(cam, (.45+.06*follow, 0, 1.14-.02*follow),
                       (2.00+.29*follow, -8, 3.78-.73*follow), 6.30-.28*follow)
        else:
            # Start shutting on the handle cue, then read the actual overlap
            # from directly above before cutting to the pressure-side section.
            angle = TRAVEL * ease(t, .40, 4.48)
            assembly = t < 1.30
            overhead = 1.30 <= t < 4.60
            sealed = not assembly and not overhead
            if assembly:
                fill = supply = 1
                camera(cam, (-.28, 0, 1.55), SECTION_DIRECTION, 7.17)
            elif overhead:
                camera(cam, (0, -.03, CONTACT_Z), PLAN_DIRECTION, 4.25)
            else:
                push = ease(t, 4.60, 7.3)
                camera(cam, (.22, 0, .43), (1.5+.15*push, -8, 3.25), 4.17-.25*push)

        show_tree(root, not sealed)
        show_tree(closed_section, sealed)
        if sealed:
            return
        for part in (driver, shell, seat):
            show_tree(part, assembly)
        if collector:
            show_tree(collector, assembly and (view == "closure" or t >= 5.24))
        entry.hide_render = not assembly or not supply
        entry.scale.z = supply
        show_tree(grip, view in ("opening-body", "closure") and assembly)
        indicator.hide_render = not overhead
        slide = ease(drop, .30, 1)
        fixed.location = (0, -.57 * slide, -.54 * drop)
        seat.location = (0, -.57 * slide, -.76 * drop)
        moving.rotation_euler.z = driver.rotation_euler.z = -angle
        wet(angle if overhead else TRAVEL)
        paint_flow(t, fill, angle if view == "closure" and assembly else 0)

    return pose


def render_key(view, frame):
    # Reuse true holds where neither the camera nor the geometry changes.
    holds = {
        "extract": STILL_INTERVALS["extract"],
        "opening-ports": ((0, 6), (33, 59)),
        "opening-body": ((77, 89),),
        "plates": ((0, 70), (132, 141), (167, 198), (256, 318)),
        "flow": ((0, 2), (58, 145)),
        "closure": ((135, 137), (219, 263)),
        "reopen": ((0, 8), (78, 124), (160, 181), (225, 282)),
        "replay-ports": ((0, 42), (103, 239)),
    }
    return next((first for first, last in holds[view] if first <= frame <= last), frame)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("views", nargs="+", choices=tuple(COUNTS))
    parser.add_argument("--preview", action="store_true")
    parser.add_argument("--points", type=int, nargs="+")
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
    for view in args.views:
        folder = args.directory / view
        folder.mkdir(parents=True, exist_ok=True)
        scene, cam = setup(0)
        scene.render.resolution_percentage = 40 if args.preview else 100
        scene.eevee.taa_render_samples = 5 if args.preview else 8
        pose = pose_for(view, cam, finishes())
        for frame in args.points if args.points else range(COUNTS[view]):
            destination = folder / f"{frame:05}.jpg"
            if destination.is_file():
                continue
            reference = folder / f"{render_key(view, frame):05}.jpg"
            if reference.is_file():
                destination.hardlink_to(reference)
                continue
            pose(frame / FPS)
            scene.render.filepath = str(destination)
            bpy.ops.render.render(write_still=True)


if __name__ == "__main__":
    main()
