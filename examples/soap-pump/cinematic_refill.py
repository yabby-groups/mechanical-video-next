"""Photograph the previously sourced US5738250 refill stroke on its native clock."""
import fcntl
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import bpy

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'blender'), str(ROOT / 'scripts')]
import cinematic as look
from common import budget, filehash
from scene import render_chunked

out = Path(sys.argv[sys.argv.index('--') + 1]).resolve()
out.mkdir(parents=True, exist_ok=True)
source = Path(bpy.data.filepath)
with (ROOT / 'work/production.lock').open('a') as handle:
    fcntl.flock(handle, fcntl.LOCK_EX)
    budget()
    scene = bpy.context.scene
    for obj in list(scene.objects):
        if obj.type == 'LIGHT':
            bpy.data.objects.remove(obj, do_unlink=True)
    scene.timeline_markers.clear()
    frames = range(51, 250)
    poses = [
        (51, (-2.4, -14.7, 4.1), (-.16, 0, 2.59)),
        (130, (-.7, -14.1, 3.45), (-.12, 0, 3.05)),
        (249, (-.7, -14.1, 3.45), (-.12, 0, 3.05)),
    ]
    scene.camera = look.camera(scene, 'Refill stroke · 42 mm', poses, lens=42)
    lighting = [
        ('Warm softbox', (-4.3, -6.0, 8.3), (0, .25, 2.8), 2800, (5, 5.5), (1, .86, .70)),
        ('Cool outline', (4.2, 2, 6.1), (0, 0, 2.65), 2050, (3.4, 6), (.53, .79, 1)),
        ('Inlet bounce', (0, -6.2, .92), (0, 0, 1.2), 520, (5, 3), (.78, .89, 1)),
    ]
    for spec in lighting:
        look.area(scene, *spec)
    look.studio_world(scene, (.19, .25, .30), .36)
    metal = look.surface('Polished stainless', (.53, .63, .65), .76, .27,
                         grain=(70, 70, 13), bump=.001)
    plastic = look.surface('Molded satin polymer', (.22, .29, .29), .02, .35,
                           grain=(64, 64, 64), bump=.0015)
    for obj in scene.objects:
        if obj.name.startswith(('18 Inlet check ball', '39 Outlet check ball', '28 Compression spring')):
            look.assign(obj, metal)
        if obj.name.startswith(('11 Cylinder around chamber', '23 Collar and neck')):
            look.assign(obj, plastic)
    look.render_settings(scene, 'BLENDER_EEVEE', 768, 432, 10)
    scene.render.image_settings.file_format = 'PNG'
    names = ('Plunger head, hollow stem, piston and outlet', '18 Inlet check ball',
             '39 Outlet check ball in hollow stem', '28 Compression spring')
    evaluated = []
    for frame in frames:
        scene.frame_set(frame)
        evaluated.append([frame, *[
            [scene.objects[name].matrix_world.translation.z, scene.objects[name].scale.z]
            for name in names
        ]])
    scene.frame_start, scene.frame_end = frames.start, frames.stop - 1
    scene.frame_set(frames.start)
    output_scene = out / 'scene.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(output_scene), compress=True)
    (out / 'photography.json').write_text(json.dumps({
        'subject': 'US5738250 fig. 1 · partially sectioned teaching reconstruction',
        'source': str(source), 'source_sha256': filehash(source),
        'scene_sha256': filehash(output_scene), 'source_frames_half_open': [frames.start, frames.stop],
        'camera': poses, 'focal_length_mm': 42, 'lights': lighting, 'engine': scene.render.engine,
        'motion_objects': names, 'evaluated_z_and_scale': evaluated,
        'scope': 'Prescribed native stroke and valve motion with illustrative soap tracers.',
    }, indent=2) + '\n')
    render_chunked(scene, frames, SimpleNamespace(out=out, chunk_frames=36, fps=30,
                                                  width=768, height=432,
                                                  video_output=out / 'soap-pump-refill.mp4'))
