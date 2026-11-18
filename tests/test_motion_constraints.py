"""Injected evaluated kinematics; no Blender process or physical QA implied."""
import copy
import importlib.util
import math
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Point:
    def __init__(self, value):
        self.value = value

    def __sub__(self, other):
        return SimpleNamespace(length=abs(self.value - other.value))

    def copy(self):
        return Point(self.value)


class MotionConstraints(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from mechanical_video_next import science_shots
        cls.schema = science_shots
        with patch.dict('sys.modules', {
            'bpy': SimpleNamespace(), 'bpy_extras': SimpleNamespace(),
            'bpy_extras.object_utils': SimpleNamespace(world_to_camera_view=None),
            'mathutils': SimpleNamespace(Vector=None),
        }):
            cls.adapter = load_module('constraints_adapter_test', ROOT/'blender/science_scene.py')

    def validate(self, item):
        self.schema.validate_motion_program({'science': {'constraints': [item]}})

    def evaluate(self, item, positions=None, rotations=None, count=5,
                 rotation_mode='XYZ', constrained=False, parented=False):
        self.validate(item)
        state = {'frame': 1}
        scene = SimpleNamespace(frame_set=lambda frame: state.update(frame=frame))
        self.adapter.bpy.context = SimpleNamespace(
            view_layer=SimpleNamespace(update=lambda: None), evaluated_depsgraph_get=lambda: None)
        positions = positions or {}
        rotations = rotations or {}
        objects = []
        for name in {ref['object'] for ref in item['points']}:
            obj = SimpleNamespace(name=name, hide_render=False, data=SimpleNamespace(vertices=[None]*8),
                                  modifiers=[], constraints=[object()] if constrained else [],
                                  parent=object() if parented else None)
            obj.evaluated_get = lambda graph, name=name: SimpleNamespace(
                rotation_mode=rotation_mode, rotation_euler=[0, 0, rotations.get(name, lambda frame: 0)(state['frame'])])
            objects.append(obj)

        def point(ref, objects, graph):
            return Point(positions.get(ref['object'], lambda frame, vertex: 0)(state['frame'], ref.get('vertex')))

        with patch.dict('sys.modules', {'science_guides': SimpleNamespace(point=point)}):
            return self.adapter.check_constraints(scene, objects, [item], count)

    def test_signed_ratio_rejects_wrong_direction_ratio_detached_and_static_driver(self):
        item = {'kind': 'rotation_ratio', 'points': [{'object': name, 'axis': 2} for name in ('Input', 'Output')],
                'ratio': -2, 'minimum_driver_travel': .3, 'tolerance': 1e-8}
        correct = {'Input': lambda frame: frame*.1, 'Output': lambda frame: 3-frame*.2}
        receipt = self.evaluate(item, rotations=correct)['samples'][0]
        self.assertAlmostEqual(receipt['driver_travel'], .4)
        self.assertLess(receipt['maximum_residual'], 1e-8)
        for label, output in (
            ('wrong direction', lambda frame: 3+frame*.2),
            ('wrong ratio', lambda frame: 3-frame*.1),
            ('stationary follower', lambda frame: 3),
            ('middle frame fault', lambda frame: 3-frame*.2+(.1 if frame == 3 else 0)),
        ):
            with self.subTest(label=label), self.assertRaisesRegex(ValueError, 'Rotation ratio'):
                self.evaluate(item, rotations=dict(correct, Output=output))
        with self.assertRaisesRegex(ValueError, 'static'):
            self.evaluate(item)
        with self.assertRaisesRegex(ValueError, 'tolerance'):
            self.evaluate(dict(item, tolerance=1), rotations={'Input': lambda frame: frame*.1})

    def test_rotation_scope_and_frame_count_fail_closed(self):
        item = {'kind': 'rotation_ratio', 'points': [{'object': name, 'axis': 2} for name in ('A', 'B')],
                'ratio': -2, 'minimum_driver_travel': .1}
        for arguments, message in (({'rotation_mode': 'QUATERNION'}, 'Euler'),
                                   ({'constrained': True}, 'constrained'),
                                   ({'parented': True}, 'parent'),
                                   ({'count': 1}, 'two'), ({'count': 0}, 'positive'),
                                   ({'rotations': {'A': lambda frame: math.inf}}, 'Nonfinite')):
            with self.subTest(arguments=arguments), self.assertRaisesRegex(ValueError, message):
                self.evaluate(item, **arguments)

    def test_anchor_detachment_fails_in_middle_even_when_endpoints_match(self):
        item = {'kind': 'distance', 'points': [{'object': name} for name in ('Body', 'Joint')],
                'range': [0, 0], 'tolerance': 1e-6}
        self.evaluate(item)
        with self.assertRaisesRegex(ValueError, 'frame 3'):
            self.evaluate(item, positions={'Joint': lambda frame, vertex: .1 if frame == 3 else 0})

    def test_flexible_path_length_checks_internal_vertices_in_every_frame(self):
        item = {'kind': 'path_length', 'points': [{'object': 'Strip', 'vertex': index} for index in range(3)],
                'range': [2, 2], 'tolerance': 1e-8}
        self.evaluate(item, positions={'Strip': lambda frame, vertex: vertex})
        # The endpoints remain fixed; only an internal vertex stretches the path.
        with self.assertRaisesRegex(ValueError, 'frame 3'):
            self.evaluate(item, positions={'Strip': lambda frame, vertex: 3 if frame == 3 and vertex == 1 else vertex})

    def test_motion_rejects_static_nan_and_jump_but_accepts_closed_cycle(self):
        item = {'kind': 'motion', 'points': [{'object': 'Tip'}], 'range': [3.9, 4.1], 'max_step': 1.01}
        receipt = self.evaluate(item, positions={'Tip': lambda frame, vertex: [0, 1, 2, 1, 0][frame-1]})
        self.assertEqual(receipt['physics_status'], 'KINEMATIC_ONLY')
        self.assertEqual(receipt['samples'][0]['total_travel'], 4)
        with self.assertRaisesRegex(ValueError, 'tolerance'):
            self.evaluate(dict(item, range=[1, 2], tolerance=2))
        for label, values, message in (
            ('static', [0, 0, 0, 0, 0], 'travel'),
            ('jump', [0, 0, 2, 1, 0], 'step'),
            ('nonfinite', [0, 1, math.nan, 1, 0], 'step'),
        ):
            with self.subTest(label=label), self.assertRaisesRegex(ValueError, message):
                self.evaluate(item, positions={'Tip': lambda frame, vertex, values=values: values[frame-1]})

    def test_event_window_rejects_missing_or_mistimed_state(self):
        item = {'kind': 'distance', 'points': [{'object': name} for name in ('Fixed', 'Tip')], 'range': [0, 2],
                'events': [{'progress': [.4, .6], 'range': [2, 2]},
                           {'progress': [1, 1], 'range': [0, 0]}]}
        result = self.evaluate(item, positions={'Tip': lambda frame, vertex: [0, 1, 2, 1, 0][frame-1]})
        self.assertEqual([row['observed_frame'] for row in result['samples'][0]['events']], [3, 5])
        for values in ([0, 1, 1, 1, 0], [0, 2, 1, 1, 0]):
            with self.subTest(values=values), self.assertRaisesRegex(ValueError, 'Missing'):
                self.evaluate(item, positions={'Tip': lambda frame, vertex: values[frame-1]})

    def test_schema_rejects_nonfinite_invalid_scope_and_vacuous_assertions(self):
        ratio = {'kind': 'rotation_ratio', 'points': [{'object': name, 'axis': 2} for name in ('A', 'B')],
                 'ratio': -2, 'minimum_driver_travel': .1}
        motion = {'kind': 'motion', 'points': [{'object': 'A'}], 'range': [1, 2], 'max_step': 1}
        path = {'kind': 'path_length', 'points': [{'object': 'A'}, {'object': 'B'}], 'range': [1, 2]}
        cases = []
        for key, value in [('ratio', 0), ('ratio', math.nan), ('minimum_driver_travel', 0), ('tolerance', math.inf)]:
            cases.append(dict(ratio, **{key: value}))
        invalid = copy.deepcopy(ratio)
        invalid['points'][0]['axis'] = True
        cases.append(invalid)
        cases.extend([dict(motion, range=[0, 2]), dict(motion, max_step=0), dict(motion, points=[]),
                      dict(path, points=[{'object': 'A'}]), dict(path, kind='collision'),
                      dict(path, events=[{'progress': [.6, .4], 'range': [1, 1]}]),
                      dict(path, events=[{'progress': [0, 1], 'range': [1, math.inf]}]),
                      dict(ratio, events=[{'progress': [0, 1], 'range': [0, 1]}])])
        for item in cases:
            with self.subTest(item=item), self.assertRaises(ValueError):
                self.validate(item)
        self.assertEqual(self.schema.referenced_parts({'science': {'constraints': [ratio, motion, path]}}), {'A', 'B'})


if __name__ == '__main__':
    unittest.main()
