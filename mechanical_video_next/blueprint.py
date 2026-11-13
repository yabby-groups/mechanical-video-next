"""Compile explicit blueprint mappings and render unapproved static animatics."""
import argparse
import copy
import json
import math
from pathlib import Path
import subprocess
import tempfile
import textwrap
import time

from scripts.common import ROOT, Metrics, budget, filehash, probe, writejson
from .viral import validate_creative_blueprint
from .workflow import lock, digest

TEMPLATES = {'overall', 'detail', 'motion', 'explode', 'assemble', 'exploded', 'layered'}
CAMERA = {'camera_view', 'camera_direction', 'camera_roll'}


def number(v):
    return not isinstance(v, bool) and isinstance(v, (int, float)) and math.isfinite(v)


def validate(data):
    """Validate the executable subset; no claim of scientific/media acceptance."""
    if not isinstance(data.get('shots'), list) or not data['shots']:
        raise ValueError('Nonempty structured shots required')
    if data.get('content_policy_version') == 1:
        from .growth import validate_contract
        validate_contract(data)
    maximum = 300 if data.get('content_policy_version') == 1 else 120
    end, ids = 0, set()
    for s in data['shots']:
        required = {'shot_id', 'time_range', 'knowledge_goal', 'mechanical_action',
                    'asset', 'template', 'camera', 'narration', 'subtitles', 'overlays'}
        if not isinstance(s, dict) or not required <= s.keys():
            raise ValueError('Shot missing executable fields')
        if any(not isinstance(s[k], str) or not s[k].strip() for k in
               ('shot_id', 'knowledge_goal', 'mechanical_action', 'asset', 'template')):
            raise ValueError('Shot identifiers and decisions must be nonempty strings')
        if s['shot_id'] in ids or s['template'] not in TEMPLATES:
            raise ValueError('Duplicate shot ID or unknown template mapping')
        ids.add(s['shot_id'])
        t = s['time_range']
        if (not isinstance(t, list) or len(t) != 2 or not all(number(x) for x in t)
                or abs(t[0]-end) > 1e-8 or t[1] <= t[0] or t[1] > maximum):
            raise ValueError('Timeline must be contiguous from zero, positive, within the versioned duration limit')
        end = t[1]
        camera = s['camera']
        if not isinstance(camera, dict) or not camera or not set(camera) <= CAMERA:
            raise ValueError('Unsupported or empty camera mapping')
        if camera.get('camera_view', 'oblique') not in {'oblique', 'top'}:
            raise ValueError('Unsupported camera_view')
        if 'camera_roll' in camera and not number(camera['camera_roll']):
            raise ValueError('camera_roll must be finite')
        if 'camera_direction' in camera:
            d = camera['camera_direction']
            if not isinstance(d, list) or len(d) != 3 or not all(number(v) for v in d) or not any(d):
                raise ValueError('camera_direction requires a nonzero finite vector')
        for key in ('narration', 'subtitles', 'overlays'):
            if not isinstance(s[key], list) or any(not isinstance(v, str) or not v.strip() for v in s[key]):
                raise ValueError(key + ' must be a list of nonempty strings')
        if not s['narration'] or len(s['narration']) != len(s['subtitles']):
            raise ValueError('One subtitle per narration utterance required')
    return end


def compile_config(blueprint, base, output, draft=False):
    blueprint, base, output = map(Path, (blueprint, base, output))
    if {output.resolve(), output.with_suffix('.binding.json').resolve()} & {blueprint.resolve(), base.resolve()}:
        raise ValueError('Output must not overwrite blueprint or base')
    data, cfg = json.loads(blueprint.read_text()), json.loads(base.read_text())
    validate(data)
    if data.get('status') != 'FROZEN' and not draft:
        raise ValueError('FROZEN blueprint required; --draft marks unapproved diagnostic output')
    if not draft:
        validate_creative_blueprint(data)
    result, shots, storyboard, mappings = copy.deepcopy(cfg), {}, [], []
    for s in data['shots']:
        key = s.get('existing_shot')
        if not isinstance(key, str) or key not in cfg['shots']:
            raise ValueError('Unknown existing_shot mapping: ' + str(key))
        if s['asset'] != cfg['asset']:
            raise ValueError('Blueprint asset does not match base assembly')
        original = cfg['shots'][key]
        if original['template'] != s['template']:
            raise ValueError('Template must match existing shot; geometry tracks cannot be repurposed')
        shot = copy.deepcopy(original)
        shot.update(s['camera'])
        shot['seconds'] = s['time_range'][1] - s['time_range'][0]
        sid = s['shot_id']; shots[sid] = shot
        inherited = next((x for x in cfg.get('storyboard', []) if x['shot'] == key), {})
        row = {k: copy.deepcopy(inherited[k]) for k in ('accent', 'formula') if k in inherited}
        row.update(id=sid, shot=sid, seconds=shot['seconds'], label=s['knowledge_goal'],
                   note=' / '.join(s['overlays']), narration=s['narration'], subtitles=s['subtitles'])
        row.setdefault('accent', '#8dc4dc'); storyboard.append(row)
        mappings.append(dict(shot_id=sid, existing_shot=key, time_range=s['time_range'],
                             knowledge_goal=s['knowledge_goal'], mechanical_action=s['mechanical_action'],
                             asset=s['asset'], template=s['template'], camera=s['camera'],
                             overlays=s['overlays'], motion_validation='UNKNOWN'))
    result.update(id=cfg.get('id', 'video') + '-blueprint-' + filehash(blueprint)[:16], shots=shots, storyboard=storyboard,
                  blueprint_program_sha256=digest({k: val for k, val in data.items() if k != 'production_config'}),
                  production_status='DRAFT_UNAPPROVED' if draft else 'BLUEPRINT_BOUND_UNVALIDATED')
    if data.get('content_policy_version') == 1:
        from .growth import shot_requirements
        result.update(content_policy_version=1, growth_goals=copy.deepcopy(data['growth_goals']))
        for row, shot in zip(storyboard, data['shots']):
            row.update(shot_requirements(shot))
        for row, shot in zip(mappings, data['shots']):
            row.update(shot_requirements(shot))
    writejson(output, result)
    binding = dict(schema_version=1, status=result['production_status'], blueprint_path=str(blueprint.resolve()),
                   blueprint_program_sha256=result['blueprint_program_sha256'],
                   blueprint_sha256=filehash(blueprint), base_config_sha256=filehash(base),
                   config_sha256=filehash(output), shot_requirements=mappings,
                   scientific_acceptance='UNKNOWN', visual_acceptance='UNKNOWN', listening='UNKNOWN')
    writejson(output.with_suffix('.binding.json'), binding)
    return binding


def image_source(s, directory):
    spec = s.get('animatic', {})
    if not isinstance(spec, dict):
        raise ValueError('animatic must be an object')
    if not spec.get('image'):
        return None
    image = (directory / spec['image']).resolve()
    if image.suffix.lower() not in {'.png', '.jpg', '.jpeg'} or not image.is_file():
        raise ValueError('Existing static PNG/JPEG screenshot required')
    if filehash(image) != spec.get('sha256'):
        raise ValueError('Animatic image hash mismatch: ' + str(image))
    return image


def sampled_run(args, log, metrics):
    """Stop the subprocess on a 0.5-second budget sample failure; retain its log."""
    Path(log).parent.mkdir(parents=True, exist_ok=True)
    with Path(log).open('w') as handle:
        with subprocess.Popen([str(a) for a in args], stdout=handle, stderr=subprocess.STDOUT) as process:
            try:
                while True:
                    try:
                        code = process.wait(timeout=.5)
                    except subprocess.TimeoutExpired:
                        code = None
                    used = budget()
                    metrics.peak = max(metrics.peak, used)
                    metrics.temp_samples.append(dict(epoch=time.time(), bytes=used))
                    if code is not None:
                        if code:
                            raise subprocess.CalledProcessError(code, args)
                        break
            except BaseException:
                process.terminate()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill(); process.wait()
                raise


def animatic(blueprint, output):
    blueprint, output = Path(blueprint).resolve(), Path(output).resolve()
    data = json.loads(blueprint.read_text()); duration = validate(data)
    sources = [image_source(s, blueprint.parent) for s in data['shots']]
    if any(abs(t*15-round(t*15)) > 1e-6 for s in data['shots'] for t in s['time_range']):
        raise ValueError('Animatic boundaries must fall on 15fps frames')
    font = next((p for p in (Path('/System/Library/Fonts/PingFang.ttc'),
                            Path('/System/Library/Fonts/STHeiti Medium.ttc'),
                            Path('/System/Library/Fonts/Supplemental/Songti.ttc'),
                            Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')) if p.is_file()), None)
    if font is None:
        raise ValueError('No supported drawtext font available')
    # Prefer PingFang; macOS also ships Chinese glyphs in Heiti and Songti.
    if font.name == 'DejaVuSans.ttf' and any(ord(c) > 127 for c in json.dumps(data, ensure_ascii=False)):
        raise ValueError('Chinese animatic requires an installed Chinese font')
    output.mkdir(parents=True, exist_ok=True)
    manifest_path, media = output/'animatic-manifest.json', output/'animatic.mp4'
    if media.exists() or manifest_path.exists() or (output/'animatic.failed.json').exists():
        raise ValueError('Use a new output directory; existing animatic is immutable')
    with lock(ROOT/'work/production.lock'):
        metrics = Metrics('blueprint-animatic-' + str(time.time_ns()))
        metrics.temp_samples = []
        try:
            with tempfile.TemporaryDirectory(prefix='animatic-', dir=ROOT/'work') as tmp:
                work, pieces, coverage = Path(tmp), [], []
                for i, (s, source) in enumerate(zip(data['shots'], sources)):
                    started = time.time(); seconds = s['time_range'][1]-s['time_range'][0]
                    # Keep diagnostic metadata above the model and speech below
                    # it. Text must not conceal the very mechanism QA inspects.
                    caption = '\n'.join([*s['subtitles'], *s['overlays']])
                    text = work/f'caption-{i}.txt'
                    wrapped = '\n'.join(textwrap.fill(line, 36) for line in caption.splitlines())
                    if len(wrapped.splitlines()) > 4:
                        raise ValueError('Animatic caption exceeds reserved four-line band; split the utterance or shot')
                    text.write_text(wrapped)
                    title = work/f'title-{i}.txt'
                    title.write_text(s['shot_id'] + ' | ' + s['knowledge_goal'])
                    watermark = work/'watermark.txt'
                    watermark.write_text('PROVISIONAL / STATIC PLACEHOLDER')
                    # All filter paths are generated safe filenames, never user text or image paths.
                    vf = ('scale=960:310:force_original_aspect_ratio=decrease,pad=960:540:(ow-iw)/2:100:color=0x555555,'
                          f"drawtext=fontfile='{font}':textfile={watermark}:fontcolor=yellow:fontsize=24:x=20:y=20,"
                          f"drawtext=fontfile='{font}':textfile={title}:expansion=none:fontcolor=white:fontsize=20:x=20:y=65,"
                          f"drawtext=fontfile='{font}':textfile={text}:expansion=none:fontcolor=white:fontsize=24:"
                          'x=20:y=430:box=1:boxcolor=black@0.7:boxborderw=8')
                    args = ['ffmpeg', '-v', 'error', '-nostdin', '-n']
                    args += ['-loop', '1', '-i', str(source)] if source else ['-f', 'lavfi', '-i', 'color=c=0x555555:s=960x540:r=15']
                    piece = work/f'shot-{i}.mp4'
                    sampled_run(args + ['-vf', vf, '-r', '15', '-frames:v', str(round(seconds*15)),
                                '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-an', str(piece)], output/'logs'/f'shot-{i}.log', metrics)
                    pieces.append(piece); metrics.record('static-shot', started, shot_id=s['shot_id'])
                    coverage.append(dict(shot_id=s['shot_id'], time_range=s['time_range'],
                                         kind='STATIC_SCREENSHOT' if source else 'GRAY_SLATE',
                                         image=str(source) if source else None,
                                         sha256=filehash(source) if source else None, mechanical_motion='NOT_SHOWN'))
                listing = work/'concat.txt'
                listing.write_text(''.join("file '" + str(p) + "'\n" for p in pieces))
                started = time.time()
                sampled_run(['ffmpeg', '-v', 'error', '-nostdin', '-n', '-f', 'concat', '-safe', '0', '-i', listing,
                     '-c', 'copy', '-movflags', '+faststart', media], output/'logs'/'concat.log', metrics)
                sampled_run(['ffmpeg', '-v', 'error', '-xerror', '-i', media, '-f', 'null', '-'], output/'logs'/'decode.log', metrics)
                info = probe(media)
                video = next(s for s in info['streams'] if s['codec_type'] == 'video')
                if abs(float(info['format']['duration'])-duration) > 1/15+.001 or (video['width'], video['height']) != (960, 540):
                    raise ValueError('Encoded animatic timeline/dimensions mismatch')
                metrics.record('concat-and-decode', started)
                manifest = dict(status='DRAFT_UNAPPROVED', blueprint_sha256=filehash(blueprint),
                                media_sha256=filehash(media), media=str(media), duration_seconds=duration,
                                coverage=coverage, full_decode='PASS', listening='UNKNOWN', continuous_viewing='UNKNOWN',
                                core_mechanics='UNKNOWN', production_approved=False, probe=info)
                manifest['layout'] = {'model_band_y': [100, 410], 'caption_band_y': [422, 534],
                                      'title_band_y': [65, 85], 'text_model_band_overlap_pixels': 0}
                writejson(manifest_path, manifest)
                return manifest
        except BaseException as error:
            writejson(output/'animatic.failed.json', dict(status='FAILED', error=str(error),
                      blueprint_sha256=filehash(blueprint), production_approved=False,
                      logs=[str(p) for p in sorted((output/'logs').glob('*.log'))],
                      temp_peak_sampled_bytes=metrics.peak, temp_samples=metrics.temp_samples))
            raise
        finally:
            metrics.finish(tokens=None, cost=None, human_interventions=None, temp_sample_interval_seconds=.5,
                           temp_samples=metrics.temp_samples)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for command in ('compile', 'animatic'):
        p = sub.add_parser(command)
        p.add_argument('--blueprint', required=True, type=Path); p.add_argument('--output', required=True, type=Path)
        if command == 'compile':
            p.add_argument('--base', required=True, type=Path); p.add_argument('--draft', action='store_true')
    a = parser.parse_args(argv)
    result = compile_config(a.blueprint, a.base, a.output, a.draft) if a.command == 'compile' else animatic(a.blueprint, a.output)
    print(json.dumps({'status': result['status'], 'output': str(a.output)}))


if __name__ == '__main__':
    main()
