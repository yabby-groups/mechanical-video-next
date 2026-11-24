"""Render only the two plates used in the faucet opening comparison."""

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scene import (FPS, PORT_HALF, TRAVEL, block, camera, ease, finishes, group,
                   outside_pose, overlap, plate_set, setup, wet_ports)
import bpy


def port_pose(camera_object, materials):
    block("Studio sweep", (0, 0, 0), (30, 30, .12), materials["wall"], edge=0)
    root = group("Ceramic pair")
    _, moving = plate_set(materials, root)
    wet = wet_ports(materials, root)
    camera(camera_object, (0, 0, .69), (.12, -2.4, 11), 4.65)

    def pose(time):
        angle = -TRAVEL * ease(time, .23, 1.08)
        moving.rotation_euler.z = angle
        wet(angle)

    return pose


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("view", choices=("exterior", "ports"))
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
    args.directory.mkdir(parents=True, exist_ok=True)
    scene, cam = setup(0)
    scene.render.resolution_percentage = 50
    scene.eevee.taa_render_samples = 8
    materials = finishes()
    pose = (outside_pose(cam, materials, 0, 5) if args.view == "exterior"
            else port_pose(cam, materials))
    for frame in range(2 * FPS):
        path = args.directory / f"{frame:05}.jpg"
        if not path.is_file():
            pose(frame / FPS)
            scene.render.filepath = str(path)
            bpy.ops.render.render(write_still=True)

    states = []
    for frame in range(2 * FPS):
        time = frame / FPS
        angle = TRAVEL * ease(time, .23, 1.08)
        states.append({"frame": frame, "time_seconds": time,
                       "handle_and_disc_turn_degrees": angle * 180 / 3.141592653589793,
                       "shared_open_area_fraction": overlap(angle) / (2 * PORT_HALF),
                       "sink_impact_flow_fraction": overlap(TRAVEL * ease(time - .64, .23, 1.08)) / (2 * PORT_HALF)})
    (args.directory / "states.json").write_text(json.dumps(states, indent=2) + "\n")


if __name__ == "__main__":
    main()
