"""Numerical and Blender-adapter checks; no rendering or physical QA implied."""
import copy
import importlib.util
import math
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from mechanical_video_next import science_shots


ROOT = Path(__file__).resolve().parents[1]


def scene_module():
    """Load the real adapter with only Blender's import-time dependencies stubbed."""
    spec = importlib.util.spec_from_file_location('science_adapter_test', ROOT/'blender/science_scene.py')
    module = importlib.util.module_from_spec(spec)
    with patch.dict('sys.modules', {
        'bpy': SimpleNamespace(),
        'bpy_extras': SimpleNamespace(),
        'bpy_extras.object_utils': SimpleNamespace(world_to_camera_view=None),
        'mathutils': SimpleNamespace(Vector=None),
    }):
        spec.loader.exec_module(module)
    return module


class Keys(list):
    def add(self, count):
        self.extend(SimpleNamespace(co=None, interpolation=None) for _ in range(count))


class Curve:
    """A linear Blender F-curve; evaluate intentionally uses the current keys."""
    def __init__(self, samples):
        self.keyframe_points = Keys(SimpleNamespace(co=SimpleNamespace(x=x, y=y)) for x, y in samples)

    def as_pointer(self):
        return id(self)

    def evaluate(self, frame):
        samples = [(key.co.x, key.co.y) for key in self.keyframe_points]
        for a, b in zip(samples, samples[1:]):
            if frame <= b[0]:
                return a[1] + max(0, (frame-a[0])/(b[0]-a[0]))*(b[1]-a[1])
        return samples[-1][1]

    def update(self):
        for key in self.keyframe_points:
            key.co = SimpleNamespace(x=key.co[0], y=key.co[1])


def owner(curves, *, layered=False):
    action = (SimpleNamespace(layers=[SimpleNamespace(strips=[SimpleNamespace(
        channelbags=[SimpleNamespace(fcurves=curves)])])]) if layered
        else SimpleNamespace(fcurves=curves))
    return SimpleNamespace(animation_data=SimpleNamespace(action=action))


class ScienceMotion(unittest.TestCase):
    def setUp(self):
        self.shot = {'science': {'driver': 'data_tracks'}}
        self.mapping = [[0, 0], [.25, .5], [.5, .5], [1, 1]]

    def test_shared_clock_preserves_corners_holds_and_every_source_state(self):
        for values in ([0, .2, 1], [1, .5, 0], [-1, 2, -3]):
            source = [[0, values[0]], [.3, values[1]], [1, values[2]]]
            keys = science_shots.retimed_progress_keys(self.mapping, [key[0] for key in source])
            self.assertIn(.15, keys)  # The original .3 corner must survive compression.
            retimed = [[key, interpolate(source, science_shots.source_progress(self.mapping, key))]
                       for key in keys]
            for frame in range(101):
                progress = frame/100
                expected = interpolate(source, science_shots.source_progress(self.mapping, progress))
                self.assertAlmostEqual(interpolate(retimed, progress), expected)
        self.assertEqual(science_shots.source_progress(self.mapping, .4), .5)
        self.assertEqual(science_shots.source_progress(self.mapping, 1), 1)
        with self.assertRaisesRegex(ValueError, 'validated'):
            science_shots.source_progress(self.mapping, 1.01)

    def test_blender_adapter_retimes_rigid_and_layered_mesh_channels_once(self):
        adapter = scene_module()
        rigid = Curve([(1, 0), (31, .2), (101, 1)])
        weights = Curve([(1, 1), (31, .8), (101, 0)])
        mesh = owner([weights], layered=True)
        body = owner([rigid])
        body.name = 'Body'
        body.data = SimpleNamespace(shape_keys=mesh)
        self.shot.update(tracks=[{'object': 'Body'}], mesh_tracks=[{'object': 'Body'}])
        self.shot['science']['time_map'] = self.mapping
        adapter.retime_data(self.shot, [body], 101)
        for frame in range(1, 102):
            self.assertAlmostEqual(rigid.evaluate(frame) + weights.evaluate(frame), 1)
        for frame in range(26, 52):
            self.assertAlmostEqual(rigid.evaluate(frame), rigid.evaluate(26))
        self.assertAlmostEqual(rigid.evaluate(16), .2)
        self.assertAlmostEqual(rigid.evaluate(101), 1)
        self.assertEqual(rigid.extrapolation, 'CONSTANT')

    def test_reject_reversal_out_of_range_duplicate_and_unsynchronized_clocks(self):
        for mapping in ([[0, 0], [.5, .8], [.8, .6], [1, 1]],
                        [[0, 0], [.5, 1.1], [1, 1]], [[0, 0], [0, .2], [1, 1]],
                        [[0, .1], [1, 1]], [[0, 0], [1, True]]):
            with self.subTest(mapping=mapping), self.assertRaisesRegex(ValueError, 'Time map'):
                science_shots.validate_motion_program({'science': {'driver': 'data_tracks', 'time_map': mapping}})
        self.shot['science'].update(driver='asset_motion', time_map=self.mapping)
        with self.assertRaisesRegex(ValueError, 'Time map'):
            science_shots.validate_motion_program(self.shot)

    def test_opacity_bounds_and_object_scope(self):
        self.shot['science']['opacity_tracks'] = [{'object': 'Cover', 'keys': [[0, 1], [.5, .15], [1, 1]]}]
        self.shot['science']['constraints'] = [{'kind': 'distance', 'points': [
            {'object': 'Cover'}, {'object': 'Tip', 'vertex': 3}], 'range': [.01, .02], 'tolerance': .0001}]
        science_shots.validate_motion_program(self.shot)
        self.assertEqual(science_shots.referenced_parts(self.shot), {'Cover', 'Tip'})
        invalid = copy.deepcopy(self.shot)
        invalid['science']['opacity_tracks'][0]['keys'][1][1] = 1.1
        with self.assertRaisesRegex(ValueError, 'Opacity keys'):
            science_shots.validate_motion_program(invalid)
        invalid = copy.deepcopy(self.shot)
        invalid['science']['opacity_tracks'] *= 2
        with self.assertRaisesRegex(ValueError, 'unique'):
            science_shots.validate_motion_program(invalid)
        invalid = copy.deepcopy(self.shot)
        invalid['science']['constraints'][0]['range'] = [.02, .01]
        with self.assertRaisesRegex(ValueError, 'Distance constraint'):
            science_shots.validate_motion_program(invalid)

    def test_evaluated_distance_constraint_checks_every_frame_and_fails_closed(self):
        adapter = scene_module()
        current = {'frame': 1}
        scene = SimpleNamespace(frame_set=lambda frame: current.update(frame=frame))
        adapter.bpy.context = SimpleNamespace(view_layer=SimpleNamespace(update=lambda: None),
                                              evaluated_depsgraph_get=lambda: None)
        parts = [SimpleNamespace(name=name, hide_render=False, data=SimpleNamespace(vertices=[]))
                 for name in ('Origin', 'Follower')]
        class Point:
            def __init__(self, value):
                self.value = value
            def __sub__(self, other):
                return SimpleNamespace(length=abs(self.value-other.value))
        def point(ref, objects, depsgraph):
            return Point(0 if ref['object'] == 'Origin' else current['frame']*.01)
        item = {'kind': 'distance', 'points': [{'object': 'Origin'}, {'object': 'Follower'}],
                'range': [.01, .05], 'tolerance': 1e-9}
        with patch.dict('sys.modules', {'science_guides': SimpleNamespace(point=point)}):
            receipt = adapter.check_constraints(scene, parts, [item], 5)
            self.assertEqual(receipt['frame_count'], 5)
            self.assertAlmostEqual(receipt['samples'][0]['maximum'], .05)
            with self.assertRaisesRegex(ValueError, 'frame 6'):
                adapter.check_constraints(scene, parts, [item], 6)

    def test_ribbon_winding_preserves_topology_centerline_and_width(self):
        for turn in (0, .25, .7):
            # An authored planar path; no material/contact claim.
            centers = [[math.cos(i*.1+turn), math.sin(i*.1+turn), 0] for i in range(20)]
            strip = science_shots.centerline_strip(centers, .02, [0, 0, 1])
            self.assertEqual(len(strip['vertices']), 40)
            self.assertEqual(len(strip['faces']), 19)
            for index, center in enumerate(centers):
                left, right = strip['vertices'][2*index:2*index+2]
                for axis in range(3):
                    self.assertAlmostEqual((left[axis]+right[axis])/2, center[axis])
                self.assertAlmostEqual(math.dist(left, right), .02)
        for points, normal in (([[0, 0, 0], [0, 0, 0]], [0, 0, 1]),
                               ([[0, 0, 0], [0, 0, 1]], [0, 0, 1])):
            with self.assertRaisesRegex(ValueError, 'Ribbon'):
                science_shots.centerline_strip(points, .02, normal)


def interpolate(keys, progress):
    for a, b in zip(keys, keys[1:]):
        if progress <= b[0]:
            return a[1] + (b[1]-a[1])*(progress-a[0])/(b[0]-a[0])
    return keys[-1][1]


if __name__ == '__main__':
    unittest.main()
