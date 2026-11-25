"""Render the revised opening and the closed ceramic interface."""

import argparse
import math
from pathlib import Path
import sys

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
from opening_scene import port_pose
from scene import (
    FPS, PORT_HALF, TRAVEL, block, camera, cartridge_shell, ease, faucet,
    finishes, group, lever, material, overlap, plate_set, ring, setup, stem,
)


def opening_turn(time):
    return TRAVEL * ease(time, .23, 1.08)


def exterior(cam, f):
    handle, water = faucet(f)

    def pose(time):
        handle.rotation_euler.z = TRAVEL - opening_turn(time)
        water(time, lambda earlier: overlap(opening_turn(earlier)) / (2 * PORT_HALF))
        push = ease(time, 0, 2)
        camera(cam, (-1.08, -.63, 1.08), (4.1, -9.9, 5.6), 8.2 - .34 * push)

    return pose


def opening_ports(cam, f):
    f["water"] = material("Visible shared water opening", (.008, .47, .86), 0, .27, .4)
    return port_pose(cam, f)


def stem_connection(cam, f):
    block("Studio floor", (0, 0, -.17), (60, 60, .12), f["wall"], edge=0)
    root = group("Closed valve assembly")
    cartridge_shell(f, root)
    _, moving = plate_set(f, root)
    driver = group("Handle and stem share a rotation axis", parent=root)
    stem(f, driver)
    grip = group("Left lever", (0, 0, 2.79), driver)
    grip.rotation_euler.z = TRAVEL
    lever("Left lever", grip, f["chrome"], f["hot"])
    for side in (-1, 1):
        for side_of_lug in (-1, 1):
            # The shoulders extend from the solid outer rim and grip the lug.
            block("Ceramic shoulder at driver", (side * .756, side_of_lug * .155, 1.02),
                  (.26, .085, .30), f["moving"], moving, edge=.012)
        block("Housing keyway cheek", (side * .151, -.96, .60),
              (.105, .19, .26), f["cut"], root, edge=.012)
    # Retain the lower rim on both sides of the locating slot.
    for start, end in ((-math.pi, math.radians(-96)), (math.radians(-84), 0)):
        ring("Lower housing rim at locating slot",
             ((.95, .48), (1.053, .48), (1.053, .558), (.95, .558)),
             f["brass"], root, start=start, end=end)
    driver.rotation_euler.z = moving.rotation_euler.z = -TRAVEL

    def pose(time):
        rise = ease(time, 0, 1.35)
        settle = ease(time, 1.33, 3.0)
        camera(cam, (-.07, 0, 1.12 + .51 * rise),
               (3.4 - 1.35 * settle, -7, 4.4 - 2.2 * rise),
               4.75 + 2.0 * rise - .18 * settle)

    return pose


def section_disc(f, root, name, base, angle, finish):
    """Retain the back half of each ceramic solid at the same section plane."""
    top = base + .19
    ring(name + " rim", ((.77, base), (.95, base), (.95, top), (.77, top)),
         finish, root, start=0, end=math.pi)
    ring(name + " hub", ((0, base), (.27, base), (.27, top), (0, top)),
         finish, root, start=0, end=math.pi)
    for turn in range(-1, 3):
        start = max(0, angle + turn * math.pi + PORT_HALF)
        end = min(math.pi, angle + (turn + 1) * math.pi - PORT_HALF)
        if start < end:
            ring(name + " solid ceramic", ((.27, base), (.77, base), (.77, top), (.27, top)),
                 finish, root, start=start, end=end, sides=36)


def sealed_port(cam, f):
    block("Studio sweep", (0, 0, -.58), (60, 60, .12), f["wall"], edge=0)
    root = group("Longitudinal cut through the same two seated discs")
    section_disc(f, root, "Fixed disc", .50, 0, f["fixed"])
    section_disc(f, root, "Rotating disc", .69, -TRAVEL, f["moving"])
    block("Moving disc index", (0, .856, .887), (.09, .125, .022), f["mark"], root, .008)
    block("Fixed disc locating tab", (0, .96, .595), (.20, .13, .19), f["fixed"], root, .015)
    # The inlet fills both fixed ports and ends at the actual ceramic contact plane.
    water = material("Water at the cut face", (.008, .33, .65), 0, .23, .42)
    for start, end in ((0, PORT_HALF), (math.pi - PORT_HALF, math.pi)):
        ring("Water below the blocked interface",
             ((.27, -.09), (.77, -.09), (.77, .69), (.27, .69)),
             water, root, start=start, end=end, sides=24)
    ring("Section of the inlet seat", ((.77, -.20), (.99, -.20), (.99, .50), (.77, .50)),
         f["brass"], root, start=0, end=math.pi)

    def pose(time):
        move = ease(time, 0, 3.9)
        camera(cam, (.37 + .075 * move, 0, .56), (.95 + .28 * move, -8, 3.28),
               4.05 - .24 * move)

    return pose


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("view", choices=("exterior", "ports", "stem", "seal"))
    parser.add_argument("folder", type=Path)
    parser.add_argument("frames", type=int)
    parser.add_argument("--preview", action="store_true")
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
    args.folder.mkdir(parents=True, exist_ok=True)
    scene, cam = setup(0)
    scene.render.resolution_percentage = 40 if args.preview else 100
    scene.eevee.taa_render_samples = 6 if args.preview else 12
    poses = {"exterior": exterior, "ports": opening_ports, "stem": stem_connection, "seal": sealed_port}
    pose = poses[args.view](cam, finishes())
    for frame in range(0, args.frames, 30 if args.preview else 1):
        path = args.folder / f"{frame:05}.jpg"
        if not path.is_file():
            pose(frame / FPS)
            scene.render.filepath = str(path)
            bpy.ops.render.render(write_still=True)


if __name__ == "__main__":
    main()
