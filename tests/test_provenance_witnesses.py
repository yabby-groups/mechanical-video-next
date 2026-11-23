"""Exact-frame source checks with generated media and optional native Blender."""
import json
import importlib.util
from itertools import product
import os
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from mechanical_video_next import blender_runtime, provenance, workflow
from scripts.common import ROOT


class VectorFixture(tuple):
    x = property(lambda self: self[0])
    y = property(lambda self: self[1])
    z = property(lambda self: self[2])

    def lerp(self, other, fraction):
        return VectorFixture(a + fraction * (b - a) for a, b in zip(self, other, strict=True))


class CameraTransformFixture:
    def __init__(self, depth_offset=0):
        self.depth_offset = depth_offset

    def normalized(self):
        return self

    def inverted(self):
        return self

    def __matmul__(self, point):
        return VectorFixture((point.x, point.y, point.z + self.depth_offset))


def box(x, y, depth):
    return SimpleNamespace(name='fixture box', matrix_world=CameraTransformFixture(),
                           bound_box=list(product(x, y, (-depth[1], -depth[0]))))


class NumericalWitnessTests(unittest.TestCase):
    def setUp(self):
        def project(scene, camera, point):
            point = camera.matrix_world @ point
            scale = -point.z if camera.data.type == 'PERSP' else 1
            return VectorFixture((.5 + point.x / scale, .5 + point.y / scale, -point.z))

        spec = importlib.util.spec_from_file_location('witness_fixture', ROOT/'blender/provenance_audit.py')
        audit = importlib.util.module_from_spec(spec)
        with patch.dict('sys.modules', {'bpy': SimpleNamespace(), 'mathutils': SimpleNamespace(Vector=VectorFixture),
                                       'bpy_extras.object_utils': SimpleNamespace(world_to_camera_view=project)}):
            spec.loader.exec_module(audit)
        self.bounds = audit.witness_bounds
        self.camera = SimpleNamespace(matrix_world=CameraTransformFixture(),
                                      data=SimpleNamespace(type='ORTHO', clip_start=1, clip_end=3))

    def test_near_and_far_intersections_keep_visible_parts(self):
        other = box((.2, .3), (-.1, .1), (1.5, 2))
        for depth in ((.5, 1.5), (2.5, 4)):
            with self.subTest(depth=depth):
                visible = self.bounds(None, self.camera, [box((-.45, -.15), (-.1, .1), depth), other])
                self.assertEqual([round(x, 2) for x in visible], [.05, .4, .8, .6])

    def test_each_screen_boundary_and_invisible_subject(self):
        for x, y, expected in [
            ((-.8, -.3), (-.2, .2), [0, .3, .2, .7]),
            ((.3, .8), (-.2, .2), [.8, .3, 1, .7]),
            ((-.2, .2), (.3, .8), [.3, 0, .7, .2]),
            ((-.2, .2), (-.8, -.3), [.3, .8, .7, 1]),
        ]:
            with self.subTest(x=x, y=y):
                self.assertEqual([round(v, 2) for v in self.bounds(None, self.camera, [box(x, y, (1, 2))])],
                                 expected)
        self.assertIsNone(self.bounds(None, self.camera, [box((.6, .8), (-.1, .1), (1, 2)),
                                                          box((-.2, .2), (-.1, .1), (4, 5))]))

    def test_clipped_subject_difference_is_in_actual_comparison_region(self):
        subject = box((-.45, -.15), (-.1, .1), (.5, 1.5))
        other = box((.2, .3), (-.1, .1), (1.5, 2))
        region = self.bounds(None, self.camera, [subject, other])
        with tempfile.TemporaryDirectory() as tmp:
            clips = []
            for color in ('red', 'blue'):
                clip = Path(tmp) / f'{color}.mp4'
                subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i',
                                'color=gray:s=640x360:r=30:d=0.1,'
                                f'drawbox=x=32:y=144:w=192:h=72:color={color}:t=fill,'
                                'drawbox=x=448:y=144:w=64:h=72:color=green:t=fill',
                                '-c:v', 'libx264', str(clip)], check=True)
                clips.append(clip)
            actual, substituted = (provenance.frame_rgb(clip, 0, region) for clip in clips)
            self.assertEqual(len(actual), 320 * 320 * 3)
            self.assertGreater(sum(abs(a-b) for a, b in zip(actual, substituted, strict=True)) / len(actual), 3)

    def test_camera_moves_from_full_to_partial_perspective_view(self):
        self.camera.data.type = 'PERSP'
        subject = box((-.4, -.2), (-.1, .1), (1.5, 2))
        full = self.bounds(None, self.camera, [subject])
        self.assertAlmostEqual(full[0], .5 - .4/1.5)
        self.camera.matrix_world.depth_offset = .7
        partial = self.bounds(None, self.camera, [subject])
        self.assertIsNotNone(partial)
        self.assertAlmostEqual(partial[0], .1)

    def test_uncertain_projection_does_not_fall_back_to_other_object(self):
        with self.assertRaisesRegex(ValueError, 'fixture box'):
            self.bounds(None, self.camera, [box((float('nan'), 0), (-.1, .1), (1.5, 2)),
                                           box((.2, .3), (-.1, .1), (1.5, 2))])


class ProvenanceWitnessTests(unittest.TestCase):
    def test_same_background_cannot_hide_replaced_subject(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inputs = []
            for prefix, color in (('original', 'red'), ('substitute', 'blue')):
                clip = root / (prefix + '.mp4')
                subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i',
                                'color=gray:s=640x360:r=30:d=0.5,'
                                f'drawbox=x=470:y=100:w=48:h=44:color={color}:t=fill',
                                '-c:v', 'libx264', str(clip)], check=True)
                inputs.append(clip)
            audit = {'resolution': [640, 360], 'subject_bounds': {
                '7': [470/640, 100/360, 518/640, 144/360],
                '8': [0.1, 0.2, 0.2, 0.3],
            }}
            with self.assertRaisesRegex(ValueError, 'frame 9'):
                provenance.require_witness_bounds(audit, 9)
            roi = provenance.require_witness_bounds(audit, 7)
            source, replacement = (provenance.frame_rgb(clip, 6, roi) for clip in inputs)
            self.assertEqual(len(source), 320 * 320 * 3)
            self.assertGreater(sum(abs(a-b) for a, b in zip(source, replacement)) / len(source), 3)

    @unittest.skipUnless(os.environ.get('RUN_BLENDER_TESTS') == '1',
                         'Optional native Blender scene integration (set RUN_BLENDER_TESTS=1)')
    def test_actual_evaluated_motion_and_trimmed_witnesses(self):
        with tempfile.TemporaryDirectory() as tmp, workflow.lock(ROOT / 'work/production.lock', wait=True):
            root = Path(tmp)
            report_path = root / 'audit.json'
            blender_runtime.run_blender(['--factory-startup', '--python-exit-code', '1', '--python',
                                        ROOT / 'tests/fixtures/provenance_motion_scene.py', '--', report_path],
                                       name='provenance-motion-fixture')
            report = json.loads(report_path.read_text())
            loop = report['loop']
            self.assertTrue(loop['spatial_motion'])
            self.assertEqual(loop['motion_samples']['1'], loop['motion_samples']['16'])
            self.assertEqual(loop['motion_samples']['1'], loop['motion_samples']['31'])
            self.assertTrue(report['trimmed']['spatial_motion'])
            self.assertTrue(all(provenance.require_witness_bounds(report['trimmed'], f) for f in (7, 9, 11)))
            camera_only = report['camera_only']
            self.assertEqual(camera_only['motion_status'], 'STATIC_ON_RENDERED_FRAMES')
            self.assertNotEqual(camera_only['subject_bounds']['1'], camera_only['subject_bounds']['8'])
            with self.assertRaisesRegex(ValueError, 'STATIC_ON_RENDERED_FRAMES'):
                provenance.require_shot_motion(camera_only, {'shot_id': 'core'}, {})
            provenance.require_shot_motion(camera_only, {'shot_id': 'detail', 'shot_role': 'structural_detail'}, {})
            with self.assertRaisesRegex(ValueError, 'frame 8'):
                provenance.require_witness_bounds(report['offscreen'], 8)
            self.assertEqual(report['one_frame']['motion_status'], 'INSUFFICIENT_SAMPLES')

    @unittest.skipUnless(os.environ.get('RUN_BLENDER_TESTS') == '1', 'Optional native Blender witness rendering')
    def test_native_witness_detects_change_on_near_clipped_subject(self):
        with tempfile.TemporaryDirectory() as tmp, workflow.lock(ROOT / 'work/production.lock', wait=True):
            root = Path(tmp)
            report_path = root / 'audit.json'
            blender_runtime.run_blender(['--factory-startup', '--python-exit-code', '1', '--python',
                                        ROOT / 'tests/fixtures/provenance_motion_scene.py', '--', report_path,
                                        '--render-clipped-witness'], name='provenance-clipped-witness-fixture')
            audit = json.loads(report_path.read_text())['clipped']
            before = provenance.require_witness_bounds(audit, 1)
            after = provenance.require_witness_bounds(audit, 8)
            other = provenance.require_witness_bounds(audit, 9)
            self.assertLess(before[0], .5)
            self.assertLess(after[0], .5)
            self.assertGreater(other[0], .5)
            self.assertNotEqual(before, after)
            image, repeat, replacement = (provenance.frame_rgb(root/name, 0, after)
                                          for name in ('witness.png', 'repeat.png', 'replacement.png'))
            self.assertEqual(len(image), 320 * 320 * 3)
            self.assertEqual(image, repeat)
            self.assertGreater(sum(abs(a-b) for a, b in zip(image, replacement, strict=True)) / len(image), 3)
