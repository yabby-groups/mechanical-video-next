"""Show the service tray and the opening it closes in the toaster base."""

import importlib.util
from pathlib import Path

import bpy

original = importlib.util.spec_from_file_location("toaster_scene", Path(__file__).with_name("scene.py"))
toaster = importlib.util.module_from_spec(original)
original.loader.exec_module(toaster)
base_build = toaster.build


def build(shot):
    scene, pose = base_build(shot)
    base = scene.objects["Bottom rim"]
    finish = base.data.materials[0]
    bpy.data.objects.remove(base, do_unlink=True)
    outside = toaster.rounded_rectangle(2.75, 4.01, .27)
    opening = toaster.rounded_rectangle(2.01, 3.24, .08)
    n = len(outside)
    vertices = [(x, y, z) for z in (.205, .415) for loop in (outside, opening) for x, y in loop]
    faces = []
    for i in range(n):
        j = (i + 1) % n
        faces.extend([
            (i, j, j + 2*n, i + 2*n),
            (i + n, i + 3*n, j + 3*n, j + n),
            (i, i + n, j + n, j),
            (i + 2*n, j + 2*n, j + 3*n, i + 3*n),
        ])
    rim = toaster.surface("Bottom rim", vertices, faces, finish)
    toaster.bevel(rim, .028)
    hinge = scene.objects["Crumb tray hinge"]
    metal = scene.objects["Crumb door"].data.materials[0]
    for x in (-.83, .83):
        toaster.block("Fixed hinge seat", (x, 1.66, .32), (.17, .13, .09), finish, edge=.012)
        toaster.block("Tray hinge leaf", (x, 0, 0), (.14, .16, .046), metal, hinge, edge=.012)
    return scene, pose


if __name__ == "__main__":
    # The scene's original camera, pose, checking and render loop are shared.
    toaster.build = build
    if "check_mechanics" in globals():
        toaster.check_mechanics = check_mechanics
    toaster.main()
