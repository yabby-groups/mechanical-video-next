"""Measured typography only: no CAD, render, audio generation or guessed alignment.

Splitting text and splitting time are deliberately separate. Existing short cues
retain exact timing. Long cues need verified, text-matching segment alignment.
"""
import json
import math
import glob
from functools import lru_cache
from pathlib import Path
from PIL import ImageFont

ROOT = Path(__file__).resolve().parents[1]
STYLE_PATH = ROOT / 'config/text-style.json'


def load_style():
    return json.loads(STYLE_PATH.read_text())


def font_path(style=None):
    style = style or load_style()
    return _resolve_font_path(tuple(style['font_candidates']))


@lru_cache(maxsize=16)
def _resolve_font_path(candidates):
    for candidate in candidates:
        for path in sorted(glob.glob(candidate)):
            if Path(path).is_file():
                return path
    raise ValueError('CJK font unavailable: single-line measurement BLOCKED')


def measure_text(text, size=None, style=None):
    style = style or load_style()
    font = measured_font(round(size or style['subtitle']['font_size']), style)
    box = font.getbbox(text)
    return {'width': float(font.getlength(text)) + 2 * style['stroke_width'],
            'height': box[3] - box[1] + 2 * style['stroke_width']}


def resolved_font_family(style=None):
    """The renderer must use this family to agree with the measured font."""
    style = style or load_style()
    family = measured_font(64, style).getname()[0]
    if style.get('require_reference_font', True) and family != style['font_family']:
        raise ValueError('Approved font unavailable; refusing a silent visual style change')
    return family


@lru_cache(maxsize=16)
def _font_index(path, family, font_style):
    family_matches = []
    for index in range(64):
        try:
            name = ImageFont.truetype(path, 64, index=index).getname()
        except OSError:
            break
        if name[0] == family:
            family_matches.append(index)
            if name[1] == font_style:
                return index
    return family_matches[0] if family_matches else 0


def measured_font(size, style=None):
    """Resolve the exact CJK subfont; TTC index zero may be HK instead of SC."""
    style = style or load_style()
    path = font_path(style)
    index = _font_index(path, style['font_family'], style.get('font_style', 'Regular'))
    return _load_font(path, round(size), index)


@lru_cache(maxsize=32)
def _load_font(path, size, index):
    return ImageFont.truetype(path, size, index=index)


def scaled_style(width=1920, height=1080, route='3d'):
    style = load_style()
    if route not in style['routes']:
        raise ValueError('Unknown text route')
    if width <= 0 or height <= 0:
        raise ValueError('Invalid frame size')
    sx, sy = width / 1920, height / 1080
    if abs(sx - sy) > .001:
        raise ValueError('Text profile requires an unstretched 16:9 frame')
    for name in ('subtitle', 'chapter', 'part', 'principle', 'numeric', 'auxiliary'):
        layer = style[name]
        layer['font_size'] *= sx
        layer['min_font_size'] *= sx
        layer['safe_box'] = [v * sx for v in layer['safe_box']]
    style['stroke_width'] *= sx
    return style


def _boundaries(text, terms):
    forbidden = set()
    for term in terms:
        if not term:
            raise ValueError('Protected technical terms must not be empty')
        at = text.find(term)
        while at >= 0:
            forbidden.update(range(at + 1, at + len(term)))
            at = text.find(term, at + 1)
    return [i for i in range(1, len(text) + 1) if i not in forbidden]


def split_text(text, *, style=None, protected_terms=()):
    """Suggest semantic chunks without assigning invented speech timestamps."""
    style = style or load_style()
    if not isinstance(text, str) or not text or '\n' in text or '\r' in text:
        raise ValueError('Subtitle must be nonempty single-line text')
    layer = style['subtitle']
    capacity = layer['safe_box'][2] - layer['safe_box'][0]
    low, high = layer['preferred_characters']
    result = []
    remaining = text
    terms = [*style['protected_terms'], *protected_terms]
    while remaining:
        candidates = [i for i in _boundaries(remaining, terms)
                      if measure_text(remaining[:i], style=style)['width'] <= capacity]
        if not candidates:
            raise ValueError('Protected term cannot fit at the configured font size')
        if len(remaining) <= high and len(remaining) in candidates:
            result.append(remaining)
            break
        preferred = [i for i in candidates if low <= i <= high]
        semantic = [i for i in preferred if remaining[i - 1] in '，。；、！？：,.;!?: ']
        end = max(semantic or preferred or [i for i in candidates if i <= high] or candidates[:1])
        result.append(remaining[:end])
        remaining = remaining[end:]
    return result


def validate_layout(items, *, width=1920, height=1080, route='3d', critical_boxes=(), platform_insets=None):
    """Validate actual text boxes; overlapping layers need disjoint display times.

    Items: layer, text, box=[left,top,right,bottom], optional font_size/start/end.
    critical_boxes are producer-supplied projected mechanical contact regions.
    """
    style = scaled_style(width, height, route)
    insets = platform_insets or {'left': 0, 'top': 0, 'right': 0, 'bottom': 0}
    errors = []
    for i, item in enumerate(items):
        layer = style[item['layer']]
        box = item['box']
        size = item.get('font_size', layer['font_size'])
        if size < layer['min_font_size']:
            errors.append(f'{i}: font below minimum')
        allowed = layer['safe_box']
        if not (max(allowed[0], insets['left']) <= box[0] < box[2] <= min(allowed[2], width-insets['right'])
                and max(allowed[1], insets['top']) <= box[1] < box[3] <= min(allowed[3], height-insets['bottom'])):
            errors.append(f'{i}: outside layer or platform safe area')
        measured = measure_text(item['text'], size=round(size), style=style)
        if '\n' in item['text'] or '\r' in item['text'] or measured['width'] > box[2]-box[0] or measured['height'] > box[3]-box[1]:
            errors.append(f'{i}: text does not fit a single line')
        if any(_overlap(box, contact) for contact in critical_boxes):
            errors.append(f'{i}: covers critical mechanism')
        for j, other in enumerate(items[:i]):
            simultaneous = max(item.get('start', 0), other.get('start', 0)) < min(item.get('end', math.inf), other.get('end', math.inf))
            if simultaneous and _overlap(box, other['box']):
                errors.append(f'{j}/{i}: overlapping text')
    return errors


def _overlap(a, b):
    return max(a[0], b[0]) < min(a[2], b[2]) and max(a[1], b[1]) < min(a[3], b[3])


def normalize_cues(cues, width=1920, height=1080, alignment=None, audio_sha256=None):
    """Return single-line cues, preserving audio/timing and refusing guessed cuts.

    alignment = {verified: true, method: str, source_sha256: str,
      cues: [{index: 0, segments: [{text, start, end}, ...]}]}.
    Segment text must concatenate exactly to original text; timestamps must be
    measured, nonoverlapping and within the original cue interval.
    """
    style = scaled_style(width, height)
    by_index = {}
    if alignment is not None:
        source_sha = alignment.get('source_sha256', '')
        if alignment.get('verified') is not True or not alignment.get('method') or len(source_sha) != 64 or any(c not in '0123456789abcdefABCDEF' for c in source_sha):
            raise ValueError('Verified alignment with source SHA256 and method required')
        by_index = {c['index']: c['segments'] for c in alignment.get('cues', [])}
    result = []
    previous_end = 0
    for i, cue in enumerate(cues):
        if not (math.isfinite(cue['start']) and math.isfinite(cue['end']) and previous_end <= cue['start'] < cue['end']):
            raise ValueError('Subtitle intervals must be finite, positive and nonoverlapping')
        previous_end = cue['end']
        # 8-14 characters is a drafting preference, never a reason to invent
        # speech timing. A longer measured single line keeps its original cue.
        if not isinstance(cue['text'], str) or not cue['text'] or '\n' in cue['text'] or '\r' in cue['text']:
            raise ValueError('Subtitle must be nonempty single-line text')
        capacity = style['subtitle']['safe_box'][2] - style['subtitle']['safe_box'][0]
        if measure_text(cue['text'], style=style)['width'] <= capacity:
            result.append(dict(cue))
            continue
        segments = by_index.get(i)
        if not segments:
            raise ValueError(f'Cue {i} needs verified segment alignment; audio is not regenerated')
        if not audio_sha256 or alignment['source_sha256'].lower() != audio_sha256.lower():
            raise ValueError('Alignment source SHA256 must match actual audio SHA256')
        if ''.join(s['text'] for s in segments) != cue['text']:
            raise ValueError('Aligned subtitle text must preserve exact original order')
        last = cue['start']
        offset = 0
        boundaries = _boundaries(cue['text'], style['protected_terms'])
        for segment in segments:
            offset += len(segment['text'])
            if offset not in boundaries:
                raise ValueError('Aligned segment splits a protected technical term')
            if not (math.isfinite(segment['start']) and math.isfinite(segment['end']) and last <= segment['start'] < segment['end'] <= cue['end']):
                raise ValueError('Alignment must stay within cue and not overlap')
            if not segment['text'] or '\n' in segment['text'] or '\r' in segment['text'] or measure_text(segment['text'], style=style)['width'] > capacity:
                raise ValueError('Aligned segment still needs a shorter verified interval')
            result.append({**cue, **segment})
            last = segment['end']
    return result


def prepare_text_props(props, *, audio_sha256=None, critical_boxes=None, platform_insets=None):
    """Bind measured text and validate all overlays before composition.

    No supplied production objects are mutated. The caption and final credit
    share the auxiliary region at disjoint times. The renderer must implement
    that same timing and use the returned measured ``text_style``.
    """
    width, height = props.get('width', 1920), props.get('height', 1080)
    route = props.get('route', '3d')
    style = scaled_style(width, height, route)
    style['font_family'] = resolved_font_family(style)
    duration = props['duration']
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError('Composition duration must be finite and positive')
    fps = props.get('fps', 30)
    if not math.isfinite(fps) or fps <= 0:
        raise ValueError('Composition fps must be finite and positive')
    cues = normalize_cues(props.get('cues', []), width, height,
                          props.get('subtitle_alignment'), audio_sha256=audio_sha256)
    items = []

    def add(layer, text, start, end, box=None):
        if not isinstance(text, str) or not text:
            raise ValueError('Overlay text must be nonempty')
        if not (math.isfinite(start) and math.isfinite(end) and 0 <= start < end <= duration):
            raise ValueError('Overlay interval must stay within composition duration')
        if layer not in ('chapter', 'subtitle', 'part', 'principle', 'numeric', 'auxiliary'):
            raise ValueError('Unknown text layer')
        items.append({'layer': layer, 'text': text, 'start': start, 'end': end,
                      'box': list(box or style[layer]['safe_box'])})

    if props.get('title'):
        add('chapter', props['title'], 0, duration)
    shots = props.get('shots', [])
    credit = props.get('fullframe_credit')
    credit_start = sum(round(shot['seconds'] * fps) for shot in shots[:-1]) / fps if shots else 0
    caption_end = credit_start if credit else duration
    if props.get('fullframe_caption') and caption_end > 0:
        add('auxiliary', props['fullframe_caption'], 0, caption_end)
    if credit:
        add('auxiliary', credit, credit_start, duration)
    for cue in cues:
        add('subtitle', cue['text'], cue['start'], cue['end'])
    annotations = []
    for annotation in props.get('annotations', []):
        if annotation['layer'] not in ('part', 'principle', 'numeric', 'auxiliary'):
            raise ValueError('Annotation must use a name, principle, numeric or auxiliary layer')
        add(annotation['layer'], annotation['text'], annotation['start'], annotation['end'], annotation.get('box'))
        annotations.append(dict(annotation))
    errors = validate_layout(items, width=width, height=height, route=route,
                             critical_boxes=critical_boxes if critical_boxes is not None else props.get('critical_boxes', ()),
                             platform_insets=platform_insets if platform_insets is not None else props.get('platform_insets'))
    if errors:
        raise ValueError('Text layout BLOCKED: ' + '; '.join(errors))
    return {**props, 'cues': cues, 'annotations': annotations,
            'text_style': style, 'text_layout_items': items}
