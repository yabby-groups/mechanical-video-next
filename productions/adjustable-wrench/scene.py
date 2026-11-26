"""Original Blender cutaway of a conventional single-start adjustable wrench."""
import argparse
from importlib.util import module_from_spec, spec_from_file_location
import json
import math
import os
from pathlib import Path
import sys

import bpy
from mathutils import Quaternion, Vector

spec = spec_from_file_location(
    "episode_studio", Path(__file__).resolve().parents[1] / "quarter-turn-faucet" / "scene.py"
)
studio = module_from_spec(spec)
spec.loader.exec_module(studio)

PITCH = .31
WORM_Y = -.72
WORM_RADIUS = .445
NUT_Y = .92
NUT_RADIUS = .87
TAU = math.tau
DRAFT_STEP = 5


def prism(name, outline, depth, finish, parent=None, *, edge=.045):
    count = len(outline)
    vertices = [(x, y, z) for z in (-depth / 2, depth / 2) for x, y in outline]
    faces = [tuple(reversed(range(count))), tuple(range(count, 2 * count))]
    faces.extend((i, (i + 1) % count, (i + 1) % count + count, i + count) for i in range(count))
    return studio.bevel(studio.surface(name, vertices, faces, finish, parent), edge)


def cut_hole(body, cutter):
    boolean = body.modifiers.new("Machined through opening", "BOOLEAN")
    boolean.object = cutter
    boolean.operation = "DIFFERENCE"
    bpy.context.view_layer.objects.active = body
    bpy.ops.object.modifier_apply(modifier=boolean.name)
    bpy.data.objects.remove(cutter, do_unlink=True)


def finish(name, color, metal, roughness, grain):
    result = studio.material(name, color, metal, roughness)
    nodes, links = result.node_tree.nodes, result.node_tree.links
    bsdf = nodes.get("Principled BSDF")
    coord = nodes.new("ShaderNodeTexCoord")
    stretch = nodes.new("ShaderNodeVectorMath")
    stretch.operation = "MULTIPLY"
    stretch.inputs[1].default_value = grain
    links.new(coord.outputs["Object"], stretch.inputs[0])
    noise = nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 27
    noise.inputs["Detail"].default_value = 2
    links.new(stretch.outputs["Vector"], noise.inputs["Vector"])
    rough = nodes.new("ShaderNodeMapRange")
    rough.inputs["To Min"].default_value = roughness * .72
    rough.inputs["To Max"].default_value = roughness * 1.25
    links.new(noise.outputs["Fac"], rough.inputs[0])
    links.new(rough.outputs["Result"], bsdf.inputs["Roughness"])
    bump = nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = .19
    bump.inputs["Distance"].default_value = .005
    links.new(noise.outputs["Fac"], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    return result


def finishes():
    return {
        "forged": finish("Satin nickel finish on forged steel", (.35, .43, .49), .79, .35, (1.3, .26, 2.5)),
        "jaw": finish("Ground steel jaws", (.51, .56, .59), .82, .32, (.32, 2.1, 2.7)),
        "worm": finish("Dark machined adjustment worm", (.20, .21, .22), .74, .34, (.24, 1.5, 1.8)),
        "pin": studio.material("Steel worm pin", (.47, .51, .53), .78, .30),
        "nut": finish("Zinc plated hex nut", (.33, .34, .32), .65, .43, (1, 1, 1.7)),
        "stage": finish("Matte petrol blue work surface", (.021, .067, .086), .12, .60, (1, 1, 1)),
        "amber": studio.material("Contact and moving index", (1, .39, .05), .11, .37, .60),
        "cyan": studio.material("Fixed guide markers", (.12, .68, .84), .12, .35, .48),
    }


def forged_body(root, parts):
    fixed_face = -NUT_RADIUS * math.cos(math.pi / 6)
    outline = [
        (-.38, -6.25), (.38, -6.25), (.63, -6.03), (.65, -5.72), (.55, -3.20),
        (.63, -2.35), (.96, -1.74), (1.34, -1.34), (1.52, -1.00), (1.53, -.54),
        (1.44, -.30), (-.63, -.30), (-.68, .10), (fixed_face, .34), (fixed_face, 1.39),
        (-1.04, 1.50), (-1.43, 1.28), (-1.74, .75), (-1.79, .11), (-1.58, -.78),
        (-1.29, -1.31), (-.84, -1.96), (-.57, -2.57), (-.56, -3.30), (-.63, -5.74),
        (-.61, -6.03),
    ]
    body = prism("One-piece forged head and handle", outline, .59, parts["forged"], root, edge=0)
    window = studio.block("Through window cutter", (0, WORM_Y, 0), (2.08, .96, 1.6), None, edge=0)
    cut_hole(body, window)
    hole = studio.cylinder("Hanging hole cutter", .215, 1.8, 0, None, edge=0)
    hole.location.y = -5.78
    cut_hole(body, hole)
    studio.bevel(body, .053)
    spine = studio.block("Lower edge of the jaw guide", (0, -.115, -.35),
                         (2.6, .39, .21), parts["forged"], root, edge=.052)
    return body, spine


def worm_mesh(root, parts):
    half_width, sections, around = .88, 115, 80
    vertices = []
    for i in range(sections + 1):
        x = -half_width + 2 * half_width * i / sections
        for j in range(around):
            a = TAU * j / around
            phase = abs((x / PITCH - a / TAU + .5) % 1 - .5)
            crown = min(1, max(0, (.33 - phase) / .21))
            end = min(1, (half_width - abs(x)) / .065)
            radius = .295 + (WORM_RADIUS - .295) * crown * end
            vertices.append((x, radius * math.cos(a), radius * math.sin(a)))
    faces = [
        (i * around + j, i * around + (j+1) % around,
         (i+1) * around + (j+1) % around, (i+1) * around + j)
        for i in range(sections) for j in range(around)
    ]
    faces.extend([tuple(reversed(range(around))), tuple(range(sections * around, len(vertices)))])
    return studio.surface("Single-start helical adjustment worm", vertices, faces, parts["worm"], root, True)


def assembly(parts):
    root = studio.group("Adjustable wrench")
    body, guide = forged_body(root, parts)
    moving = studio.group("Sliding jaw and rack", parent=root)
    xface = NUT_RADIUS * math.cos(math.pi/6)
    outline = [(xface-.01, .33), (xface, .48), (xface, 1.39), (1.01, 1.50),
               (1.31, 1.42), (1.61, .91), (1.72, .34), (1.66, .05),
               (1.45, -.117), (-.94, -.117), (-.98, .04)]
    prism("Ground sliding jaw and rack back", outline, .43, parts["jaw"], moving)
    for i in range(-3, 5):
        x = (i + .5) * PITCH
        prism("Rack tooth", [(x-.113, -.105), (x-.056, -.373), (x+.056, -.373),
                            (x+.113, -.105)], .32, parts["jaw"], moving, edge=.012)
    worm = studio.group("Worm rotates about its retained pin", (0, WORM_Y, 0), root)
    worm_mesh(worm, parts)
    pin = studio.cylinder("Retaining pin", .107, 2.38, 0, parts["pin"], root, edge=.02)
    pin.location.y = WORM_Y
    pin.rotation_euler.y = math.pi / 2
    return root, body, guide, moving, worm, pin


def hex_nut(parts, position, radius=NUT_RADIUS):
    root = studio.group("Hex nut", position)
    half = math.pi / 6
    profile = ((.43, -.272), (radius-.17, -.272), (radius, -.172),
               (radius, .172), (radius-.17, .272), (.43, .272), (.43, -.272))
    obj = studio.ring("Chamfered six-flat nut", profile, parts["nut"], root, start=half,
                      end=half + TAU, sides=6)
    studio.bevel(obj, .018)
    # These shallow grooves are a representative rendering of the internal thread.
    points = [(radius * math.cos(a), radius * math.sin(a), -.24 + .48 * i / 383)
              for i in range(384) for a in (TAU * 4 * i / 383,) for radius in (.436,)]
    studio.pipe("Internal thread detail", points, .023, parts["pin"], root)
    return root


def arrow(name, start, end, mat, root):
    a, b = Vector(start), Vector(end)
    direction = (b - a).normalized()
    side = direction.cross(Vector((0, 0, 1)))
    foot = b - direction * .16
    return [studio.pipe(name, (a, foot), .025, mat, root),
            studio.pipe(name + " tip", (foot + side*.075, b, foot - side*.075), .025, mat, root)]


def show(objects, visible):
    for obj in objects:
        obj.hide_render = not visible


def motion(cam, parts, shot, duration):
    root, body, guide, moving, worm, pin = assembly(parts)
    gap = studio.ease
    xface = NUT_RADIUS * math.cos(math.pi / 6)
    use_nut = shot in (3, 4, 5, 6)
    nut = hex_nut(parts, (0, NUT_Y, 0)) if use_nut else None
    larger_nut = None
    if shot == 5:
        larger_radius = NUT_RADIUS + PITCH / (2 * math.cos(math.pi / 6))
        larger_nut = hex_nut(parts, (0, NUT_Y, 0), larger_radius)

    # Witnesses sit just above the contact plane so they remain visible in a shallow view.
    contact = studio.bead("Worm–rack witness", (0, WORM_Y + WORM_RADIUS, .23), .070, parts["amber"], root)
    stripe = studio.pipe("Paint witness on one helical crest", [
        (PITCH * angle / TAU, .449 * math.cos(angle), .449 * math.sin(angle))
        for angle in (.94, 1.13, 1.32, 1.51, 1.70, 1.89, 2.08)
    ], .024, parts["amber"], worm)
    witness = studio.block("Index on the active rack", (-.45, .046, .231), (.052, .17, .032),
                           parts["amber"], moving, edge=.008)
    scale = [studio.block("Fixed pitch witness", (-.45 + i * PITCH, .27, -.231),
                          (.032, .105, .029), parts["cyan"], root, edge=.005) for i in range(5)]
    forces = arrow("Force from fixed face", (-xface-.48, NUT_Y-.31, .35),
                   (-xface+.10, NUT_Y-.31, .35), parts["amber"], root)
    forces += arrow("Force from movable face", (xface+.48, NUT_Y+.31, .35),
                    (xface-.10, NUT_Y+.31, .35), parts["amber"], root)
    show(forces, False)
    show([stripe], shot == 0)
    show([contact, witness, *scale], shot in (0, 2))
    if shot != 2:
        contact.hide_render = True

    def pose(t):
        f = t / duration
        travel = 0
        if shot == 0:
            travel = PITCH * gap(t, .18, 1.48)
            reveal = gap(t, 4.0, 6.9)
            studio.camera(cam, (.22, -.32-.82*reveal, .04), (1.0, -2.5, 8.0), 4.75+1.52*reveal)
        elif shot == 1:
            reveal = gap(f, .10, .31)*(1-gap(f, .78, .96))
            moving.location.y = .44 * reveal
            moving.location.z = 1.08 * reveal
            worm.location.y = WORM_Y - .64 * reveal
            worm.location.z = .62 * reveal
            pin.location.y = worm.location.y
            pin.location.z = worm.location.z
            pin.location.x = -1.45 * gap(f, .37, .51)*(1-gap(f, .65, .79))
            studio.camera(cam, (.04, -.36, .20), (2.1, -4.1, 8.2), 5.62)
        elif shot == 2:
            # One turn moves one rack pitch on a single-start thread.
            travel = PITCH * (gap(f, .19, .38)*.5 + gap(f, .46, .64)*.5 - gap(f, .83, .96))
            contact.location.x = travel
            studio.camera(cam, (.12+travel*.40, -.27, -.02), (.7, -1.3, 8.5), 3.50)
        elif shot == 3:
            travel = .38*(1-gap(f, .16, .40))
            nut.location.y = NUT_Y + .9 * (1-gap(f, .03, .18))
            low = gap(f, .60, .92)
            studio.camera(cam, (.17, .60, .02), (.50-2.35*low, -2.26-2.51*low, 8.6-3.05*low), 4.19)
        elif shot == 4:
            travel = .155
            play = gap(f, .11, .35)
            root.rotation_euler.z = math.radians(12) * play
            # Shift the wrench center around the nut as the clearance moves to the corners.
            root.location.x = NUT_Y * math.sin(root.rotation_euler.z) - travel*.5*play
            root.location.y = NUT_Y * (1-math.cos(root.rotation_euler.z))
            studio.camera(cam, (.17, .60, .02), (-1.85, -4.77, 5.55), 4.19)
        elif shot == 5:
            turn = gap(f, .08, .29)
            angle = math.radians(23)*turn
            root.rotation_euler.z = nut.rotation_euler.z = angle
            root.location.x = NUT_Y * math.sin(angle)
            root.location.y = NUT_Y * (1-math.cos(angle))
            show(forces, .09 < f < .34)
            if f < .36:
                # Keep the handle and both contact forces inside the frame.
                studio.camera(cam, (.14, -1.55, .02), (1.1, -2.85, 8.3), 9.4)
                rotation = cam.rotation_euler.to_quaternion() @ Quaternion((0, 0, 1), math.radians(-97))
                cam.rotation_euler = rotation.to_euler()
                cam.location += rotation @ Vector((.27, .21, 0))
            else:
                studio.camera(cam, (.12, -.06, .02), (1.1, -2.85, 8.3), 6.35)
            travel = PITCH * gap(f, .73, .86)
            # Move each nut along the open end of the jaws at its own clearance.
            outward = Vector((-math.sin(angle), math.cos(angle), 0))
            across = Vector((math.cos(angle), math.sin(angle), 0))
            seat = Vector((0, NUT_Y, 0))
            nut.location = seat + outward * (3.4 * gap(f, .68, .80))
            larger_nut.location = seat + across * (PITCH / 2) + outward * (
                3.4 * (1-gap(f, .86, .98))
            )
            larger_nut.rotation_euler.z = angle
            show(nut.children, f < .80)
            show(larger_nut.children, f >= .86)
        else:
            travel = .25 * (1-gap(f, .32, .59))
            angle = -.27 * gap(f, .69, .91)
            root.rotation_euler.z = nut.rotation_euler.z = angle
            root.location.x = NUT_Y * math.sin(angle)
            root.location.y = NUT_Y * (1-math.cos(angle))
            zoom = gap(f, .28, .75)
            studio.camera(cam, (.34, -.45-1.00*zoom, .0), (1.1, -2.5, 8.6), 4.48+2.44*zoom)
        moving.location.x = travel
        worm.rotation_euler.x = -TAU * travel / PITCH
        return (tuple(cam.location), tuple(cam.rotation_euler), cam.data.ortho_scale,
                tuple(root.location), root.rotation_euler.z, tuple(moving.location), tuple(worm.location),
                pin.location.x, tuple(nut.location) if nut else None,
                tuple(larger_nut.location) if larger_nut else None, forces[0].hide_render)

    return pose


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--timing", type=Path, required=True)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--shot", type=int, required=True)
    parser.add_argument("--preview", action="store_true")
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
    frames = json.loads(args.timing.read_text())[args.shot]
    scene, cam = studio.setup(args.shot)
    scene.eevee.taa_render_samples = 4 if args.preview else 16
    scene.eevee.shadow_ray_count = 2
    scene.render.resolution_percentage = 25 if args.preview else 100
    scene.render.image_settings.quality = 89
    window = bpy.data.lights["Window"]
    window.shape, window.size, window.size_y = "RECTANGLE", 3.8, 8.0
    window.energy = 1550
    rim = bpy.data.lights["Rim strip"]
    rim.shape, rim.size, rim.size_y = "RECTANGLE", 1.65, 6.6
    rim.energy = 2000
    bpy.data.lights["Front fill"].energy = 430
    parts = finishes()
    studio.block("Studio surface", (0, 0, -2.12), (85, 85, 2), parts["stage"], edge=0)
    pose = motion(cam, parts, args.shot, frames / 30)
    directory = args.directory / f"shot-{args.shot}"
    directory.mkdir(parents=True, exist_ok=True)
    previous_pose = previous_frame = None
    for frame in range(0, frames, DRAFT_STEP if args.preview else 1):
        destination = directory / f"{frame:05}.jpg"
        scene.frame_set(frame)
        current_pose = pose(frame / 30)
        if not destination.is_file():
            if current_pose == previous_pose:
                os.link(previous_frame, destination)
            else:
                scene.render.filepath = str(destination)
                bpy.ops.render.render(write_still=True)
        previous_pose, previous_frame = current_pose, destination


if __name__ == "__main__":
    main()
