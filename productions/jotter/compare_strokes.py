"""Matched strokes on the original explanatory Jotter geometry."""
from pathlib import Path
import sys

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scene import PI, animate_pen, camera, material, pen, setup, track


def render(destination):
    destination.mkdir(parents=True, exist_ok=True)
    for extended in (False, True):
        scene, view = setup(1)
        scene.render.resolution_percentage = 34
        scene.render.image_settings.file_format = 'JPEG'
        palette = (
            material('Forest green', (.026, .23, .116), .15),
            material('Satin steel', (.52, .61, .63), .81),
            material('Refill', (.11, .15, .16), .35),
            material('Plunger', (.78, .71, .50)),
            material('Cam', (.84, .275, .033)),
            material('Guide', (.045, .34, .66)),
            material('Ink', (.013, .045, .22)),
        )
        parts = pen(palette, cut=True)
        rotation = PI / 2 if extended else 0
        for frame in range(0, 150, 3):
            time = frame / 30
            stroke = track(time, [(0, 0), (.22, 0), (.75, .49), (.98, .49), (1.55, 0)])
            offset = track(time, [(0, .27 if extended else 0), (.22, .27 if extended else 0),
                                  (.75, .49), (.98, .49), (1.55, 0 if extended else .27)])
            angle = rotation + track(time, [(0, 0), (.61, 0), (.75, PI / 4),
                                             (.98, PI / 4), (1.4, PI / 2)])
            animate_pen(parts, offset, stroke, angle)
            close = time < 2.85
            camera(view, (4.65 if close else -5.85, 0, 0), (.2, -1, .8),
                   3.6 if close else 2.7)
            scene.render.filepath = str(destination / f'{int(extended)}-{frame // 3:03}.jpg')
            bpy.ops.render.render(write_still=True)


if __name__ == '__main__':
    render(Path(sys.argv[sys.argv.index('--') + 1]).resolve())
