"""Diagnose Blender capabilities and test an exact project scene in isolation."""

import argparse
import json
from pathlib import Path

from PIL import Image

from scripts.common import ROOT, budget, filehash, writejson
from .blender_runtime import run_blender


PROBE = ROOT / 'blender/render_preflight.py'


def probe_frame(directory, *, name, timeout, scene=None, frame=None, engine=None, device=None):
    path = directory / 'frame.png'
    args = ['--factory-startup', '--disable-autoexec']
    if scene is not None:
        args.append(scene)
    args += ['--python-exit-code', '23', '--python', PROBE, '--', 'render',
             '--output', path.resolve()]
    if scene is None:
        args.append('--factory-scene')
    if frame is not None:
        args += ['--frame', frame]
    if engine:
        args += ['--engine', engine]
    if device:
        args += ['--device', device]
    row = run_blender(args, name=name, directory=directory, timeout=timeout,
                      allow_failure=True, engine=engine)
    skipped = next((event for event in row['events'] if event['phase'] == 'skipped'), None)
    if skipped and row['status'] == 'PASS':
        row.update(status='SKIP', reason=skipped['reason'])
    elif row['status'] == 'PASS':
        try:
            with Image.open(path) as image:
                image.load()
                row['image'] = dict(path=str(path.resolve()), sha256=filehash(path),
                                    pixels=list(image.size), mode=image.mode)
        except OSError as exc:
            from .blender_runtime import render_crash_report
            row.update(status='FAIL', classification='ENGINE_ERROR',
                       evidence=[f'Blender reported success but did not produce a decodable image: {exc}'])
            render_crash_report(row, directory, 0, '', '')
    writejson(row['report'], row)
    return row


def render_engine_fallback(failure, scene, frame, directory, *, timeout=300):
    """Render a review candidate only after specific engine evidence."""
    evidence = ' '.join(failure.get('evidence', ())).lower()
    reasons = ('mvn_engine_unsupported: blender_eevee', 'eevee', 'cuda error',
               'cuda device not found', 'hip error', 'opening metal', 'compiling metal',
               'no compatible cycles device', 'no compatible metal device')
    requested = failure.get('engine')
    requested_device = next((e.get('device') for e in failure.get('events', ())
                             if e['phase'] == 'preflight_start'), None)
    compatible = (failure.get('classification') == 'ENGINE_ERROR'
                  and requested in {'BLENDER_EEVEE', 'CYCLES'}
                  and requested_device != 'CPU'
                  and any(reason in evidence for reason in reasons)
                  and scene is not None and Path(scene).is_file())
    report = dict(status='NOT_APPLICABLE', original_engine=requested, original_failure=failure['report'],
                  reason='A compatible alternative requires evidence of an engine/device error and a saved scene.')
    if compatible:
        report.update(scene=str(scene), scene_sha256=filehash(scene), frame=frame)
        alternative = 'CYCLES'
        device = 'CPU'
        report['candidate_engine'] = alternative
        report['candidate_device'] = device
        try:
            budget()
        except RuntimeError as exc:
            report.update(status='FAIL', classification='RESOURCE_ERROR', evidence=[str(exc)])
        else:
            candidate = probe_frame(directory / 'cycles-cpu-candidate', name='engine-fallback',
                                    timeout=timeout, scene=scene, frame=frame,
                                    engine=alternative, device=device)
            before = next((e for e in candidate['events'] if e['phase'] == 'original_settings'), {})
            after = next((e for e in candidate['events'] if e['phase'] == 'preflight_start'), {})
            report.update(
                status='NEEDS_REVIEW' if candidate['status'] == 'PASS' else 'FAIL',
                candidate=candidate['report'], image=candidate.get('image'),
                settings={key: {'original': before.get(key), 'candidate': after.get(key)}
                          for key in ('engine', 'device', 'resolution', 'camera', 'lights',
                                      'materials', 'view_transform', 'samples')},
                review_requirements=[
                    'Compare material shading and transparency, lighting/shadows, reflections and noise.',
                    'Compare resulting pixels against an approved original-engine frame where available.',
                ])
    path = directory / 'render_engine_fallback.json'
    writejson(path, report)
    return path


def render_diagnostics(output, *, scene, frame=None, timeout=300):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    scene = Path(scene).resolve(strict=True)
    budget()
    results = []
    version = run_blender(['--factory-startup'], name='background-startup', directory=output / 'background-startup',
                          timeout=min(30, timeout), allow_failure=True)
    results.append(version)
    api = run_blender(['--factory-startup', '--python-exit-code', '23', '--python', PROBE,
                       '--', 'api'], name='python-api', directory=output / 'python-api',
                      timeout=min(30, timeout), allow_failure=True)
    results.append(api)
    for name, engine, device in (
        ('workbench', 'BLENDER_WORKBENCH', None),
        ('eevee', 'BLENDER_EEVEE', None),
        ('cycles-cpu', 'CYCLES', 'CPU'),
        ('cycles-metal', 'CYCLES', 'METAL'),
        ('project-scene', None, None),
    ):
        actual = name == 'project-scene'
        results.append(probe_frame(output / name, name=name, engine=engine, device=device,
                                   timeout=timeout, scene=scene if actual else None,
                                   frame=frame if actual else 1))
    for result in results:
        if not result['blender_version']:
            result['blender_version'] = version['blender_version']
            writejson(result['report'], result)
    project = results[-1]
    fallback_report = None
    if project['status'] != 'PASS':
        fallback_report = render_engine_fallback(project, scene, frame, output, timeout=timeout)
    receipt = dict(scene=str(scene), scene_sha256=filehash(scene), frame=frame,
                   blender_version=version['blender_version'], tests=results,
                   fallback_report=str(fallback_report) if fallback_report else None,
                   status='PASS' if all(r['status'] in {'PASS', 'SKIP'} for r in results) else 'FAIL')
    writejson(output / 'render_diagnostics.json', receipt)
    return receipt


def main():
    from .workflow import lock

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scene', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--frame', type=int)
    parser.add_argument('--timeout', type=float, default=300, help='Wall-clock seconds per render')
    args = parser.parse_args()
    with lock(ROOT / 'work/production.lock'):
        result = render_diagnostics(args.output, scene=args.scene, frame=args.frame, timeout=args.timeout)
    print(json.dumps({'status': result['status'], 'report': str(args.output / 'render_diagnostics.json'),
                      'tests': {r['name']: r['status'] for r in result['tests']}}, ensure_ascii=False))
    return 0 if result['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
