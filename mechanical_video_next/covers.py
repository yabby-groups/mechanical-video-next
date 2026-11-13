"""Version-bound cover composition from existing video frames; no production reruns.

Input: TASK/cover-plan.json. Run: uv run python -m mechanical_video_next.covers TASK
"""
import argparse
import json
import math
from pathlib import Path
import subprocess
import tempfile

from PIL import Image, ImageDraw, ImageFont, ImageStat
from .multiroute import ROUTES, probe, sha, write

SIZES = {'portrait_cover_3x4.png': (1080, 1440), 'landscape_cover_4x3.png': (1440, 1080)}
CHECKS = ('mechanical_subject', 'topic_recognition', 'copy_consistency', 'text_readability',
          'portrait_composition', 'landscape_composition', 'structure_unobscured',
          'series_consistency', 'non_misleading', 'recommended_version_consistency')


def read(path):
    if not Path(path).is_file():
        raise ValueError('Cover missing required file: '+str(path))
    return json.loads(Path(path).read_text())


def binding(path):
    path = Path(path).resolve()
    return {'path': str(path), 'sha256': sha(path)}


def font_path():
    for path in ('/System/Library/Fonts/PingFang.ttc', '/System/Library/Fonts/Supplemental/Songti.ttc', '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'):
        if Path(path).is_file():
            return path
    raise ValueError('Cover BLOCKED: CJK font unavailable; specify font_path')


def prepare(task, paths=None):
    from .growth_report import paths_for
    task = Path(task).resolve()
    plan = read(task/'cover-plan.json')
    data = read(task/'task.json')
    if paths is None:
        paths = paths_for(task)
        for r, run in data.get('route_runs', {}).items():
            candidate = run.get('outputs', {}).get('candidate', {})
            if r in ROUTES and not paths[r].is_file() and candidate.get('path'):
                paths[r] = Path(candidate['path'])
    if plan.get('topic') != data['topic']:
        raise ValueError('Cover topic does not match task')
    route = plan.get('recommended_route')
    if route not in ROUTES or not str(plan.get('recommendation_reason', '')).strip():
        raise ValueError('Cover requires recommended_route and recommendation_reason')
    if set(plan.get('route_analysis', {})) != set(ROUTES):
        raise ValueError('Cover requires suitability analysis for all three routes')
    for analysis in plan['route_analysis'].values():
        if analysis.get('suitability') not in ('PASS', 'FAIL', 'UNKNOWN') or not analysis.get('reason'):
            raise ValueError('Cover requires route suitability and reason')
    title = plan.get('title', [])
    if not isinstance(title, list) or not 1 <= len(title) <= 2 or any(not isinstance(s, str) or not s.strip() or len(s) > 24 for s in title):
        raise ValueError('Cover title must contain 1-2 nonempty short lines (at most 24 characters each)')
    for key in ('series', 'copy_rationale', 'frame_rationale'):
        if not str(plan.get(key, '')).strip():
            raise ValueError('Cover missing '+key)
    candidates = plan.get('candidates', [])
    selected = next((c for c in candidates if c.get('id') == plan.get('selected_candidate') and c.get('route') == route), None)
    if selected is None:
        raise ValueError('Cover candidate missing for recommended version')
    sources = {}
    for r in ROUTES:
        if r not in paths or not Path(paths[r]).is_file():
            raise ValueError('Cover requires all three completed route videos: '+r)
        sources[r] = binding(paths[r])
    identifiers = set()
    for c in candidates:
        ident = c.get('id', '')
        if not ident or any(x not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_' for x in ident) or ident in identifiers:
            raise ValueError('Cover candidate IDs must be unique safe names')
        identifiers.add(ident)
        if c.get('route') not in ROUTES:
            raise ValueError('Invalid candidate route')
        seconds = c.get('seconds')
        duration = float(probe(sources[c['route']]['path'])['format']['duration'])
        if isinstance(seconds, bool) or not isinstance(seconds, (float, int)) or not math.isfinite(seconds) or not 0 <= seconds < duration:
            raise ValueError('Cover candidate time outside actual video')
        if not c.get('shot_id') or not c.get('mechanical_moment'):
            raise ValueError('Cover candidate requires shot and mechanical moment')
        box = c.get('subject_box')
        if not isinstance(box, list) or len(box) != 4 or not all(isinstance(x, (int,float)) and math.isfinite(x) for x in box) or not (0 <= box[0] < box[2] <= 1 and 0 <= box[1] < box[3] <= 1):
            raise ValueError('Cover requires normalized subject_box enclosing important structure')
        crop = c.get('source_crop', [0,0,1,1])
        if not isinstance(crop, list) or len(crop) != 4 or not all(isinstance(x, (int,float)) and math.isfinite(x) for x in crop) or not (0 <= crop[0] <= box[0] < box[2] <= crop[2] <= 1 and 0 <= crop[1] <= box[1] < box[3] <= crop[3] <= 1):
            raise ValueError('Cover crop must preserve the important subject_box')
    return plan, sources, selected


def compose(source, target, size, plan, box):
    """Contain the complete frame beneath a separate title band; never crop mechanics."""
    width, height = size
    canvas = Image.new('RGB', size, '#20252b')
    draw = ImageDraw.Draw(canvas)
    fp = plan.get('font_path') or font_path()
    title_font = ImageFont.truetype(fp, 70)
    series_font = ImageFont.truetype(fp, 34)
    draw.text((60, 38), plan['series'], font=series_font, fill='#ecbc72')
    band = 290
    for i, line in enumerate(plan['title']):
        if draw.textlength(line, font=title_font) > width-120:
            raise ValueError('Cover title exceeds safe width; shorten copy')
        draw.text((60, 100+i*85), line, font=title_font, fill='white')
    with Image.open(source) as im:
        im = im.convert('RGB')
        scale = min((width-80)/im.width, (height-band-60)/im.height)
        resized = im.resize((round(im.width*scale), round(im.height*scale)), Image.Resampling.LANCZOS)
        x, y = (width-resized.width)//2, band+(height-band-resized.height)//2
        canvas.paste(resized, (x,y))
        subject_width = (box[2]-box[0])*resized.width/width
        subject_height = (box[3]-box[1])*resized.height/height
        problems = []
        if subject_width < .30 or subject_height < .18:
            problems.append('Mechanical subject too small in composition')
        if max(ImageStat.Stat(im.resize((64,64))).stddev) < 4:
            problems.append('Source frame is blank or lacks visible structure')
    canvas.save(target, format='PNG')
    return {'status': 'FAIL' if problems else 'UNKNOWN', 'issues': problems,
            'layout': 'Full source frame contained below separate title band; no mechanical crop',
            'subject_fraction': [subject_width, subject_height]}


def generate(task, paths=None):
    task = Path(task).resolve()
    plan, sources, selected = prepare(task, paths)
    folder = task/'cover'; folder.mkdir(exist_ok=True)
    candidates_dir = folder/'candidates'; candidates_dir.mkdir(exist_ok=True)
    outputs = []; compositions = {}
    with tempfile.TemporaryDirectory() as tmp:
        for candidate in plan['candidates']:
            frame = Path(tmp)/'frame.png'
            subprocess.run(['ffmpeg','-v','error','-nostdin','-y','-ss',str(candidate['seconds']),
                            '-i',sources[candidate['route']]['path'],'-frames:v','1','-update','1',str(frame)],
                           check=True, capture_output=True)
            box = candidate['subject_box']
            if candidate.get('source_crop'):
                crop = candidate['source_crop']
                with Image.open(frame) as im:
                    im.crop(tuple(round(v * (im.width if i % 2 == 0 else im.height)) for i,v in enumerate(crop))).save(Path(tmp)/'cropped.png')
                frame = Path(tmp)/'cropped.png'
                box = [(box[i]-crop[i%2])/(crop[2+i%2]-crop[i%2]) for i in range(4)]
            for name, size in SIZES.items():
                target = candidates_dir/(candidate['id']+'-'+name)
                composition = compose(frame, target, size, plan, box)
                if candidate.get('source_crop'):
                    composition['layout'] = 'Approved source region contained below title; important subject_box preserved without stretching'
                    composition['source_crop'] = candidate['source_crop']
                outputs.append(binding(target))
                if candidate == selected:
                    final = folder/name
                    final.write_bytes(target.read_bytes())
                    outputs.append(binding(final)); compositions[name] = composition
    report = {'schema_version': 1, 'topic': plan['topic'], 'recommended_route': plan['recommended_route'],
              'source_media': sources, 'plan': binding(task/'cover-plan.json'), 'generator': binding(__file__),
              'font': binding(plan.get('font_path') or font_path()),
              'selected_candidate': selected, 'title': plan['title'], 'rationale': plan,
              'compositions': compositions, 'artifacts': outputs,
              'growth_goals': {'retention': '准确预告视频兑现的问题', 'engagement': '突出关键机械关系',
                               'following': '统一系列标题与视觉'},
              'cover_checks': {k: {'status': 'UNKNOWN', 'evidence': 'Independent exact-cover review required'} for k in CHECKS},
              'status': 'CANDIDATE_UNACCEPTED'}
    for name, key in zip(SIZES, ('portrait_composition', 'landscape_composition')):
        if compositions[name]['status'] == 'FAIL':
            report['cover_checks'][key] = compositions[name]
    md = folder/'cover-report.md'
    md.write_text('# 封面报告\n\n'+json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    report['artifacts'].append(binding(md))
    if any(sha(ref['path']) != ref['sha256'] for ref in [*sources.values(),report['plan']]):
        raise ValueError('Cover inputs changed during generation')
    write(folder/'cover-report.json', report)
    return report


def validate(task, require_pass=False, paths=None):
    task = Path(task).resolve()
    report = read(task/'cover/cover-report.json')
    plan, sources, selected = prepare(task, paths)
    if sources != report['source_media'] or selected != report['selected_candidate']:
        raise ValueError('Cover STALE: recommended version or media changed')
    for ref in [report['plan'], report['generator'], report['font'], *report['artifacts']]:
        if not Path(ref['path']).is_file() or sha(ref['path']) != ref['sha256']:
            raise ValueError('Cover STALE: source or artifact changed')
    for name, size in SIZES.items():
        with Image.open(task/'cover'/name) as im:
            if im.format != 'PNG' or im.size != size:
                raise ValueError('Cover dimensions/format invalid')
    if require_pass:
        qa = read(task/'cover/cover-qa.json')
        refs = {ref['path']: ref['sha256'] for ref in report['artifacts']}
        if not qa.get('independent_reviewer') or not qa.get('reviewer_thread_id') or qa.get('report_sha256') != sha(task/'cover/cover-report.json'):
            raise ValueError('Cover QA missing independent exact-report evidence')
        for key in CHECKS:
            row = qa.get('cover_checks', {}).get(key, {})
            reviewed = row.get('artifacts', [])
            required = {str(task/'cover'/name) for name in SIZES}
            if report['cover_checks'][key]['status'] == 'FAIL' or row.get('status') != 'PASS' or not row.get('evidence') or row.get('visual_inspection') is not True or {r.get('path') for r in reviewed} != required or any(refs.get(r.get('path')) != r.get('sha256') for r in reviewed):
                raise ValueError('Cover QA FAIL/UNKNOWN/missing or stale: '+key)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('task', type=Path)
    parser.add_argument('--validate', action='store_true')
    parser.add_argument('--require-pass', action='store_true')
    args = parser.parse_args()
    result = validate(args.task, args.require_pass) if args.validate or args.require_pass else generate(args.task)
    print(json.dumps({'status': result['status'], 'cover': str(args.task/'cover')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
