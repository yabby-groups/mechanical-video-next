"""Direction for the US7900978B2 teaching assembly in the existing source Blend."""

import argparse
import fcntl
import hashlib
import json
import math
from types import SimpleNamespace
from pathlib import Path
import shutil
import sys

import bpy

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'blender'))
import cinematic as look
from scene import render_chunked

sys.path[:0] = [str(ROOT), str(ROOT / 'scripts')]
from common import budget


def frame(seconds):
    return round(seconds * 30) + 1


def animated(obj, channel, keys):
    for seconds, value in keys:
        setattr(obj, channel, value)
        obj.keyframe_insert(channel, frame=frame(seconds))


def placement(obj, *keys):
    animated(obj, 'location', keys)


def clear_channels(obj, channel):
    if not obj.animation_data or not obj.animation_data.action:
        return
    for layer in obj.animation_data.action.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                for curve in list(bag.fcurves):
                    if curve.data_path == channel:
                        bag.fcurves.remove(curve)


def visible(obj, *keys):
    clear_channels(obj, 'hide_render')
    animated(obj, 'hide_render', [(time, not on) for time, on in keys])


def annulus(name, radius, bore, from_y, to_y, material, edge=.045):
    segments = 128
    vertices = [
        (r * math.cos(angle), y, r * math.sin(angle))
        for r, y in ((radius, from_y), (bore, from_y), (radius, to_y), (bore, to_y))
        for angle in (math.tau * index / segments for index in range(segments))
    ]
    faces = []
    for i in range(segments):
        j = (i + 1) % segments
        a, b, c, d = (offset * segments for offset in range(4))
        faces.extend(((a+i, c+i, c+j, a+j), (b+i, b+j, d+j, d+i),
                      (a+i, a+j, b+j, b+i), (c+i, d+i, d+j, c+j)))
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    for face in mesh.polygons:
        face.use_smooth = face.index % 4 < 2
    bevel = obj.modifiers.new('Rolled edge', 'BEVEL')
    bevel.width, bevel.segments = edge, 4
    obj.modifiers.new('Face normals', 'WEIGHTED_NORMAL')
    look.assign(obj, material)
    return obj


def box(name, position, dimensions, material):
    bpy.ops.mesh.primitive_cube_add(size=1, location=position)
    obj = bpy.context.object
    obj.name, obj.dimensions = name, dimensions
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    bevel = obj.modifiers.new('Rounded joinery', 'BEVEL')
    bevel.width, bevel.segments = .045, 3
    look.assign(obj, material)
    return obj


def apply_direction(scene, *, full_edit=False, short_macro=False):
    objects = bpy.data.objects
    door = objects['Door panel with a through bore']
    stile = objects['Door stile']
    lever = objects['Lever handle']
    housing = objects['12 housing and flange']
    cover = objects['58 cover plate']
    shaft = objects['66 square drive spindle']
    spring = objects['30 continuous wire arc spring']
    driver = objects['34 active flat spring driver']
    stationary = objects['32 opposite flat spring driver']

    brass = look.surface('Satin champagne PVD', (.49, .31, .15), .87, .29,
                         grain=(5, 155, 200), bump=.003, anisotropy=.34)
    trim = look.surface('Dark anodized bronze', (.085, .070, .048), .71, .31,
                        grain=(155, 10, 150), bump=.002)
    steel = look.surface('Cold machined steel', (.44, .53, .59), .88, .27,
                         grain=(130, 130, 8), bump=.002)
    wire = look.surface('Drawn spring steel', (.60, .69, .73), .76, .25, anisotropy=.25)
    black = look.surface('Graphite oxide', (.055, .083, .103), .56, .38,
                         grain=(22, 22, 22), bump=.001)
    passive = look.surface('Blued steel', (.15, .26, .33), .62, .34)
    active = look.surface('Warm plated steel', (.57, .25, .056), .66, .31)
    oak = look.surface('Quartersawn oak', (.18, .073, .028), 0, .43,
                       grain=(11, 15, .65), grain_colors=((.094, .035, .013), (.29, .14, .061)),
                       bump=.025)
    paint = look.surface('Petrol painted joinery', (.025, .074, .091), .03, .52)
    for obj in lever.children:
        look.assign(obj, brass)
    for obj in shaft.children:
        look.assign(obj, steel)
    for obj in housing.children:
        look.assign(obj, black)
    for obj in cover.children:
        look.assign(obj, steel)
    for obj in driver.children:
        look.assign(obj, active)
    for obj in stationary.children:
        look.assign(obj, passive)
    look.assign(spring, wire)
    look.assign(door, oak)
    if full_edit:
        # Extend the panel to the joinery and off camera. The bore keeps its original mesh.
        for vertex in door.data.vertices:
            if vertex.co.x < -7:
                vertex.co.x = -4.96
            elif vertex.co.x > 7:
                vertex.co.x = 11.5
            if abs(vertex.co.z) > 5:
                vertex.co.z = math.copysign(15.0, vertex.co.z)
        door.data.update()
    look.assign(stile, trim)
    look.assign(objects['Studio backdrop'], paint)

    # These external finishes are scenic geometry. Native moving meshes are reused.
    skin = annulus('Scenic rosette', 2.105, .48, -.71, -.48, trim, .06)
    edge = annulus('Scenic rosette highlight', 2.086, 2.035, -.731, -.69, brass, .015)
    bezel = annulus('Scenic spindle collar', .52, .405, -.80, -.69, brass, .029)
    for obj in (skin, edge, bezel):
        obj.parent = cover
    jamb = box('Door jamb', (-5.30, .36, 0), (.52, .75, 15), paint)
    gap = box('Door jamb shadow', (-4.98, .50, 0), (.07, .16, 15), black)
    for obj in (door, stile, jamb, gap):
        visible(obj, (0, True), (33, True))
    stile.animation_data_clear()
    stile.location = (-4.94, .53, 0)

    # Clear only legacy presentation channels on rigid parts. Preserve their rotation curves.
    for obj in (lever, shaft, driver, stationary, housing, spring, cover):
        clear_channels(obj, 'location')
        obj.location = (0, 0, 0)
    for obj in (spring, *driver.children, *stationary.children):
        visible(obj, (0, True))
    for obj in cover.children:
        visible(obj, (0, True), (10.9, False), (33, True))

    # Extract along the spindle first. The camera rotates to expose the gap.
    # The cut at 11.0s returns to an operating section with the cover removed.
    placement(lever, (0, (0, 0, 0)), (5.4, (0, 0, 0)),
              (6.29, (0, -2.35, 0)), (8.3, (2.48, -2.35, 0)),
              (10.83, (2.48, -2.35, 0)), (11, (0, 0, 0)))
    placement(shaft, (0, (0, 0, 0)), (5.4, (0, 0, 0)),
              (6.29, (0, -2.35, 0)), (8.3, (2.48, -2.35, 0)),
              (10.83, (2.48, -2.35, 0)), (11, (0, 0, 0)))
    placement(cover, (0, (0, 0, 0)), (6.75, (0, 0, 0)),
              (7.35, (0, -.87, 0)), (8.55, (-3.20, -.87, .55)),
              (10.83, (-3.20, -.87, .55)), (11, (0, 0, 0)))
    # Remove front surfaces to inspect the aperture while the handle is still at rest.
    for name in ('Lever shank', 'Lever grip', '48 hub with actual square opening'):
        visible(objects[name], (0, True), (11, False), (15.55, True))

    # An independent scenic backplate takes over on the inspection cut.
    # The disassembly stays on the installed door until the cut.
    for obj in (door, stile, jamb, gap):
        visible(obj, (0, True), (11, False), (33, True))

    scene.timeline_markers.clear()
    cameras = [
        ('Installed lever · 54 mm dolly', 54, None, [
            (0, (5.3, -13.5, 3.0), (.25, -.4, -.12)),
            (5.26, (3.7, -12, 2.4), (.45, -.38, -.22))]),
        ('Axial extraction · 39 mm', 39, None, [
            (5.3, (4.3, -13, 3.0), (.55, -.33, 0)),
            (8.35, (5.7, -15.9, 4.6), (.92, -.62, .02)),
            (10.96, (5.2, -15.9, 4.1), (.9, -.60, .03))]),
        ('Spindle aperture · 67 mm', 67, None, [
            (11, (-.25, -8.85, 1.1), (-.68, -.04, .04)),
            (15.53, (-.45, -8.2, .83), (-.73, -.03, .03))]),
        ('Loading and release · frontal reference', 50, 8.9, [
            (15.55, (.24, -12, .32), (.45, 0, -.16))]),
        ('Spring seat · 82 mm', 82, None, [
            (18.55, (-2.5, -7.65, -.35), (-.71, -.02, -.79))]),
        ('Return · frontal reference', 50, 8.9, [
            (26.45, (.24, -12, .32), (.45, 0, -.16))]),
        ('Installed lever · return', 54, None, [
            (33, (3.7, -12, 2.4), (.45, -.38, -.22)),
            (40.46, (5.0, -14, 3.2), (.25, -.4, -.12))]),
    ]
    if short_macro:
        cameras[4][3][0] = (20.25, (-2.5, -7.65, -.35), (-.71, -.02, -.79))
        cameras[5][3][0] = (21.38, (.24, -12, .32), (.45, 0, -.16))
    for name, lens, ortho, poses in cameras:
        look.camera(scene, name, [(frame(t), pos, target) for t, pos, target in poses],
                    lens=lens, ortho=ortho)
    scene.camera = bpy.data.objects[cameras[0][0]]

    lighting = [
        ('Warm window key', (-5.5, -7, 7.8), (0, 0, 0), 3800, (8, 5), (1, .83, .66)),
        ('Cool vertical edge', (5.6, -2.8, 2.6), (.7, 0, 0), 2100, (3, 7), (.56, .79, 1)),
        ('Soft front reflector', (.7, -8.0, -2.7), (-.5, 0, -.45), 870, (7, 4), (.76, .88, 1)),
        ('Spring strip', (-4.6, -2.7, -.8), (-1.15, -.1, -.11), 240, (1.1, 4), (1, .95, .82)),
    ]
    for spec in lighting:
        look.area(scene, *spec)
    look.studio_world(scene, (.14, .22, .32), .35)
    return {'cameras': cameras, 'lighting': lighting, 'mechanism': 'US7900978B2 figs. 1–5'}


def render_core(scene, out, *, revised):
    # Source-clock intervals are half-open, using Blender's 1-based frame numbers.
    # The long staged motion is sampled at twice its old illustrative playback speed.
    intervals = ([(19, 91, 1), (160, 263, 1), (470, 905, 3)] if revised else
                 [(19, 91, 1), (160, 263, 1), (501, 632, 2), (721, 901, 2)])
    source_frames = [source for start, end, step in intervals for source in range(start, end, step)]
    frames = out.resolve() / 'core-frames'
    frames.mkdir(exist_ok=True)
    receipt = {
        'source_frames': source_frames, 'fps': 30,
        'scene_sha256': hashlib.sha256((out / 'scene.blend').read_bytes()).hexdigest(),
    }
    mapping = out / 'core-clock.json'
    mapping.write_text(json.dumps(receipt, indent=2) + '\n')
    for number, source in enumerate(source_frames, 1):
        scene.frame_set(source)
        scene.render.filepath = str(frames / f'{number:04d}.jpg')
        bpy.ops.render.render(write_still=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('out', type=Path)
    parser.add_argument('--engine', default='BLENDER_EEVEE')
    parser.add_argument('--width', type=int, default=768)
    parser.add_argument('--samples', type=int, default=12)
    parser.add_argument('--probes', action='store_true')
    parser.add_argument('--core', action='store_true')
    parser.add_argument('--full', action='store_true')
    parser.add_argument('--revised', action='store_true')
    parser.add_argument('--motion-patch', action='store_true')
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    args.out.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(ROOT).free < 3 * 1024**3:
        raise RuntimeError('Less than 3 GiB free')
    with (ROOT / 'work/production.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        budget()
        scene = bpy.context.scene
        if args.engine != 'BLENDER_WORKBENCH':
            config = apply_direction(scene, full_edit=args.full or args.revised, short_macro=args.revised)
            look.render_settings(scene, args.engine, args.width, args.width * 9 // 16, args.samples)
            config.update(engine=args.engine, samples=args.samples, width=args.width,
                          source=bpy.data.filepath, blender=bpy.app.version_string)
            (args.out / 'photography.json').write_text(json.dumps(config, indent=2) + '\n')
        scene.render.fps = 30
        scene.render.filepath = str(args.out.resolve() / 'frame-')
        scene.frame_set(1)
        bpy.ops.wm.save_as_mainfile(filepath=str(args.out.resolve() / 'scene.blend'), compress=True)
        if args.full or args.motion_patch:
            scene.render.image_settings.file_format = 'PNG'
            chunks = SimpleNamespace(out=args.out.resolve(), chunk_frames=48, fps=30,
                                     width=scene.render.resolution_x, height=scene.render.resolution_y,
                                     video_output=args.out.resolve() / 'native-picture.mp4')
            render_chunked(scene, range(1, 1216) if args.full else range(557, 795), chunks)
        if args.core:
            render_core(scene, args.out, revised=args.revised)
        if args.probes:
            for seconds in (1.5, 8.5, 20.5, 27.2):
                scene.frame_set(frame(seconds))
                scene.render.filepath = str(args.out.resolve() / f'probe-{seconds}.jpg')
                bpy.ops.render.render(write_still=True)


if __name__ == '__main__':
    main()
