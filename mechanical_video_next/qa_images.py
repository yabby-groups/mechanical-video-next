"""Content-addressed visual evidence. Never modifies production assets.

Static evidence never grants continuous-motion, scientific or readability PASS.
"""
from pathlib import Path
import argparse
import hashlib
import io
import json
import math
import subprocess
import tempfile
import time
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / 'work/qa-images'
VERSION = '1'


def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def key(params):
    return hashlib.sha256(json.dumps(params, sort_keys=True).encode()).hexdigest()


def get_cached_image(cache_key, cache_dir=CACHE):
    path = Path(cache_dir) / (cache_key + '.json')
    if path.exists():
        data = json.loads(path.read_text())
        if Path(data['qa_path']).exists() and sha(data['qa_path']) == data['qa_sha256']:
            path.touch()  # Last successful access, never source mtime.
            return dict(data, cache_hit=True)
    return None


def prepare_image(source, *, max_size=1024, quality=80, format='webp',
                  crop_region=None, source_time=None, shot_id=None, target_bytes=300_000,
                  cache_dir=CACHE):
    start = time.monotonic()
    source = Path(source).resolve()
    format = format.lower()
    if format not in {'webp', 'jpeg'} or max_size < 1 or not 1 <= quality <= 100 or target_bytes < 1:
        raise ValueError('Invalid QA image parameters')
    params = dict(source_sha256=sha(source), version=VERSION, code_sha256=sha(__file__),
                  format=format, max_size=max_size, quality=quality,
                  crop_region=list(crop_region) if crop_region is not None else None,
                  target_bytes=target_bytes, color='exif-transpose-rgb-white-alpha')
    cache_key = key(params)
    hit = get_cached_image(cache_key, cache_dir)
    if hit:
        return dict(hit, source_path=str(source), source_time=source_time, shot_id=shot_id,
                    elapsed_seconds=time.monotonic()-start)
    with Image.open(source) as raw:
        im = ImageOps.exif_transpose(raw).convert('RGBA')
        if crop_region is not None:
            x0, y0, x1, y1 = crop_region
            if not (0 <= x0 < x1 <= im.width and 0 <= y0 < y1 <= im.height):
                raise ValueError('Crop must be within oriented source pixels')
            im = im.crop(tuple(crop_region))
        bg = Image.new('RGBA', im.size, 'white'); bg.alpha_composite(im)
        im = bg.convert('RGB')
        im.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
        q = quality
        while True:
            buf = io.BytesIO(); im.save(buf, format=format, quality=q)
            if buf.tell() <= target_bytes or q <= 35:
                break
            q = max(35, q-5)
        if buf.tell() > target_bytes:
            raise ValueError('Byte budget cannot preserve minimum quality; request a crop')
    folder = Path(cache_dir); folder.mkdir(parents=True, exist_ok=True)
    path = folder / (cache_key + ('.webp' if format == 'webp' else '.jpg'))
    # Atomic replacement permits independent roles to share a cache safely.
    with tempfile.NamedTemporaryFile(dir=folder, delete=False) as f:
        f.write(buf.getvalue()); tmp = Path(f.name)
    tmp.replace(path)
    result = dict(params, source_path=str(source), qa_path=str(path.resolve()),
                  qa_sha256=sha(path), width=im.width, height=im.height, quality=q,
                  requested_quality=quality, source_time=source_time, shot_id=shot_id,
                  bytes=path.stat().st_size, cache_key=cache_key, cache_hit=False,
                  readability='UNKNOWN', elapsed_seconds=time.monotonic()-start)
    with tempfile.NamedTemporaryFile(mode='w', dir=folder, delete=False) as f:
        json.dump(result, f, indent=2); tmp = Path(f.name)
    tmp.replace(folder / (cache_key + '.json'))
    return result


def prepare_crop(source, crop_region, **kwargs):
    return prepare_image(source, crop_region=crop_region, max_size=kwargs.pop('max_size', 1600), **kwargs)


def prepare_cover_preview(source, **kwargs):
    with Image.open(source) as im:
        if im.size not in {(1080, 1440), (1440, 1080)}:
            raise ValueError('Expected formal 3:4 or 4:3 cover')
    return prepare_image(source, max_size=1200, **kwargs)


def prepare_contact_sheet(sources, *, cache_dir=CACHE):
    if not sources or len(sources) > 16:
        raise ValueError('Contact sheet requires 1..16 representative frames')
    refs = [prepare_image(p, cache_dir=cache_dir) for p in sources]
    folder = Path(cache_dir)
    sheet_key = key({'version':VERSION, 'code':sha(__file__), 'inputs':[r['qa_sha256'] for r in refs]})
    sheet = folder / (sheet_key + '.png')
    if not sheet.exists():
        cols = min(4, len(refs)); rows = math.ceil(len(refs)/cols)
        canvas = Image.new('RGB', (cols*320, rows*200), '#333333')
        for i, ref in enumerate(refs):
            with Image.open(ref['qa_path']) as im:
                im.thumbnail((320, 180))
                canvas.paste(im, ((i%cols)*320, (i//cols)*200))
        canvas.save(sheet)
    result = prepare_image(sheet, max_size=1280, cache_dir=cache_dir)
    result['sources'] = refs
    return result


def prepare_video_frames(source, times, *, shot_ids=None, format='webp', quality=80,
                         max_size=1024, cache_dir=CACHE):
    times = list(times)
    if not times or len(times) > 4 or any(not math.isfinite(t) or t < 0 for t in times):
        raise ValueError('Each review round requires 1..4 finite nonnegative event times')
    if shot_ids is not None and len(shot_ids) != len(times):
        raise ValueError('One shot_id is required per event time')
    source = Path(source).resolve(); source_sha = sha(source)
    folder = Path(cache_dir); folder.mkdir(parents=True, exist_ok=True)
    refs = []
    for i, t in enumerate(times):
        frame = folder / (key({'video':source_sha, 'time':t, 'version':VERSION})+'.png')
        if not frame.exists():
            with tempfile.TemporaryDirectory(dir=folder) as tmp:
                extracted = Path(tmp)/'frame.png'
                subprocess.run(['ffmpeg','-v','error','-nostdin','-ss',str(t),'-i',str(source),
                                '-frames:v','1',str(extracted)], check=True, capture_output=True)
                extracted.replace(frame)
        ref = prepare_image(frame, source_time=t, shot_id=shot_ids[i] if shot_ids else None,
                            format=format, quality=quality, max_size=max_size, cache_dir=folder)
        ref.update(video_path=str(source), video_sha256=source_sha)
        refs.append(ref)
    return refs


def visual_packet(frames=(), sheets=()):
    if len(frames) > 4 or len(sheets) > 1:
        raise ValueError('Review round limit: four frames and one sheet')
    unique = {r['qa_sha256']: r for r in [*frames, *sheets]}
    for r in unique.values():
        if Path(r['qa_path']).suffix not in {'.webp', '.jpg'} or sha(r['qa_path']) != r['qa_sha256']:
            raise ValueError('Missing/stale compressed evidence')
    return dict(images=list(unique.values()), image_count=len(unique),
                total_bytes=sum(r['bytes'] for r in unique.values()),
                actual_agent_reads=None, actual_visual_tokens=None, acceptance='UNKNOWN')


def record_reads(packet, paths, log_path):
    """Call only after actual tool reads; never infer reads from prepared files."""
    allowed = {r['qa_path']:r for r in packet['images']}
    refs = [allowed[p] for p in dict.fromkeys(paths)]
    row = dict(image_count=len(refs), total_bytes=sum(r['bytes'] for r in refs),
               images=[{k:r[k] for k in ('qa_path','qa_sha256','format','width','height','bytes')} for r in refs],
               actual_visual_tokens=None)
    with open(log_path, 'a') as f:
        f.write(json.dumps(row)+'\n')
    return row


def handoff_visuals(payload):
    """Attach bounded role evidence without rewriting production source bindings."""
    found = []
    def visit(value):
        if isinstance(value, str):
            if 'data:image/' in value:
                raise ValueError('Inline image data forbidden in handoffs')
            if len(found) < 4 and Path(value).suffix.lower() in {'.png','.jpg','.jpeg','.webp'} and Path(value).is_file():
                if value not in found: found.append(value)
        elif isinstance(value, dict):
            for k, v in value.items():
                if k != 'visual_evidence': visit(v)
        elif isinstance(value, list):
            for v in value: visit(v)
    visit(payload)
    return visual_packet([prepare_image(p) for p in found])


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('source', nargs='+'); ap.add_argument('--times', nargs='+', type=float)
    ap.add_argument('--crop', nargs=4, type=int); ap.add_argument('--cover', action='store_true')
    ap.add_argument('--sheet', action='store_true'); ap.add_argument('--format', default='webp')
    args = ap.parse_args()
    if args.times:
        refs = prepare_video_frames(args.source[0], args.times, format=args.format)
    else:
        fn = prepare_cover_preview if args.cover else prepare_image
        refs = [(prepare_crop(p,args.crop,format=args.format) if args.crop else fn(p,format=args.format)) for p in args.source]
    packet = visual_packet(refs, [prepare_contact_sheet([r['qa_path'] for r in refs])] if args.sheet else [])
    print(json.dumps(packet, indent=2))


if __name__ == '__main__': main()
