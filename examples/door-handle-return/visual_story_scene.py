"""Direct a source-clock workprint from the existing cinematic teaching Blend."""

import argparse
import fcntl
from itertools import groupby
import json
from pathlib import Path
from types import SimpleNamespace
import sys

import bpy

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from cinematic_scene import budget, look, placement, render_chunked, ROOT, visible
from common import filehash, writejson


def time(source_index):
    return source_index / 30


def build_section(scene, objects):
    """Section the view of the shank and hub with the square spindle left intact."""
    lever = objects['Lever handle']
    bpy.ops.mesh.primitive_cube_add(size=2, location=(-1.06, -.6, 0))
    cutter = bpy.context.object
    cutter.name = 'Presentation cutter · shank and hub'
    cutter.parent = lever
    cutter.hide_render = True
    cutter.hide_set(True)
    cutter.display_type = 'WIRE'
    for name in ('Lever shank', '48 hub with actual square opening'):
        original = objects[name]
        section = original.copy()
        section.animation_data_clear()
        scene.collection.objects.link(section)
        section.name = name + ' · section'
        cut = section.modifiers.new('Presentation section', 'BOOLEAN')
        cut.operation, cut.object = 'DIFFERENCE', cutter
        visible(original, (0, True), (time(430), False), (time(900), True))
        visible(section, (0, False), (time(430), True), (time(900), False))


def reveal_cover(cover):
    """Wipe only the cover's opacity in place, with a shared world-space edge."""
    group = bpy.data.node_groups.new('Cover visibility across the face', 'ShaderNodeTree')
    group.interface.new_socket(name='Visible', in_out='OUTPUT', socket_type='NodeSocketFloat')
    nodes, links = group.nodes, group.links
    output = nodes.new('NodeGroupOutput')
    position = nodes.new('ShaderNodeNewGeometry')
    separate = nodes.new('ShaderNodeSeparateXYZ')
    links.new(position.outputs['Position'], separate.inputs[0])
    edge = nodes.new('ShaderNodeMath')
    edge.operation = 'SUBTRACT'
    links.new(separate.outputs['X'], edge.inputs[0])
    threshold = edge.inputs[1]
    for source, value in ((0, -2.4), (385, -2.4), (424, 2.4), (899, 2.4), (928, -2.4)):
        threshold.default_value = value
        threshold.keyframe_insert(data_path='default_value', frame=source + 1)
    transition = nodes.new('ShaderNodeMapRange')
    transition.inputs['From Min'].default_value = -.08
    transition.inputs['From Max'].default_value = .08
    links.new(edge.outputs[0], transition.inputs['Value'])
    links.new(transition.outputs[0], output.inputs['Visible'])
    for obj in cover.children:
        visible(obj, (0, True), (time(425), False), (time(900), True))
        material = obj.data.materials[0].copy()
        obj.data.materials[0] = material
        nodes, links = material.node_tree.nodes, material.node_tree.links
        surface = next(node for node in nodes if node.type == 'OUTPUT_MATERIAL').inputs['Surface']
        original = surface.links[0].from_socket
        mask = nodes.new('ShaderNodeGroup')
        mask.node_tree = group
        transparent = nodes.new('ShaderNodeBsdfTransparent')
        mixer = nodes.new('ShaderNodeMixShader')
        links.new(mask.outputs['Visible'], mixer.inputs[0])
        links.new(transparent.outputs[0], mixer.inputs[1])
        links.new(original, mixer.inputs[2])
        links.new(mixer.outputs[0], surface)


def direct(scene, edit):
    objects = scene.objects
    for name in ('Lever handle', '66 square drive spindle'):
        placement(objects[name], (0, (0, 0, 0)), (time(1214), (0, 0, 0)))
    cover = objects['58 cover plate']
    home = (0, 0, 0)
    placement(cover, (0, home), (time(1214), home))
    reveal_cover(cover)
    for name in ('Door panel with a through bore', 'Door stile', 'Door jamb', 'Door jamb shadow',
                 'Lever grip', '30 continuous wire arc spring'):
        visible(objects[name], (0, True))
    build_section(scene, objects)
    spec = edit['seat_fill']
    fill = look.area(scene, 'Spring seat fill', spec['position'], spec['target'],
                     spec['power'], spec['size'], spec['color'])
    start, end = spec['source']
    for source, power in ((start - 1, 0), (start, spec['power']),
                          (end - 1, spec['power']), (end, 0)):
        fill.data.energy = power
        fill.data.keyframe_insert(data_path='energy', frame=source + 1)

    scene.timeline_markers.clear()
    for shot in edit['shots']:
        camera = shot['camera']
        poses = [(source + 1, position, target) for source, position, target in camera['poses']]
        look.camera(scene, shot['id'], poses, lens=camera.get('lens', 50), ortho=camera.get('ortho'))
    scene.frame_start = 1
    scene.frame_end = edit['shots'][-1]['source'][1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('out', type=Path)
    parser.add_argument('--probes', type=int, nargs='+')
    parser.add_argument('--repair-only', action='store_true',
                        help='Render the changed source span for splicing into the bound workprint')
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    edit_path = HERE / 'visual_story.json'
    edit = json.loads(edit_path.read_text())
    with (ROOT / 'work/production.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        budget()
        scene = bpy.context.scene
        source = Path(bpy.data.filepath)
        direct(scene, edit)
        look.render_settings(scene, 'BLENDER_EEVEE', 768, 432, 8)
        scene.render.fps = 30
        selected = [index + 1 for shot in edit['shots'] for index in range(*shot['source'])]
        scene.frame_set(selected[0])
        scene.render.filepath = str(out / 'frame-')
        target = out / 'scene.blend'
        bpy.ops.wm.save_as_mainfile(filepath=str(target), compress=True)
        writejson(out / 'source-clock.json', {
            'fps': 30, 'blender_frame_base': 1, 'source_frames': selected,
            'source': {'path': str(source), 'sha256': filehash(source)},
            'scene_sha256': filehash(target), 'camera_config_sha256': filehash(edit_path),
        })
        if args.probes:
            for index in args.probes:
                scene.frame_set(index + 1)
                scene.render.filepath = str(out / f'probe-{index}.jpg')
                bpy.ops.render.render(write_still=True)
            return
        if args.repair_only:
            start, end = edit['seat_fill']['source']
            selected = [frame for frame in selected if start <= frame - 1 < end]
        scene.render.image_settings.file_format = 'PNG'
        # The encoder reads consecutive numbered PNGs. Split at source clock jumps.
        for _, block in groupby(enumerate(selected), key=lambda pair: pair[1] - pair[0]):
            frames = [source_frame for _, source_frame in block]
            folder = out / f'source-{frames[0]:04d}-{frames[-1]:04d}'
            folder.mkdir(exist_ok=True)
            chunks = SimpleNamespace(out=folder, chunk_frames=48, fps=30, width=768, height=432,
                                     video_output=folder / 'picture.mp4', managed_render=True)
            render_chunked(scene, frames, chunks)


if __name__ == '__main__':
    main()
