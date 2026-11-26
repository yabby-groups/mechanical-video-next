"""Run production-scene mechanics in Blender under the production lock.

From the repository root:
    uv run python tests/episode_mechanics_blender.py --work-dir work/mechanics-regression
Use the logged-in desktop executor for Metal on macOS.
Pass --wrench-picture with the 1080p30 wrench opening and its current
.motion.json to test two edits of the actual rendered source.
"""

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mechanical_video_next import episode
from mechanical_video_next.workflow import lock
from scripts.common import ROOT, filehash, writejson


CASES = [
    ('wrench', 'adjustable-wrench', 'scene.py', 0, 60, None, None),
    ('reverse', 'adjustable-wrench', 'scene.py', 0, 60,
     ('worm.rotation_euler.x = -TAU', 'worm.rotation_euler.x = TAU'), 'signed lead error'),
    ('ratio', 'adjustable-wrench', 'scene.py', 0, 60,
     ('-TAU * travel / PITCH', '-TAU * travel / (2 * PITCH)'), 'signed lead error'),
    ('slide', 'drawer-slide', 'scene.py', 2, 300, None, None),
    ('slide-section', 'drawer-slide', 'scene.py', 3, 180, None, None),
    ('limit', 'drawer-slide', 'scene.py', 2, 300,
     ('mid = 4.56 * a', 'mid = 6.2 * a'), 'Slide stage stroke'),
    ('spring-cycle', 'pop-up-toaster', 'scene.py', 7, 360, None, None),
    ('interference', 'pop-up-toaster', 'scene.py', 7, 360,
     ('slider.location.z = -TRAVEL*d', '''slider.location.z = -TRAVEL*d
        for support in slider.children:
            if support.name.startswith("Toast support rail"):
                support.location.z = 1.79 + .035 * ease(t, .19, .45)'''), 'Bread / rail signed gap'),
    ('separation', 'pop-up-toaster', 'scene.py', 7, 360,
     ('(x + side*.14, y, z) for side', '(x + side*.14, y, z + .024) for side'), 'Bread / rail signed gap'),
    ('cancel', 'pop-up-toaster', 'audience_scene.py', 5, 360, None, None),
    ('early-release', 'pop-up-toaster', 'audience_scene.py', 5, 360,
     ('original_pose(t, duration)\n            side_button', 'original_pose(t if t < 6.58 else t + .35, duration)\n            side_button'),
     'before the visible cancel press'),
]

REVIEWED_CASES = [
    ('tray-baseline', 'pop-up-toaster', 'scene.py', 6, 417, 'tray', None,
     'Fixed base blocks the crumb path'),
    ('tray-repaired', 'pop-up-toaster', 'service_scene.py', 6, 417, 'tray', None, None),
    ('worm-independent', 'adjustable-wrench', 'scene.py', 0, 60, 'worm_rack', None, None),
    ('worm-shared-error', 'adjustable-wrench', 'scene.py', 0, 60, 'worm_rack', (
        ('worm.rotation_euler.x = -TAU * travel / PITCH',
         'worm.rotation_euler.x = TAU * travel / PITCH'),
        ('travel - first_jaw + turns * PITCH', 'travel - first_jaw - turns * PITCH'),
    ), 'Independent worm / rack signed lead'),
]


def evaluate_reviewed_case(work, case):
    name, product, filename, shot, count, relation, changes, expected = case
    folder = work / name
    folder.mkdir(exist_ok=True)
    origin = ROOT / 'productions' / product
    scene = folder / filename
    if filename != 'scene.py':
        (folder / 'scene.py').write_bytes((origin / 'scene.py').read_bytes())
    source = (origin / filename).read_text()
    for old, new in changes or ():
        assert source.count(old) == 1, old
        source = source.replace(old, new)
    scene.write_text(source)
    timing = folder / 'timing.json'
    writejson(timing, [0] * shot + [count])
    args = ['--timing', timing, '--directory', folder, '--shot', shot]
    binding = {'scene': filehash(scene), 'frames': count, 'shot': shot}
    previous = folder / 'previous'
    previous.mkdir(exist_ok=True)
    legacy = episode.prepare_motion(scene, args, previous, binding)
    assert legacy['status'] == 'PASS'
    reviewed = folder / 'reviewed'
    reviewed.mkdir(exist_ok=True)
    verifier = origin / episode.episode_evidence.VERIFIER
    current = dict(binding, verifier=filehash(verifier),
                   runner=filehash(episode.episode_evidence.RELATIONS_RUNNER))
    try:
        motion = episode.prepare_motion(scene, args, reviewed, current,
                                        reviewer=(verifier, json.dumps([relation])))
    except ValueError as error:
        if expected and expected in str(error):
            return dict(case=name, status='PASS', legacy='PASS', rejected=str(error))
        raise
    assert expected is None, f'{name}: unchanged verifier accepted {expected}'
    return dict(case=name, status='PASS', legacy='PASS', evaluated_poses=motion['evaluated_poses'])


def evaluate_case(work, case):
    name, product, filename, shot, count, fault, expected = case
    folder = work / name
    folder.mkdir(exist_ok=True)
    origin = ROOT / 'productions' / product
    source = folder / filename
    if filename != 'scene.py':
        (folder / 'scene.py').write_bytes((origin / 'scene.py').read_bytes())
    text = (origin / filename).read_text()
    if fault:
        old, new = fault
        if text.count(old) != 1:
            raise AssertionError(f'{name}: expected one fault target')
        text = text.replace(old, new)
    source.write_text(text)
    timing = folder / 'timing.json'
    writejson(timing, [0] * shot + [count])
    command = ['--timing', timing, '--directory', folder, '--shot', shot]
    binding = {'scene': filehash(source), 'runner': filehash(episode.MECHANICS_SCRIPT),
               'scene_inputs': {str(path.relative_to(ROOT)): filehash(path) for path in (
                   origin / 'research.md', origin / 'scene.py',
                   ROOT / 'productions/quarter-turn-faucet/scene.py')},
               'shot': shot, 'frames': count}
    row = {'case': name, 'binding': binding}
    try:
        motion = episode.prepare_motion(source, command, folder, binding)
    except (ValueError, RuntimeError) as error:
        return dict(row, status='PASS' if expected and expected in str(error) else 'FAIL',
                    rejected=str(error))
    return dict(row, status='FAIL' if expected else 'PASS',
                evaluation_sha256=filehash(folder / 'evaluation.json'),
                **{key: motion[key] for key in ('blender', 'evaluated_poses', 'preview_range', 'preview_sha256')})


def check_wrench_cuts(work, picture):
    source = {'path': str(picture.resolve()), 'sha256': filehash(picture)}
    shots = [
        {'picture': source},
        {'picture': dict(source, start_frame=0), 'mechanics': {'checks': [
            {'channel': 'jaw_travel', 'continue_from': 'shot-0', 'max_cut_step': .014},
        ]}},
    ]
    speech = [(None, [], frames) for frames in (85, 85)]
    try:
        episode.picture_sources(work, speech, work, shots=shots)
    except ValueError as error:
        if 'mechanical_cut_jump' not in str(error):
            raise
        failed = json.loads((work / 'mechanics-preflight-failure.json').read_text())
    else:
        raise AssertionError('Rewinding to the closed jaw was accepted as a continuous cut')
    shots[1]['picture']['start_frame'] = 85
    pictures = episode.picture_sources(work, speech, work, shots=shots)
    findings = []
    for path, shot in zip(pictures, shots, strict=True):
        offset = shot['picture'].get('start_frame', 0)
        findings.extend(episode.video_review.pixel_findings(path, picture, 0, 85, offset, 'wrench-recut'))
    if findings:
        raise AssertionError(findings)
    return {'case': 'wrench-recut', 'status': 'PASS', 'source_sha256': source['sha256'],
            'rejected': failed, 'accepted_source_ranges': [[0, 85], [85, 170]],
            'recut_sha256': [filehash(path) for path in pictures]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-dir', required=True, type=Path)
    parser.add_argument('--wrench-picture', type=Path)
    parser.add_argument('cases', nargs='*')
    args = parser.parse_args()
    work = args.work_dir.resolve()
    work.mkdir(parents=True, exist_ok=True)
    studio = work / 'quarter-turn-faucet'
    if not studio.exists():
        studio.symlink_to(ROOT / 'productions/quarter-turn-faucet', target_is_directory=True)
    results = []
    with lock(ROOT / 'work/production.lock', wait=True):
        for case in CASES:
            if args.cases and case[0] not in args.cases:
                continue
            result = evaluate_case(work, case)
            results.append(result)
            print(json.dumps(result), flush=True)
        for case in REVIEWED_CASES:
            if args.cases and case[0] not in args.cases:
                continue
            result = evaluate_reviewed_case(work, case)
            results.append(result)
            print(json.dumps(result), flush=True)
    if args.wrench_picture:
        results.append(check_wrench_cuts(work, args.wrench_picture))
        print(json.dumps(results[-1]), flush=True)
    writejson(work / 'results.json', results)
    if not results or any(row['status'] != 'PASS' for row in results):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
