"""Blender reconstruction of the M185 wheel assembly and a quadrature teaching model."""

import argparse
import json
from math import cos, pi, sin, tau
from pathlib import Path
from shutil import copyfile
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "quarter-turn-faucet"))
from scene import bevel, block, camera, cylinder, ease, group, material, pipe, ring, setup, surface

FPS = 30
AXIS = (0, 2.43, 2.27)
PITCH = tau / 8
DETENT = tau / 24
BASE_PHASES = (.875, .625)
CONTACT_ANGLES = (.31, .31 - PITCH / 4)

# Front is +Y. Sections list position, half width and centerline height.
CONTOUR = (
    (-4.94, .04, .92), (-4.80, .86, 1.85), (-4.51, 1.73, 2.65),
    (-4.03, 2.31, 3.23), (-3.34, 2.69, 3.59), (-2.40, 2.84, 3.80),
    (-1.30, 2.83, 3.87), (-.20, 2.72, 3.74), (.90, 2.74, 3.47),
    (1.62, 2.84, 3.34), (2.45, 2.97, 3.15), (3.28, 2.91, 2.89),
    (3.89, 2.70, 2.47), (4.36, 2.21, 2.24), (4.68, 1.61, 2.02),
    (4.91, .80, 1.74), (5.00, .05, 1.29),
)


def shell(top, side, dark, feet):
    base = group("M185 lower shell")
    hull = [(x * width, y, z) for y, width, _ in CONTOUR
            for x, z in ((-.91, .10), (.91, .10), (1, .66), (.98, .98),
                         (-.98, .98), (-1, .66))]
    faces = [(i * 6 + j, i * 6 + (j + 1) % 6,
              (i + 1) * 6 + (j + 1) % 6, (i + 1) * 6 + j)
             for i in range(len(CONTOUR) - 1) for j in range(6)]
    # Keep the rim and bottom flat at their bearing surfaces.
    faces.extend((tuple(reversed(range(6))), tuple(range(len(hull) - 6, len(hull)))))
    surface("Injection molded base", hull, faces, side, base, smooth=True)
    for y, w in ((3.5, 3.45), (-3.18, 3.4)):
        block("Glide pad", (0, y, .097), (w, .79, .10), feet, base, edge=.046)
    block("Battery cover seam", (0, -2.2, .11), (3.4, 3.35, .09), dark, base, edge=.045)

    cover = group("M185 button cover")
    across = 19
    for sign in (-1, 1):
        vertices = []
        for y, outer, crown in CONTOUR:
            if y < -.20:
                gap = 0
            elif 1.62 <= y <= 3.28:
                gap = .59
            else:
                gap = .037
            gap = min(gap, outer * .8)
            for column in range(across):
                x = gap + (.98 * outer - gap) * sin(pi / 2 * column / (across - 1))
                profile = max(0, 1 - (x / (.98 * outer)) ** 2)
                z = 1.00 + (crown - 1.00) * profile ** .65
                vertices.append((sign * x, y, z))
        cells = [(a, a + 1, a + across + 1, a + across)
                 for a in range(len(vertices) - across) if a % across != across - 1]
        if sign == -1:
            cells = [tuple(reversed(face)) for face in cells]
        panel = surface("Left button and palm" if sign < 0 else "Right button and palm",
                        vertices, cells, top, cover, smooth=True)
        wall = panel.modifiers.new("Molded wall", "SOLIDIFY")
        wall.thickness = .10
        smoothing = panel.modifiers.new("Rounded housing", "SUBSURF")
        smoothing.levels = 2
        smoothing.render_levels = 2
    return cover, base


def polygon_plate(name, outline, low, high, finish, parent):
    vertices = [(x, y, z) for z in (low, high) for x, y in outline]
    n = len(outline)
    faces = [tuple(reversed(range(n))), tuple(range(n, 2 * n))]
    faces.extend((i, (i + 1) % n, (i + 1) % n + n, i + n) for i in range(n))
    return surface(name, vertices, faces, finish, parent)


def axial(name, profile, finish, parent, **options):
    carrier = group(name + " axis", parent=parent)
    carrier.rotation_euler.y = pi / 2
    return ring(name, profile, finish, carrier, **options)


def lathe_solid(name, radius, start, end, finish, parent, sides=48):
    return axial(name, ((.001, start), (radius, start), (radius, end), (.001, end)),
                 finish, parent, sides=sides)


def wheel(parts):
    root = group("Wheel on axle", AXIS)
    axial("Overmolded rubber tread", (
        (.80, -.49), (.99, -.49), (1.079, -.41), (1.12, -.25),
        (1.12, .25), (1.079, .41), (.99, .49), (.80, .49),
    ), parts["rubber"], root, sides=72)
    axial("Molded rim", ((.63, -.49), (.83, -.49), (.90, -.39), (.90, .39),
                         (.83, .49), (.63, .49)), parts["hub"], root, sides=56)
    lathe_solid("Wheel hub", .265, -.57, .61, parts["hub"], root)
    lathe_solid("Free support end", .185, -.91, -.27, parts["hub"], root)
    lathe_solid("Drive end of axle", .143, .22, 1.22, parts["axle"], root, sides=6)
    for i in range(6):
        angle = i * tau / 6
        spoke = block("Wheel rib", (0, .48 * cos(angle), .48 * sin(angle)),
                      (.56, .68, .155), parts["hub"], root, edge=.026)
        spoke.rotation_euler.x = angle
    for i in range(36):
        angle = i * tau / 36
        tread = block("Tread groove", (0, 1.122 * cos(angle), 1.122 * sin(angle)),
                      (.55, .010, .038), parts["tread"], root, edge=.004)
        tread.rotation_euler.x = angle
    block("Tread witness", (0, 0, 1.135),
          (.49, .085, .026), parts["mint"], root, edge=.01)
    return root


def electronics(parts):
    root = group("210-002250 REV002 board relationship")
    outline = ((-1.12, -3.12), (.55, -3.12), (.78, -2.76), (.78, -1.32),
               (.68, -1.22), (.82, -.58), (1.94, .90), (2.26, 2.29),
               (2.24, 2.89), (1.30, 3.58), (-1.24, 3.58), (-2.06, 2.99),
               (-2.02, 1.66), (-1.26, 1.13), (-1.15, -2.21),
               (-1.04, -2.31), (-1.04, -2.49), (-1.15, -2.58))
    board = polygon_plate("Solder-masked FR-4", outline, 1.03, 1.15, parts["pcb_mask"], root)
    board.data.materials.append(parts["board_edge"])
    for face in board.data.polygons:
        if face.index != 1:
            face.material_index = 1

    opening = polygon_plate("Wheel aperture tool",
                            ((-.61, 1.25), (.62, 1.25), (.62, 3.31), (-.61, 3.31)),
                            .95, 1.26, parts["board_edge"], root)
    cut = board.modifiers.new("Wheel aperture", "BOOLEAN")
    cut.operation, cut.object = "DIFFERENCE", opening
    bpy.context.view_layer.objects.active = board
    bpy.ops.object.modifier_apply(modifier=cut.name)
    bpy.data.objects.remove(opening, do_unlink=True)
    bevel(board, .017)

    for x in (-1.64, 1.78):
        block("Left or right click microswitch", (x, 2.40, 1.50),
              (.51, 1.34, .69), parts["dark"], root, edge=.045)
        block("Microswitch actuator", (x, 2.68, 1.86),
              (.23, .33, .085), parts["white"], root, edge=.024)
    block("Wheel support and middle switch", (-.87, 2.43, 1.65),
          (.33, .73, .73), parts["hub"], root, edge=.04)

    resonator = group("Seamed crystal can", (.39, .59, 1.15), root)
    resonator.rotation_euler.z = -.57
    for name, radius, half_length, bottom, top, finish in (
        ("Footprint", .245, .29, 0, .022, "pcb_print"),
        ("Insulator", .223, .28, .018, .045, "dark"),
        ("Crimp flange", .222, .278, .042, .104, "pcb_solder"),
        ("Stamped cover", .190, .275, .087, .234, "steel"),
    ):
        capsule = []
        for sign in (-1, 1):
            for segment in range(17):
                angle = (pi if sign < 0 else 0) + segment * pi / 16
                capsule.append((radius * cos(angle), sign * half_length + radius * sin(angle)))
        bevel(polygon_plate(name, capsule, bottom, top, parts[finish], resonator), .027)

    cap = group("Sleeved capacitor", (-.76, -1.71, 1.15), root)
    cylinder("Capacitor silkscreen", .274, .010, .005, parts["pcb_print"], cap, edge=0)
    cylinder("Molded capacitor base", .240, .046, .026, parts["dark"], cap, edge=.01)
    cylinder("Black sleeve", .226, .315, .191, parts["pcb_sleeve"], cap, edge=.023)
    cylinder("Rolled aluminum rim", .220, .052, .343, parts["steel"], cap, edge=.016)
    cylinder("Aluminum face", .193, .018, .365, parts["pcb_solder"], cap, edge=.005)
    for angle in (0, pi / 2):
        mark = block("Vent score", (0, 0, .375), (.237, .012, .002),
                     parts["steel"], cap, edge=0)
        mark.rotation_euler.z = angle

    block("Sensor footprint", (.12, -2.13, 1.158), (.53, .43, .013),
          parts["pcb_print"], root, edge=.013)
    block("Sensor socket", (.12, -2.13, 1.184), (.464, .36, .054),
          parts["pcb_sleeve"], root, edge=.019)
    block("Inset sensor window", (.12, -2.13, 1.215), (.295, .198, .039),
          parts["pcb_window"], root, edge=.013)
    for x in (-.064, .304):
        block("Sensor terminal", (x, -2.13, 1.211), (.061, .259, .032),
              parts["steel"], root, edge=.007)

    # Visible-side layout from the 210-002250 REV002 teardown photos.
    # Trace and solder patterns are modeled at photo resolution.
    solder_joints = (
        (-1.61, 1.60), (-1.43, 1.68), (-1.27, 1.51), (-1.45, 1.40), (-1.19, 1.33),
        (-1.08, 1.09), (-.91, 1.01), (-.72, .97), (-1.01, .76), (-.85, .70),
        (-.98, .46), (-.76, .41), (-.65, .26), (-.94, .19), (-.79, .07),
        (-.59, -.09), (-.39, -.08), (-.28, -.24), (-.14, -.32), (-.43, -.42),
        (-.59, -.38), (-.79, -.29), (-.96, -.24), (-1.00, -.44), (-.73, -.57),
        (-.50, -.67), (-.34, -.70), (-.19, -.77), (.05, -.76), (.16, -.58),
        (.34, -.60), (.37, -.40), (.52, -.30), (.66, -.44), (.94, .23), (1.06, .42),
        (-.52, -1.27), (-.36, -1.34), (-.22, -1.20), (.13, -1.48), (.24, -1.40),
        (.43, -1.55), (.28, -1.68), (.01, -1.74), (-.72, -2.55), (-.53, -2.71),
        (-.75, -2.86), (-.23, -2.58), (-.11, -2.76), (.34, -2.59), (.42, -2.84),
    )
    for i, (x, y) in enumerate(solder_joints):
        radius = (.043, .050, .056, .047, .062)[i % 5]
        joint = group("Solder joint", (x, y, 1.148), root)
        ring("Wet solder fillet", ((0, 0), (radius, 0), (radius, .008),
                                   (radius * .66, .027), (radius * .40, .040), (0, .041)),
             parts["pcb_solder"], joint, sides=16)
        cylinder("Clipped pin", radius * .30, .016, .041, parts["pcb_sleeve"],
                 joint, sides=12, edge=.003)

    traces = (
        (0, (-1.58, 1.22), 5), (2, (-1.19, 1.11), 7),
        (6, (-.83, .86), 9), (8, (-1.08, .61), 10), (9, (-.68, .57), 12),
        (10, (-1.13, .15), (-1.08, -.10), 22), (11, (-.58, .24), 15),
        (13, (-.85, -.06), 21), (14, (-.86, -.17), 23),
        (15, (-.51, -.07), (-.41, .05), (-.28, .05), 17),
        (20, (-.67, -.47), 24), (19, (-.54, -.52), 25),
        (18, (-.01, -.47), 28), (26, (-.32, -.83), (-.32, -1.10), 37),
        (30, (.40, -.79), (.35, -1.22), 39), (41, (.48, -1.79), (.48, -2.04)),
    )
    for path in traces:
        points = [solder_joints[node] if isinstance(node, int) else node for node in path]
        pipe("Trace beneath solder mask", [(x, y, 1.146) for x, y in points],
             .011, parts["pcb_trace"], root)
    return root


def encoder_case(parts):
    root = group("Axle-end encoder on the board", (1.12, AXIS[1], AXIS[2]))
    block("Encoder frame", (.24, 0, -.30), (.42, .90, 1.10),
          parts["steel"], root, edge=.055)
    axial("Encoder axle bushing", ((.147, -.02), (.36, -.02), (.36, .16),
                                  (.31, .23), (.147, .23)), parts["dark"], root)
    for i in range(3):
        y = -.33 + i * .33
        block("Encoder PCB terminal", (.24, y, -.87), (.17, .12, .49),
              parts["gold"], root, edge=.02)
    return root


def text_obj(name, body, size, location, finish, parent, font=None):
    data = bpy.data.curves.new(name, "FONT")
    data.body = body
    data.size = size
    data.align_x = "CENTER"
    data.align_y = "CENTER"
    data.extrude = .002
    data.materials.append(finish)
    if font is not None:
        data.font = font
    obj = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(obj)
    obj.parent, obj.location = parent, location
    return obj


def palette():
    specs = {
        "top": ((.027, .039, .052), .13, .41, 0),
        "side": ((.107, .15, .184), .48, .29, 0),
        "rubber": ((.075, .104, .118), .06, .52, 0),
        "tread": ((.024, .039, .045), 0, .56, 0),
        "hub": ((.041, .057, .066), .14, .35, 0),
        "axle": ((.078, .22, .23), .30, .31, 0),
        "dark": ((.014, .027, .037), .14, .35, 0),
        "steel": ((.49, .59, .66), .80, .24, 0),
        "gold": ((.73, .39, .105), .68, .31, 0),
        "board": ((.040, .165, .087), .12, .46, 0),
        "trace": ((.20, .36, .195), .38, .46, 0),
        "pcb_mask": ((.068, .113, .047), .09, .52, 0),
        "board_edge": ((.170, .145, .073), .02, .59, 0),
        "pcb_trace": ((.088, .126, .055), .09, .49, 0),
        "pcb_print": ((.55, .54, .40), .01, .55, 0),
        "pcb_solder": ((.27, .30, .31), .74, .35, 0),
        "pcb_sleeve": ((.021, .025, .024), .07, .47, 0),
        "pcb_window": ((.52, .43, .25), .26, .33, 0),
        "white": ((.85, .91, .90), .05, .36, .05),
        "paper": ((.62, .73, .72), .03, .5, .13),
        "desk": ((.051, .095, .118), .09, .54, 0),
        "mint": ((.03, .73, .43), .18, .36, .22),
        "orange": ((.99, .31, .09), .06, .32, .46),
        "blue": ((.17, .55, 1.0), .08, .32, .48),
        "orange_signal": ((1, .19, .025), .04, .32, 2.4),
        "blue_signal": ((.018, .36, 1), .04, .32, 2.4),
        "dim": ((.056, .089, .105), .27, .42, 0),
        "substrate": ((.044, .11, .14), .20, .32, 0),
    }
    return {key: material(key, color, metal, rough, glow)
            for key, (color, metal, rough, glow) in specs.items()}


def page_window(parts):
    root = group("Original scrolling webpage")
    panel = group("Desk display", (4.85, .37, .88), root)
    panel.rotation_euler.x = .20
    block("Display body", (0, 0, 0), (5.6, 5.18, .22),
          parts["dark"], panel, edge=.10)
    block("Screen background", (0, .02, .16), (5.28, 4.87, .09),
          parts["paper"], panel, edge=.044)
    contents = group("Scrolling article column", (0, 0, .24), panel)
    cards = []
    for i in range(6):
        card = group("Article entry", (0, 0, 0), contents)
        block("Article divider", (-.14, -.47, .008), (4.39, .018, .012),
              parts["substrate"], card, edge=.0)
        accent = (parts["mint"], parts["blue"], parts["orange"])[i % 3]
        block("Article thumbnail", (-1.65, .03, .025), (1.06, .72, .045),
              accent, card, edge=.035)
        text_obj("Scroll reference number", f"{i + 1:02}", .29,
                 (-1.65, .02, .058), parts["dark"], card)
        for j, width in enumerate((2.25, 1.72, 2.56)):
            block("Article text line", (-.87 + width / 2, .24 - .21 * j, .02),
                  (width, .077 if j == 0 else .049, .027),
                  parts["substrate"], card, edge=.013)
        cards.append(card)
    block("Scrollbar gutter", (2.39, -.16, .248), (.07, 3.95, .029),
          parts["substrate"], panel, edge=.016)
    slider = block("Scrollbar thumb", (2.39, .89, .288), (.13, .76, .047),
                   parts["mint"], panel, edge=.022)
    # The screen mask sits above the articles so they scroll behind the header.
    block("Top display mask", (0, 2.40, .335), (5.55, .81, .10),
          parts["dark"], panel, edge=.025)
    block("Bottom display mask", (0, -2.35, .335), (5.55, .65, .10),
          parts["dark"], panel, edge=.025)
    block("Browser header", (0, 2.04, .366), (5.45, .59, .11),
          parts["dark"], panel, edge=.04)
    for i, key in enumerate(("orange", "white", "mint")):
        dot = cylinder("Window control", .061, .039, .439, parts[key], panel, sides=16, edge=.011)
        dot.location.x, dot.location.y = -2.32 + i * .21, 2.04
    block("Address bar", (.40, 2.04, .439), (2.90, .21, .035),
          parts["side"], panel, edge=.016)

    def scroll(steps):
        for i, card in enumerate(cards):
            y = 2.05 - i * 1.035 + .45 * steps
            card.location.y = y
            visible = -2.19 < y < 2.21
            for shape in card.children:
                shape.hide_render = not visible
        slider.location.y = .89 - steps * .30

    return root, scroll


def polar(x, radius, angle):
    return x, radius * cos(angle), radius * sin(angle)


def disk_arc(name, profile, start, end, finish, parent):
    # With the cylinder on X, a positive ring angle advances from -Z toward +Y.
    return axial(name, profile, finish, parent, start=start + pi / 2,
                 end=end + pi / 2, sides=16)


def contact_spring(name, angle, radius, outer_radius, finish, tip_finish, parent):
    """Stamp a bent leaf with a small contact dimple facing the rotor."""
    width = .108
    thickness = .037
    span = outer_radius - radius
    profile = ((outer_radius, .20), (radius + span * .76, .20),
               (radius + span * .48, .135), (radius + span * .19, .086),
               (radius - .045, .086))
    tangent = Vector((0, -sin(angle), cos(angle)))
    vertices = [Vector(polar(x + side * thickness / 2, r, angle)) + tangent * across
                for r, x in profile
                for across, side in ((-width / 2, -1), (width / 2, -1),
                                     (width / 2, 1), (-width / 2, 1))]
    faces = [(i + j, i + (j + 1) % 4, i + (j + 1) % 4 + 4, i + j + 4)
             for i in range(0, len(vertices) - 4, 4) for j in range(4)]
    faces.extend(((3, 2, 1, 0), tuple(range(len(vertices) - 4, len(vertices)))))
    bevel(surface(name, vertices, faces, finish, parent), .012)
    dimple = group(name + " contact point", polar(0, radius, angle), parent)
    axial("Rounded contact dimple",
          ((.001, .038), (.023, .042), (.039, .052), (.046, .068), (.044, .087), (.001, .087)),
          tip_finish, dimple, sides=32)


def shaft_plate(name, bore, half_width, back, front, finish, parent):
    profile = ((bore, back), (bore, front), (half_width, front), (half_width, back))
    face = axial(name, profile, finish, parent, sides=96)
    for vertex in face.data.vertices:
        if vertex.co.xy.length > 1:
            point = vertex.co
            scale = half_width / max(abs(point.x), abs(point.y))
            point.x *= scale
            point.y *= scale
    bevel(face, .018)


def inspection_cap(parts, parent):
    cover = group("Stamped encoder cover", parent=parent)
    shaft_plate("Stamped face around shaft opening", .39, 1.56,
                .553, .63, parts["case_metal"], cover)
    for coordinate in (-1.55, 1.55):
        block("Stamped cover return", (.29, coordinate, -.055), (.62, .10, 3.15),
              parts["case_metal"], cover, edge=.027)
    for y in (-1.57, 1.57):
        for z in (-.98, .96):
            block("Crimp tab", (.13, y, z), (.53, .13, .26),
                  parts["case_metal"], cover, edge=.030)
    return cover


def make_contacts(parts, cam):
    model = group("Sectioned axle-end encoder", (0, -.60, 2.17))
    rotor = group("Coaxial molded rotor", parent=model)
    lathe_solid("Molded insulating rotor", 1.405, -.235, .035, parts["rotor"], rotor, 128)
    axial("Continuous copper common track",
          ((.51, .032), (.695, .032), (.695, .037), (.51, .037)),
          parts["contact_copper"], rotor, sides=128)
    start_angle = CONTACT_ANGLES[0] - BASE_PHASES[0] * PITCH
    profile = ((.68, .032), (1.302, .032), (1.302, .037), (.68, .037))
    for i in range(8):
        start = start_angle + i * PITCH
        disk_arc("Flush plated contact sector", profile, start, start + PITCH / 2,
                 parts["contact_copper"], rotor)
    axial("Molded shaft socket", ((.158, -.36), (.305, -.36), (.305, .160), (.158, .160)),
          parts["carrier"], rotor, sides=64)
    lathe_solid("Hexagonal wheel axle through rotor", .155, -.28, .12,
                parts["axle"], rotor, sides=6)

    stator = group("Fixed molded carrier and terminals", parent=model)
    block("Molded lower carrier", (.07, 0, -1.466), (.93, 3.01, .27),
          parts["carrier"], stator, edge=.047)
    for y in (-1.47, 1.47):
        block("Molded side rail", (-.22, y, -.135), (.45, .19, 2.62),
              parts["carrier"], stator, edge=.046)
    shaft_plate("Molded back with axle clearance", .318, 1.49,
                -.417, -.257, parts["carrier"], stator)
    block("PCB under the encoder", (-.52, -.26, -1.79), (3.90, 3.99, .136),
          parts["board"], stator, edge=.032)
    for y in (-.64, 0, .64):
        pad = cylinder("PCB terminal solder fillet", .132, .071, -1.696,
                       parts["case_metal"], stator, sides=32)
        pad.location.x, pad.location.y = .19, y
        block("Through-hole terminal", (.19, y, -1.580), (.095, .137, .417),
              parts["spring"], stator, edge=.018)
        pipe("PCB trace", ((.19, y, -1.716), (-.37, y, -1.716),
                          (-.62, y * 1.47, -1.716), (-2.14, y * 1.47, -1.716)),
             .014, parts["trace"], stator)

    block("Common contact seat", (.18, -.619, -1.337), (.26, .27, .22),
          parts["carrier"], stator, edge=.029)
    contact_spring("Common phosphor bronze spring", -2.01, .606, 1.47,
                   parts["spring"], parts["contact_copper"], stator)

    status = group("Separate continuity indicators", parent=model)
    cjk = Path("/System/Library/Fonts/STHeiti Medium.ttc")
    font = bpy.data.fonts.load(str(cjk)) if cjk.is_file() else None
    signals = []
    for i, (angle, key) in enumerate(zip(CONTACT_ANGLES, ("orange", "blue"), strict=True)):
        radius = 1.057 if i == 0 else 1.21
        block("Signal contact seat", polar(.145, 1.51, angle), (.25, .31, .18),
              parts["carrier"], stator, edge=.032)
        contact_spring(f"Channel {i + 1} phosphor bronze spring", angle, radius, 1.54,
                       parts["spring"], parts["contact_copper"], stator)
        tab = block("Channel identification lacquer", polar(.223, 1.48, angle), (.014, .10, .074),
                    parts[key], stator, edge=.006)
        tab.rotation_euler.x = angle
        sense = group("Signal reader", (.72, 2.61, .57 - i * .86), status)
        block("Readout backing", (0, 0, 0), (1.05, .53, .065),
              parts["dark"], sense, edge=.044)
        lamp = cylinder("Circuit continuity", .112, .045, .050, parts["dim"], sense,
                        sides=32, edge=.017)
        lamp.location.x = -.285
        text_obj("Channel identifier", ("甲乙" if font else "AB")[i],
                 .32, (.16, 0, .048), parts["white"], sense, font)
        signals.append((sense, lamp, key))

    def state(cycles, show_indicators):
        rotor.rotation_euler.x = -cycles * PITCH
        for part in status.children_recursive:
            part.hide_render = not show_indicators
        for i, (sense, lamp, key) in enumerate(signals):
            connected = (BASE_PHASES[i] + cycles) % 1 < .5
            lamp.data.materials[0] = parts[key + "_signal"] if connected else parts["dim"]
            world_location = model.location + sense.location
            sense.rotation_euler = (cam.location - world_location).to_track_quat("Z", "Y").to_euler()

    return model, state


def pose_outside(cam, parts, shot, duration):
    cover, base = shell(parts["top"], parts["side"], parts["hub"], parts["dark"])
    cover.location.x = base.location.x = -2.60
    disk = wheel(parts)
    disk.location.x = -2.60
    _, scroll = page_window(parts)

    def pose(t):
        if shot == 0:
            phase = (ease(t, .28, .60) + ease(t, 1.06, 1.38)
                     - ease(t, 3.36, 3.70) - ease(t, 4.17, 4.48))
            end = 0
        else:
            phase = (ease(t, .85, 1.18) + ease(t, 2.54, 2.86)
                     - ease(t, 5.55, 5.88) - ease(t, 6.33, 6.66))
            end = ease(t, 8.35, duration)
        camera(cam, (.75 - 1.05 * end, .55, .98), (.80, -3.3, 10), 18.45 - end)
        disk.rotation_euler.x = -phase * DETENT
        scroll(phase)
        return phase, end

    return pose


def pose_teardown(cam, parts, duration):
    cover, _ = shell(parts["top"], parts["side"], parts["hub"], parts["dark"])
    electronics(parts)
    disk = wheel(parts)
    encoder_case(parts)

    def pose(t):
        lift = ease(t, .43, 2.79)
        cover.location = (-4.75 * lift, .40 * lift, 2.75 * lift)
        cover.rotation_euler.y = -.38 * lift
        fit = ease(t, duration * .33, duration * .45) - ease(t, duration * .52, duration * .64)
        disk.location.x = -.45 * fit
        wobble = ease(t, duration * .69, duration * .79) - ease(t, duration * .86, duration * .96)
        disk.rotation_euler.x = -.74 * wobble
        close = ease(t, 2.55, duration * .71)
        camera(cam, (.0, .15 + 1.76 * close, 1.51 + .57 * close),
               (2.7 + 2.6 * close, -5.1, 9.7 - 3.0 * close), 13.35 - 6.00 * close)
        return lift, fit, wobble, close

    return pose


def pace(t, boundaries):
    return sum(.25 * ease(t, start, end) for start, end in boundaries)


def pose_macro(cam, parts, shot, duration):
    parts.update({
        "case_metal": material("Stamped satin nickel steel", (.44, .47, .46), .86, .30, 0),
        "carrier": material("Molded black contact carrier", (.039, .032, .024), .07, .39, 0),
        "rotor": material("Brown molded insulating rotor", (.106, .062, .037), .07, .38, 0),
        "spring": material("Formed phosphor bronze", (.43, .24, .11), .86, .27, 0),
        "contact_copper": material("Thin plated contact tracks", (.71, .36, .124), .87, .27, 0),
    })
    model, state = make_contacts(parts, cam)
    disk = wheel(parts)
    disk.location = (-1.45, -.60, 2.17)
    if shot == 2:
        cover = inspection_cap(parts, model)

    def pose(t):
        if shot == 2:
            pull = ease(t, .40, 1.23)
            move_aside = ease(t, 1.05, 2.95)
            cover.location = (1.45 * pull, -5.80 * move_aside, .50 * move_aside)
            cover.rotation_euler.x = .17 * move_aside
            cycles = .66 * (ease(t, 3.26, 5.93) - ease(t, 7.90, 10.20))
            settle = ease(t, 1.24, 7.42)
            show_indicators = t >= 6.28
            camera(cam, (.0, -.17 + .32 * settle, 2.22),
                   (10, -5.05 + 1.19 * settle, 3.79 - 1.58 * settle), 7.75 - .57 * settle)
            pose_key = cycles, pull, move_aside, settle, show_indicators
        else:
            show_indicators = True
            if shot == 3:
                ranges = ((1.30, 1.94), (3.58, 4.20), (5.37, 6.00), (6.79, 7.43))
                cycles = pace(t, ranges)
            else:
                ranges = ((.25 * duration, .34 * duration), (.42 * duration, .50 * duration),
                          (.64 * duration, .72 * duration), (.75 * duration, .84 * duration))
                cycles = 1 - pace(t, ranges)
            camera(cam, (.0, .15, 2.22), (10, -3.86, 2.21), 7.18)
            pose_key = (cycles,)
        disk.rotation_euler.x = -cycles * PITCH
        state(cycles, show_indicators)
        return pose_key

    return pose


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--timing", type=Path, required=True)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--shot", type=int, choices=range(6), required=True)
    parser.add_argument("--preview", action="store_true")
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
    count = json.loads(args.timing.read_text())[args.shot]
    duration = count / FPS
    scene, cam = setup(args.shot)
    scene.eevee.taa_render_samples = 8 if args.preview else 16
    scene.eevee.shadow_ray_count = 2
    scene.render.resolution_percentage = 38 if args.preview else 100
    parts = palette()
    block("Studio surface", (0, 0, -.24), (150, 150, .45), parts["desk"], edge=0)
    if args.shot in (0, 5):
        pose = pose_outside(cam, parts, args.shot, duration)
    elif args.shot == 1:
        pose = pose_teardown(cam, parts, duration)
    else:
        pose = pose_macro(cam, parts, args.shot, duration)
    folder = args.directory / f"shot-{args.shot}"
    folder.mkdir(parents=True, exist_ok=True)
    step = 5 if args.preview else 1
    rendered = {}
    for frame in range(0, count, step):
        path = folder / f"{frame:05}.jpg"
        key = pose(frame / FPS)
        if path.is_file():
            rendered[key] = path
            continue
        if key in rendered:
            copyfile(rendered[key], path)
            continue
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        rendered[key] = path


if __name__ == "__main__":
    main()
