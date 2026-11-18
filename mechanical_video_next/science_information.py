"""Translate shot-local editorial overlays and render receipts into Remotion props."""

import json

from .science_shots import MODE_LABEL, name, number, source_binding, vector


def information_props(shot, editorial, media, kind):
    science = shot.get('science', {})
    items = editorial.get('information', [])
    if not isinstance(items, list) or len(items) > 24:
        raise ValueError('Shot information must be a bounded list')
    anchors = None
    if any(isinstance(item, dict) and item.get('type') == 'label' for item in items):
        if kind != 'video':
            raise ValueError('Tracked labels require a fullframe 3D clip')
        anchors = json.loads((media.parent/'checks.json').read_text()).get('screen_anchors')
        if (not anchors or anchors['frame_count'] != round(anchors['fps'] * shot['seconds'])
                or any(len(samples) != anchors['frame_count'] for samples in anchors['samples'].values())):
            raise ValueError('Missing or incompatible screen anchor render receipt')
    for item in items:
        if not isinstance(item, dict) or item.get('type') not in {'label', 'value', 'inset', 'note'}:
            raise ValueError('Unknown shot information component')
        if not vector(item.get('box'), 4):
            raise ValueError('Information component requires a pixel box')
        if (not vector(item.get('time'), 2) or not 0 <= item['time'][0] < item['time'][1] <= shot['seconds']):
            raise ValueError('Information times must be relative to this shot')
        if item['type'] == 'label' and item.get('anchor') not in anchors['samples']:
            raise ValueError('Tracked label names an anchor missing from its render receipt')
        if item['type'] in {'note', 'label'} and not name(item.get('text')):
            raise ValueError('Information text is required')
        if item['type'] == 'inset':
            crop = item.get('crop')
            if (not vector(crop, 4) or not 0 <= crop[0] < crop[2] <= 1 or not 0 <= crop[1] < crop[3] <= 1):
                raise ValueError('Inset requires normalized source crop bounds')
        if item['type'] == 'value':
            samples = item.get('samples')
            if (not name(item.get('prefix')) or not isinstance(item.get('unit'), str)
                    or type(item.get('digits')) is not int or not 0 <= item['digits'] <= 3
                    or not isinstance(samples, list) or not 2 <= len(samples) <= 1024
                    or not all(vector(sample, 2) for sample in samples)
                    or samples[0][0] != 0 or samples[-1][0] != 1
                    or any(not start[0] < end[0] for start, end in zip(samples, samples[1:]))):
                raise ValueError('Value requires named units, precision and ordered [progress, value] samples')
            source_binding(item.get('basis'))
    return {'information': items, 'screenAnchors': anchors,
            'scienceLabel': MODE_LABEL[science['mode']] if science else None}
