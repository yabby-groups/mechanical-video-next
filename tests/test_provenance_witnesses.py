"""Exact-frame source checks with generated media and optional native Blender."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from mechanical_video_next import blender_runtime, provenance, workflow
from scripts.common import ROOT


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
