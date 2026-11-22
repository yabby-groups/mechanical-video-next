"""Compare authored channel evaluations across the entire edited native clock."""

import json
import math
from pathlib import Path
import sys

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from common import filehash, writejson

RIGS = ('Lever handle', '66 square drive spindle',
        '34 active flat spring driver', '32 opposite flat spring driver')
SPRING = '30 continuous wire arc spring'


def curves(owner, prefix):
    action = owner.animation_data.action
    slot = owner.animation_data.action_slot
    selected = {}
    for layer in action.layers:
        for strip in layer.strips:
            bag = strip.channelbag(slot)
            if bag:
                selected.update({(curve.data_path, curve.array_index): curve
                                 for curve in bag.fcurves if curve.data_path.startswith(prefix)})
    return selected


def samples(frames):
    objects = bpy.context.scene.objects
    channels = {}
    for name in RIGS:
        obj = objects[name]
        channels[name] = {'angle_y': [obj.rotation_euler.y] * len(frames)}
        if obj.animation_data and obj.animation_data.action:
            curve = curves(obj, 'rotation_euler').get(('rotation_euler', 1))
            if curve:
                channels[name]['angle_y'] = [curve.evaluate(frame) for frame in frames]
    shape_keys = objects[SPRING].data.shape_keys
    channels[SPRING] = {path: [curve.evaluate(frame) for frame in frames]
                        for (path, _), curve in curves(shape_keys, 'key_blocks').items()}
    if not channels[SPRING]:
        raise ValueError('Spring source requires animated shape keys')
    return channels


def main():
    original, folder = map(Path, sys.argv[sys.argv.index('--') + 1:])
    clock = json.loads((folder / 'source-clock.json').read_text())
    source = Path(bpy.data.filepath)
    if source.resolve() != original.resolve() or clock['inputs'][str(source)] != filehash(source):
        raise ValueError('Verified Blend binding changed')
    mapped = [frame + 1 for frame in clock['source_frames']]
    expected = samples(mapped)
    rendered = folder / 'scene.blend'
    if filehash(rendered) != clock['scene_sha256']:
        raise ValueError('Edited Blend changed')
    bpy.ops.wm.open_mainfile(filepath=str(rendered))
    actual = samples(list(range(1, len(mapped) + 1)))
    maxima = {}
    for name, data in expected.items():
        if set(data) != set(actual[name]):
            raise ValueError(f'Channels changed for {name}')
        maxima[name] = max(abs(left - right) for row in data
                           for left, right in zip(data[row], actual[name][row], strict=True))
    if max(maxima.values()) > 1e-6:
        raise ValueError(f'Edited rotation/spring tracks differ from verified motion: {maxima}')
    plan = json.loads((folder.parent / 'joint-timeline.json').read_text())
    for action in plan['actions']:
        first, last = (action[k] for k in ('start_frame', 'end_frame'))
        if mapped[first:last] != list(range(action['source_start_frame'] + 1, action['source_end_frame'] + 1)):
            raise ValueError(f'Action lost the original clock: {action["id"]}')
    event_rows = {}
    for action in plan['actions']:
        first, last = action['start_frame'], action['end_frame']
        angle = actual[RIGS[2]]['angle_y'][first:last]
        event_rows[action['id']] = dict(frame_range=[first, last], angle_start=math.degrees(angle[0]),
                                                angle_end=math.degrees(angle[-1]),
                                                max_deg_step=max(math.degrees(abs(b-a)) for a, b in zip(angle, angle[1:])))
    writejson(folder / 'motion-review.json', dict(status='PASS', frame_count=len(mapped),
                    max_errors=maxima, events=event_rows, source_sha256=filehash(source),
                    rendered_sha256=filehash(rendered), physical_simulation=False,
                    scope='Authored rotations, spring key weights and source frame mapping only'))


if __name__ == '__main__':
    main()
