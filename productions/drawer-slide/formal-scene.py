"""New Blender shots for the full-length 3832EDO explanation."""

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

        front_line(z + .73, guide, reach=3.8)
        return box, set_rail

    lower, lower_rail = example(0, True)
    upper, upper_rail = example(6.15, False)

    def pose(t):
        top = MID * drawer.ease(t, 2.9, 5.18)
        bottom = OPEN * drawer.ease(t, 7.8, min(duration - .5, 12.0))
        upper.location.x, lower.location.x = top, bottom
        upper_rail(top)
        lower_rail(bottom)
        drawer.camera(cam, (-.32, 0, 5.78), (1.8, -14, 4.25), 24.9)
        return top, bottom

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
        drawer.pipe(name, ((x, -.84, height), (end - direction * .10, -.84, height)), .024,
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
    contact = drawer.bead("Fixed contact at end of movement", (x0 + 1.36, -.49, lower),
                          .073, white)

    def pose(t):
        dx = 1.36 * drawer.ease(t, 3.1, 6.1)
        ball.location.x = x0 + dx
        ball.rotation_euler.y = dx / radius
        silver.location.x = 2 * dx
        for nodes, threshold in (((center,), 3.1), (top, 5.15), (bottom, 8.25)):
            for node in nodes:
                for obj in node.children:
                    obj.hide_render = t < threshold
        contact.hide_render = t < 8.25
        drawer.camera(cam, (.16, 0, 2.80), (0, -13, 0), 8.7)
        return dx, t >= 5.15, t >= 8.25

    return pose


def reassemble(cam, parts, duration):
    parts["cage"] = reveal_material("Visible retainer", (.09, .73, .43))
    _, side, box = drawer.drawer_system(parts)
    side.location.z = 10
    drawer.bpy.data.objects["Countertop"].hide_render = True
    rails = [drawer.slide(parts, mirror=mirror) for mirror in (False, True)]
    guide = reveal_material("Inner-member entry", (.98, .48, .07))
    for rail in rails:
        middle, inner, cages = rail
        drawer.block("Drawer-member alignment index", (-8.91, .052, .027),
                     (.09, .16, .17), guide, inner)
        drawer.block("Intermediate-member alignment index", (-.06, .093, .025),
                     (.09, .065, .18), guide, middle)

    def pose(t):
        forward = drawer.ease(t, 3.72, 6.45)
        enter = drawer.ease(t, 7.35, 9.75)
        shut = drawer.ease(t, 10.55, 12.08)
        reopen = drawer.ease(t, 12.70, duration - .30)
        travel = (OPEN + MID + .25) * (1 - enter) + OPEN * (enter - shut + reopen)
        middle_travel = MID * (1 - shut + reopen)
        box.location.x = travel
        for rail in rails:
            drawer.move_slide(rail, travel, middle_travel)
            prepared_cage = middle_travel - 2.85 + 1.12 * forward
            rail[2][1].location.x = prepared_cage * (1 - enter) + rail[2][1].location.x * enter
        closeup = drawer.ease(t, 2.75, 3.65) - drawer.ease(t, 6.35, 7.30)
        drawer.camera(cam, (3.0 - 3.4 * shut + 2.8 * reopen - .60 * closeup,
                            .3 - 4.08 * closeup, 2.78 + .24 * closeup),
                      (1.6, -9.8, 9.0 - 5.75 * closeup), 27.3 - 20.2 * closeup)
        return forward, enter, shut, reopen, closeup

    return pose


def recap(cam, parts, duration):
    _, side, box = drawer.drawer_system(parts)
    side.location.z = 10
    rails = [drawer.slide(parts, mirror=mirror) for mirror in (False, True)]
    rear = reveal_material("Object behind the cabinet opening", (.93, .27, .07))
    witness = reveal_material("Cabinet opening line", (.18, .77, .87))
    drawer.bead("Rear object", (-8.08, -1.15, 3.21), .46, rear, box)
    front_line(.71, witness, reach=4.1)
    markers = []
    for left, right, height, key in ((MID - drawer.LENGTH, 0, 2.23, "outer"),
                                     (OPEN - drawer.LENGTH, MID, 1.91, "inner")):
        marker = drawer.group("Remaining contact span")
        drawer.pipe("Overlap", ((left, -4.81, height), (right, -4.81, height)),
                    .045, parts[key], marker)
        for x in (left, right):
            drawer.pipe("Overlap end", ((x, -4.81, height - .10), (x, -4.81, height + .16)),
                        .043, parts[key], marker)
        markers.extend(marker.children)

    def pose(t):
        first = drawer.ease(t, .12, 1.39)
        second = drawer.ease(t, 1.45, 3.38)
        travel = MID * (first + second)
        box.location.x = travel
        for rail in rails:
            drawer.move_slide(rail, travel, MID * first)
        read = drawer.ease(t, 7.85, 9.25)
        for obj in markers:
            obj.hide_render = t < 8.2
        drawer.camera(cam, (-3.45 + travel * .45, -.3 - read * 1.35, 2.8),
                      (3.9 - read * 2.6, -12, 5.1 - read * 3.5), 22.5 - read * 3.6)
        return first, second, read, t >= 8.2

    return pose


def full_scene(cam, parts, shot, duration):
    return {0: comparison, 1: velocity_diagram, 2: reassemble}[shot](cam, parts, duration)


if __name__ == "__main__":
    drawer.full_scene = full_scene
    drawer.macro_scene = recap
    drawer.main()
