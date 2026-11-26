"""TR1278B relations from the repair photos and manufacturer operation.

Distances and tolerances refer to the teaching model coordinate system.
"""
import math

from mathutils import Vector

from episode_mechanics import position, require_range, surface_hit


def bounds(obj, graph):
    obj = obj.evaluated_get(graph)
    corners = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    return [(min(p[axis] for p in corners), max(p[axis] for p in corners)) for axis in range(3)]


def lift(scene, graph):
    objects = scene.objects
    slider = objects['Guided carriage and toast']
    guide = objects['Guide rail fixed to chassis']
    lever = objects['Handle stem passing through front']
    crossbar = objects['Crossbar joining both supports']
    rails, arms, loaves = [
        sorted((obj for obj in objects if obj.name.startswith(prefix)),
               key=lambda obj: sum(bounds(obj, graph)[0]))
        for prefix in ('Toast support rail', 'Support arm into carriage', 'Toast slice')
    ]
    fixed_guide = position(guide, graph)
    initial_offsets = [position(obj, graph) - position(slider, graph)
                       for obj in (*rails, *arms, crossbar, lever)]
    for rail, arm in zip(rails, arms, strict=True):
        for a, b in ((rail, arm), (arm, crossbar)):
            overlap = [min(hi, top) - max(lo, bottom)
                       for (lo, hi), (bottom, top) in zip(bounds(a, graph), bounds(b, graph))]
            if min(overlap) <= 0:
                raise ValueError('Support arm, rail and carriage crossbar must meet')
    if len(rails) != 2 or len(loaves) != 2:
        raise ValueError('The common carriage needs a support and a slice in each slot')

    def sample(graph):
        carriage = position(slider, graph)
        require_range('Fixed guide shift', (position(guide, graph) - fixed_guide).length, 0, .0001)
        require_range('Carriage off guide direction', math.hypot(carriage.x, carriage.y), 0, .0001)
        require_range('Carriage stroke', carriage.z, -1.061, .001)
        for obj, initial in zip((*rails, *arms, crossbar, lever), initial_offsets, strict=True):
            require_range('Handle and both supports must share carriage travel',
                          (position(obj, graph) - carriage - initial).length, 0, .0001)
        gaps = []
        for loaf, rail in zip(loaves, rails, strict=True):
            x, y, z = position(rail, graph)
            top = surface_hit(rail, graph, (x, y, z + .2), (0, 0, -1)).z
            bottom = surface_hit(loaf, graph, (x, y, z - .2), (0, 0, 1)).z
            gaps.append(abs(require_range('Bread / rail signed gap', bottom - top, -.002, .002)))
        return {'height': carriage.z, 'gap': max(gaps)}
    return sample


def spring(scene, graph):
    objects = scene.objects
    coil = objects['Upper extension spring']
    fixed = objects['Fixed spring attachment']
    moving = objects['Moving spring attachment']
    slider = objects['Guided carriage and toast']
    initial_anchor = position(fixed, graph)
    initial_offset = position(moving, graph) - position(slider, graph)

    def sample(graph):
        evaluated = coil.evaluated_get(graph)
        ends = evaluated.data.splines[0].points
        bottom, top = (evaluated.matrix_world @ ends[i].co.to_3d() for i in (0, -1))
        fixed_position, moving_position = position(fixed, graph), position(moving, graph)
        for end, anchor in ((top, fixed), (bottom, moving)):
            limits = bounds(anchor, graph)
            if any(not lo - .003 <= value <= hi + .003 for value, (lo, hi) in zip(end, limits)):
                raise ValueError('Spring endpoint leaves its mounting tab')
        require_range('Fixed spring anchor movement', (fixed_position - initial_anchor).length, 0, .0001)
        require_range('Moving spring anchor must follow the carriage',
                      (moving_position - position(slider, graph) - initial_offset).length, 0, .0001)
        return {'length': top.z - bottom.z}
    return sample


def cancel(scene, graph):
    button = scene.objects['Center cancel button']
    face = scene.objects['Pressable cancel face']
    dial = scene.objects['Browning dial axis']
    finger = scene.objects['Finger pressing CANCEL']
    rest = position(button, graph)
    center = position(dial, graph)
    require_range('Cancel center alignment with shade dial',
                  math.hypot(rest.x - center.x, rest.z - center.z), 0, .001)

    def sample(graph):
        current = position(button, graph)
        press = require_range('Cancel button stroke', current.y - rest.y, -.001, .049)
        if press > .004:
            contact = position(finger, graph)
            # Probe the flat face away from the coincident fan vertices at its center.
            outer = surface_hit(face, graph,
                                (current.x + .019, current.y - .2, current.z + .009), (0, 1, 0))
            require_range('Fingertip to cancel face signed gap', outer.y - contact.y, -.004, .004)
            require_range('Fingertip on cancel face',
                          math.hypot(contact.x - current.x, contact.z - current.z), 0, .12)
        return {'press': press, 'height': position(scene.objects['Guided carriage and toast'], graph).z}
    return sample


def crumb_tray(scene, graph):
    rim = scene.objects['Bottom rim']
    hinge = scene.objects['Crumb tray hinge']
    door = scene.objects['Crumb door']
    pivot = position(hinge, graph)
    # Follow the vertical path beneath both slots through the fixed base. The original
    # animation's solid slab fails here even though its carriage channels all pass.
    for x in (-.62, .62):
        for y in (-1.0, 0, 1.0):
            origin = Vector((x, y, .68))
            evaluated = rim.evaluated_get(graph)
            inverse = evaluated.matrix_world.inverted()
            hit, *_ = evaluated.ray_cast(inverse @ origin,
                                         inverse.to_3x3() @ Vector((0, 0, -1)), distance=.55)
            if hit:
                raise ValueError('Fixed base blocks the crumb path below the bread slots')
            z = surface_hit(door, graph, origin, (0, 0, -1)).z
            require_range('Closed tray sits inside the opening', z, .26, .39)
    seats = [obj for obj in scene.objects if obj.name.startswith('Fixed hinge seat')]
    leaves = [obj for obj in hinge.children if obj.name.startswith('Tray hinge leaf')]
    if len(seats) != 2 or len(leaves) != 2:
        raise ValueError('Tray requires two modelled attachments to the fixed base')

    def sample(graph):
        require_range('Crumb tray hinge movement', (position(hinge, graph) - pivot).length, 0, .0001)
        for seat, leaf in zip(seats, leaves, strict=True):
            if any(min(hi, top) <= max(lo, bottom)
                   for (lo, hi), (bottom, top) in zip(bounds(seat, graph), bounds(leaf, graph))):
                raise ValueError('Tray hinge leaf detaches from the base')
        rotation = hinge.evaluated_get(graph).matrix_world.to_euler()
        require_range('Tray hinge axis', math.hypot(rotation.y, rotation.z), 0, .0001)
        angle = require_range('Tray must open down around the hinge', rotation.x, -.001, .86)
        return {'angle': angle}
    return sample


RELATIONS = {'lift': lift, 'spring': spring, 'cancel': cancel, 'tray': crumb_tray}
