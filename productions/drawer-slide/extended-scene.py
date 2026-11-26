"""Follow the bearing retainer, then compare the motion of one ball and its race."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

spec = spec_from_file_location("drawer_scene", Path(__file__).with_name("scene.py"))
drawer = module_from_spec(spec)
spec.loader.exec_module(drawer)

LENGTH = 2.4
Y = -drawer.CABINET_Y


def roll(rail, outer_slip, inner_slip):
    drawer.move_slide(rail, outer_slip + inner_slip, outer_slip, LENGTH)
    for cage, slip in zip(rail[2], (outer_slip, inner_slip), strict=True):
        for ball in cage.children:
            if ball.type == "EMPTY":
                sign = -1 if ball.location.z > 0 else 1
                ball.rotation_euler.y = sign * slip / (2 * drawer.BALL_RADIUS)


def retainer_scene(cam, parts, _shot, _duration):
    parts["cage"] = drawer.material("Green retainer identification tint",
                                    (.10, .66, .46), .23, .38, glow=.14)
    rail = drawer.slide(parts, LENGTH, macro=True)

    def pose(t):
        inspect = drawer.ease(t, .12, 3.30)
        slide = (1 - drawer.ease(t, 4.05, 7.18)
                 + drawer.ease(t, 7.65, 9.30) - drawer.ease(t, 9.47, 11.11))
        roll(rail, .19 + .21 * slide, .14 + .23 * slide)
        drawer.camera(cam, (-.87 + inspect * .14, Y + .11, 2.99),
                      (1.22 - inspect * 1.13, -10.4, .64 - inspect * .41),
                      3.49 - inspect * .29)
        return inspect, slide

    return pose


def ratio_scene(cam, parts, _duration):
    rail = drawer.slide(parts, LENGTH, macro=True)
    middle, inner, (cage, inner_cage) = rail
    for node in (inner, inner_cage):
        for obj in node.children_recursive:
            obj.hide_render = True

    tracked_ball = max((obj for obj in cage.children
                        if obj.type == "EMPTY" and obj.location.z < 0),
                       key=lambda obj: obj.location.x)
    x0 = cage.location.x + tracked_ball.location.x
    step = .30
    ruler_y = Y - .09
    ball_z = drawer.RAIL_Z + tracked_ball.location.z
    ruler_finish = drawer.material("Fixed scale", (.44, .66, .78), .12, glow=.21)
    ball_finish = drawer.material("Tracked ball and pointer", (1.0, .44, .09),
                                  .45, glow=.32)
    rail_finish = drawer.material("Silver rail pointer", (.80, .93, 1.0), .18, glow=.70)
    sphere = next(obj for obj in tracked_ball.children if obj.name.startswith("Steel sphere"))
    sphere.data.materials[0] = ball_finish

    def ruler(z, direction, name, color):
        drawer.pipe(name + " baseline", ((x0 - .07, ruler_y, z),
                    (x0 + 2 * step + .07, ruler_y, z)), .009, ruler_finish)
        for i in range(3):
            x = x0 + step * i
            drawer.pipe(name + " tick", ((x, ruler_y, z),
                        (x, ruler_y, z + direction * .072)), .010, ruler_finish)
        marker = drawer.group(name + " follower")
        drawer.surface(name + " arrowhead",
                       ((x0, ruler_y - .025, z + direction * .010),
                        (x0 - .038, ruler_y - .025, z - direction * .062),
                        (x0 + .038, ruler_y - .025, z - direction * .062)),
                       ((0, 1, 2),), color, marker)
        return marker

    rail_pointer = ruler(3.55, 1, "Rail displacement", rail_finish)
    ball_pointer = ruler(2.47, -1, "Ball displacement", ball_finish)
    # One witness stays with the silver rail, the other sits on the ball's centerline.
    drawer.pipe("Silver rail witness", ((x0, ruler_y - .02, 3.50),
                 (x0, Y + drawer.section_y(326), 3.34)), .011, rail_finish, rail_pointer)
    drawer.pipe("Ball center witness", ((x0, ruler_y - .02, 2.52),
                 (x0, Y + tracked_ball.location.y - drawer.BALL_RADIUS, ball_z - .04)),
                .010, ball_finish, ball_pointer)

    def pose(t):
        travel = (drawer.ease(t, 2.54, 4.24) - drawer.ease(t, 4.84, 5.90)
                  + drawer.ease(t, 6.06, 8.18)) * (2 * step)
        roll(rail, travel, 0)
        rail_pointer.location.x = middle.location.x
        ball_pointer.location.x = cage.location.x + tracked_ball.location.x - x0
        drawer.camera(cam, (-.61, Y, 3.03), (0, -10, .22), 3.63)
        return travel

    return pose


if __name__ == "__main__":
    drawer.full_scene = retainer_scene
    drawer.macro_scene = ratio_scene
    drawer.main()
