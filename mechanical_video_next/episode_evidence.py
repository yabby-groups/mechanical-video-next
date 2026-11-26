"""Bind independent, source-reviewed episode coverage to an exact edit and its inputs."""

import json
import math

from scripts.common import ROOT, digest, filehash

PLAN = 'mechanics-plan.json'
VERIFIER = 'mechanics_review.py'
RELATIONS_RUNNER = ROOT / 'blender/episode_relations.py'
NON_MECHANICAL = {'exterior', 'display', 'auxiliary', 'other'}


def shot_signature(episode, cut, index, narration):
    picture = cut.get('picture')
    scene = cut.get('scene', 'scene.py')
    if 'graphic' in cut:
        inputs = []
    elif picture and (not picture.get('fallback_to_scene') or (episode / picture['path']).is_file()):
        inputs = []  # The picture reference itself contains its SHA-256.
    else:
        inputs = [scene, *cut.get('scene_inputs', ())]
    return digest({
        'cut': {k: v for k, v in cut.items() if k != 'mechanics'},
        'scene_shot': cut.get('scene_shot', index) if inputs else None,
        'inputs': {name: filehash(episode / name) if (episode / name).is_file() else None
                   for name in inputs},
        'narration': narration,
    })


def load(episode):
    path = episode / PLAN
    return json.loads(path.read_text()) if path.is_file() else {}


def coverage(episode, plan, cut, index, narration):
    signature = shot_signature(episode, cut, index, narration)
    row = plan.get('shots', {}).get(signature)
    if row is None:
        return None, 'No independent coverage for this picture, edit and narration'
    kind = row.get('kind')
    if kind in NON_MECHANICAL:
        # A non-mechanical verdict is only valid for the reviewed, exact media and wording.
        if row.get('relations') or cut.get('mechanics') is not None or not row.get('basis'):
            return None, 'Non-mechanical scope disagrees with the reviewed content'
        return row, None
    if kind not in {'core', 'graphic'} or (kind == 'graphic') != ('graphic' in cut):
        return None, 'Picture type disagrees with its independent review'
    evidence = plan.get('evidence', {})
    path = episode / evidence.get('path', '')
    if not path.is_file() or filehash(path) != evidence.get('sha256'):
        return None, 'Source research is missing or changed'
    notes = path.read_text()
    relations = row.get('relations')
    if not isinstance(relations, dict) or not relations or not set(relations) <= plan.get('claims', {}).keys():
        return None, 'Required mechanical relations are missing from the reviewed cut'
    for name in relations:
        claim = plan['claims'][name]
        anchor = claim.get('quote')
        if not isinstance(anchor, str) or len(anchor.strip()) < 8 or anchor not in notes:
            return None, f'Source research does not support the registered relation {name}'
        if not claim.get('source') or not claim.get('expectation'):
            return None, f'Source and reviewed expectation are missing for {name}'
    if kind == 'core':
        if (cut.get('mechanics') or {}).get('evidence') != evidence['path']:
            return None, 'Core picture requires the reviewed mechanics declaration'
        verifier = episode / VERIFIER
        if not verifier.is_file() or filehash(verifier) != plan.get('verifier_sha256'):
            return None, 'Independent Blender verifier is missing or changed'
        for name, rule in relations.items():
            channels = rule.get('channels', ())
            if not channels or any(not event.get('ranges') or
                                   not event['ranges'].keys() <= set(channels)
                                   for event in rule.get('events', ())):
                return None, f'Independent measurements are missing for {name}'
    return row, None


def motion_covers(motion, requirements, offset, count, episode):
    if not motion or motion.get('status') != 'PASS':
        return False
    binding = motion.get('binding', {})
    inputs = binding.get('mechanics', {}).get('inputs', {})
    if not requirements.keys() <= binding.get('independent_relations', {}).keys():
        return False
    for path in (episode / VERIFIER, RELATIONS_RUNNER):
        if not path.is_file() or inputs.get(str(path.resolve())) != filehash(path):
            return False
    frames, substeps = motion.get('frames', 0), motion.get('substeps', 0)
    if type(substeps) is not int or substeps < 2 or frames < offset + count:
        return False
    expected = (frames - 1) * substeps + 1
    if motion.get('evaluated_poses') != expected:
        return False
    return all(
        isinstance(values := motion.get('samples', {}).get(f'review.{relation}.{channel}'), list)
        and len(values) == expected and all(math.isfinite(value) for value in values)
        for relation, rule in requirements.items() for channel in rule['channels']
    )


def events_hold(motion, rule, relation, offset, count):
    if not rule.get('events'):
        return True
    substeps = motion['substeps']
    start = offset * substeps
    stop = (offset + count - 1) * substeps + 1
    previous = start
    for event in rule['events']:
        first, last = event.get('window', (0, count))
        if not 0 <= first < last <= count:
            return False
        channels = [(motion['samples'][f'review.{relation}.{name}'], *limits)
                    for name, limits in event['ranges'].items()]
        # A held state must persist for its declared duration. Search on the original,
        # contiguous subframe clock, including when a picture is reused as a recut.
        span = max(1, event.get('hold_frames', 0) * substeps + 1)
        streak = 0
        for sample in range(max(previous, start + first * substeps),
                            min(stop, start + last * substeps)):
            streak = streak + 1 if all(lo <= series[sample] <= hi for series, lo, hi in channels) else 0
            if streak == span:
                previous = sample + 1
                break
        else:
            return False
    return True


def graphic_relation(graphic, rule, count):
    """Check qualitative, synchronized traces for the source-reviewed work cycle."""
    if (rule.get('type') != 'opposed_traces' or graphic.get('type') != 'data_animation'
            or graphic.get('qualitative') is not True or graphic.get('presentation') != 'trace'):
        return False
    items = {item['label']: item['keyframes'] for item in graphic['items']}
    if len(items) != 2 or set(items) != set(rule['labels']):
        return False
    height, spring = (items[label] for label in rule['labels'])
    if (len(height) != 6 or [t for t, _ in height] != [t for t, _ in spring]
            or not 0 <= height[0][0] < height[-2][0] < count / 30):
        return False

    def direction(keys):
        values = [value for _, value in keys]
        return [(b > a) - (b < a) for a, b in zip(values, values[1:])]

    return direction(height) == [0, -1, 0, 1, 0] and direction(spring) == [0, 1, 0, -1, 0]
