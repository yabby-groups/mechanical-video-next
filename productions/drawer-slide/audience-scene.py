"""Comparison and contact-point shots for the revised 3832EDO film."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

spec = spec_from_file_location("drawer_scene", Path(__file__).with_name("scene.py"))
drawer = module_from_spec(spec)
spec.loader.exec_module(drawer)

OPEN = 9.12
MID = OPEN / 2


def reveal_material(name, color):
    return drawer.material(name, color, .18, .34, glow=.48)


def front_line(z, finish, *, reach=5.7):
    drawer.pipe("Cabinet opening", ((0, -4.4, z), (0, 4.45, z)), .032, finish)
    for y in (-4.4, 4.45):
        drawer.pipe("Opening plane edge", ((0, y, z), (0, y, z + reach)), .034, finish)


def comparison(cam, parts, duration):
    guide = reveal_material("Cabinet front witness", (.13, .72, .87))
    payload = reveal_material("Object in the rear compartment", (.84, .20, .055))

    def example(z, full):
        root = drawer.group("Three members" if full else "Two members", (0, 0, z))
        cabinet, side, box = drawer.drawer_system(parts)
        side.location.z = 11
        cabinet.parent = box.parent = root
        for name in ("Countertop", "Far cabinet side"):
            drawer.bpy.data.objects[name if full else f"{name}.001"].hide_render = True
        drawer.bead("Rear object", (-8.08, -.70, 3.47), .57, payload, box)
        if full:
            rail = drawer.slide(parts)
            rail[0].parent.parent = root
            set_rail = lambda travel: drawer.move_slide(rail, travel, travel / 2)
        else:
            fixed = drawer.group("Fixed two-member guide", (0, -drawer.CABINET_Y, drawer.RAIL_Z), root)
            moving = drawer.group("Moving two-member guide", (0, -drawer.CABINET_Y, drawer.RAIL_Z), root)
            drawer.channel("Fixed channel", drawer.OUTER, drawer.LENGTH, parts["outer"], fixed)
            drawer.channel("Moving channel", drawer.MIDDLE, drawer.LENGTH, parts["inner"], moving)

            def set_rail(travel):
                moving.location.x = travel

        front_line(z + .73, guide, reach=4.25)
        drawer.pipe("Cabinet front reference", ((0, -4.4, z + .73), (0, -4.4, z + 4.98)),
                    .072, guide)
        return box, set_rail

    lower, lower_rail = example(0, True)
    upper, upper_rail = example(6.15, False)

    overlap = reveal_material("Remaining two-member overlap", (1.0, .54, .08))
    still_nested = drawer.pipe("Two-member overlap at the stop",
                              ((MID - drawer.LENGTH, -4.56, 8.79), (0, -4.56, 8.79)),
                              .045, overlap)
    extra_stage = drawer.pipe("Exposed intermediate member at the stop",
                              ((0, -4.52, 2.76), (MID, -4.52, 2.76)),
                              .043, reveal_material("Intermediate rail witness", (.82, .89, 1.0)))

    def pose(t):
        first_stage = drawer.ease(t, .26, 2.0)
        second_stage = drawer.ease(t, 2.40, 4.48)
        top = MID * first_stage
        bottom = MID * (first_stage + second_stage)
        upper.location.x, lower.location.x = top, bottom
        upper_rail(top)
        lower_rail(bottom)
        still_nested.hide_render = not 6.88 <= t < 10.23
        extra_stage.hide_render = t < 10.23
        detail = drawer.ease(t, 8.7, 13.20)
        drawer.camera(cam, (-.32 + .80 * detail, -.35 * detail, 5.78),
                      (1.8 - .85 * detail, -14, 4.25 - .95 * detail), 24.9 - 2.2 * detail)
        return top, bottom, detail, still_nested.hide_render, extra_stage.hide_render

    return pose


def velocity_diagram(cam, parts, duration):
    orange = reveal_material("Center translation", (.97, .39, .07))
    green = reveal_material("Rotation at the contact", (.22, .79, .39))
    white = reveal_material("Velocity of the moving race", (.80, .92, 1.0))
    radius, x0, z = .68, -1.72, 2.7
    lower, upper = z - radius, z + radius
    ball = drawer.group("Bearing", (x0, 0, z))
    drawer.bead("Bearing section", (0, 0, 0), radius, orange, ball)
    drawer.bead("Rotation witness", (.34, -.54, .26), .057, parts["fastener"], ball)
    drawer.block("Fixed lower race", (0, 0, lower - .13), (8.1, .72, .26), parts["outer"])
    silver = drawer.group("Moving upper race")
    drawer.block("Upper race", (-1.66, 0, upper + .13), (5.9, .72, .26),
                 parts["middle"], silver)
    drawer.block("Moving race index", (-1.72, -.38, upper + .13), (.084, .025, .22), white, silver)

    def arrow(name, x, height, length, finish):
        node = drawer.group(name)
        end = x + length
        direction = 1 if length > 0 else -1
        drawer.pipe(name, ((x, -.84, height), (end - direction * .10, -.84, height)), .035,
                    finish, node)
        drawer.surface(name + " tip", ((end, -.84, height),
                       (end - direction * .18, -.84, height + .092),
                       (end - direction * .18, -.84, height - .092)), ((0, 1, 2),), finish, node)
        return node

    center = arrow("Center translation", .79, z, .71, orange)
    top = (arrow("Top translation", .79, upper + .61, .71, orange),
           arrow("Top rotation", 1.59, upper + .61, .71, green))
    bottom = (arrow("Bottom translation", .79, lower - .59, .71, orange),
              arrow("Bottom rotation", 1.50, lower - .85, -.71, green))
    contacts = []
    for name, height, color in (("Upper contact", upper, (.66, .88, 1.0)),
                                ("Lower contact", lower, (.16, .66, 1.0))):
        finish = reveal_material(name, color)
        dot = drawer.bead(name + " witness", (x0, -.77, height), .089, finish)
        stem = drawer.pipe(name + " projection", ((0, 0, height), (0, -.77, height)),
                           .025, finish)
        contacts.append((dot, stem))

    def pose(t):
        dx = 1.36 * drawer.ease(t, 3.1, 6.1)
        ball.location.x = x0 + dx
        ball.rotation_euler.y = dx / radius
        silver.location.x = 2 * dx
        for nodes, threshold in (((center,), 3.1), (top, 5.15), (bottom, 8.25)):
            for node in nodes:
                for obj in node.children:
                    obj.hide_render = t < threshold
        for (dot, stem), threshold in zip(contacts, (5.15, 8.25)):
            dot.location.x = stem.location.x = x0 + dx
            dot.hide_render = stem.hide_render = t < threshold
        drawer.camera(cam, (.16, 0, 2.80), (0, -13, 0), 8.7)
        return dx, t >= 5.15, t >= 8.25

    return pose


def revised_scene(cam, parts, shot, duration):
    return {0: comparison, 1: velocity_diagram}[shot](cam, parts, duration)


if __name__ == "__main__":
    drawer.full_scene = revised_scene
    drawer.main()
