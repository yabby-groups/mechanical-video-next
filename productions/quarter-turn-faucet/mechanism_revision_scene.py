"""Blender shots for the faucet's installation, water route and final replay."""

import argparse
import math
from pathlib import Path
import sys

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scene import (
    FPS, HOT_X, PORT_HALF, TAU, TRAVEL, basin, bead, bevel, block, camera,
    cylinder, ease, exterior_water, finishes, group, lever, material, overlap,
    pipe, plate_set, ring, setup, show_tree, spout, stem, surface, wet_ports,
)

CARTRIDGE_SCALE = .31
INSTALLED_Z = -.025
HEX_RADIUS = 1.22
TRIM_BORE = .393
THREAD_ROOT = 1.04
THREAD_CREST = 1.105
THREAD_PITCH = .073
THREAD_START = 1.24
THREAD_TURNS = 4.5
MOUNT_LIP_Z = .45
MOUNT_THREAD_ROOT = .349
MOUNT_THREAD_CREST = .331
LOWER_DROP = .54
STILL_INTERVALS = {
    "extract": ((0, 6), (274, 288)),
    "plates": ((0, 61), (116, 193), (260, 318)),
    "flow": ((0, 4), (55, 145)),
    "turn": ((133, 137),),
    "replay-exterior": ((123, 239),),
    "replay-ports": ((0, 42), (103, 239)),
}


def bathroom(f):
    basin(f)
    block("Tiled backsplash", (0, 2, 2.8), (28, .2, 7), f["wall"], edge=0)
    for i in range(-5, 6):
        block("Vertical grout", (i * 2, 1.895, 2.5), (.024, .014, 5), f["dark"], edge=0)
    for i in range(1, 4):
        block("Horizontal grout", (0, 1.893, i * 1.35), (25, .014, .023), f["dark"], edge=0)
    spout(f)
    cold = group("Cold lever stays installed", (-HOT_X, 0, .82))
    cold.rotation_euler.z = math.pi
    lever("Cold", cold, f["chrome"], f["fixed"])
    trim(f, group("Cold trim", (-HOT_X, 0, 0)))


def trim(f, parent):
    ring("Hollow handle escutcheon", (
        (.445, .025), (.73, .025), (.71, .14), (.53, .23), (.448, .34),
        (.426, .63), (TRIM_BORE, .63), (TRIM_BORE, .48), (.414, .34), (.445, .24),
    ), f["chrome"], parent)


def hot_handle(f, parent):
    # Same lever silhouette, with a real blind socket open from the underside.
    bevel(ring("Handle hub with splined socket", (
        (.116, -.17), (.36, -.17), (.36, .23), (.116, .23),
    ), f["chrome"], parent), .014)
    ring("Domed handle top", ((0, .23), (.31, .23), (.33, .25), (.28, .31), (0, .33)),
         f["chrome"], parent)
    pipe("Lever grip", [(-.13, 0, .15), (-.51, 0, .19), (-1.08, 0, .25), (-1.37, 0, .26)],
         .13, f["chrome"], parent, bezier=True)
    bead("Rounded grip end", (-1.37, 0, .26), .13, f["chrome"], parent)
    cylinder("Hot-side index", .104, .022, .338, f["hot"], parent, edge=.008)


def housing(f, parent, *, section):
    # Split the sidewall at the outlet. The opening is bounded by brass above,
    # below and on both sides. Section views retain the back half of the bore.
    end = math.pi if section else TAU
    limits = {"start": 0, "end": end}
    ring("Lower brass body", ((.965, .50), (1.055, .50), (1.055, .94), (.965, .94)),
         f["brass"], parent, **limits)
    aperture = math.radians(19)
    ring("Brass wall around the side outlet",
         ((.965, .94), (1.055, .94), (1.055, 1.20), (.965, 1.20)),
         f["brass"], parent, start=aperture, end=end if section else end - aperture)
    ring("Upper brass body", ((.765, 1.20), (1.055, 1.20), (1.04, 1.57),
         (.86, 1.80), (.77, 2.18), (.345, 2.18), (.345, 1.80), (.75, 1.57)),
         f["brass"], parent, **limits)
    ring("Brass hex wrench flats", ((.75, 1.70), (1.18, 1.70), (HEX_RADIUS, 1.76),
         (HEX_RADIUS, 2.03), (1.14, 2.12), (.75, 2.12)), f["brass"], parent,
         sides=3 if section else 6, **limits)

    mounting_thread(f, parent, section=section)

    if section:
        for side in (-1, 1):
            block("Face of axial locating groove", (side * .151, -.96, .57),
                  (.105, .19, .26), f["cut"], parent, edge=.012)
        for start, end in ((-math.pi, math.radians(-96)), (math.radians(-84), 0)):
            ring("Lower collar around locating groove",
                 ((.95, .48), (1.055, .48), (1.055, .557), (.95, .557)),
                 f["brass"], parent, start=start, end=end)
    else:
        for center in (-math.pi / 2, math.pi / 2):
            for offset in (-.145, .145):
                block("Fixed plate slot cheek", (offset, math.sin(center) * .96, .57),
                      (.085, .15, .25), f["brass"], parent, edge=.009)


def mounting_thread(f, parent, *, section):
    # One helical crest makes the screw-out movement legible.
    vertices = []
    steps = round(THREAD_TURNS * 48)
    for i in range(steps + 1):
        angle = i * TAU / 48
        z = THREAD_START + angle * THREAD_PITCH / TAU
        vertices.extend((r * math.cos(angle), r * math.sin(angle), z + h)
                        for r, h in ((THREAD_ROOT, 0), (THREAD_CREST, .016),
                                     (THREAD_CREST, .038), (THREAD_ROOT, .054)))
    faces = []
    for i in range(steps):
        if section and i % 48 >= 24:
            continue
        for j in range(4):
            faces.append((4 * i + j, 4 * (i + 1) + j, 4 * (i + 1) + (j + 1) % 4, 4 * i + (j + 1) % 4))
    surface("Helical mounting thread", vertices, faces, f["brass"], parent)

def ceramic_assembly(f, root, *, section):
    housing(f, root, section=section)
    fixed, moving = plate_set(f, root)
    driver = group("Stem and moving ceramic rotate together", parent=root)
    stem(f, driver)
    for side in (-1, 1):
        for shoulder in (-1, 1):
            block("Ceramic shoulder engaging driver lug", (side * .756, shoulder * .155, 1.02),
                  (.26, .085, .30), f["moving"], moving, edge=.012)
    limits = {"start": 0, "end": math.pi} if section else {}
    ring("Open inlet seal below the ceramic pair", (
        (.70, .34), (.97, .34), (1.02, .42), (.99, .50), (.70, .50),
    ), f["dark"], fixed, **limits)
    return fixed, moving, driver


def threaded_mount(f, parent):
    # The brass bore has a right-hand thread whose teeth sit in the gaps
    # between the cartridge teeth. Both helices use the same pitch.
    bevel(ring("Valve body with a lead-in chamfer", (
        (.347, -.10), (.42, -.10), (.42, .24), (.397, .38), (.39, MOUNT_LIP_Z),
        (.357, MOUNT_LIP_Z), (.347, .435),
    ), f["cut"], parent), .004)
    ring("Valve seat below the mounting thread", (
        (.214, .036), (.348, .036), (.348, .080), (.214, .080),
    ), f["cut"], parent)
    pitch = THREAD_PITCH * CARTRIDGE_SCALE
    phase_z = INSTALLED_Z + (THREAD_START + .027 + THREAD_PITCH / 2) * CARTRIDGE_SCALE
    profile = ((MOUNT_THREAD_ROOT, -.0040), (MOUNT_THREAD_CREST, -.0018),
               (MOUNT_THREAD_CREST, .0018), (MOUNT_THREAD_ROOT, .0040))
    vertices, faces = [], []
    for step in range(-48, 4 * 48 + 1):
        turn = step / 48
        angle = turn * TAU
        z = phase_z + turn * pitch
        if not .355 <= z <= .432:
            continue
        depth = min(1, (z - .355) / .009, (.432 - z) / .009)
        for radius, height in profile:
            radius = MOUNT_THREAD_ROOT - depth * (MOUNT_THREAD_ROOT - radius)
            vertices.append((radius * math.cos(angle), radius * math.sin(angle), z + height))
    for first in range(0, len(vertices) - 4, 4):
        for corner in range(4):
            following = (corner + 1) % 4
            faces.append((first + corner, first + following, first + following + 4, first + corner + 4))
    faces.extend([(3, 2, 1, 0), tuple(range(len(vertices) - 4, len(vertices)))])
    surface("Matching female mounting thread", vertices, faces, f["cut"], parent)


def open_end_wrench(f, parent):
    # In this orientation a pair of opposite hex flats is parallel to X.
    jaw = HEX_RADIUS * CARTRIDGE_SCALE * math.cos(math.pi / 6) + .003
    outline = (
        (-1.33, -.083), (-.51, -.083), (-.43, -.30), (-.31, -.422),
        (.23, -.422), (.27, -jaw), (-.394, -jaw), (-.394, jaw),
        (.27, jaw), (.23, .422), (-.31, .422), (-.43, .30),
        (-.51, .083), (-1.33, .083),
    )
    count = len(outline)
    vertices = [(x, y, z) for z in (-.033, .033) for x, y in outline]
    faces = [tuple(reversed(range(count))), tuple(range(count, 2 * count))]
    faces.extend((i, (i + 1) % count, (i + 1) % count + count, i + count) for i in range(count))
    bevel(surface("Open-end wrench on the cartridge hex", vertices, faces, f["chrome"], parent), .014)


def extraction(cam, f, *, cartridge_builder=ceramic_assembly, lifted_rotation=0):
    assert TRIM_BORE > HEX_RADIUS * CARTRIDGE_SCALE
    assert MOUNT_THREAD_CREST > 1.055 * CARTRIDGE_SCALE
    pitch = THREAD_PITCH * CARTRIDGE_SCALE
    assert INSTALLED_Z + THREAD_START * CARTRIDGE_SCALE + THREAD_TURNS * pitch > MOUNT_LIP_Z
    bathroom(f)
    collar = group("Hot trim", (HOT_X, 0, 0))
    trim(f, collar)
    mount = group("Permanent hot-side valve body", (HOT_X, 0, 0))
    threaded_mount(f, mount)

    handle = group("Hot handle", (HOT_X, 0, .82))
    hot_handle(f, handle)
    cartridge = group("Complete threaded ceramic cartridge", (HOT_X, 0, INSTALLED_Z))
    cartridge.scale = (CARTRIDGE_SCALE,) * 3
    _, moving, driver = cartridge_builder(f, cartridge, section=False)
    moving.rotation_euler.z = driver.rotation_euler.z = -TRAVEL
    wrench_pivot = group("Wrench axis follows the threaded cartridge")
    wrench = group("Wrench enters and leaves radially", parent=wrench_pivot)
    open_end_wrench(f, wrench)

    def pose(t):
        lift_handle = ease(t, .70, 1.72)
        offset_handle = ease(t, 1.74, 2.64)
        lift_trim = ease(t, 2.68, 4.00)
        offset_trim = ease(t, 4.02, 4.82)
        loosen = ease(t, 5.24, 5.84) / 6
        turn = loosen + (THREAD_TURNS - 1 / 6) * ease(t, 6.06, 8.17)
        clear = ease(t, 8.26, 9.13)
        handle.location = (HOT_X - 1.18 * offset_handle, .21 * offset_handle, .82 + .77 * lift_handle)
        collar.location = (HOT_X + .84 * offset_trim, .72 * offset_trim,
                           1.05 * lift_trim - .98 * ease(t, 4.70, 5.22))
        cartridge.location.z = INSTALLED_Z + pitch * turn + .71 * clear
        cartridge.rotation_euler.z = TAU * turn + lifted_rotation * ease(t, 8.63, 9.13)
        wrench_pivot.location = (HOT_X, 0, INSTALLED_Z + pitch * loosen + 1.92 * CARTRIDGE_SCALE)
        wrench_pivot.rotation_euler.z = TAU * loosen
        tool_visible = 4.62 <= t < 6.33
        show_tree(wrench, tool_visible)
        wrench.location.x = -3.6 * (1 - ease(t, 4.62, 5.22)) - 3.6 * ease(t, 5.86, 6.33)

        wide = ease(t, .2, 4.60)
        close = ease(t, 4.65, 6.48)
        camera(cam, (-.47 - 1.33 * wide - .25 * close, -.14,
                     .97 - .31 * close + .31 * clear),
               (3.93 - 2.28 * wide, -9.9, 4.84 + 1.62 * ease(t, 8.20, 9.13)),
               8.35 - 3.56 * wide - 1.89 * close + .26 * clear)
    return pose


def chamber(f, root):
    seat = group("Inlet seat supports the seal below the fixed ceramic", parent=root)
    ring("Section through the inlet seat", ((.72, -.36), (.988, -.36), (.988, .34), (.72, .34)),
         f["brass"], seat, start=0, end=math.pi)
    water = material("Water traveling through the ports", (.006, .31, .67), 0, .24, .42)
    left_inlet = pipe("Continuous water inside the inlet", [(-.55, 0, -.385), (-.55, 0, .55)],
                      .077, water, root)
    right_inlet = pipe("Continuous water inside the inlet", [(.55, 0, -.385), (.55, 0, .55)],
                       .077, water, root)
    path = [(.55, 0, .81), (.57, 0, 1.047), (.67, 0, 1.08),
            (.89, 0, 1.08), (1.115, 0, 1.08), (1.52, 0, 1.08)]
    exit_stream = pipe("Water leaving through the machined side port", path, .062,
                       water, root, bezier=True)
    merge = pipe("Water from the other port enters the same outlet chamber",
                 [(-.55, 0, .81), (-.55, .03, .96), (-.42, .31, 1.05),
                  (0, .37, 1.08), (.40, .24, 1.08), (.67, 0, 1.08)],
                 .055, water, root, bezier=True)
    channel = group("Radial spout channel", (0, 0, 1.08), root)
    channel.rotation_euler.y = math.pi / 2
    ring("Cutaway of the spout feed channel", ((.077, 1.04), (.128, 1.04), (.128, 1.52), (.077, 1.52)),
         f["brass"], channel, start=0, end=math.pi)
    markers = [bead("Direction of flow", (0, 0, 0), .028, f["spark"], root) for _ in range(5)]

    def flow(t, drop):
        seat.location.z = -LOWER_DROP * drop
        left_inlet.hide_render = right_inlet.hide_render = t < 5.37
        exit_stream.hide_render = merge.hide_render = t < 7.95
        for i, marker in enumerate(markers):
            phase = (t * .68 + i / len(markers)) % 1
            marker.hide_render = t < 5.37 or (phase > .55 and t < 7.95)
            if phase < .55:
                marker.location = (.55, -.041, -.34 + 1.23 * phase / .55)
            else:
                x = (phase - .55) / .45
                marker.location = (.55 + .96 * x, -.035, .89 + .19 * ease(x, 0, .24))
    return flow


def inner(cam, f, view):
    block("Studio floor", (0, 0, -1.03), (60, 60, .12), f["wall"], edge=0)
    root = group("One cartridge on the inspection axis")
    fixed, moving, driver = ceramic_assembly(f, root, section=True)
    water = wet_ports(f, root)
    grip = group("Lever fitted onto the same stem", (0, 0, 2.72), driver)
    hot_handle(f, grip)
    grip.rotation_euler.z = TRAVEL
    # Use a compact lever depiction in the cutaway, framing the spline and the actuator.
    grip.scale = (1.75, 1.75, 1.5)
    show_tree(grip, view == "turn")
    channel = group("Inlet seat and spout feed", parent=root)
    chamber_pose = chamber(f, channel)

    def pose(t):
        if view == "plates":
            closed = 1 - ease(t, 2.06, 3.85)
            drop = ease(t, 6.45, 8.64)
            camera(cam, (.10, 0, 1.33 - .20 * drop), (1.36 - .45 * drop, -8, 3.82 + 1.79 * drop),
                   5.04 + .45 * drop)
            wet_angle = TRAVEL
            chamber_pose(0, drop)
        elif view == "flow":
            closed = 0
            drop = 1 - ease(t, .15, 1.82)
            follow = ease(t, 4.86, 8.1)
            camera(cam, (.10 + .23 * follow, 0, 1.33 - .20 * drop - .54 * follow),
                   (1.36 - .45 * drop, -8, 3.82 + 1.79 * drop - 2.0 * follow), 5.04 + .45 * drop - .64 * follow)
            wet_angle = 0 if t >= 5.72 else TRAVEL
            chamber_pose(t, drop)
        else:
            closed = ease(t, .23, 4.42)
            drop = 0
            dive = t >= 1.3
            show_tree(channel, not dive)
            if not dive:
                chamber_pose(t + 8, drop)
            for obj in root.children:
                if obj.name.startswith(("Lower brass", "Upper brass", "Brass ", "Helical",
                                        "Face of", "Lower collar")):
                    obj.hide_render = dive
            for obj in driver.children_recursive:
                obj.hide_render = dive
            for obj in moving.children:
                if obj.name.startswith("Ceramic shoulder"):
                    obj.hide_render = dive
            for obj in fixed.children:
                if obj.name.startswith("Open inlet seal"):
                    obj.hide_render = dive
            if dive:
                camera(cam, (0, 0, .70), (0, -.45, 12), 3.76)
            else:
                camera(cam, (-.17, 0, 1.76), (1.72, -8, 3.10), 6.63)
            wet_angle = TRAVEL * closed
        fixed.location.z = -LOWER_DROP * drop
        moving.rotation_euler.z = driver.rotation_euler.z = -TRAVEL * closed
        water(wet_angle)
    return pose


def replay(cam, f, *, exterior):
    if exterior:
        bathroom(f)
        trim(f, group("Installed hot trim", (HOT_X, 0, 0)))
        handle = group("Installed hot lever", (HOT_X, 0, .82))
        hot_handle(f, handle)
        water = exterior_water(f)
    else:
        block("Studio floor", (0, 0, -.23), (60, 60, .12), f["wall"], edge=0)
        root = group("The same two ceramic plates")
        _, moving = plate_set(f, root)
        water = wet_ports(f, root)

    def closed(t):
        return ease(t, 1.40, 3.43)

    def pose(t):
        angle = TRAVEL * closed(t)
        if exterior:
            handle.rotation_euler.z = TRAVEL - angle
            water(t, lambda earlier: overlap(TRAVEL * closed(earlier)) / (2 * PORT_HALF))
            camera(cam, (-1.08, -.60, 1.07), (4.1, -9.9, 5.6), 7.94)
        else:
            moving.rotation_euler.z = -angle
            water(angle)
            camera(cam, (0, 0, .69), (.12, -2.4, 11), 4.65)
    return pose


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("view", choices=("extract", "plates", "flow", "turn", "replay-exterior", "replay-ports"))
    parser.add_argument("folder", type=Path)
    parser.add_argument("frames", type=int)
    parser.add_argument("--preview", action="store_true")
    parser.add_argument("--points", type=int, nargs="+")
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
    args.folder.mkdir(parents=True, exist_ok=True)
    scene, cam = setup(0)
    scene.eevee.taa_render_samples = 6 if args.preview else 12
    scene.render.resolution_percentage = 40 if args.preview else 100
    f = finishes()
    if args.view == "extract":
        pose = extraction(cam, f)
    elif args.view.startswith("replay-"):
        pose = replay(cam, f, exterior=args.view == "replay-exterior")
    else:
        pose = inner(cam, f, args.view)
    index = args.points if args.points is not None else range(args.frames)
    for frame in index:
        path = args.folder / f"{frame:05}.jpg"
        if path.is_file():
            continue
        first = next((start for start, end in STILL_INTERVALS[args.view] if start < frame <= end), frame)
        reference = args.folder / f"{first:05}.jpg"
        if reference.is_file():
            path.hardlink_to(reference)
            continue
        pose(frame / FPS)
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)


if __name__ == "__main__":
    main()
