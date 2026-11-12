#!/usr/bin/env -S uv run python
"""Seven bounded production regressions. --run executes real tools serially.

This is a deterministic regression harness, not a Codex or perceptual reviewer.
All generated media remain unaccepted workprints. Failed commands stop the run.
"""
import argparse
import copy
import json
from pathlib import Path
import subprocess
import sys
import time
import struct

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))
from common import budget, filehash, writejson
from mechanical_video_next import workflow as w

NAMES = {1: 'baseline', 2: 'second-video-same-model', 3: 'voice-only',
         4: 'subtitle-only', 5: 'single-explode-shot',
         6: 'independent-qa-local-repair', 7: 'unqualified-model-safe-stop'}


def configuration(number, first, second):
    cfg = copy.deepcopy(second if number == 2 else first)
    cfg['id'] = 'acceptance-' + NAMES[number]
    if number == 3:
        # Use existing known audio, change speech only. This fixture intentionally
        # mismatches subtitles and cannot receive a synchronization PASS.
        overall = next(s for s in second['storyboard'] if s['shot'] == 'overall')
        cfg['storyboard'][0]['narration'] = copy.deepcopy(overall['narration'])
    elif number == 4:
        s = cfg['storyboard'][0]
        s['subtitles'][0] = '(测试字幕)' + s['subtitles'][0]
    elif number == 5:
        cfg['shots']['explode']['distance'] = 1.9
    return cfg


def observations(log):
    rows = []
    for line in log.read_text().splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict) and 'cache_hit' in row:
            rows.append(row)
    return rows


def invoke(cfgpath, phase, directory):
    """Collect only current subprocess observations; never select historic runs."""
    budget()
    logfile = directory / (phase + '-' + str(time.time_ns()) + '.log')
    started = time.time()
    with logfile.open('w') as out:
        result = subprocess.run(['uv', 'run', '--project', str(ROOT), 'python', str(ROOT / 'scripts/produce.py'),
                                 str(cfgpath), '--phase', phase], cwd=ROOT,
                                stdout=out, stderr=subprocess.STDOUT)
    rows = observations(logfile)
    return dict(phase=phase, seconds=round(time.time()-started, 3),
                returncode=result.returncode, log=str(logfile),
                log_sha256=filehash(logfile), observations=rows,
                cache_hit_rate=sum(r['cache_hit'] for r in rows)/len(rows) if rows else None,
                full_shot_renders=sum(r['stage'].startswith('final:') and not r['cache_hit']
                                      for r in rows),
                composition_renders=sum(r['stage'].startswith('composition:') and not r['cache_hit']
                                        for r in rows))


def keys_are_safe(cfg):
    import produce
    evidence = []
    for shot in cfg['shots'].values():
        folder = produce.CACHE / 'shots' / produce.shot_key(shot, 'keys', cfg['render'], cfg.get('assembly_config'))
        marker = folder / 'complete.json'
        if not marker.is_file():
            raise ValueError('Missing keyframe cache')
        files = list(json.loads(marker.read_text()))
        if not produce.cached(folder, files):
            raise ValueError('Keyframe hashes changed')
        checks = json.loads((folder / 'checks.json').read_text())['checks']
        if checks.get('min_projected_margin', -1) < 0:
            raise ValueError('Projected keyframe boundary failure')
        if any(gap <= 0 for gap in checks.get('exploded_axial_gaps', {}).values()):
            raise ValueError('Exploded axial gap failure')
        evidence.append(dict(path=str(folder / 'checks.json'), sha256=filehash(folder / 'checks.json')))
    return evidence


def reject_unqualified(directory):
    task = w.create_task('unqualified fixture', task_id='reject-' + str(time.time_ns()), root=directory,
                         protocol_version=1)  # isolate the historical asset-rejection regression
    w.put_handoff(task, 'Research', 'research', {'facts': []})
    w.put_handoff(task, 'Research', 'script', {'shots': []}, ['research'])
    w.put_handoff(task, 'Asset', 'asset-plan', {'qualified': False, 'reason': 'single mesh fixture'})
    w.advance(task, 'RESEARCHING')
    try:
        w.advance(task, 'ASSET_READY')
    except ValueError as exc:
        if 'not qualified' not in str(exc):
            raise
        w.advance(task, 'BLOCKED')
        return dict(status='SAFE_REJECTION_VERIFIED', task=str(task), reason=str(exc),
                    media_generated=False, full_shot_renders=0)
    raise AssertionError('Unqualified asset incorrectly advanced')


def reject_single_mesh(directory):
    """Real GLB/importer negative integration: a CC0 triangle is not an assembly."""
    directory.mkdir(parents=True, exist_ok=True)
    source = directory / 'controlled-single-mesh.glb'
    geometry = struct.pack('<9f', 0, 0, 0, 1, 0, 0, 0, 1, 0)
    document = {'asset': {'version': '2.0', 'generator': 'negative test fixture'},
                'scene': 0, 'scenes': [{'nodes': [0]}], 'nodes': [{'mesh': 0}],
                'meshes': [{'primitives': [{'attributes': {'POSITION': 0}}]}],
                'buffers': [{'byteLength': len(geometry)}],
                'bufferViews': [{'buffer': 0, 'byteOffset': 0, 'byteLength': len(geometry), 'target': 34962}],
                'accessors': [{'bufferView': 0, 'componentType': 5126, 'count': 3,
                               'type': 'VEC3', 'min': [0, 0, 0], 'max': [1, 1, 0]}]}
    body = json.dumps(document, separators=(',', ':')).encode()
    body += b' ' * (-len(body) % 4)
    source.write_bytes(struct.pack('<III', 0x46546c67, 2, 12+8+len(body)+8+len(geometry))
                       + struct.pack('<II', len(body), 0x4e4f534a) + body
                       + struct.pack('<II', len(geometry), 0x004e4942) + geometry)
    before = set((ROOT/'assets/assemblies').iterdir())
    start = time.time()
    logfile = directory/'single-mesh-rejection.log'
    with w.lock(ROOT/'work/production.lock'), logfile.open('w') as log:
        result = subprocess.run(['uv', 'run', '--project', str(ROOT), 'python', str(ROOT/'scripts/import_asset.py'), str(source),
                                 '--origin', 'local:controlled-CC0-negative-fixture',
                                 '--license', 'CC0-1.0', '--version', 'negative-v1'],
                                stdout=log, stderr=subprocess.STDOUT, cwd=ROOT)
    after = set((ROOT/'assets/assemblies').iterdir())
    # Importer redirects the Blender assertion to a deterministic work log.
    from common import digest
    key = digest({'content': filehash(source), 'origin': 'local:controlled-CC0-negative-fixture',
                  'license': 'CC0-1.0', 'version': 'negative-v1'})
    importlog = ROOT/'work/imports'/key/'import.log'
    if (result.returncode == 0 or before != after or not importlog.exists()
            or 'Single monolithic mesh is not an explodable assembly' not in importlog.read_text()):
        raise AssertionError('Actual single-mesh rejection not established; inspect retained logs')
    return dict(status='ACTUAL_SINGLE_MESH_REJECTED', seconds=round(time.time()-start, 3),
                fixture_sha256=filehash(source), returncode=result.returncode,
                import_log=str(importlog), import_log_sha256=filehash(importlog),
                assets_unchanged=True, full_shot_renders=0)


def run_scenarios(selected, execute=False, destination=None):
    destination = destination or ROOT / 'output/multi-agent-pilot'
    destination.mkdir(parents=True, exist_ok=True)
    first = json.loads((ROOT / 'tests/fixtures/production/planetary-01.json').read_text())
    second = json.loads((ROOT / 'tests/fixtures/production/planetary-02.json').read_text())
    started = time.time()
    report = dict(schema_version=1, mode='deterministic-regression-not-agent-dispatch',
                  started_epoch=started, tokens=None, agent_seconds=None,
                  human_interventions=None, rework_count=0,
                  quality_acceptance='UNKNOWN', scenarios=[])
    target = destination / 'acceptance.json'
    for number in selected:
        row = dict(scenario=number, name=NAMES[number], status='PENDING',
                   token_usage=None, agent_seconds=None, human_interventions=None,
                   rework_count=0, quality_acceptance='UNKNOWN', runs=[])
        report['scenarios'].append(row)
        writejson(target, report)
        if not execute:
            continue
        budget()
        if number == 6:
            row['reason'] = 'Requires actual independent QA issue, repairs.py execution and independent recheck; not simulated by harness'
            continue
        directory = destination / 'acceptance-configs' / str(number)
        directory.mkdir(parents=True, exist_ok=True)
        if number == 7:
            row.update(reject_unqualified(directory))
            row['actual_import_rejection'] = reject_single_mesh(directory)
            continue
        cfg = configuration(number, first, second)
        cfgpath = directory / 'video.json'
        writejson(cfgpath, cfg)
        row.update(config=str(cfgpath), config_sha256=filehash(cfgpath))
        import produce
        row['shot_key_changes'] = {
            quality: [name for name in first['shots']
                      if produce.shot_key(first['shots'][name], quality, first['render'], first.get('assembly_config')) !=
                      produce.shot_key(cfg['shots'][name], quality, cfg['render'], cfg.get('assembly_config'))]
            for quality in ('keys', 'preview', 'final')}
        expected_changes = ['explode'] if number == 5 else []
        if any(changes != expected_changes for changes in row['shot_key_changes'].values()):
            raise AssertionError('Unexpected shot cache invalidation')
        if number == 3:
            row['fixture_warning'] = 'Speech text changed using existing cached Neil audio; subtitle text deliberately fixed. Expected synchronization mismatch, not voice-timbre evaluation.'
        # Every run uses the same production mutex as the Codex stage runner.
        with w.lock(ROOT / 'work/production.lock'):
            phases = ['keys', 'preview', 'final'] if number == 5 else ['final']
            for phase in phases:
                result = invoke(cfgpath, phase, directory)
                row['runs'].append(result)
                observed = [r for run in row['runs'] for r in run.get('observations', [])]
                row.update(seconds=sum(r.get('seconds', 0) for r in row['runs']),
                           cache_hit_rate=sum(r['cache_hit'] for r in observed)/len(observed) if observed else None,
                           full_shot_renders=sum(r.get('full_shot_renders', 0) for r in row['runs']))
                if result['returncode']:
                    row['status'] = 'FAILED'
                    break
                if phase == 'keys':
                    try:
                        row['keyframe_technical_evidence'] = keys_are_safe(cfg)
                    except ValueError as exc:
                        row.update(status='FAILED', reason=str(exc))
                        break
                    row['keyframe_visual_acceptance'] = 'UNKNOWN'
            if row['status'] == 'FAILED':
                report['stopped_on_failure'] = number
                break
        final = ROOT / 'output' / (cfg['id'] + '-final.mp4')
        validation = final.with_suffix('.validation.json')
        if not final.is_file() or not validation.is_file():
            raise ValueError('Successful command lacks final validation artifacts')
        v = json.loads(validation.read_text())
        if v.get('sha256') != filehash(final):
            raise ValueError('Final validation hash mismatch')
        rows = [r for run in row['runs'] for r in run['observations']]
        row.update(status='TECHNICAL_WORKPRINT_ONLY', seconds=sum(r['seconds'] for r in row['runs']),
                   cache_hit_rate=sum(r['cache_hit'] for r in rows)/len(rows) if rows else None,
                   full_shot_renders=sum(r['full_shot_renders'] for r in row['runs']),
                   final=dict(path=str(final), sha256=filehash(final)),
                   validation=dict(path=str(validation), sha256=filehash(validation)))
    report['elapsed_seconds'] = round(time.time()-started, 3)
    writejson(target, report)
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run', action='store_true')
    p.add_argument('--scenario', nargs='+', type=int, choices=range(1, 8), default=list(range(1, 8)))
    p.add_argument('--output', type=Path)
    a = p.parse_args()
    report = run_scenarios(a.scenario, a.run, a.output)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report.get('stopped_on_failure'):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
