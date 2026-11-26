"""Reframe the original toaster model for the revised edit."""

import argparse
import importlib.util
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Vector

original = importlib.util.spec_from_file_location("toaster_scene", Path(__file__).with_name("scene.py"))
toaster = importlib.util.module_from_spec(original)
original.loader.exec_module(toaster)
from scene import bead, ring


def add_opening_cutaway():
    housing = bpy.data.objects["Gloss black housing"]
    vertices = [vertex.co.copy() for vertex in housing.data.vertices]
    faces = [tuple(face.vertices) for face in housing.data.polygons
             if face.center.x < .17 and face.center.y > -.63]
    wall = toaster.surface("Far half of housing", vertices, faces,
                           housing.data.materials[0], smooth=True)
    wall.modifiers.new("Shell thickness", "SOLIDIFY").thickness = .045

    top = bpy.data.objects["Slotted top"]
    back_trim = [obj.copy() for obj in top.children if obj.location.y > 1 or
                 (obj.location.y == 0 and obj.location.x <= 0)]
    for obj in back_trim:
        bpy.context.collection.objects.link(obj)
        obj.parent = None
    return [wall, *back_trim]


def support_materials():
    names = ("Toast support rail", "Support arm into carriage",
             "Crossbar joining both supports", "Open-sided carriage")
    return [(obj, obj.data.materials[0]) for obj in
            bpy.data.objects["Guided carriage and toast"].children if obj.name.startswith(names)]


def add_cancel_press():
    # The manufacturer photo shows CANCEL in the center of the shade dial.
    dial = bpy.data.objects["Browning dial axis"]
    front = dial.parent
    rim = toaster.material("Cancel face", (.075, .083, .09), .18, .37)
    center = toaster.group("Center cancel button", (0, -2.276, .66), front)
    center.rotation_euler.x = math.pi / 2
    toaster.cylinder("Pressable cancel face", .142, .087, 0, rim, center, edge=.018)
    label = bpy.data.curves.new("Maker control label", "FONT")
    label.body = "CANCEL"
    label.align_x = "CENTER"
    label.align_y = "CENTER"
    label.size = .051
    label.materials.append(toaster.material("Light control lettering", (.76, .79, .80)))
    text = bpy.data.objects.new("Cancel label", label)
    bpy.context.collection.objects.link(text)
    text.parent = center
    text.location.z = .045

    skin = toaster.material("Fingertip", (.46, .225, .123), 0, .58)
    nail = toaster.material("Fingernail", (.56, .32, .23), 0, .47)
    axis = Vector((.82, -.46, -.17)).normalized()
    finger = toaster.group("Finger pressing CANCEL")
    finger.rotation_euler = axis.to_track_quat("Z", "Y").to_euler()
    # Local z runs from the finger pad back towards the hand.
    capsule = [(0, .0), (.095, .035), (.145, .13), (.152, .31),
               (.142, .49), (.157, .72), (.151, .97), (.126, 1.19), (0, 1.27)]
    ring("Index finger", capsule, skin, finger, sides=40)
    # The upper surface of the pad carries the nail.
    bead("Nail", (0, .119, .19), .12, nail, finger).scale = (.72, .29, 1.08)
    return center, finger, axis


def build(shot):
    scene, original_pose = toaster.build(7 if shot == 8 else shot)
    cam = scene.camera
    if shot in (0, 8):
        teal = toaster.material("Carriage and supports", (.04, .44, .52), .27, .34, .28)
        supports = support_materials()
    if shot == 0:
        cutaway = add_opening_cutaway()
    if shot == 5:
        cancel, finger, finger_axis = add_cancel_press()
        side_button = bpy.data.objects["Cancel button"]
    if shot == 8:
        for obj, _ in supports:
            obj.data.materials[0] = teal
        amber = toaster.material("Chart spring", (.53, .25, .055), .45, .34, .15)
        bpy.data.objects["Upper extension spring"].data.materials[0] = amber

    def pose(t, duration):
        if shot == 0:
            # The shell outline stays visible during the first lift. The next angle
            # follows the two tinted support rails into the front crossbar.
            for obj, finish in supports:
                obj.data.materials[0] = teal if t < 5.35 else finish
            for part in cutaway:
                part.hide_render = t >= 1.67
            if t < 5.35:
                original_pose(t, 11.967)
                if t < 1.67:
                    toaster.camera(cam, (0, -.05, 1.89), (4.9, -7, 3.8), 6.35)
                else:
                    turn = toaster.ease(t, 1.67, 4.5)
                    toaster.camera(cam, (0, -.83, 2.05), (2.45 + .8 * turn, -7, 4.45), 5.58)
            else:
                reference_duration = 359 / 30
                original_pose(t + .48 * reference_duration - 5.35, reference_duration)
        elif shot == 5:
            original_pose(t, duration)
            side_button.location.y = -2.15
            toaster.show_tree(finger, 7.06 <= t < 9.27)
            if t >= 6.58:
                approach = toaster.ease(t, 7.06, 8.06)
                retreat = toaster.ease(t, 8.59, 9.27)
                travel = .048 * (toaster.ease(t, 8.06, 8.21) - toaster.ease(t, 8.36, 8.59))
                cancel.location.y = -2.276 + travel
                finger.location = Vector((0, -2.32 + travel, .66)) + finger_axis * (
                    1.63 * (1 - approach + retreat))
                toaster.camera(cam, (.13, -.54, 1.85), (2.25, -8, 2.78), 5.63)
        else:
            original_pose(0, duration)
            toaster.camera(cam, (0, -.46, 2.02), (3.8 - .5 * t / duration, -7, 4.45), 6.1)

    return scene, pose


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--timing", type=Path, required=True)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--shot", type=int, choices=(0, 5, 8), required=True)
    parser.add_argument("--preview", action="store_true")
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
    count = json.loads(args.timing.read_text())[args.shot]
    scene, pose = build(args.shot)
    scene.render.resolution_percentage = 35 if args.preview else 100
    folder = args.directory / f"shot-{args.shot}"
    folder.mkdir(parents=True, exist_ok=True)
    for frame in range(0, count, 6 if args.preview else 1):
        path = folder / f"{frame:05}.jpg"
        if not path.is_file():
            pose(frame / 30, count / 30)
            scene.render.filepath = str(path)
            bpy.ops.render.render(write_still=True)


if __name__ == "__main__":
    main()
