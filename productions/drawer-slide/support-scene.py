"""Show the two real overlap lengths and an illustrative load path."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys

import bpy
from mathutils import Vector

spec = spec_from_file_location("drawer_growth", Path(__file__).with_name("growth-scene.py"))
growth = module_from_spec(spec)
sys.modules[spec.name] = growth
spec.loader.exec_module(growth)
from drawer_scene import (
    BALL_RADIUS, CABINET_Y, LENGTH, RAIL_Z, bead, block, camera, drawer_system,
    ease, group, material, move_slide, pipe, section_z, slide,
)


def configure_shadows():
    eevee = bpy.context.scene.eevee
    eevee.taa_render_samples = 12
    eevee.shadow_ray_count = 2


def overlap_marker(name, z, finish):
    marker = group(name, (0, -CABINET_Y - .49, z))
    span = pipe(name + " span", ((0, 0, 0), (1, 0, 0)), .031, finish, marker)
    ends = [pipe(name + " end", ((0, 0, -.07), (0, 0, .23)), .030, finish, marker)
            for _ in range(2)]

    def place(start, end, visible):
        span.location.x = ends[0].location.x = start
        ends[1].location.x = end
        span.scale.x = end - start
        for obj in (span, *ends):
            obj.hide_render = not visible

    return place


def explanation_opening(cam, parts, shot, duration):
    original_pose = growth.opening(cam, parts, shot, duration)
    cool = material("Cabinet to intermediate overlap", (.13, .76, 1.0), glow=.6)
    warm = material("Intermediate to drawer overlap", (1.0, .54, .08), glow=.6)
    cabinet_overlap = overlap_marker("Fixed and intermediate overlap", 2.58, cool)
    drawer_overlap = overlap_marker("Intermediate and drawer overlap", 2.58, warm)

    def pose(t):
        travel, middle, close = original_pose(t)
        cabinet_marked = t >= .55
        drawer_marked = t >= 4.15
        cabinet_overlap(middle - LENGTH, 0, cabinet_marked)
        drawer_overlap(travel - LENGTH, middle, drawer_marked)
        return travel, middle, close, cabinet_marked, drawer_marked

    return pose


def path_arrow(name, start, end, finish, *, radius=.013):
    start, end = Vector(start), Vector(end)
    axis = (end - start).normalized()
    side = Vector((-axis.z, 0, axis.x))
    shoulder = end - .095 * axis
    return (
        pipe(name + " shaft", (start, end), radius, finish),
        pipe(name + " head", (shoulder + .045 * side, end, shoulder - .045 * side),
             radius, finish),
    )


def load_path_scene(cam, parts, duration):
    configure_shadows()
    length = 2.4
    rail = slide(parts, length, macro=True)
    # Two cut pieces retain the mounting sides and colors of the full assembly.
    block("Cutaway of cabinet mounting side", (-2.11, -4.18, 2.94),
          (.58, .22, 1.17), parts["cabinet"], edge=.023)
    for z in (2.79, 3.12):
        bead("Fixed rail fastening point", (-1.95, -4.306, z), .030, parts["fastener"])
    block("Cutaway of drawer side", (-.30, .37, .52),
          (1.28, .24, .80), parts["oak"], rail[1], edge=.023)
    for x in (-.31, -.53):
        bead("Drawer rail fastening point", (x, .217, .12), .024,
             parts["fastener"], rail[1])

    load = material("Illustrative load path", (1.0, .57, .11), glow=.76)
    overlay_y = -4.38

    def point(x, z):
        return x, overlay_y, z

    # Centers of the chosen lower balls at the teaching pose with both stages extended.
    inner_contact = point(-length / 2 + (.40 + .77) / 2 + .315, RAIL_Z + section_z(267))
    outer_contact = point(-length / 2 + .40 / 2 + .105, RAIL_Z + section_z(295))
    drawer = point(.65, 3.59)
    gold = point(.40, 3.00)
    silver = point(-.62, 2.81)
    blue = point(-1.49, 2.66)
    cabinet = point(-2.09, 2.94)
    stages = (
        (6.16, path_arrow("Drawer onto inner rail", drawer, gold, load)),
        (6.53, (*path_arrow("Inner rail to first bearing row", gold, inner_contact, load),
                bead("Inner to intermediate contact", inner_contact, .034, load))),
        (7.06, path_arrow("First bearing row into intermediate rail", inner_contact, silver, load)),
        (7.60, (*path_arrow("Intermediate rail to second bearing row", silver, outer_contact, load),
                bead("Intermediate to outer contact", outer_contact, .034, load))),
        (8.10, path_arrow("Second bearing row into outer rail", outer_contact, blue, load)),
        (8.92, path_arrow("Outer rail into cabinet", blue, cabinet, load)),
    )

    def pose(t):
        amount = ease(t, 1.18, 5.67)
        middle_travel, travel = .40 * amount, .77 * amount
        move_slide(rail, travel, middle_travel, length)
        for cage, slip in zip(rail[2], (middle_travel, travel - middle_travel)):
            for ball in cage.children:
                if ball.type == "EMPTY":
                    sign = -1 if ball.location.z > 0 else 1
                    ball.rotation_euler.y = sign * slip / (2 * BALL_RADIUS)
        camera(cam, (-.91 + .09 * amount, -4.00, 3.16),
               (1.15, -10.4, .95), 4.05)
        visible_count = 0
        for start, objects in stages:
            visible = t >= start
            visible_count += visible
            for obj in objects:
                obj.hide_render = not visible
        return amount, visible_count

    return pose


def closing(cam, parts, shot, duration):
    _, side, drawer = drawer_system(parts)
    rails = [slide(parts), slide(parts, mirror=True)]

    def pose(t):
        opening = .90 + .10 * ease(t, .12, 1.10)
        push = ease(t, 3.37, 5.80)
        reopen = ease(t, 6.18, duration - .70)
        travel = 9.12 * (opening * (1 - push) + reopen)
        panel_clearance = ease(t, 6.43, 7.39)
        panel_seat = ease(t, 7.39, 7.85)
        orbit = ease(t, 6.43, 8.34)
        side.location.z = 8.9 * (1 - panel_clearance)
        side.location.y = -.66 * (1 - panel_seat)
        drawer.location.x = travel
        for rail in rails:
            move_slide(rail, travel, travel * .50)
        camera(cam, (-3.75 + travel * .46, -.25, 2.87),
               (3.0 + 4.5 * orbit, -10.7, 2.1 + 3.3 * orbit), 22.9)
        return travel, panel_clearance, panel_seat, orbit

    return pose


def full_scene(cam, parts, shot, duration):
    configure_shadows()
    if shot == 4:
        return closing(cam, parts, shot, duration)
    return explanation_opening(cam, parts, shot, duration)


if __name__ == "__main__":
    growth.drawer_scene.full_scene = full_scene
    growth.drawer_scene.macro_scene = load_path_scene
    growth.drawer_scene.main()
