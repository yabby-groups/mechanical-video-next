"""Geometric reconstruction of the TR1278B lift, with editorial cutaways."""

import argparse
import json
import math
from pathlib import Path
import random
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "quarter-turn-faucet"))
from scene import bevel, block, camera, cylinder, ease, group, material, pipe, setup, show_tree, surface

TRAVEL = 1.06
SLOTS = (-.62, .62)


def rounded_rectangle(width, length, radius):
    return [
        (x + radius * math.cos(angle + math.pi * i / 16),
         y + radius * math.sin(angle + math.pi * i / 16))
        for x, y, angle in (
            (width / 2 - radius, length / 2 - radius, 0),
            (-width / 2 + radius, length / 2 - radius, math.pi / 2),
            (-width / 2 + radius, -length / 2 + radius, math.pi),
            (width / 2 - radius, -length / 2 + radius, 3 * math.pi / 2),
        )
        for i in range(9)
    ]


def case_wall(parent, finish):
    rings = [(0.33, 2.83, 4.18, .89), (.52, 2.94, 4.32, .97),
             (2.33, 2.9, 4.25, .92), (2.63, 2.65, 4.0, .8)]
    vertices = [(x, y, z) for z, w, l, r in rings for x, y in rounded_rectangle(w, l, r)]
    cols = len(vertices) // len(rings)
    faces = [(row * cols + i, row * cols + (i + 1) % cols, (row + 1) * cols + (i + 1) % cols,
              (row + 1) * cols + i) for row in range(len(rings) - 1) for i in range(cols)]
    obj = surface("Gloss black housing", vertices, faces, finish, parent, smooth=True)
    obj.modifiers.new("Shell thickness", "SOLIDIFY").thickness = .035


def toast(parent, x, finish, crust, seed):
    shape = [(-1.06,0), (1.06,0), (1.15,.13), (1.15,.98), (1.29,1.11),
             (1.23,1.33), (.99,1.49), (.47,1.60), (0,1.65), (-.47,1.60), (-.99,1.49),
             (-1.23,1.33), (-1.29,1.11), (-1.15,.98), (-1.15,.13)]
    vertices = [(x + side*.14, y, z) for side in (-1, 1) for y, z in shape]
    n = len(shape)
    faces = [tuple(reversed(range(n))), tuple(range(n, 2*n))]
    faces += [(i, (i+1)%n, (i+1)%n+n, i+n) for i in range(n)]
    bread = surface("Toast slice", vertices, faces, finish, parent)
    bevel(bread, .055)
    bread.data.materials.append(crust)
    for polygon in bread.data.polygons[2:]:
        polygon.material_index = 1
    texture = finish.node_tree
    shader = texture.nodes.get("Principled BSDF")
    if not texture.nodes.get("Crumb"):
        coord = texture.nodes.new("ShaderNodeTexCoord")
        noise = texture.nodes.new("ShaderNodeTexNoise")
        noise.name = "Crumb"
        noise.inputs["Scale"].default_value = 32
        noise.inputs["Detail"].default_value = 4
        texture.links.new(coord.outputs["Object"], noise.inputs["Vector"])
        ramp = texture.nodes.new("ShaderNodeValToRGB")
        ramp.color_ramp.elements[0].position = .24
        ramp.color_ramp.elements[0].color = (.24,.082,.017,1)
        ramp.color_ramp.elements[1].position = .74
        ramp.color_ramp.elements[1].color = (.92,.58,.26,1)
        texture.links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
        texture.links.new(ramp.outputs[0], shader.inputs["Base Color"])
        bump = texture.nodes.new("ShaderNodeBump")
        bump.inputs["Strength"].default_value = .52
        bump.inputs["Distance"].default_value = .055
        texture.links.new(noise.outputs["Fac"], bump.inputs["Height"])
        texture.links.new(bump.outputs[0], shader.inputs["Normal"])
    rng = random.Random(seed)
    points = []
    faces = []
    for _ in range(65):
        y = rng.uniform(-1.02,1.02)
        z = rng.uniform(.1,1.32)
        side = -1 if rng.random() < .5 else 1
        radius = rng.uniform(.009,.028)
        first = len(points)
        points.extend((x + side*.141, y+radius*math.cos(i*math.tau/6), z+.024+radius*.66*math.sin(i*math.tau/6))
                      for i in range(6))
        faces.append(tuple(range(first,first+6)))
    surface("Shaded crumb pores",points,faces,crust,parent)


def build(shot):
    scene, cam = setup(shot)
    scene.eevee.taa_render_samples = 6
    scene.eevee.shadow_ray_count = 1
    black = material("Gloss black", (.022,.027,.034), .12,.28)
    steel = material("Brushed stainless", (.51,.58,.62), .72,.28)
    wire = material("Spring steel", (.63,.68,.71), .74,.24)
    inner = material("Frame steel", (.19,.23,.26), .54,.34)
    ivory = material("Slider polymer", (.83,.58,.35), .04,.33)
    bread = material("Toasted crumb", (.69,.43,.14), 0,.79)
    crust = material("Golden crust", (.29,.098,.025), 0,.73)
    stone = material("Blue grey counter", (.062,.13,.155), 0,.58)
    glow = material("Heating element off", (.17,.045,.012), .31,.52)
    block("Counter", (0,0,-.8), (200,200,.2), stone, edge=0)

    shell = group("Removable housing")
    front = group("Front trim")
    frame = group("Heating chassis")
    top = group("Slotted top")
    slider = group("Guided carriage and toast")
    knob = group("Lever grip", parent=slider)
    tray = group("Crumb tray hinge", (0,1.59,.32))

    case_wall(shell, black)
    block("Bottom rim", (0,0,.31), (2.75,4.01,.21), black, edge=.2)
    for x in (-1.02,1.02):
        for y in (-1.51,1.51):
            block("Foot", (x,y,.16), (.35,.39,.16), black, edge=.07)
    for x,w in ((-1.14,.43),(0,.39),(1.14,.43)):
        block("Top slot surround", (x,0,2.64), (w,3.16,.12), steel, top, .045)
    for y in (-1.71,1.71):
        block("Top slot bridges", (0,y,2.64), (2.59,.43,.12), steel, top, .12)
    for x in SLOTS:
        for side in (-1,1):
            xx = x + side*.35
            block("Heater backing", (xx,0,1.50), (.045,3.04,1.90), inner, frame)
            for rung in range(8):
                z = .69 + .224*rung
                pipe("Heating ribbon", [(xx-side*.03,-1.4,z),(xx-side*.03,1.4,z)], .013, glow, frame)
            for y in (-1.36,-.97,-.58,-.19,.19,.58,.97,1.36):
                pipe("Bread guide", [(xx-side*.055,y,.56),(xx-side*.12,y,1.36),
                                     (xx-side*.12,y,2.34),(xx-side*.04,y,2.53)], .019, wire, frame)
        block("Toast support rail", (x,0,1.79), (.40,3.08,.07), steel, slider)
        block("Support arm into carriage", (x,-1.64,1.78), (.27,.45,.11), ivory, slider)
        slice_root = group("Bread resting on support", (0,0,1.825), slider)
        toast(slice_root,x,bread,crust,42+int(x>0))
    block("Crossbar joining both supports", (0,-1.78,1.80), (1.61,.20,.15), ivory, slider)
    for x in (-.73,.73):
        block("Stamped end wall", (x,-1.63,1.49), (.60,.065,2.09), inner, frame, .055)
        block("Pressed reinforcement", (x,-1.675,1.47), (.25,.043,1.65), steel, frame, .026)
    block("Guide rail fixed to chassis", (0,-1.82,1.53), (.088,.088,1.96), steel)
    for x in (-.17,.17):
        block("Open-sided carriage", (x,-1.91,1.79), (.23,.23,.34), ivory, slider, .055)
    block("Moving spring attachment", (0,-1.96,1.97), (.17,.13,.09), ivory, slider, .024)
    block("Fixed spring attachment", (0,-1.97,2.48), (.19,.145,.08), steel)
    spring = pipe("Upper extension spring", [(0,0,0)]*161, .0215, wire)
    lower = pipe("Lower spring in guide", [(0,0,0)]*161, .016, inner)
    block("Handle stem passing through front", (0,-2.11,1.78), (.10,.48,.10), inner, slider)
    block("Handle grip", (0,-2.39,1.78), (.59,.28,.17), black, knob, .063)

    for x in (-.39,.39):
        block("Brushed front trim", (x,-1.987,1.48), (.64,.13,2.12), steel, front, .082)
    block("Bottom control bridge", (0,-2.057,.69), (1.22,.126,.52), steel, front, .05)
    dial_parent = group("Browning dial axis", (0,-2.18,.66), front)
    dial_parent.rotation_euler.x = math.pi/2
    cylinder("Browning dial", .21,.14,0,black,dial_parent,edge=.022)
    block("Dial index", (0,-2.259,.786), (.028,.015,.092), steel, front, .007)
    for x in (-.41,.41):
        button = group("Cancel button" if x > 0 else "Control button", (x,-2.15,.70), front)
        button.rotation_euler.x = math.pi/2
        cylinder("Button", .088,.09,0,black,button,edge=.014)
    block("Crumb door", (0,-1.52,.014), (1.89,3.06,.055), steel, tray, .029)
    for x in (-.91,.91):
        block("Tray turned edge", (x,-1.52,.076), (.047,3.03,.08), inner,tray,.017)
    block("Crumb door tab", (0,-3.05,.063), (.44,.23,.09), black,tray,.028)
    rng = random.Random(54)
    for n in range(28):
        x, y = rng.uniform(-.82,.82), rng.uniform(-2.92,-.13)
        size = rng.uniform(.026,.09)
        crumb = block("Crumb", (x,y,.049), (size,size*.8,size*.62), crust,tray,size*.18)
        crumb.rotation_euler.z = rng.random()*math.tau

    def helix(obj, start, end, radius):
        for i, point in enumerate(obj.data.splines[0].points):
            p = i/160
            angle = p*math.tau*10
            point.co = (radius*math.cos(angle), -1.978+radius*math.sin(angle),
                        start+(end-start)*p, 1)

    def pose(t, duration):
        p = t/duration
        d = 0
        shell.location = (0,0,0)
        front.location = (0,0,0)
        tray.rotation_euler.x = 0
        show_tree(shell, shot in (0,1,5,6))
        show_tree(front, shot in (0,1,5,6))
        show_tree(top, shot in (0,1,5,6))
        glow.node_tree.nodes["Principled BSDF"].inputs["Emission Color"].default_value = (1,.20,.03,1)
        heat = 0
        if shot == 0:
            # The opening immediately relates the moving support to the bread.
            show_tree(shell, p >= .48)
            show_tree(front, p >= .48)
            show_tree(top, p >= .48)
            show_tree(frame, p >= .48)
            if p < .48:
                d = 1-ease(t,.18,.73)
                camera(cam,(0,-.24,2.04),(5,-7,3.6),7.0-.15*ease(t,.7,3))
            else:
                d = 1-ease(t,.48*duration+.16,.48*duration+.57)
                camera(cam,(0,0,1.88),(5.2,-7,4.0),6.15-.20*ease(p,.5,1))
        elif shot == 1:
            separation = ease(p,.02,.30)
            shell.location = (3.42*separation,.2*separation,.52*separation)
            front.location = (3.42*separation,.2*separation,.52*separation)
            top.location = shell.location
            show_tree(shell, p < .34)
            show_tree(front, p < .34)
            show_tree(top, p < .34)
            show_tree(frame, p < .45)
            d = ease(p,.73,.87)
            camera(cam,(.7*math.sin(math.pi*separation),-.17,1.95-.24*d),
                   (4.8-2*separation,-7,4.1+1.1*separation),6.66+.69*math.sin(math.pi*separation))
        elif shot == 2:
            d = ease(p,.08,.43)
            heat = ease(p,.63,.84)*.45
            camera(cam,(0,-1.63,1.75-.42*d),(2.35-1.9*p,-8,2.3-.9*p),4.53-.43*p)
        elif shot == 3:
            d = 1-ease(p,.31,.73)
            show_tree(frame, False)
            camera(cam,(-.03,-.68,1.73+.47*(1-d)),(4.5-1.9*p,-7,2.0+2.3*p),7.0-.13*p)
        elif shot == 5:
            d = 1-ease(t,4.25,4.70) if t < 6.58 else 1-ease(t,8.23,8.68)
            heat = .28*d
            cancel = t >= 6.58
            if cancel:
                button.location.y = -2.15+.071*(ease(t,7.91,8.21)-ease(t,8.31,8.49))
                camera(cam,(.17,-1.0,1.71),(1.98,-7,2.45),6.15)
            else:
                camera(cam,(0,-.25,1.64+.22*(1-d)),(4,-7,3.2),6.18)
        elif shot == 6:
            tray.rotation_euler.x = .83*(ease(p,.27,.48)-ease(p,.78,.97))
            cam_target = (0,-.41,.84-.60*ease(p,.13,.55))
            camera(cam,cam_target,(4.4-1.4*p,-6.4,-1.4-1.65*ease(p,.13,.53)),7.03-.43*p)
            # The service view exposes the base and the door's inner face.
            bpy.data.objects["Counter"].hide_render = True
        else:
            show_tree(frame, False)
            d = ease(p,.10,.25)-ease(p,.54,.60)
            camera(cam,(0,-.18,1.87+.29*(1-d)),(5.5-3.0*p,-7,3.6+1.1*p),7.05-.15*p)
        slider.location.z = -TRAVEL*d
        helix(spring,1.99-TRAVEL*d,2.455,.072)
        helix(lower,.38,1.79-TRAVEL*d,.055)
        glow.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"].default_value = heat
    return scene, pose


def check_lift(check, scene, pose, count, *, cancel=None):
    from episode_mechanics import position, require_range, surface_hit

    objects = scene.objects
    slider = objects["Guided carriage and toast"]
    guide = objects["Guide rail fixed to chassis"]
    spring = objects["Upper extension spring"]
    moving = objects["Moving spring attachment"]
    fixed = objects["Fixed spring attachment"]
    rails = sorted((obj for obj in slider.children if obj.name.startswith("Toast support rail")),
                   key=lambda obj: obj.location.x)
    slices = []

    def contact(depsgraph, loaf, rail):
        x, y, z = position(rail, depsgraph)
        top = surface_hit(rail, depsgraph, (x, y, z + .2), (0, 0, -1)).z
        bottom = surface_hit(loaf, depsgraph, (x, y, z - .2), (0, 0, 1)).z
        return require_range('Bread / rail signed gap', bottom - top, -.002, .002)

    def model(depsgraph):
        bread = [obj for obj in slider.children_recursive if obj.name.startswith("Toast slice")]
        if len(bread) != 2 or len(rails) != 2 or guide.type != 'MESH':
            raise ValueError('Both bread supports, slices and the fixed guide must be present')
        for rail in rails:
            # Pair by the actual slice center in the slide, regardless of object name suffix.
            x = position(rail, depsgraph).x
            loaf = min(bread, key=lambda obj: abs(x - sum(
                (obj.evaluated_get(depsgraph).matrix_world @ corner).x
                for corner in map(Vector, obj.evaluated_get(depsgraph).bound_box)) / 8))
            bread.remove(loaf)
            contact(depsgraph, loaf, rail)
            slices.append(loaf)

    pressed = False

    def measure(depsgraph):
        nonlocal pressed
        x, y, z = position(slider, depsgraph)
        require_range('Carriage off vertical axis', math.hypot(x, y), 0, .0001)
        require_range('Carriage stroke', z, -TRAVEL - .0001, .0001)
        require_range('Carriage tilt', slider.evaluated_get(depsgraph).matrix_world.to_quaternion().angle, 0, .001)
        gaps = [contact(depsgraph, loaf, rail) for loaf, rail in zip(slices, rails, strict=True)]
        coil = spring.evaluated_get(depsgraph)
        endpoints = coil.data.splines[0].points
        lower, upper = (coil.matrix_world @ endpoints[i].co.to_3d() for i in (0, -1))
        # The modeled coils stop inside the two mounting tabs.
        for point, tab in ((lower, moving), (upper, fixed)):
            offset = point - position(tab, depsgraph)
            require_range('Spring anchor height', abs(offset.z), 0, .027)
            require_range('Spring anchor lateral placement', offset.length, 0, .081)
        values = {'carriage_z': z, 'spring_length': upper.z - lower.z, 'bread_gap': max(map(abs, gaps))}
        if cancel is not None:
            button = position(cancel, depsgraph).y + 2.276
            # Second lift is a separate take that starts with the carriage held down.
            if scene.frame_current_final / 30 >= 6.58:
                pressed |= button >= .043
                if z > -TRAVEL + .008 and not pressed:
                    raise ValueError('Carriage rises before the visible cancel press')
            values['cancel_travel'] = button
        return values

    return check(scene, pose, count, measure, model=model, substeps=4)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--timing", type=Path, required=True)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--shot", type=int, choices=(0,1,2,3,5,6,7), required=True)
    parser.add_argument("--preview", action="store_true")
    args = parser.parse_args(sys.argv[sys.argv.index("--")+1:])
    count = json.loads(args.timing.read_text())[args.shot]
    scene, pose = build(args.shot)
    scene.render.resolution_percentage = 35 if args.preview else 100
    if 'check_mechanics' in globals() and check_lift(
            check_mechanics, scene, lambda t: pose(t, count / 30), count):
        return
    folder = args.directory / f"shot-{args.shot}"
    folder.mkdir(parents=True, exist_ok=True)
    for frame in range(0,count,6 if args.preview else 1):
        path = folder / f"{frame:05}.jpg"
        if not path.is_file():
            scene.frame_set(frame)
            pose(frame / 30, count / 30)
            scene.render.filepath = str(path)
            bpy.ops.render.render(write_still=True)


if __name__ == "__main__":
    main()
