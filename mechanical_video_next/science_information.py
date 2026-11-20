"""Translate shot-local editorial overlays and render receipts into Remotion props."""

import json

from .science_shots import MODE_LABEL, name, number, source_binding, vector


def information_props(shot, editorial, media, kind, *, natural=True):
    science = shot.get('science', {})
    items = editorial.get('information', [])
    if not isinstance(items, list) or len(items) > 24:
        raise ValueError('Shot information must be a bounded list')
    anchors = None
    if science.get('observation_window') or any(isinstance(item, dict) and item.get('type') == 'label' for item in items):
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
            'scienceLabel': MODE_LABEL[science['mode']] if science and not natural else None}


def observation_overlay_findings(props, windows):
    """Locate projected datums inside active overlay boxes on the output clock."""
    width, height, fps = (props[key] for key in ('width', 'height', 'fps'))
    global_items = props['text_layout_items']
    findings = []
    offset = 0
    for shot in props['shots']:
        count = round(shot['seconds'] * fps)
        window = windows.get(shot['id'])
        if window:
            track = shot['screenAnchors']
            start, end = window['progress']
            first, last = offset/fps, (offset+count)/fps
            items = [row for row in global_items if row['start'] < last and row['end'] > first]
            items.extend(dict(layer=item['type'], box=item['box'], start=first+item['time'][0],
                              end=first+item['time'][1], label_anchor=item.get('anchor'))
                         for item in shot.get('information', []))
            for index in range(count):
                if not start <= index / max(1, count - 1) <= end:
                    continue
                sample = min(track['frame_count']-1, index*track['fps']//fps)
                time = (offset+index)/fps
                for name in window['anchors']:
                    point = track['samples'][name][sample]
                    if point is None:
                        continue  # The Blender projection report records offscreen datums.
                    x, y = point[0]*width, point[1]*height
                    for item in items:
                        if not item['start'] <= time < item['end']:
                            continue
                        if item.get('label_anchor') and track['samples'][item['label_anchor']][sample] is None:
                            continue
                        left, top, right, bottom = item['box']
                        if left <= x <= right and top <= y <= bottom:
                            findings.append(dict(shot_id=shot['id'], frame=offset+index,
                                                 anchor=name, box_layer=item['layer']))
        offset += count
    return findings
