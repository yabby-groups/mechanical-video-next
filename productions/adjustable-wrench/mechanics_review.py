"""Measure single-start worm lead from the teaching model's evaluated meshes."""

import math

from mathutils import Vector

from episode_mechanics import relative_matrix, require_range


def worm_rack(scene, graph):
    objects = scene.objects
    root = objects['Adjustable wrench']
    rack = objects['Sliding jaw and rack']
    worm = objects['Worm rotates about its retained pin']
    pin = objects['Retaining pin']
    thread = objects['Single-start helical adjustment worm']
    teeth = [obj for obj in rack.children if obj.name.startswith('Rack tooth')]
    centers = sorted(relative_matrix(tooth, rack, graph).translation.x
                     + sum(corner[0] for corner in tooth.bound_box) / 8 for tooth in teeth)
    # The prisms bake their tooth center into local geometry. Read the lead from the
    # separate rack mesh instead of using the animator's drive constant.
    gaps = [b - a for a, b in zip(centers, centers[1:])]
    if len(gaps) < 3:
        raise ValueError('Missing rack teeth')
    pitch = sum(gaps) / len(gaps)
    if pitch <= .01 or any(abs(gap - pitch) > .002 for gap in gaps):
        raise ValueError('Rack tooth pitch is not uniform')

    mesh = thread.evaluated_get(graph).data
    vertices = [vertex.co for vertex in mesh.vertices if -.73 < vertex.co.x < .73]
    radius = max(math.hypot(v.y, v.z) for v in vertices)
    crests = [v for v in vertices if math.hypot(v.y, v.z) > radius - .008]
    # The rise of one positive angular turn must match the positive rack axis.
    # Compare crest phase across angular sectors to establish actual handedness.
    alignments = []
    for hand in (-1, 1):
        phases = [math.tau * v.x / pitch - hand * math.atan2(v.z, v.y) for v in crests]
        alignments.append(math.hypot(sum(map(math.cos, phases)), sum(map(math.sin, phases))) / len(phases))
    if alignments[1] < .80 or alignments[1] <= alignments[0]:
        raise ValueError('Worm mesh lead or handedness disagrees with the reviewed rack')
    worm_offset = relative_matrix(worm, root, graph).translation.copy()
    pin_offset = relative_matrix(pin, root, graph).translation.copy()
    axis = relative_matrix(pin, root, graph).to_quaternion() @ Vector((0, 0, 1))
    require_range('Retaining pin parallel to worm axis', abs(axis.x), .999, 1.001)
    tooth_tip = min(v[1] for tooth in teeth for v in tooth.bound_box) - worm_offset.y
    root_radius = min(math.hypot(v.y, v.z) for v in vertices)
    # The tooth tip enters the thread envelope while clearing its root.
    # Flank contact depends on phase and tooth profile and is outside this test.
    if not root_radius < tooth_tip < radius:
        raise ValueError('Rack tooth tips do not lie between the worm root and crest')
    first = relative_matrix(rack, root, graph).translation.x
    previous = relative_matrix(worm, root, graph).to_euler().x
    turns = 0

    def sample(graph):
        nonlocal previous, turns
        jaw = relative_matrix(rack, root, graph)
        roll = relative_matrix(worm, root, graph)
        angle = roll.to_euler().x
        turns += math.remainder(angle - previous, math.tau) / math.tau
        previous = angle
        require_range('Jaw slides along its guide', math.hypot(jaw.translation.y, jaw.translation.z), 0, .001)
        require_range('Worm stays on its retained axis', (roll.translation - worm_offset).length, 0, .001)
        require_range('Pin stays in the tool body',
                      (relative_matrix(pin, root, graph).translation - pin_offset).length, 0, .001)
        error = jaw.translation.x - first + pitch * turns
        require_range('Independent worm / rack signed lead', error, -.001, .001)
        return {'travel': jaw.translation.x, 'turns': turns}
    return sample


RELATIONS = {'worm_rack': worm_rack}
