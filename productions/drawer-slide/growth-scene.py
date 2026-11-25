"""Opening cutaway for the same Accuride 3832EDO assembly."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys

spec = spec_from_file_location("drawer_scene", Path(__file__).with_name("scene.py"))
drawer_scene = module_from_spec(spec)
sys.modules[spec.name] = drawer_scene
spec.loader.exec_module(drawer_scene)
from drawer_scene import camera, drawer_system, ease, move_slide, slide


def opening(cam, parts, shot, duration):
    _, side, drawer = drawer_system(parts)
    rails = [slide(parts), slide(parts, mirror=True)]
    side.hide_render = True
    for panel in side.children:
        panel.hide_render = True

    def pose(t):
        # Both sliding stages remain nested while their relative travels add.
        first = ease(t, .15, 2.20)
        second = ease(t, .65, 3.95)
        middle = 1.2 + 3.36 * first
        travel = middle + 1.2 + 3.36 * second
        close = ease(t, 4.15, duration - .40)
        # Track both overlaps, retaining an oak edge and the cabinet as reference.
        camera(cam, (-2.45 + .32 * travel + .50 * close, -2.35 - 1.4 * close, 2.88),
               (4.6 - 3.0 * close, -12, 3.65 - 2.0 * close), 19.4 - 3.9 * close)
        drawer.location.x = travel
        for rail in rails:
            move_slide(rail, travel, middle)
        return travel, middle, close

    return pose


if __name__ == "__main__":
    drawer_scene.full_scene = opening
    drawer_scene.main()
