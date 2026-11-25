"""Original Blender scene for a side-mounted full-extension drawer slide."""

import argparse
import json
from math import sin, cos
from pathlib import Path
from shutil import copyfile
import sys

import bpy
import bmesh
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "quarter-turn-faucet"))
from scene import bead, bevel, block, camera, ease, group, material, pipe, setup, surface

FPS = 30
LENGTH = 9.0
CABINET_Y = 4.05
DRAWER_Y = 3.80
RAIL_Z = 3.00
SECTION_SCALE = .00381
BALL_RADIUS = 12 * SECTION_SCALE
# Polylines follow the bent webs in the product section. Coordinates on each
# member's web are used for modeling the steel sheet, not the ball geometry.
OUTER = ((341, 100), (341, 88), (338, 81), (332, 79), (294, 79),
         (287, 83), (286, 90), (286, 302), (290, 310), (332, 310),
         (338, 307), (341, 302), (341, 291))
MIDDLE = ((339, 116), (334, 110), (326, 107), (304, 105), (296, 109),
          (296, 145), (299, 152), (312, 158), (315, 164), (315, 228),
          (312, 234), (299, 240), (296, 245), (296, 281), (302, 285),
          (326, 284), (334, 281), (339, 275))
INNER = ((312, 123), (313, 131), (322, 141), (337, 136), (343, 137),
         (346, 142), (346, 250), (343, 254), (337, 255), (322, 250),
         (313, 259), (312, 268))


def section_y(pixel):
    return (pixel - 283) * SECTION_SCALE


def section_z(pixel):
    return (195 - pixel) * SECTION_SCALE


def palette():
    return {
        "floor": material("Slate studio floor", (.102, .155, .177), 0, .49),
        "cabinet": material("Eucalyptus painted cabinet", (.072, .246, .239), 0, .33),
        "edge": material("Cabinet edge and feet", (.03, .067, .075), .24, .36),
        "oak": material("White oak", (.55, .335, .16), 0, .36),
        "end": material("Cut oak", (.38, .201, .085), 0, .43),
        "handle": material("Satin brass", (.62, .32, .087), .72, .29),
        "outer": material("Blue identification tint on fixed rail", (.075, .29, .56), .53, .29),
        "middle": material("Zinc-plated intermediate", (.55, .65, .69), .70, .27),
        "inner": material("Gold identification tint on drawer rail", (.80, .38, .078), .53, .28),
        "ball": material("Polished ball bearing", (.71, .76, .79), .76, .22),
        "cage": material("Dark stamped retainer", (.043, .062, .066), .46, .33),
        "fastener": material("Mount hardware", (.099, .115, .12), .55, .35),
        "goods": material("Ceramic organizer", (.72, .76, .66), 0, .39),
        "liner": material("Dark green liner", (.10, .19, .17), 0, .55),
        "cloth": material("Oatmeal textile", (.62, .46, .28), 0, .67),
    }


def channel(name, profile, length, finish, parent, end=0):
    """Extrude a closed bent-sheet section along the direction of travel."""
    center = [Vector((section_y(y), section_z(z))) for y, z in profile]
    offsets = []
    for i, point in enumerate(center):
        incoming = (point - center[max(0, i - 1)]).normalized()
        outgoing = (center[min(len(center) - 1, i + 1)] - point).normalized()
        direction = (incoming + outgoing).normalized()
        offsets.append(Vector((-direction.y, direction.x)) * (1.7 * SECTION_SCALE))
    outline = [point + offset for point, offset in zip(center, offsets)]
    outline.extend(reversed([point - offset for point, offset in zip(center, offsets)]))
    vertices = [(x, y, z) for x in (end - length, end) for y, z in outline]
    n = len(outline)
    faces = [tuple(reversed(range(n))), tuple(range(n, 2 * n))]
    faces.extend((i, (i + 1) % n, (i + 1) % n + n, i + n) for i in range(n))
    obj = surface(name, vertices, faces, finish, parent)
    # Sign-independent normals protect both mirrored installations.
    mesh = obj.data
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(mesh)
    bm.free()
    return bevel(obj, .002)


def drawer_system(parts):
    fixed = group("Cabinet")
    side = group("Cabinet near panel", parent=fixed)
    drawer = group("Drawer with payload")
    for name, position, size, parent in (
        ("Near removable side panel", (-4.55, -4.22, 3.78), (9.40, .34, 2.26), side),
        ("Near fixed side section", (-4.55, -4.22, 1.555), (9.40, .34, 2.19), fixed),
        ("Far cabinet side", (-4.55, 4.22, 2.70), (9.40, .34, 4.42), fixed),
        ("Cabinet back", (-9.13, 0, 2.67), (.28, 8.20, 4.28), fixed),
        ("Countertop", (-4.54, 0, 5.09), (9.66, 8.88, .29), fixed),
        ("Low cabinet bottom", (-4.53, 0, .64), (9.0, 8.25, .31), fixed),
    ):
        block(name, position, size, parts["cabinet"], parent, edge=.075)
    for x in (-8.45, -.63):
        for y in (-3.73, 3.73):
            block("Low cabinet foot", (x, y, .26), (.62, .61, .52), parts["edge"], fixed)
    for x in (-7.5, -1.9):
        block("Fixed rail mounting section", (x, -4.10, 2.82), (.47, .098, .38),
              parts["cabinet"], fixed, edge=.023)
    block("Lower cabinet panel", (-.04, 0, 1.31), (.32, 8.17, 1.57), parts["cabinet"], fixed, edge=.062)
    block("Drawer front", (.06, 0, 3.37), (.36, 8.03, 2.61), parts["oak"], drawer, edge=.075)
    block("Drawer floor", (-4.44, 0, 2.54), (8.88, 7.58, .22), parts["end"], drawer)
    block("Drawer liner", (-4.45, 0, 2.657), (8.32, 7.11, .025), parts["liner"], drawer)
    for sign in (-1, 1):
        block("Drawer side", (-4.49, sign * (DRAWER_Y - .13), 3.36),
              (8.95, .26, 1.54), parts["oak"], drawer)
    block("Drawer rear", (-8.83, 0, 3.36), (.26, 7.58, 1.54), parts["oak"], drawer)
    for y in (-1.09, 1.09):
        block("Handle stand-off", (.392, y, 3.55), (.32, .18, .16), parts["handle"], drawer, edge=.035)
    pipe("Drawer pull", ((.56, -1.3, 3.55), (.56, 1.3, 3.55)), .096, parts["handle"], drawer)
    for x, y in ((-2.05, 1.85), (-4.92, 1.85)):
        block("Tray floor", (x, y, 2.78), (2.33, 2.38, .24), parts["goods"], drawer, edge=.10)
        for direction in (-1, 1):
            block("Tray side", (x, y + direction * 1.11, 2.99),
                  (2.30, .16, .51), parts["goods"], drawer, edge=.068)
            block("Tray end", (x + direction * 1.08, y, 2.99),
                  (.16, 2.30, .51), parts["goods"], drawer, edge=.068)
    for level in range(3):
        block("Folded kitchen cloth", (-3.16, -1.82, 2.82 + .23 * level),
              (2.83 - .12 * level, 2.28, .26), parts["cloth"], drawer, edge=.105)
    return fixed, side, drawer


def slide(parts, length=LENGTH, mirror=False, macro=False):
    base_y = CABINET_Y if mirror else -CABINET_Y
    root = group("Far slide" if mirror else "Accessible slide", (0, base_y, RAIL_Z))
    if mirror:
        root.scale.y = -1
    outer, middle, inner = [group(name, parent=root) for name in
                            ("Cabinet member", "Intermediate member", "Drawer member")]
    for profile, key, node in zip((OUTER, MIDDLE, INNER), ("outer", "middle", "inner"),
                                  (outer, middle, inner), strict=True):
        if macro and key != "inner":
            channel(key + " back of sectional window", profile, .58, parts[key], node, end=-1.82)
            channel(key + " window upper lip", profile[:5 if key == "outer" else 4],
                    1.82, parts[key], node)
            channel(key + " window lower lip", profile[-4:], 1.82, parts[key], node)
        else:
            channel(key + " formed steel channel", profile, length, parts[key], node)

    def retainer(name, y_pixel, rows):
        cage = group(name, (-length / 2, 0, 0), root)
        count = 6 if macro else 12
        step = .21 if macro else .27
        y = section_y(y_pixel)
        for row in rows:
            z = section_z(row)
            for i in range(count):
                x = (i - (count - 1) / 2) * step
                # Leave a window around every ball in the keeper.
                if macro:
                    sphere = group("Rolling bearing", (x, y, z), cage)
                    bead("Steel sphere", (0, 0, 0), BALL_RADIUS, parts["ball"], sphere)
                    for angle in (0, 2.0, 4.1):
                        bead("Rolling witness dot",
                             (BALL_RADIUS * cos(angle) * .76, -.65 * BALL_RADIUS,
                              BALL_RADIUS * sin(angle) * .76),
                             .007, parts["fastener"], sphere)
                else:
                    bead("Bearing", (x, y, z), BALL_RADIUS, parts["ball"], cage)
                if i + 1 < count:
                    block("Retainer bridge", (x + step / 2, y, z),
                          (step - BALL_RADIUS * 1.87, .023, .086),
                          parts["cage"], cage, edge=.004)
            for edge in (-1, 1):
                block("Retainer edge", (0, y, z + edge * .051),
                      ((count - 1) * step + .14, .022, .015), parts["cage"], cage, edge=.003)
        return cage

    cages = (retainer("Cabinet/intermediate ball retainer", 313, (96, 295)),
             retainer("Intermediate/drawer ball retainer", 326, (124, 267)))
    if not macro:
        for x in (-.36, -2.27, -5.92, -8.38):
            block("Drawer member mounting screw", (x, .226, 0),
                  (.106, .019, .106), parts["fastener"], inner, edge=.03)
    return middle, inner, cages


def move_slide(rail, travel, middle_travel, length=LENGTH):
    middle, inner, cages = rail
    middle.location.x = middle_travel
    inner.location.x = travel
    # With pure rolling between two races, the retainer translates at their mean speed.
    cages[0].location.x = -length / 2 + middle_travel / 2
    cages[1].location.x = -length / 2 + (middle_travel + travel) / 2


def full_scene(cam, parts, shot, duration):
    _, side, drawer = drawer_system(parts)
    rails = [slide(parts), slide(parts, mirror=True)]

    def pose(t):
        if shot == 0:
            travel = 9.12 * (.15 + .85 * ease(t, .12, 1.77))
            mid = travel * .50
            focus = (-3.75 + travel * .46, 0, 2.87)
            camera(cam, focus, (7.5, -10.7, 5.4), 22.9)
            key = (travel,)
        elif shot == 1:
            travel, mid = 9.12, 4.56
            clear = ease(t, .15, .54)
            separation = ease(t, .54, 1.75)
            side.location.y = -.66 * clear
            side.location.z = 8.9 * separation
            push_in = ease(t, .85, 3.35)
            camera(cam, (.47 + .30 * push_in, -.45 - 1.06 * push_in, 2.72 + .30 * push_in),
                   (7.5 - 4.4 * push_in, -10.7, 5.4 - 3.1 * push_in), 22.9 - 3.1 * push_in)
            key = (clear, separation, push_in)
        elif shot == 2:
            side.location.z = 10
            start = .37
            # The two paths overlap in time. Separate pacing exposes both real
            # degrees of freedom while leaving the exact specimen phasing open.
            a = ease(t, start, duration * .45)
            b = ease(t, duration * .22, duration * .64)
            mid = 4.56 * a
            travel = mid + 4.56 * b
            camera(cam, (-4.25 + travel * .47, -2.95, 2.86),
                   (2.8, -12, 2.22), 17.2 + 3.7 * b)
            key = (a, b)
        else:
            open_amount = .91 + .09 * ease(t, .12, 1.22)
            shut_amount = ease(t, duration * .47, duration * .65)
            reopen = ease(t, duration * .68, duration - 1.27)
            travel = 9.12 * (open_amount * (1 - shut_amount) + reopen)
            mid = travel * .5
            close_panel = ease(t, duration * .69, duration * .79)
            seat_panel = ease(t, duration * .79, duration * .83)
            side.location.z = 8.9 * (1 - close_panel)
            side.location.y = -.66 * (1 - seat_panel)
            orbit = ease(t, duration * .67, duration * .88)
            camera(cam, (-3.75 + travel * .46, -.25, 2.87),
                   (3.0 + 4.5 * orbit, -10.7, 2.1 + 3.3 * orbit), 22.9)
            key = (travel, close_panel, seat_panel, orbit)
        drawer.location.x = travel
        for rail in rails:
            move_slide(rail, travel, mid)
        return key

    return pose


def macro_scene(cam, parts, duration):
    length = 2.40
    rail = slide(parts, length, macro=True)
    # A removed length of track exposes a cut end and the actual four ball rows.
    def pose(t):
        amount = ease(t, duration * .21, duration * .70)
        middle_travel, travel = .40 * amount, .77 * amount
        move_slide(rail, travel, middle_travel, length)
        for cage, slip in zip(rail[2], (middle_travel, travel - middle_travel)):
            for ball in cage.children:
                if ball.type == "EMPTY":
                    ball.rotation_euler.y = -slip / (2 * BALL_RADIUS) if ball.location.z > 0 else slip / (2 * BALL_RADIUS)
        camera(cam, (-.65 + .26 * amount, -3.90, 2.99),
               (2.1 + 1.8 * amount, -9.75, 2.95 - .6 * amount), 3.80)
        return (amount,)

    return pose


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--timing", type=Path, required=True)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--shot", type=int, choices=range(5), required=True)
    parser.add_argument("--preview", action="store_true")
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
    count = json.loads(args.timing.read_text())[args.shot]
    scene, cam = setup(args.shot)
    scene.render.resolution_percentage = 38 if args.preview else 100
    scene.eevee.taa_render_samples = 12 if args.preview else 32
    scene.eevee.shadow_ray_count = 3
    front = bpy.data.objects["Front fill"]
    front.location = (9, -5.5, 6)
    front.data.energy = 1450
    front.data.size = 6.5
    front.rotation_euler = (Vector((0, -1, 2)) - front.location).to_track_quat("-Z", "Y").to_euler()
    parts = palette()
    block("Studio floor", (0, 0, -.23), (120, 120, .45), parts["floor"], edge=0)
    duration = count / FPS
    pose = macro_scene(cam, parts, duration) if args.shot == 3 else full_scene(cam, parts, args.shot, duration)
    folder = args.directory / f"shot-{args.shot}"
    folder.mkdir(parents=True, exist_ok=True)
    rendered = {}
    for frame in range(0, count, 5 if args.preview else 1):
        path = folder / f"{frame:05}.jpg"
        key = pose(frame / FPS)
        if path.is_file():
            rendered[key] = path
            continue
        if key not in rendered:
            scene.render.filepath = str(path)
            bpy.ops.render.render(write_still=True)
            rendered[key] = path
        else:
            copyfile(rendered[key], path)


if __name__ == "__main__":
    main()
