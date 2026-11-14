"""Protect approved source files and compare same-time frames outside text masks.

Pixel checks are deterministic evidence, never continuous viewing or style acceptance.
"""
import hashlib
import json
from pathlib import Path
from PIL import Image, ImageChops, ImageDraw, ImageStat


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def verify_lock(lock_path, root=None, *, shared_only=False):
    lock_path = Path(lock_path)
    root = Path(root or Path(__file__).resolve().parents[1])
    lock = json.loads(lock_path.read_text())
    results = []
    for entry in lock['protected_files']:
        # Per-video snapshots are strict during that video's acceptance audit,
        # but must not make a clean checkout depend on private historical CAD.
        if shared_only and entry['path'].startswith(('output/', 'assets/assemblies/')):
            continue
        path = root / entry['path']
        actual = sha256(path) if path.is_file() else None
        results.append(dict(path=entry['path'], expected=entry['sha256'], actual=actual,
                            status='PASS' if actual == entry['sha256'] else 'FAIL'))
    return dict(status='PASS' if results and all(r['status'] == 'PASS' for r in results) else 'FAIL',
                files=results)


def compare_frames(before, after, text_regions, *, pixel_tolerance=12,
                   max_changed_fraction=0.005, max_mean_difference=1.0):
    """Compare RGB frames with identical geometry, excluding declared text rectangles.

    Mask coordinates are source pixels, not normalized. At least 65% of the image
    must remain inspected; avoid permitting whole-frame exclusions to hide drift.
    """
    if not 0 <= pixel_tolerance <= 255 or not 0 <= max_changed_fraction <= 1 or max_mean_difference < 0:
        raise ValueError('Invalid visual difference threshold')
    with Image.open(before) as image:
        a = image.convert('RGB')
    with Image.open(after) as image:
        b = image.convert('RGB')
    if a.size != b.size:
        raise ValueError('Same frame dimensions required; resizing could hide framing drift')
    mask = Image.new('L', a.size, 255)
    draw = ImageDraw.Draw(mask)
    for region in text_regions:
        if len(region) != 4:
            raise ValueError('Text region requires four source-pixel coordinates')
        x0, y0, x1, y1 = region
        if not (0 <= x0 < x1 <= a.width and 0 <= y0 < y1 <= a.height):
            raise ValueError('Text region outside image')
        draw.rectangle((x0, y0, x1 - 1, y1 - 1), fill=0)
    inspected = mask.histogram()[255]
    if inspected < a.width * a.height * .65:
        raise ValueError('Text masks must leave at least 65 percent inspected')
    diff = ImageChops.difference(a, b)
    mean = sum(ImageStat.Stat(diff, mask).mean) / 3
    channels = diff.split()
    maximum = ImageChops.lighter(ImageChops.lighter(channels[0], channels[1]), channels[2])
    changed = maximum.point(lambda value: 255 if value > pixel_tolerance else 0)
    changed_count = ImageChops.multiply(changed, mask).histogram()[255]
    fraction = changed_count / inspected
    return dict(status='PASS' if fraction <= max_changed_fraction and mean <= max_mean_difference else 'FAIL',
                inspected_pixels=inspected, excluded_pixels=a.width * a.height - inspected,
                changed_pixels=changed_count, changed_fraction=fraction, mean_rgb_difference=mean,
                pixel_tolerance=pixel_tolerance, max_changed_fraction=max_changed_fraction,
                max_mean_difference=max_mean_difference, text_regions=list(text_regions),
                before_sha256=sha256(before), after_sha256=sha256(after),
                scope='same-time static non-text pixels only; motion and listening UNKNOWN')
