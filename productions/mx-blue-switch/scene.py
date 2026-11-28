"""Qualitative section models of the CHERRY MX2A Blue and Red switches."""
import argparse
import importlib.util
import json
import math
import os
from pathlib import Path
import sys

import bpy

studio_path = Path(__file__).resolve().parents[1] / 'quarter-turn-faucet' / 'scene.py'
studio_spec = importlib.util.spec_from_file_location('faucet_studio', studio_path)
studio = importlib.util.module_from_spec(studio_spec)
sys.modules[studio_spec.name] = studio
studio_spec.loader.exec_module(studio)
from faucet_studio import block, camera, cylinder, ease, group, material, pipe, setup

# Time windows for press and release. Positions are illustrative.
STROKES = (
    (.13, 1.05, 4.1, 4.68), (1.35, 2.55, 5.75, 6.75), None,
    (.85, 3.65, 6.8, 8.6), (1.25, 3.5, 6.25, 7.92),
    (1.1, 2.8, 4.2, 7.75), (.7, 3.3, 6.25, 8.25),
    (3.7, 8.2, 8.6, 9.8),
)


def switch(name, x, colors, *, key=False, red=False):
    shell, base_color, blue, red_color, white, gold, steel, cap = colors
    root = group(name, (x, 0, 0))
    base = group(name + ' base', (0, 0, 0), root)
    block(name + ' base plate', (0, 0, .22), (2.58, 2.4, .38), base_color, base)
    block(name + ' rear housing', (0, .99, .57), (2.49, .33, .65), base_color, base)
    for side in (-1, 1):
        block(name + ' base catch', (side * 1.23, 0, .55), (.18, 1.97, .47), base_color, base)
        block(name + ' mounting rim', (side * 1.31, 0, .83), (.29, 2.53, .14), shell, base)
    housing = group(name + ' upper housing', (0, 0, 0), root)
    block(name + ' rear guide wall', (0, .98, 1.32), (2.5, .36, 1.21), shell, housing)
    for side in (-1, 1):
        block(name + ' side clip', (side * 1.12, .18, 1.34), (.28, 1.74, 1.2), shell, housing)
        block(name + ' upper guide', (side * .65, .10, 2.06), (.51, 1.24, .21), shell, housing)
    stem = group(name + ' stem', (0, 0, 0), root)
    stem_color = red_color if red else blue
    block(name + ' stem cross x', (0, 0, 2.41), (.88, .28, .81), stem_color, stem, edge=.051)
    block(name + ' stem cross y', (0, 0, 2.41), (.28, .88, .81), stem_color, stem, edge=.051)
    block(name + ' stem collar', (0, 0, 2.02), (1.28, 1.05, .18), stem_color, stem)
    cylinder(name + ' center post', .17, 1.20, 1.42, stem_color, stem)
    slider = group(name + ' slider', (0, 0, 0), root)
    driver = stem if red else slider
    driver_color = red_color if red else white
    block(name + ' driver crossbar', (0, -.29, 1.79), (1.49, .37, .19), driver_color, driver)
    for side in (-1, 1):
        block(name + ' driver leg', (side * .61, -.38, 1.55), (.27, .32, .52), driver_color, driver)
    if not red:
        for side in (-1, 1):
            block(name + f' impact seat {side}', (side * .61, -.38, .98),
                  (.30, .38, .12), stem_color, stem, edge=.012)
    block(name + ' contact ramp', (.71, -.40, 1.45), (.24, .34, .37), driver_color, driver)
    fixed = group(name + ' fixed contact', (.99, -.42, 1.02), root)
    leaf = group(name + ' moving contact', (.57, 0, 0), root)
    block(name + ' fixed leaf', (.08, 0, -.22), (.13, .36, .97), gold, fixed)
    block(name + ' contact dot fixed', (0, 0, 0), (.085, .19, .18), gold, fixed, edge=.02)
    block(name + ' contact dot moving', (.345, -.42, 1.02), (.065, .19, .18), gold, leaf, edge=.02)
    pipe(name + ' spring leaf', [(0, -.42, .36), (.08, -.42, .57), (.20, -.42, .88),
                                (.33, -.42, 1.02)], .055, gold, leaf)
    for loc in ((.57, -.42, -.04), (1.07, -.42, -.04)):
        block(name + ' through-hole pin', loc, (.11, .16, .53), steel, root, edge=.018)
    spring = group(name + ' coil', (0, 0, .46), root)
    coil = []
    for i in range(165):
        a = i / 164 * math.tau * 7
        coil.append((.36 * math.cos(a), .36 * math.sin(a), i / 164 * 1.46))
    pipe(name + ' return spring', coil, .045, steel, spring)
    if key:
        block(name + ' keycap', (0, .15, 3.07), (2.57, 2.54, .43), cap, stem, edge=.125)
        block(name + ' keycap front edge', (0, -1.04, 2.82), (2.47, .13, .36), cap, stem)
    return root, housing, stem, slider, leaf, spring


def pose_switch(parts, t, stroke, *, red=False, exploded=False, travel=False):
    root, housing, stem, slider, leaf, spring = parts
    if exploded:
        separation = ease(t, .35, 2.1) * (1 - ease(t, 5.65, 7.5))
        housing.location.z = 2.05 * separation
        stem.location.z = 1.31 * separation
        slider.location.z = .82 * separation
        return
    start, down, release, up = stroke
    press = min(1, max(0, (t - start) / (down - start)))
    lift = ease(t, release, up)
    depth = .63 * (press - lift)
    trip = start + (.55 if travel else .49) * (down - start)
    reset = release + .67 * (up - release)
    snap = ease(t, trip, trip + .09) * (1 - ease(t, reset, reset + .10))
    stem.location.z = -depth
    slider.location.z = -depth - .25 * snap if not red else 0
    close = (ease(t, trip, trip + .16) * (1 - ease(t, reset, reset + .14))
             if not red else ease(depth, .26, .38))
    leaf.scale.x = .44 + .56 * close
    spring.scale.z = 1 - depth / 1.46


def build(shot):
    scene, cam = setup(shot)
    colors = (
        material('Graphite upper housing', (.10, .15, .20)),
        material('Slate lower housing', (.24, .32, .38)),
        material('Blue operating stem', (.035, .26, .86)),
        material('Red operating stem', (.72, .034, .038)),
        material('White click slider', (.94, .93, .82)),
        material('Gold contact', (.86, .45, .084), .57),
        material('Return spring steel', (.59, .65, .72), .72),
        material('Graphite keycap', (.12, .17, .23)),
    )
    ground = material('Workbench', (.055, .078, .104), .05, .49)
    block('Bench', (0, 0, -.46), (200, 200, .22), ground)
    pair = shot == 6
    main = switch('Blue', -1.78 if pair else 0, colors, key=shot in (0, 1, 7))
    other = switch('Red', 1.78, colors, red=True) if pair else None
    if shot == 2:
        main[4].scale.x = .44
    framing = (
        ((0, 0, 1.40), (.16, -1, .30), 6.1),
        ((0, 0, 1.42), (.48, -1, .60), 6.5),
        ((0, 0, 2.40), (.28, -1, .43), 8.5),
        ((.22, -.16, 1.39), (.04, -1, .18), 4.0),
        ((.76, -.31, .97), (.06, -1, .11), 2.15),
        ((.10, -.10, 1.15), (.24, -1, .22), 4.5),
        ((0, 0, 1.19), (.025, -1, .32), 8.0),
        ((0, 0, 1.27), (.21, -1, .34), 6.0),
    )
    camera(cam, *framing[shot])

    def pose(t):
        pose_switch(main, t, STROKES[shot], exploded=shot == 2, travel=shot == 7)
        if other:
            pose_switch(other, t, STROKES[shot], red=True)

    return scene, pose, main, other


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--timing', type=Path, required=True)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--shot', type=int, required=True)
    parser.add_argument('--preview', action='store_true')
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    count = json.loads(args.timing.read_text())[args.shot]
    scene, pose, blue, _ = build(args.shot)
    if 'check_mechanics' in globals():
        def measure(graph):
            return {'stem': blue[2].evaluated_get(graph).matrix_world.translation.z}

        if check_mechanics(scene, pose, count, measure, model=lambda graph: None, substeps=3):
            return

    scene.render.resolution_percentage = 40 if args.preview else 100
    folder = args.directory / f'shot-{args.shot}'
    folder.mkdir(exist_ok=True)
    previous = None
    for frame in range(0, count, 3 if args.preview else 1):
        path = folder / f'{frame:05}.jpg'
        scene.frame_set(frame)
        pose(frame / 30)
        signature = tuple((obj.location[:], obj.scale[:]) for obj in scene.objects)
        if not path.is_file():
            if previous and signature == previous[0]:
                os.link(previous[1], path)
            else:
                scene.render.filepath = str(path)
                bpy.ops.render.render(write_still=True)
        previous = signature, path


if __name__ == '__main__':
    main()
