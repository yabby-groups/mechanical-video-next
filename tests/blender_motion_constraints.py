"""Bounded real-bpy kinematics integration; no rendering or product acceptance.

Run only after the Producer releases the existing production lock:
Blender --background --factory-startup --python-exit-code 1 --python THIS --
  --repo /absolute/repo --receipt /private/tmp/blender-motion-constraints.json
By default this exercises repository sources. Optional --sources DIR tests the
flat science_shots.py/science_scene.py copies in an unapplied patch directory.
The runner takes that same nonblocking lock; it never renders or saves a blend.
"""
import argparse
import fcntl
import hashlib
import importlib.util
import json
from pathlib import Path
import platform
import sys
import time
import traceback


COUNT = 5


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--sources', type=Path)
    parser.add_argument('--receipt', type=Path, default=Path('/private/tmp/blender-motion-constraints.json'))
    args = parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    repo = args.repo.resolve()
    sources = args.sources.resolve() if args.sources else None
    lock_path = repo/'work/production.lock'
    with lock_path.open('a') as lock:
        # Do not compete or wait invisibly for the existing sole Producer.
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        execute(args, repo, sources, lock_path)


def execute(args, repo, sources, lock_path):
    import bpy
    sys.path.insert(0, str(repo))
    sys.path.insert(0, str(repo/'blender'))
    schema_path = sources/'science_shots.py' if sources else repo/'mechanical_video_next/science_shots.py'
    adapter_path = sources/'science_scene.py' if sources else repo/'blender/science_scene.py'
    schema = load('motion_integration_schema', schema_path)
    adapter = load('science_scene', adapter_path)
    # This real production helper reads evaluated shape-key vertices/matrix_world.
    guides = load('science_guides', repo/'blender/science_guides.py')
    paths = [Path(__file__).resolve(), schema_path, adapter_path,
             repo/'blender/science_guides.py']
    receipt = {'status': 'RUNNING', 'physics_status': 'KINEMATIC_ONLY', 'started_epoch': time.time(),
               'blender_version': bpy.app.version_string, 'python_version': platform.python_version(),
               'sources': [{'path': str(path), 'sha256': sha(path)} for path in paths],
               'lock_path': str(lock_path), 'frame_count_per_case': COUNT,
               'rendered_frames': 0, 'external_assets': [], 'cases': [],
               'scope': 'Real bpy objects, linear F-curves, evaluated transforms and shape-key points; '
                        'declared output-frame kinematics only, not product mechanics, collision/contact, '
                        'subframe dynamics, force, continuous sensory review or film acceptance',
               'formal_acceptance': False}

    def linear(owner):
        action = owner.animation_data.action
        curves = list(getattr(action, 'fcurves', []))
        for layer in getattr(action, 'layers', []):
            for strip in layer.strips:
                for bag in getattr(strip, 'channelbags', []):
                    curves.extend(bag.fcurves)
        if not curves:
            raise AssertionError('Fixture has no real animation F-curves')
        for curve in curves:
            curve.extrapolation = 'CONSTANT'
            for key in curve.keyframe_points:
                key.interpolation = 'LINEAR'

    def animate(obj, channel, values):
        for frame, value in values:
            setattr(obj, channel, value)
            obj.keyframe_insert(data_path=channel, frame=frame)
        linear(obj)

    def mesh(name, strip=False):
        data = bpy.data.meshes.new(name)
        if strip:
            vertices = [(station, side*.05, 0) for station in range(3) for side in (-1, 1)]
            faces = [(0, 2, 3, 1), (2, 4, 5, 3)]
        else:
            vertices, faces = [(0, 0, 0), (.01, 0, 0), (0, .01, 0)], [(0, 1, 2)]
        data.from_pydata(vertices, [], faces)
        obj = bpy.data.objects.new(name, data)
        bpy.context.scene.collection.objects.link(obj)
        return obj

    def reset():
        for obj in list(bpy.data.objects):
            bpy.data.objects.remove(obj, do_unlink=True)
        bpy.context.scene.frame_set(1)
        bpy.context.scene.frame_end = COUNT

    def check(item):
        schema.validate_motion_program({'science': {'constraints': [item]}})
        result = adapter.check_constraints(bpy.context.scene, list(bpy.context.scene.objects), [item], COUNT)
        if result.get('physics_status') != 'KINEMATIC_ONLY':
            raise AssertionError('Constraint receipt must disclose KINEMATIC_ONLY physics scope')
        return result

    def run(name, factory, expected=None):
        reset()
        row = {'id': name, 'expected': 'REJECT' if expected else 'PASS'}
        try:
            details = factory()
        except ValueError as exc:
            row['observed_error'] = str(exc)
            row['status'] = 'PASS' if expected and expected in str(exc) else 'FAIL'
        except Exception:
            row.update(status='FAIL', unexpected_error=traceback.format_exc())
        else:
            row['status'] = 'FAIL' if expected else 'PASS'
            row['observed'] = 'ACCEPTED'
            row['details'] = details
        receipt['cases'].append(row)

    def ratio_case(mode='correct'):
        a, b = mesh('Input'), mesh('Output')
        animate(a, 'rotation_euler', [(1, (0, 0, 0)), (5, (0, 0, .4 if mode != 'static' else 0))])
        end = .8 if mode == 'sign' else -.4 if mode == 'ratio' else 0 if mode == 'loose_follower' else -.8
        keys = [(1, (0, 0, 0)), (5, (0, 0, end if mode != 'static' else 0))]
        if mode == 'middle':
            keys = [(frame, (0, 0, -.2*(frame-1)+(.1 if frame == 3 else 0))) for frame in range(1, 6)]
        animate(b, 'rotation_euler', keys)
        if mode == 'parent':
            parent = mesh('AnimatedParent')
            animate(parent, 'rotation_euler', [(1, (0, 0, 0)), (5, (0, 0, .6))])
            a.parent = parent
        if mode == 'constraint':
            b.constraints.new('COPY_ROTATION').target = a
        if mode == 'quaternion':
            b.rotation_mode = 'QUATERNION'
        return check({'kind': 'rotation_ratio', 'points': [{'object': obj.name, 'axis': 2} for obj in (a, b)],
                      'ratio': -2, 'minimum_driver_travel': .3, 'tolerance': 1 if mode == 'loose_follower' else 1e-5})

    def joint_case(detach=False):
        a, b = mesh('Body'), mesh('Joint')
        animate(a, 'location', [(1, (0, 0, 0)), (5, (1, 0, 0))])
        animate(b, 'location', [(frame, ((frame-1)/4, .1 if detach and frame == 3 else 0, 0))
                                for frame in range(1, 6)])
        return check({'kind': 'distance', 'points': [{'object': obj.name} for obj in (a, b)],
                      'range': [0, 0], 'tolerance': 1e-6})

    def path_case(stretch=False):
        obj = mesh('Strip', strip=True)
        obj.shape_key_add(name='Basis')
        key = obj.shape_key_add(name='Middle deformation')
        for index, vertex in enumerate(key.data):
            if stretch and index in (2, 3):
                vertex.co.x = 3
            elif not stretch:
                vertex.co.y += 1
        for frame, value in ((1, 0), (3, 1), (5, 0)):
            key.value = value
            key.keyframe_insert(data_path='value', frame=frame)
        linear(obj.data.shape_keys)
        bpy.context.scene.frame_set(3)
        bpy.context.view_layer.update()
        evaluated = guides.point({'object': obj.name, 'vertex': 2}, {obj.name: obj},
                                 bpy.context.evaluated_depsgraph_get())
        source = obj.data.vertices[2].co.copy()
        if (evaluated-source).length < .5:
            raise AssertionError('Fixture did not produce evaluated shape-key geometry')
        result = check({'kind': 'path_length', 'points': [{'object': obj.name, 'vertex': index} for index in (0, 2, 4)],
                        'range': [2, 2], 'tolerance': 1e-5})
        result['evaluated_vertex_witness'] = {'frame': 3, 'source': list(source), 'evaluated': list(evaluated)}
        return result

    def cycle_case(mode='correct', events=False):
        tip = mesh('Tip')
        values = {'correct': [0, 1, 2, 1, 0], 'static': [0, 0, 0, 0, 0], 'loose_static': [0, 0, 0, 0, 0],
                  'jump': [0, 0, 2, 1, 0], 'missing': [0, 1, 1, 1, 0],
                  'mistimed': [0, 2, 1, 1, 0]}[mode]
        animate(tip, 'location', [(frame, (value, 0, 0)) for frame, value in enumerate(values, 1)])
        if events:
            fixed = mesh('Fixed')
            item = {'kind': 'distance', 'points': [{'object': fixed.name}, {'object': tip.name}],
                    'range': [0, 2], 'events': [{'progress': [.4, .6], 'range': [2, 2]},
                                               {'progress': [1, 1], 'range': [0, 0]}]}
        else:
            item = {'kind': 'motion', 'points': [{'object': tip.name}], 'range': [3.9, 4.1], 'max_step': 1.01}
            if mode == 'loose_static':
                item.update(range=[1, 2], tolerance=2)
        return check(item)

    try:
        run('ratio_correct', ratio_case)
        for mode, message in [('sign', 'Rotation ratio'), ('ratio', 'Rotation ratio'),
                              ('middle', 'frame 3'), ('static', 'static'), ('parent', 'parent'),
                              ('constraint', 'constrained'), ('quaternion', 'Euler'),
                              ('loose_follower', 'tolerance')]:
            run('ratio_'+mode, lambda mode=mode: ratio_case(mode), message)
        run('joint_attached', joint_case)
        run('joint_middle_detachment', lambda: joint_case(True), 'frame 3')
        run('path_evaluated_shape_translation', path_case)
        run('path_middle_shape_stretch', lambda: path_case(True), 'frame 3')
        run('motion_closed_cycle', cycle_case)
        run('motion_static', lambda: cycle_case('static'), 'travel')
        run('motion_loose_static', lambda: cycle_case('loose_static'), 'tolerance')
        run('motion_middle_jump', lambda: cycle_case('jump'), 'frame 3')
        run('events_observed_cycle', lambda: cycle_case(events=True))
        run('events_missing', lambda: cycle_case('missing', events=True), 'Missing')
        run('events_mistimed', lambda: cycle_case('mistimed', events=True), 'Missing')
    finally:
        receipt['finished_epoch'] = time.time()
        receipt['passed_cases'] = [row['id'] for row in receipt['cases'] if row['status'] == 'PASS']
        receipt['failed_cases'] = [row['id'] for row in receipt['cases'] if row['status'] != 'PASS']
        receipt['status'] = 'PASS' if len(receipt['cases']) == 20 and not receipt['failed_cases'] else 'FAIL'
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        args.receipt.write_text(json.dumps(receipt, ensure_ascii=False, indent=2)+'\n')
        print(json.dumps({'status': receipt['status'], 'receipt': str(args.receipt),
                          'passed': len(receipt['passed_cases']), 'failed': receipt['failed_cases']}))
    if receipt['status'] != 'PASS':
        raise RuntimeError('Real Blender kinematics integration failed; inspect receipt')


if __name__ == '__main__':
    main()
