"""Exact-frame source checks with generated media and optional native Blender."""
import json
import importlib.util
from itertools import product
import os
from pathlib import Path
import shutil
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
    return SimpleNamespace(name=f'fixture box {x} {y}', matrix_world=CameraTransformFixture(),
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
        self.parts = audit.projected_regions
        self.camera = SimpleNamespace(matrix_world=CameraTransformFixture(),
                                      data=SimpleNamespace(type='ORTHO', clip_start=1, clip_end=3))

    def test_near_and_far_intersections_keep_visible_parts(self):
        other = box((.2, .3), (-.1, .1), (1.5, 2))
        for depth in ((.5, 1.5), (2.5, 4)):
            with self.subTest(depth=depth):
                subject = box((-.45, -.15), (-.1, .1), depth)
                visible = self.bounds(None, self.camera, [subject, other])
                self.assertEqual([round(x, 2) for x in visible], [.05, .4, .8, .6])
                parts = self.parts(None, self.camera, [subject, other])
                self.assertEqual([round(x, 2) for x in parts[subject.name]], [.05, .4, .35, .6])
                self.assertEqual([round(x, 2) for x in parts[other.name]], [.7, .4, .8, .6])

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
    def test_unusable_witness_regions_are_reported(self):
        audit = dict(resolution=[1920, 1080], subject_regions={'7': {
            'edge': {'bounds': [.9, .9, 1, 1], 'status': 'VISIBLE'},
            'tiny': {'bounds': [0, 0, .001, .001], 'status': 'VISIBLE'},
            'covered': {'status': 'INSUFFICIENT_EVIDENCE', 'reason': 'No visible surface in camera-ray samples'},
        }})
        parts = provenance.witness_regions(audit, 7)
        self.assertEqual(parts['edge']['region_pixels'], [1728, 972, 1920, 1080])
        self.assertRegex(parts['tiny']['reason'], 'smaller than')
        self.assertEqual(parts['covered']['status'], 'INSUFFICIENT_EVIDENCE')
        del audit['subject_regions']['7']['edge']
        with self.assertRaisesRegex(ValueError, 'frame 7.*tiny.*covered'):
            provenance.witness_regions(audit, 7)
        with self.assertRaisesRegex(ValueError, 'frame 8.*missing part regions'):
            provenance.witness_regions(audit, 8)

    def test_aggregate_only_cache_requires_fresh_part_verification(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root/'blender').mkdir()
            shutil.copyfile(ROOT/'blender/provenance_audit.py', root/'blender/provenance_audit.py')
            clip = root/'film.mp4'
            clip.write_text('cache identity fixture')
            media = provenance.binding(clip)
            path = root/'proof.json'
            doc = dict(media=media, shots=[dict(model_assets=[media], product_references=[media])])
            path.write_text(json.dumps(doc))
            with patch.object(provenance, 'ROOT', root), \
                 patch.object(provenance, 'blender_version_output', return_value='cache fixture'), \
                 patch.object(provenance, '_validate', return_value={'status': 'PASS'}) as verify:
                def key():
                    return provenance.digest(dict(inputs=provenance.verification_key(doc, 'final', True),
                                                  provenance=str(path.resolve())))
                with patch.object(provenance, 'WITNESS_VERSION', 1):
                    old_key = key()
                new_key = key()
                self.assertNotEqual(old_key, new_key)
                cache = root/'work/cache/provenance'
                cache.mkdir(parents=True)
                for old_receipt_key in (old_key, new_key):
                    provenance.writejson(cache/(old_receipt_key+'.json'),
                                         dict(status='PASS', verification_key=old_receipt_key))
                result = provenance.validate(path, dict(media, chapter_ids=['core']))
                self.assertFalse(result['cache_hit'])
                self.assertEqual(result['witness_version'], provenance.WITNESS_VERSION)
                self.assertTrue(provenance.validate(path, dict(media, chapter_ids=['core']))['cache_hit'])
                verify.assert_called_once()

    def test_separated_subjects_validate_independently_in_encoded_media(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            witness = root/'witness.png'
            width, height = 1920, 1080
            left = 'drawbox=x=0:y=0:w=192:h=108:color=white:t=fill'
            right = 'drawbox=x=1728:y=972:w=192:h=108:color=white:t=fill'
            source = f'color=black:s={width}x{height}:r=30'
            subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', f'{source},{left},{right}',
                            '-frames:v', '1', '-update', '1', str(witness)], check=True)
            audit = dict(resolution=[width, height], fps=30, frame_range=[1, 3], spatial_motion=True,
                         subject_bounds={str(f): [0, 0, 1, 1] for f in (1, 2, 3)},
                         subject_regions={str(f): {
                             'fixed': {'bounds': [0, 0, .1, .1], 'status': 'VISIBLE'},
                             'clipped': {'bounds': [.9, .9, 1, 1], 'status': 'VISIBLE'},
                         } for f in (1, 2, 3)})

            def audit_fixture(command, **kwargs):
                Path(command[command.index('--output') + 1]).write_text(json.dumps(audit))
                frames = Path(command[command.index('--render-dir') + 1])
                frames.mkdir()
                for frame in (1, 2, 3):
                    shutil.copyfile(witness, frames/f'{frame:05d}.png')

            source_binding = provenance.binding(witness)
            path = root/'proof.json'
            for name, filter_, should_pass in [
                ('complete', f'{source},{left},{right}', True),
                ('deleted', f'{source},{left}', False),
                ('replaced', f'{source},{left},{right.replace("white", "red")}', False),
            ]:
                with self.subTest(name=name):
                    raw = root/f'{name}.mp4'
                    subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', filter_,
                                    '-f', 'lavfi', '-i', 'sine=d=0.1', '-frames:v', '3',
                                    '-c:v', 'libx264', '-crf', '23', '-c:a', 'aac', str(raw)], check=True)
                    binding = provenance.binding(raw)
                    path.write_text(json.dumps(dict(media=binding, shots=[dict(shot_id='core', scene=source_binding,
                        render_output=binding, motion_data=source_binding, model_assets=[dict(source_binding, source='fixture')],
                        product_references=[source_binding], verification_frames=[1, 2, 3])],
                        build=dict(frame_count=3, segments=[dict(shot_id='core', start_frame=0,
                                                               frame_count=3, render_output=binding)]))))
                    original = provenance.frame_rgb(witness, 0, [0, 0, 1, 1])
                    sample = provenance.frame_rgb(raw, 0, [0, 0, 1, 1])
                    union_mae = sum(abs(a-b) for a, b in zip(original, sample, strict=True))/len(original)
                    self.assertLessEqual(union_mae, 3)
                    print(f'{name}: total rectangle MAE={union_mae:.4f}')
                    with patch.object(provenance, 'run_blender', side_effect=audit_fixture), \
                         patch.object(provenance, 'compose', side_effect=lambda build, dst: shutil.copyfile(raw, dst)):
                        if should_pass:
                            self.assertEqual(provenance._validate(path)['status'], 'PASS')
                        else:
                            with self.assertRaisesRegex(ValueError, 'clipped.*MAE='):
                                provenance._validate(path)

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
            report = json.loads(report_path.read_text())
            audit = report['clipped']
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
            part = audit['subject_regions']['8']['Clipped part']
            self.assertEqual(part['status'], 'VISIBLE')
            self.assertLess(part['bounds'][2], .5)
            self.assertEqual(report['occluded']['subject_regions']['8']['Clipped part']['status'],
                             'INSUFFICIENT_EVIDENCE')
            self.assertEqual(report['occluded']['subject_regions']['8']['Fixed part']['status'], 'VISIBLE')
            single_frame = dict(audit, frame_range=[8, 8])
            for name, should_pass in (('repeat', True), ('replacement', False)):
                clip = root/f'{name}.mp4'
                subprocess.run(['ffmpeg', '-v', 'error', '-i', str(root/f'{name}.png'), '-c:v', 'libx264',
                                '-crf', '23', '-pix_fmt', 'yuv420p', str(clip)], check=True)
                if should_pass:
                    result = provenance.compare_witness_frame(clip, root/'witness.png', single_frame, 8, 'core')
                    self.assertEqual({name: part['status'] for name, part in result['parts'].items()},
                                     {'Clipped part': 'PASS', 'Fixed part': 'PASS'})
                else:
                    with self.assertRaisesRegex(ValueError, 'Clipped part.*ROI=.*MAE='):
                        provenance.compare_witness_frame(clip, root/'witness.png', single_frame, 8, 'core')
