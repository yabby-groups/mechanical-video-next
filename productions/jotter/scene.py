"""Native Blender geometry and animation for the Jotter episode.

The mechanism is an explanatory reconstruction in arbitrary scene units.
Its longitudinal axis is X, with the writing tip on the negative side.
"""
import argparse
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Vector

FPS = 30
PI = math.pi
LATCH_ANGLE = 2.12
GROOVE_ANGLE = LATCH_ANGLE - PI / 2


def material(name, color, metal=0, roughness=.32):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*color, 1)
    mat.use_nodes = True
    surface = mat.node_tree.nodes.get("Principled BSDF")
    surface.inputs["Base Color"].default_value = (*color, 1)
    surface.inputs["Metallic"].default_value = metal
    surface.inputs["Roughness"].default_value = roughness
    return mat


def mesh(name, vertices, faces, mat, bevel=0):
    data = bpy.data.meshes.new(name)
    data.from_pydata(vertices, [], faces)
    data.update()
    obj = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(obj)
    data.materials.append(mat)
    if bevel:
        edges = obj.modifiers.new("Rounded edges", "BEVEL")
        edges.width = bevel
        edges.segments = 2
        normals = obj.modifiers.new("Weighted normals", "WEIGHTED_NORMAL")
        normals.keep_sharp = True
    return obj


def shell(name, profile, inner, mat, arc=(0, 2 * PI), bevel=.012):
    """Turn a wall profile around X, optionally exposing a longitudinal section."""
    polygon = profile + [(x, r) for (x, _), r in zip(reversed(profile), reversed(inner))]
    divisions = 64
    full = abs(arc[1] - arc[0] - 2 * PI) < 1e-6
    rings = divisions if full else divisions + 1
    width = len(polygon)
    vertices = []
    for i in range(rings):
        angle = arc[0] + (arc[1] - arc[0]) * i / divisions
        vertices.extend((x, r * math.cos(angle), r * math.sin(angle)) for x, r in polygon)
    faces = []
    for i in range(divisions):
        a, b = i * width, ((i + 1) % rings) * width
        faces.extend((a + j, a + (j + 1) % width, b + (j + 1) % width, b + j)
                     for j in range(width))
    if not full:
        faces.extend((tuple(reversed(range(width))), tuple(range((rings - 1) * width, rings * width))))
    obj = mesh(name, vertices, faces, mat, bevel)
    for face in obj.data.polygons[:divisions * width]:
        face.use_smooth = True
    return obj


def rod(name, profile, mat, arc=(0, 2 * PI)):
    return shell(name, profile, [.005] * len(profile), mat, arc, .007)


def box(name, center, size, mat, bevel=.025):
    bpy.ops.mesh.primitive_cube_add(size=1, location=center)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(mat)
    if bevel:
        modifier = obj.modifiers.new("Soft edges", "BEVEL")
        modifier.width = bevel
        modifier.segments = 3
        obj.modifiers.new("Weighted normals", "WEIGHTED_NORMAL")
    return obj


def curve(name, coords, radius, mat):
    data = bpy.data.curves.new(name, "CURVE")
    data.dimensions = "3D"
    data.bevel_depth = radius
    data.bevel_resolution = 2
    line = data.splines.new("POLY")
    line.points.add(len(coords) - 1)
    for point, xyz in zip(line.points, coords):
        point.co = (*xyz, 1)
    obj = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(obj)
    data.materials.append(mat)
    return obj


def spring(name, x, length, radius, turns, wire, mat):
    coords = [(length * i / 192,
               radius * math.cos(2 * PI * turns * i / 192),
               radius * math.sin(2 * PI * turns * i / 192)) for i in range(193)]
    obj = curve(name, coords, wire, mat)
    obj.location.x = x
    return obj


def sector(name, x0, x1, radius, angle, width, mat, bevel=.012, inner=.23):
    return shell(name, [(x0, radius), (x1, radius)], [inner, inner], mat,
                 (angle - width / 2, angle + width / 2), bevel)


def ramp(name, x, angle, radius, mat):
    """Sloped face transitions into the raised landing at the end of a tooth."""
    vertices = []
    for ax, phi in [(x + .17, angle - .34), (x - .18, angle - .34),
                    (x - .18, angle + .34), (x + .17, angle + .10)]:
        vertices.extend([(ax, r * math.cos(phi), r * math.sin(phi)) for r in (.24, radius)])
    return mesh(name, vertices, [(0, 2, 4, 6), (1, 7, 5, 3), (0, 1, 3, 2),
                                 (2, 3, 5, 4), (4, 5, 7, 6), (6, 7, 1, 0)], mat, .015)


def pen(materials, cut=False):
    green, chrome, dark, ivory, orange, blue, ink = materials
    section = (-.50, 1.82) if cut else (0, 2 * PI)
    barrel_profile = [(-6.05, .155), (-5.87, .213), (-5.15, .325),
                      (-3.45, .468), (-.8, .55), (.32, .567)]
    barrel = shell("Green tapered barrel", barrel_profile,
                   [radius - .075 for _, radius in barrel_profile], green, section)
    upper = shell("Brushed cap", [(.33, .566), (2.9, .551), (5.36, .48), (5.53, .445)],
                  [.495, .48, .408, .365], chrome, section)
    collar = shell("Cap seam", [(.26, .566), (.38, .57)], [.49, .49], chrome, section)
    thread_path = [(0.25 + .46 * i / 128, .475 * math.cos(i * PI / 16),
                    .475 * math.sin(i * PI / 16)) for i in range(129)]
    thread = curve("Refill access thread", thread_path, .019, ivory)
    clip = mesh("Jotter arrow clip", [(x, y, z) for z in (.57, .65)
                for x, y in [(5.32, -.11), (5.32, .11), (3.34, .069),
                             (3.33, .17), (2.83, 0), (3.33, -.17), (3.34, -.069)]],
                [(0, 1, 2, 3, 4, 5, 6), (13, 12, 11, 10, 9, 8, 7)]
                + [(i, i+7, (i+1)%7+7, (i+1)%7) for i in range(7)], chrome, .027)
    clip_mount = box("Clip mount", (5.27, 0, .54), (.23, .22, .22), chrome)
    button = rod("Click button", [(5.43, .289), (5.98, .289), (6.05, .264)], chrome)
    refill = rod("Refill tube", [(-4.95, .157), (-4.4, .246), (3.75, .255), (3.91, .19)], dark)
    point = rod("Writing tip", [(-5.98, .034), (-5.93, .062), (-5.48, .127),
                                (-4.85, .148)], chrome)
    front = spring("Tip return spring", -5.53, 1.12, .165, 9, .025, chrome)
    back = spring("Button return spring", 5.02, .49, .32, 5, .021, chrome)
    sleeve = shell("Slotted plunger sleeve", [(4.40, .344), (5.52, .344), (5.55, .365)],
                  [.275, .275, .275], ivory, section)
    plunger_teeth = [sector("Plunger indexing edge", 4.17, 4.43, .344, angle, .57, ivory)
                     for angle in (-.85, -.85 + PI, .72, .72 + PI)]
    cam = rod("Rotating cam body", [(3.76, .241), (4.08, .272), (4.37, .255)], orange)
    teeth = [ramp("Raised cam lug", 4.14, GROOVE_ANGLE + turn, .38, orange)
             for turn in (0, PI)]
    teeth.extend(ramp("Low indexing ramp", 4.14, LATCH_ANGLE + turn, .30, orange)
                 for turn in (0, PI))
    # Opposed fixed stop members interrupt the track at alternating cam positions.
    stops = [sector("Fixed stop and guide flank", 4.04, 5.16, .404, angle, .24, blue, inner=.315)
             for angle in (LATCH_ANGLE, LATCH_ANGLE + PI)]
    stops.extend(sector("Guide slot flank", 4.03, 5.11, .405,
                        GROOVE_ANGLE + turn + edge, .12, blue, inner=.34)
                 for turn in (0, PI) for edge in (-.43, .43))
    return dict(barrel=[barrel], cap=[upper, collar, clip, clip_mount, thread],
                button=[button, sleeve, *plunger_teeth], refill=[refill, point],
                rotor=[cam, *teeth], stops=stops, front=front, back=back)


def move(objects, x=0, y=0, z=0, spin=0):
    for obj in objects:
        obj.location = (x, y, z)
        obj.rotation_euler.x = spin


def lamp(name, position, target, power, size, color):
    data = bpy.data.lights.new(name, "AREA")
    data.energy = power
    data.shape = "DISK"
    data.size = size
    data.color = color
    obj = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(obj)
    obj.location = position
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat("-Z", "Y").to_euler()
    return obj


def setup(shot):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.eevee.taa_render_samples = 8
    if shot in (0, 2, 3, 5):
        scene.eevee.taa_render_samples = 16
        scene.eevee.shadow_ray_count = 8
    scene.render.resolution_x = 1920
    scene.render.resolution_y = 1080
    scene.render.fps = FPS
    scene.view_settings.view_transform = "AgX"
    scene.world = bpy.data.worlds.new("Studio")
    scene.world.use_nodes = True
    scene.world.node_tree.nodes["Background"].inputs[0].default_value = (.14, .19, .20, 1)
    scene.world.node_tree.nodes["Background"].inputs[1].default_value = .36
    studio = material("Warm gray studio", (.21, .25, .23), 0, .72)
    box("Sweep", (0, 0, -.83), (200, 200, .16), studio, 0)
    lamp("Softbox", (-2, -4, 9), (0, 0, 0), 1550, 8, (1, .91, .78))
    lamp("Broad reflection", (3, 4, 6), (1, 0, 0), 2150, 6, (.72, .87, 1))
    lamp("Front fill", (-5, -7, 3), (0, 0, 0), 400, 5, (1, .98, .89))
    obj = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
    bpy.context.collection.objects.link(obj)
    obj.data.type = "ORTHO"
    scene.camera = obj
    return scene, obj


def camera(obj, target, angle, scale, roll=0):
    obj.location = Vector(target) + Vector(angle).normalized() * 19
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat("-Z", "Y").to_euler()
    obj.rotation_euler.rotate_axis("Z", roll)
    obj.data.ortho_scale = scale


def ease(t, start, end):
    value = min(1, max(0, (t - start) / (end - start)))
    return value * value * (3 - 2 * value)


def track(t, keys):
    current = keys[0][1]
    for (start, _), (end, target) in zip(keys, keys[1:]):
        if t < end:
            return current + (target - current) * ease(t, start, end)
        current = target
    return current


def animate_pen(pen_parts, offset, stroke, rotation):
    move(pen_parts["button"], x=-stroke)
    move(pen_parts["refill"], x=-offset)
    move(pen_parts["rotor"], x=-offset, spin=rotation)
    pen_parts["front"].scale.x = 1 - offset / 1.12
    pen_parts["back"].scale.x = 1 - stroke / .79


def cutaway_camera(cam, x, width):
    camera(cam, (x, 0, .01), (.23, -1, .63), width, .12)


def contact_arrow(cam):
    """Draw a camera-facing arrow at the visible end of the stop or groove."""
    # Coordinates are in pixels relative to the projected mechanical target.
    points = [(-91, -80), (-11, -9), (-18, -33), (-11, -9), (-36, -12)]
    paths = [
        curve("Contact arrow outline", [(0, 0, 0)] * len(points), .013,
              material("Contact arrow dark edge", (.018, .038, .05))),
        curve("Contact arrow", [(0, 0, 0)] * len(points), .006,
              material("Contact arrow white", (.92, .97, 1))),
    ]
    for obj in paths:
        mat = obj.data.materials[0]
        shader = mat.node_tree.nodes.new("ShaderNodeEmission")
        shader.inputs["Color"].default_value = mat.diffuse_color
        mat.node_tree.links.new(shader.outputs[0], mat.node_tree.nodes["Material Output"].inputs[0])

    def point_to(angle):
        for obj in paths:
            obj.hide_render = angle is None
        if angle is None:
            return
        target = Vector((4.04, .38 * math.cos(angle), .38 * math.sin(angle)))
        rotation = cam.rotation_euler.to_matrix()
        right, up, toward_cam = rotation.col
        pixel = cam.data.ortho_scale / 1920
        for index, obj in enumerate(paths):
            origin = target + toward_cam * (12 + index * .02)
            for point, (x, y) in zip(obj.data.splines[0].points, points):
                point.co = (*(origin + pixel * (x * right + y * up)), 1)

    return point_to


def scene_pen(scene, cam, shot, mats):
    cut = shot in (2, 3, 5)
    parts = pen(mats, cut)
    if shot == 0:
        section = pen(mats, cut=True)
        solid_objects = [obj for group in parts.values()
                         for obj in (group if isinstance(group, list) else [group])]
        section_objects = [obj for group in section.values()
                           for obj in (group if isinstance(group, list) else [group])]
        point_to = contact_arrow(cam)

        def pose(t):
            offset = track(t, [(0, 0), (.23, 0), (.57, .49), (.87, .27),
                               (2.21, .27), (2.56, .49), (2.76, .49), (3.04, 0)])
            stroke = track(t, [(0, 0), (.23, 0), (.57, .49), (.87, 0),
                               (2.21, 0), (2.56, .49), (2.76, .49), (3.04, 0)])
            rotation = track(t, [(0, 0), (.49, 0), (.59, PI/4), (.68, PI/4), (.87, PI/2),
                                 (2.44, PI/2), (2.58, 3*PI/4), (2.63, 3*PI/4), (2.76, PI)])
            tail_view = 1.4 <= t < 2.76 or t >= 4.1
            for obj in solid_objects:
                obj.hide_render = tail_view
            for obj in section_objects:
                obj.hide_render = not tail_view
            animate_pen(section if tail_view else parts, offset, stroke, rotation)
            if t < .37:
                camera(cam, (-.1, 0, -.08), (.38, -1, .72), 13.3, .09)
            elif tail_view:
                pull_back = ease(t, 5.05, 6.88)
                cutaway_camera(cam, 4.47 * (1 - pull_back), 4.45 + 9.15 * pull_back)
            else:
                cutaway_camera(cam, -5.68, 2.85)
            point_to(LATCH_ANGLE if 1.4 <= t < 2.16 else None)
    elif shot == 1:
        section = pen(mats, cut=True)
        solid_objects = [obj for group in parts.values()
                         for obj in (group if isinstance(group, list) else [group])]
        section_objects = [obj for group in section.values()
                           for obj in (group if isinstance(group, list) else [group])]
        # The open mechanism replaces the exploded assembly on the spoken reveal.
        reveal = 5.93
        cap_parts = [*parts["cap"], *parts["button"], *parts["rotor"], *parts["stops"], parts["back"]]
        cap_origins = [(obj, obj.location.copy()) for obj in cap_parts]

        def pose(t):
            for obj in solid_objects:
                obj.hide_render = t >= reveal
            for obj in section_objects:
                obj.hide_render = t < reveal
            if t >= reveal:
                scene.eevee.taa_render_samples = 16
                scene.eevee.shadow_ray_count = 8
                pull_back = ease(t, 6.45, 8.45)
                cutaway_camera(cam, 2.74 * (1 - pull_back), 8.6 + 4.9 * pull_back)
                return
            unscrew = ease(t, .55, 1.65)
            withdraw = ease(t, 1.65, 3.65)
            arrange = ease(t, 4.52, 5.78)
            barrel_x = -.66 * unscrew - 5.80 * withdraw + 5.20 * arrange
            barrel_y = 1.9 * ease(t, 3.65, 4.52)
            move(parts["barrel"], x=barrel_x, y=barrel_y, spin=unscrew * 2 * PI)
            cap_x = 4.05 * withdraw - 3.15 * arrange
            cap_y = 1.15 * ease(t, 3.65, 4.52)
            for obj, origin in cap_origins:
                obj.location = origin + Vector((cap_x, cap_y, 0))
            spring_slide = ease(t, 3.65, 4.91)
            spring_display = ease(t, 4.91, 5.65)
            parts["front"].location = (-5.53 - 1.66 * spring_slide + 2.4 * spring_display,
                                       -1.08 * spring_display, 0)
            wide = ease(t, 1.65, 3.42) - arrange
            camera(cam, (-1.2 * wide, -.22, 0), (.39, -1, .88), 14.7 + 10.4 * wide, .10)
    elif shot in (2, 3):
        point_to = contact_arrow(cam)
        # The second shot starts at the same locked pose, from the same side.
        if shot == 2:
            offset_keys = [(0, 0), (2.45, 0), (4.65, .38), (6.45, .38),
                           (7.9, .49), (10.03, .49), (11.65, .27)]
            stroke_keys = [(0, 0), (2.45, 0), (4.65, .38), (6.45, .38),
                           (7.9, .49), (10.03, .49), (11.5, 0)]
            spin_keys = [(0, 0), (6.65, 0), (8.0, PI/4), (10.03, PI/4), (10.77, PI/2)]
        else:
            offset_keys = [(0, .27), (.59, .27), (2.5, .49), (7.2, .49), (9.35, 0)]
            stroke_keys = [(0, 0), (.59, 0), (2.5, .49), (7.2, .49), (9.35, 0)]
            spin_keys = [(0, PI/2), (2.27, PI/2), (3.55, 3*PI/4),
                         (3.7, 3*PI/4), (4.75, PI)]
        def pose(t):
            animate_pen(parts, track(t, offset_keys), track(t, stroke_keys), track(t, spin_keys))
            if shot == 2:
                width = track(t, [(0, 13.5), (2, 13.5), (5.6, 4.45),
                                  (12.6, 4.45), (14.4, 13.5)])
                x = track(t, [(0, 0), (2, 0), (5.6, 4.47),
                              (12.6, 4.47), (14.4, 0)])
            else:
                width = track(t, [(0, 13.5), (1.85, 4.45), (6.65, 4.45), (9.15, 13.5)])
                x = track(t, [(0, 0), (1.85, 4.47), (6.65, 4.47), (9.15, 0)])
            cutaway_camera(cam, x, width)
            stop = shot == 2 and 11.48 <= t < 12.98
            groove = shot == 3 and 4.75 <= t < 6.65
            point_to(LATCH_ANGLE if stop else GROOVE_ANGLE + PI if groove else None)
    else:
        point_to = contact_arrow(cam)
        tip_shell = shell("Barrel around writing tip", [(-6.05, .155), (-5.87, .213),
                          (-5.15, .325), (-4, .424)], [.08, .138, .25, .349], mats[0])

        def pose(t):
            offset = track(t, [(0, 0), (.40, 0), (.84, .49), (.96, .49), (1.16, .27),
                               (2.75, .27), (3.22, .49), (4.13, .49), (4.52, 0)])
            stroke = track(t, [(0, 0), (.40, 0), (.84, .49), (.96, .49), (1.16, 0),
                               (2.75, 0), (3.22, .49), (4.13, .49), (4.52, 0)])
            rotation = track(t, [(0, 0), (.76, 0), (.87, PI/4), (.96, PI/4),
                                 (1.13, PI/2), (3.13, PI/2), (3.25, 3*PI/4),
                                 (3.30, 3*PI/4), (3.48, PI)])
            animate_pen(parts, offset, stroke, rotation)
            stop = 1.13 <= t < 1.73
            groove = 3.48 <= t < 4.10
            tip_view = 1.73 <= t < 2.63 or t >= 4.10
            tip_shell.hide_render = not tip_view
            parts["barrel"][0].hide_render = tip_view
            if tip_view:
                cutaway_camera(cam, -5.82, 2.68)
            else:
                cutaway_camera(cam, 4.47, 4.45)
            point_to(LATCH_ANGLE if stop else GROOVE_ANGLE + PI if groove else None)
    return pose


def scene_ball(cam, mats):
    _, chrome, dark, ivory, _, _, ink = mats
    radius = .46
    bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=24, radius=radius)
    ball = bpy.context.object
    ball.name = "Rolling ball"
    ball.data.materials.append(chrome)
    ball.data.materials.append(ink)
    for face in ball.data.polygons:
        face.use_smooth = True
        if sum(ball.data.vertices[i].co.z for i in face.vertices) / len(face.vertices) > .30:
            face.material_index = 1
    # Sectioned socket, rotated into the writing axis.
    section = (-.22, 1.70)
    socket = shell("Sectioned ball seat", [(0.21, .472), (.43, .66), (1.40, .85), (2.25, .88)],
                   [.408, .48, .37, .38], chrome, section)
    feed = rod("Ink in feed bore", [(0.43, .23), (.61, .32), (1.45, .36), (2.23, .37)], ink, section)
    body = shell("Refill section", [(2.24, .88), (3.8, .88)], [.38, .38], ivory, section)
    center = bpy.data.objects.new("Writing tip assembly", None)
    bpy.context.collection.objects.link(center)
    for obj in (socket, feed, body):
        obj.parent = center
        obj.rotation_euler.y = -PI/2
        obj.rotation_euler.x = .2
    paper = material("Uncoated paper", (.61, .66, .60), 0, .8)
    box("Paper edge", (0, -.06, -.53), (13, 7, .13), paper, .022)
    for x in (-5.8, -4.9, -4.0, -3.1, -2.2, -1.3, -.4, .5, 1.4, 2.3, 3.2, 4.1, 5):
        box("Paper ruling", (x, 0, -.463), (.009, 6.4, .003), ivory, 0)
    trace = curve("Ink deposited behind the contact", [(0, 0, -.453), (1, 0, -.453)], .033, ink)
    trace.location.x = -3.1
    def pose(t):
        distance = 6.1 * ease(t, 4.14, 10.38)
        ball.location.x = -3.1 + distance
        ball.rotation_euler.y = distance / radius
        center.location.x = ball.location.x
        trace.scale.x = max(.0001, distance)
        trace.hide_render = distance < .02
        camera(cam, (-3.02 + .74 * distance, 0, .85), (.3, -1, .56),
               5.7 + 4.3 * ease(t, 7.65, 12.9), .08)
    return pose


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--timing", type=Path, required=True)
    parser.add_argument("--directory", type=Path, required=True)
    draft = parser.add_mutually_exclusive_group()
    draft.add_argument("--preview", action="store_true")
    draft.add_argument("--sample-stills", action="store_true")
    parser.add_argument("--shot", type=int, choices=range(6), action="append")
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
    timing = json.loads(args.timing.read_text())
    for shot in args.shot if args.shot is not None else range(6):
        scene, cam = setup(shot)
        materials = (
            material("Jotter forest green", (.026, .23, .116), .15, .26),
            material("Satin steel", (.52, .61, .63), .81, .26),
            material("Refill graphite", (.11, .15, .16), .35),
            material("Ivory plunger", (.78, .71, .50), 0, .37),
            material("Cam amber", (.84, .275, .033), .07, .3),
            material("Cobalt stop members", (.045, .34, .66), .2, .27),
            material("Blue-black ink", (.013, .045, .22), .14, .27),
        )
        pose = scene_ball(cam, materials) if shot == 4 else scene_pen(scene, cam, shot, materials)
        folder = args.directory / f"shot-{shot}"
        folder.mkdir(parents=True, exist_ok=True)
        scene.render.image_settings.file_format = "JPEG"
        scene.render.image_settings.quality = 92
        scene.render.resolution_percentage = 42 if args.preview or args.sample_stills else 100
        sample_times = [(0.1, 0.58, 1.7, 2.6, 3.1, 5.0), (3.95, 5.97, 6.75), (6.15, 8.08, 11.7, 15.3),
                        (3.85, 5.6, 9.6), (2.2, 7.7, 12.35), (1.35, 2.2, 3.8, 4.6)]
        frames = range(0, timing[shot], 5 if args.preview else 1)
        if args.sample_stills:
            frames = [round(FPS * t) for t in sample_times[shot]]
        for frame in frames:
            path = folder / f"{frame:05}.jpg"
            if path.exists():
                continue
            pose(frame / FPS)
            scene.render.filepath = str(path)
            bpy.ops.render.render(write_still=True)


if __name__ == "__main__":
    main()
