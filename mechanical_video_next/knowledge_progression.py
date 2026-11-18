"""Executable evidence and phone legibility for new visual Blueprints."""
import re
import math


FIELD = 'knowledge_progression_version'
VERSION = 1
PHONE_WIDTHS = (360, 390, 430)
DYNAMIC = {'change', 'cause', 'comparison'}
KINDS = DYNAMIC | {'structure'}
PROOFS = {'physical_action', 'animated_model', 'visible_geometry'}
GRAPHIC_FONT = 86


def fit(text, width, size=GRAPHIC_FONT):
    from .text_layout import measure_text
    if (not isinstance(text, str) or not text.strip() or '\n' in text or '\r' in text
            or measure_text(text, size=size)['width'] > width):
        raise ValueError('Graphic copy must fit at the minimum phone text size: ' + str(text))


def validate_graphic_text(graphic):
    fit(graphic['title'], 1670, 96)
    if graphic['type'] == 'chart' and len(graphic['items']) > 3:
        raise ValueError('Use at most three chart rows at the minimum phone text size')
    for item in graphic['items']:
        width = 1440 if graphic['type'] == 'chart' else 790
        fit(item['label'], 1040 if graphic['type'] == 'chart' else width)
        fit(item['detail'], width)
        if 'value' in item:
            fit(f"{item['value']} {graphic['unit']}", 510)
    if 'formula' in graphic:
        fit(graphic['formula'], 1640)


def validate_angular_graphic(graphic):
    fit(graphic.get('title'), 1670, 96)
    rows = graphic.get('items', [])
    if not isinstance(rows, list) or len(rows) != 2:
        raise ValueError('Angular comparison requires two radii')
    radii = []
    for row in rows:
        fit(row.get('label'), 700)
        radius = row.get('radius')
        if type(radius) not in {int, float} or not math.isfinite(radius) or radius <= 0:
            raise ValueError('Angular comparison requires finite positive radii')
        radii.append(radius)
    travel = graphic.get('travel')
    if (min(radii) / max(radii) < .35 or radii[0] == radii[1] or type(travel) not in {int, float}
            or not math.isfinite(travel) or not 0 < travel <= math.pi * min(radii)):
        raise ValueError('Angular comparison must fit two distinct visible radii and at most a half turn')


def validate_dual_reel_graphic(graphic):
    fit(graphic.get('title'), 1670, 96)
    a, b, v = (graphic.get(k) for k in ('coreRadius', 'fullRadius', 'feedSpeed'))
    if any(type(n) not in {int, float} or not math.isfinite(n) for n in (a, b, v)):
        raise ValueError('Dual reel geometry requires finite numeric parameters')
    if not 0 < a < b or a / b < .25 or not 0 < v <= 1000:
        raise ValueError('Dual reel geometry requires positive feed and visibly distinct radii')


def enabled(document):
    value = document.get(FIELD)
    if FIELD in document and (type(value) is not int or value != VERSION):
        raise ValueError('Unsupported knowledge progression version')
    return value == VERSION


def normalize(text):
    return re.sub(r'[\W_]+', '', text.casefold())


def validate_timeline(shots):
    previous_ids, seen_ids, seen_goals, seen_visuals = set(), set(), set(), set()
    compositions = {}
    findings = []
    for shot in shots:
        sid = shot['shot_id']
        ids = set(shot['knowledge_ids'])
        progression = shot['progression']
        prior = progression.get('previous_ids')
        if not isinstance(prior, list) or any(not isinstance(item, str) for item in prior) or set(prior) != previous_ids:
            raise ValueError(f'{sid}: link the knowledge explained by the immediately preceding shot')
        goal = normalize(shot['knowledge_goal'])
        if progression['kind'] == 'recap' or (progression['kind'] == 'new' and goal in seen_goals):
            raise ValueError(f'{sid}: this shot must add a claim or a distinct visual demonstration')
        evidence = progression.get('observable')
        if not isinstance(evidence, list) or not evidence:
            raise ValueError(f'{sid}: observable knowledge evidence required')
        proven = set()
        for beat in evidence:
            claim = beat.get('knowledge_id')
            kind, proof = beat.get('kind'), beat.get('proof')
            window = beat.get('frames')
            end = round(shot['duration'] * 30)
            states = beat.get('states', [])
            if (claim not in ids or kind not in KINDS or proof not in PROOFS
                    or not isinstance(window, list) or len(window) != 2
                    or any(type(frame) is not int for frame in window)
                    or not 0 <= window[0] < window[1] <= end
                    or not isinstance(states, list) or len(states) < (2 if kind in DYNAMIC else 1)
                    or any(not isinstance(state, str) or not normalize(state) for state in states)):
                raise ValueError(f'{sid}: bind each claim to observable states and a valid frame window')
            state_keys = tuple(normalize(state) for state in states)
            if len(set(state_keys)) != len(state_keys):
                raise ValueError(f'{sid}: show distinct physical states')
            if kind in DYNAMIC and (proof == 'visible_geometry' or window[1] - window[0] < 3):
                raise ValueError(f'{sid}: change, causality and comparison need continuous visual motion')
            if shot['render_engine'] == 'remotion' and kind in DYNAMIC and proof != 'animated_model':
                raise ValueError(f'{sid}: Remotion evidence needs a data-driven model')
            signature = kind, state_keys
            if signature in seen_visuals:
                raise ValueError(f'{sid}: observable states already shown')
            seen_visuals.add(signature)
            proven.add(claim)
        if not (ids - seen_ids or progression['kind'] == 'develop') or proven != ids:
            raise ValueError(f'{sid}: every claim needs visual evidence and the shot needs an increment')
        composition = tuple(normalize(str(value)) for value in (
            shot['render_engine'], shot['camera']['scale'], shot['camera']['angle'], shot['visual_focus']))
        if composition in compositions:
            findings.append({'shot_id': sid, 'issue': 'reused_composition', 'previous_shot_id': compositions[composition]})
        compositions[composition] = sid
        covered = set(frame for beat in evidence for frame in range(*beat['frames']))
        gaps = [frame for frame in range(round(shot['duration'] * 30)) if frame not in covered]
        if gaps:
            findings.append({'shot_id': sid, 'issue': 'frames_without_observable_claim', 'frame_count': len(gaps)})
        seen_ids |= ids
        seen_goals.add(goal)
        previous_ids = ids
    return findings


def validate_media_evidence(blueprint, review, media_by_sha, *, acceptance):
    rows = review.get('visual_evidence', {})
    shots = blueprint['shots']
    if set(rows) != {shot['shot_id'] for shot in shots}:
        raise ValueError('Visual evidence must cover every reviewed shot')
    for shot in shots:
        sid = shot['shot_id']
        row = rows[sid]
        if row.get('media_sha256') not in media_by_sha:
            raise ValueError(f'{sid}: visual observations must bind the exact reviewed MP4')
        receipts = row.get('observations', [])
        expected = shot['progression']['observable']
        if len(receipts) != len(expected):
            raise ValueError(f'{sid}: review every planned observation')
        for beat, receipt in zip(expected, receipts, strict=True):
            start = round(shot['time_range'][0] * 30)
            status = receipt.get('status')
            if (receipt.get('knowledge_id') != beat['knowledge_id']
                    or receipt.get('frames') != [start + n for n in beat['frames']]
                    or status not in {'PASS', 'UNKNOWN', 'FAIL'}
                    or not isinstance(receipt.get('observation'), str) or not receipt['observation'].strip()
                    or status == 'FAIL' or (acceptance and status != 'PASS')):
                raise ValueError(f'{sid}: missing or failed actual visual evidence')
            if status == 'PASS' and beat['kind'] in DYNAMIC and receipt.get('method') != 'continuous_viewing':
                raise ValueError(f'{sid}: dynamic comprehension requires continuous viewing')
        if shot.get('graphic'):
            phone = row.get('phone_readability', {})
            if (phone.get('widths') != list(PHONE_WIDTHS) or phone.get('status') not in {'PASS', 'UNKNOWN'}
                    or (acceptance and phone['status'] != 'PASS')):
                raise ValueError(f'{sid}: actual phone readability review required')
            if phone['status'] == 'PASS':
                from .qa_images import prepare_video_frames
                from .visual_narrative import local_binding, number
                samples = phone.get('samples', [])
                timecode = phone.get('timecode')
                if (len(samples) != len(PHONE_WIDTHS) or not number(timecode)
                        or not shot['time_range'][0] <= timecode < shot['time_range'][1]):
                    raise ValueError(f'{sid}: bind phone samples at all tested sizes')
                for width, sample in zip(PHONE_WIDTHS, samples, strict=True):
                    image = local_binding(sample)
                    actual, = prepare_video_frames(
                        media_by_sha[row['media_sha256']], [timecode], max_size=width)
                    if (image.suffix != '.webp' or actual['width'] != width
                            or actual['qa_sha256'] != sample['sha256']):
                        raise ValueError(f'{sid}: phone sample does not match the exact MP4 at {width}px')
