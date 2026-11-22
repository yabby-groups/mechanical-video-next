"""Build and render the long-form EEVEE cut using the verified native source clock."""

import argparse
import fcntl
import json
from pathlib import Path
import sys
import time
from types import SimpleNamespace

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cinematic_scene import ROOT, budget, look, render_chunked
from common import filehash, writejson


LEVER = 'Lever handle'
SHAFT = '66 square drive spindle'
HOUSING = '12 housing and flange'
ACTIVE = '34 active flat spring driver'
PASSIVE = '32 opposite flat spring driver'
SPRING = '30 continuous wire arc spring'
COVER = '58 cover plate'
DOOR = ('Door panel with a through bore', 'Door stile', 'Door jamb', 'Door jamb shadow')
# Each entry describes a deliberate observation path, from inlet pose to exit pose.
CAMERAS = {
    'installed': (52, None, (2, -12.9, 1.15), (.5, -.3, -.17), (.1, .7, .04)),
    'reveal': (52, None, (2.0, -12.9, 1.15), (.5, -.3, -.17), (-3.4, 2.0, .45)),
    'back': (49, None, (-6.4, -10.8, 3.1), (-.25, .0, .18), (1.0, .8, -.6)),
    'explode': (40, None, (7.6, -12.6, 4.45), (.4, -1.65, -.13), (-.7, -.8, -.45)),
    'square': (63, None, (-3.1, -7.7, 2.8), (0, -.8, 0), (-1.6, .6, -.55)),
    'stack': (54, None, (5.1, -7.9, 2.25), (-.45, -.58, .1), (-.72, .35, -.4)),
    'axis': (52, 3.9, (-.17, -11.3, .26), (-.35, 0, .08), (.12, 0, -.08)),
    'upper': (62, 3.9, (-2.95, -10, 2.6), (-1.0, -.03, 1.02), (.24, .0, -.34)),
    'face': (50, 8.6, (-.8, -12.4, .48), (.20, 0, -.24), (0, 0, 0)),
    'lower': (52, 3.23, (-2.13, -12.55, -.06), (-1.05, -.15, -.73), (.1, 0, .08)),
    'coils': (62, 2.5, (-3.15, -10, .45), (-1.28, 0, .03), (.3, .0, .12)),
    'energy': (62, 5.8, (-4, -12, 2), (-.52, 0, .26), (.85, 0, -.5)),
    'faceBack': (50, 8.6, (-.8, -12.4, .48), (.2, 0, -.24), (0, 0, 0)),
    'torque': (50, 4.95, (-.04, -12.4, .28), (-.48, 0, -.49), (-.2, 0, .15)),
    'weight': (47, None, (2.1, -11.7, 1.25), (1.02, -.30, -.38), (-.9, .1, -.41)),
    'stop': (55, 3.9, (-.3, -11.4, 1.31), (-.78, 0, -.47), (.25, 0, -.33)),
    'home': (52, 5.4, (-.3, -11.4, .63), (-.55, 0, 0), (.07, 0, -.39)),
    'design': (54, 5.65, (2.6, -10, 1.43), (-.16, 0, .08), (-1.75, 0, -.52)),
    'map': (54, 8.7, (-.78, -12.4, .48), (.26, 0, -.1), (0, 0, 0)),
    'answer': (52, None, (-.8, -12.4, .48), (.27, 0, -.18), (3.3, -.7, .78)),
}
HIDE_GRIP = {'axis', 'upper', 'coils', 'stop', 'home', 'design', 'torque', 'stack'}
SHOW_OPEN = {'back', 'explode', 'square', 'stack', 'axis', 'upper', 'face',
             'lower', 'coils', 'energy', 'faceBack', 'torque', 'stop', 'home', 'design', 'map'}
# Source intervals preserve individual authored poses and the complete release at 1:1.
LEAD_FRAMES = {'hook': 0, 'reveal': 44, 'lost': 52, 'mid': 51, 'lower': 0,
               'release': 8, 'answer': 104}


def source_at(shot, local, count):
    first, last = shot['source']
    if shot['id'] == 'coils':
        return 469 if local < count // 2 else first
    moving = max(last - first, 1)
    return first + min(moving - 1, max(0, local - LEAD_FRAMES.get(shot['id'], 0)))


def original_curves():
    return [curve for action in bpy.data.actions if not action.name.startswith('Formal ')
            for layer in action.layers for strip in layer.strips
            for bag in strip.channelbags for curve in bag.fcurves]


def bake_clock(curves, frame_map):
    """Keep evaluations of original channels at integer source frames."""
    for curve in curves:
        old = [curve.evaluate(index + 1) for index in frame_map]
        if not curve.keyframe_points:
            continue
        boolean = curve.data_path == 'hide_render'
        indices = [0]
        indices.extend(i for i in range(1, len(old) - 1)
                       if old[i - 1] != old[i] or old[i] != old[i + 1])
        indices.append(len(old) - 1)
        curve.keyframe_points.clear()
        curve.keyframe_points.add(len(indices))
        for key, index in zip(curve.keyframe_points, indices, strict=True):
            key.co = index + 1, old[index]
            key.interpolation = 'CONSTANT' if boolean else 'LINEAR'
        curve.update()


def visibility(obj, frame, on):
    obj.hide_render = not on
    obj.keyframe_insert(data_path='hide_render', frame=frame)


def expose(scene, shot, first, stop):
    objects = scene.objects
    view = shot['camera']
    for name in ('Lever shank', 'Lever grip', '48 hub with actual square opening',
                 'Lever shank · section', '48 hub with actual square opening · section',
                 *DOOR, *(obj.name for obj in objects[COVER].children)):
        obj = objects[name]
        if name in DOOR:
            forced = view not in {'explode', 'square', 'stack', 'axis', 'coils', 'design'}
        elif obj.parent == objects[COVER]:
            forced = False if view in SHOW_OPEN else None
        elif view in HIDE_GRIP:
            forced = False
        elif view == 'square':
            forced = 'section' not in name or name.startswith('Lever')
        elif view in {'explode', 'weight'}:
            forced = 'section' not in name
        elif view in SHOW_OPEN:
            forced = 'section' in name or name == 'Lever grip'
        else:
            forced = None
        if forced is not None:
            visibility(obj, first, forced)
            visibility(obj, stop - 1, forced)


def animate_extraction(scene, start, end):
    duration = end - start
    origin = (0, 0, 0)
    # Orthogonal, single-axis separation reveals the order of the assembly.
    for name, offset, left, right in ((LEVER, -4.15, .03, .31), (SHAFT, -2.7, .24, .53),
                                       (ACTIVE, -1.9, .51, .75), (PASSIVE, -.97, .67, .89)):
        obj = scene.objects[name]
        for frame, location in ((start, origin), (start + round(duration * left), origin),
                                (start + round(duration * right), (0, offset, 0)),
                                (end - 1, (0, offset, 0)), (end, origin)):
            obj.location = location
            obj.keyframe_insert(data_path='location', frame=frame)


def pose_parts(scene, view, start, stop):
    if view == 'square':
        offsets = {LEVER: (0, -1.4, 0), SHAFT: (0, -.62, 0)}
    elif view == 'stack':
        offsets = {LEVER: (0, -4.0, 0), SHAFT: (0, -.38, 0), ACTIVE: (0, -.96, 0),
                   PASSIVE: (0, -.48, 0)}
    else:
        return
    for name, location in offsets.items():
        obj = scene.objects[name]
        for frame, position in ((start, location), (stop - 1, location), (stop, (0, 0, 0))):
            obj.location = position
            obj.keyframe_insert(data_path='location', frame=frame)


def axis_overlay(scene, plan):
    """Add a spatial center-to-seat reference for the torque explanation."""
    material = look.surface('Diagram · luminous ivory', (.8, .64, .37), .15, .38)
    for name, begin, end in (('Pivot to spring seat', (0, -.75, 0), (-1.22, -.75, -.85)),
                             ('Spring restores rotation', (-1.22, -.75, -.85), (-.78, -.75, -1.49))):
        direction = Vector(end) - Vector(begin)
        middle = (Vector(end) + Vector(begin)) / 2
        bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=.022, depth=direction.length, location=middle)
        obj = bpy.context.object
        obj.name = name
        obj.rotation_euler = direction.to_track_quat('Z', 'Y').to_euler()
        look.assign(obj, material)
        cut = next(row for row in plan['shots'] if row['id'] == 'torque')
        for frame, on in ((1, False), (cut['start_frame'] + 25, True), (cut['end_frame'] + 1, False)):
            visibility(obj, frame, on)


def reveal_opposite_driver(scene, plan):
    """Briefly expose the rear aperture in the same axial view."""
    active_disk = scene.objects['Moving driver with swept square aperture']
    material = active_disk.data.materials[0].copy()
    active_disk.data.materials[0] = material
    nodes, links = material.node_tree.nodes, material.node_tree.links
    surface = next(node for node in nodes if node.type == 'OUTPUT_MATERIAL').inputs['Surface']
    shaded = surface.links[0].from_socket
    transparent = nodes.new('ShaderNodeBsdfTransparent')
    mixer = nodes.new('ShaderNodeMixShader')
    links.new(shaded, mixer.inputs[1])
    links.new(transparent.outputs[0], mixer.inputs[2])
    links.new(mixer.outputs[0], surface)
    opacity = mixer.inputs[0]
    cut = next(row for row in plan['shots'] if row['id'] == 'lost')
    first = cut['start_frame'] + 1
    for frame, clarity in ((1, 0), (first, 0), (first+15, .92), (first+108, .92), (first+134, 0)):
        opacity.default_value = clarity
        opacity.keyframe_insert(data_path='default_value', frame=frame)


def direct(scene, story, plan):
    old_camera_objects = set(scene.objects)
    frame_map = []
    cuts = list(zip(story['shots'], plan['shots'], strict=True))
    for shot, cut in cuts:
        count = cut['end_frame'] - cut['start_frame']
        frame_map.extend(source_at(shot, local, count) for local in range(count))
    bake_clock(original_curves(), frame_map)
    scene.timeline_markers.clear()
    for shot, cut in cuts:
        first, stop = cut['start_frame'] + 1, cut['end_frame'] + 1
        view = shot['camera']
        lens, ortho, position, target, travel = CAMERAS[view]
        arrive = Vector(position) + Vector(travel)
        look.camera(scene, 'Formal · ' + shot['id'], [(first, position, target),
                    (stop - 1, arrive, target)], lens=lens, ortho=ortho)
        expose(scene, shot, first, stop)
        if view == 'explode':
            animate_extraction(scene, first, stop)
        else:
            pose_parts(scene, view, first, stop)
    axis_overlay(scene, plan)
    reveal_opposite_driver(scene, plan)
    scene.camera = next(obj for obj in set(scene.objects) - old_camera_objects
                        if obj.type == 'CAMERA' and obj.name == 'Formal · hook')
    scene.frame_start, scene.frame_end = 1, plan['frame_count']
    return frame_map


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('folder', type=Path)
    parser.add_argument('quality', choices=('preview', 'final'))
    parser.add_argument('--prepare', action='store_true')
    parser.add_argument('--probe', nargs='+', type=int)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    folder = args.folder.resolve()
    path = folder / 'joint-timeline.json'
    story_file = Path(__file__).with_name('formal-story.json')
    plan, story = json.loads(path.read_text()), json.loads(story_file.read_text())
    out = folder / args.quality
    out.mkdir(exist_ok=True)
    with (ROOT / 'work/production.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        budget()
        width, height, samples = (640, 360, 4) if args.quality == 'preview' else (1920, 1080, 8)
        scene = bpy.context.scene
        started = time.monotonic()
        blender_source = Path(bpy.data.filepath)
        scene_path = out / 'scene.blend'
        clock_path = out / 'source-clock.json'
        inputs = {str(p): filehash(p) for p in (blender_source, path, story_file, Path(__file__))}
        if clock_path.is_file() and scene_path.is_file():
            clock = json.loads(clock_path.read_text())
            if clock['inputs'] != inputs or clock['scene_sha256'] != filehash(scene_path):
                raise RuntimeError('Use a new output directory for changed scene inputs')
            bpy.ops.wm.open_mainfile(filepath=str(scene_path))
            scene = bpy.context.scene
        else:
            frame_map = direct(scene, story, plan)
            look.render_settings(scene, 'BLENDER_EEVEE', width, height, samples)
            scene.render.fps = 30
            scene.frame_set(1)
            scene.render.filepath = str(out / 'frame-')
            bpy.ops.wm.save_as_mainfile(filepath=str(scene_path), compress=True)
            writejson(clock_path, dict(fps=30, source_frames=frame_map, source_frame_base=0,
                                      scene_sha256=filehash(scene_path), inputs=inputs))
        if args.prepare:
            return
        if args.probe:
            scene.render.image_settings.file_format = 'JPEG'
            for source in args.probe:
                scene.frame_set(source)
                scene.render.filepath = str(out / f'probe-{source}.jpg')
                bpy.ops.render.render(write_still=True)
            return
        scene.render.image_settings.file_format = 'PNG'
        render_chunked(scene, range(1, plan['frame_count'] + 1),
                       SimpleNamespace(out=out, chunk_frames=60, fps=30, width=width, height=height,
                                       video_output=out / 'picture.mp4', managed_render=True))
        writejson(out / 'render-timing.json', dict(seconds=time.monotonic() - started,
                                                  frames=plan['frame_count'], engine='EEVEE',
                                                  samples=samples, width=width, height=height))


if __name__ == '__main__':
    main()
