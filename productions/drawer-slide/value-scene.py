"""Make both overlaps visible while the recognizable drawer is still moving."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

spec = spec_from_file_location("drawer_support", Path(__file__).with_name("support-scene.py"))
support = module_from_spec(spec)
spec.loader.exec_module(support)


def opening(cam, parts, shot, duration):
    base = support.growth.opening(cam, parts, shot, duration + .65)
    blue = support.material("Fixed overlap", (.13, .76, 1.0), glow=.6)
    gold = support.material("Moving overlap", (1.0, .54, .08), glow=.6)
    fixed = support.overlap_marker("Fixed and middle rails", 2.58, blue)
    moving = support.overlap_marker("Middle and drawer rails", 2.58, gold)

    def pose(t):
        travel, middle, close = base(t + .65)
        fixed(middle - support.LENGTH, 0, True)
        moving(travel - support.LENGTH, middle, True)
        return travel, middle, close, True, True

    return pose


if __name__ == "__main__":
    support.growth.drawer_scene.full_scene = opening
    support.growth.drawer_scene.main()
