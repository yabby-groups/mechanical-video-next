import json
from pathlib import Path
import tempfile
import unittest
import subprocess
from mechanical_video_next import growth_report as gr


class GrowthReportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.task = Path(self.tmp.name)
        video = self.task/'source.mp4'
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i',
                        'testsrc2=size=320x180:rate=1', '-t', '2', '-c:v', 'libx264', str(video)], check=True)
        paths = {route: video for route in gr.ROUTES}
        gr.write(self.task/'task.json', {'id': 'fixture', 'topic': 'gear',
                 'route_runs': {r: {'outputs': {'path': str(video)}} for r in gr.ROUTES}})
        gr.write(self.task/'cover-plan.json', dict(topic='gear', recommended_route='3d',
            recommendation_reason='Synthetic test recommendation',
            route_analysis={r: dict(suitability='UNKNOWN', reason='Not reviewed') for r in gr.ROUTES},
            title=['Gear motion'], series='Mechanisms', copy_rationale='Test copy', frame_rationale='Test frame',
            selected_candidate='main', candidates=[dict(id='main', route='3d', seconds=0,
                shot_id='s1', mechanical_moment='Test motion', subject_box=[0, 0, 1, 1])]))
        gr.generate(self.task, paths, video)

    def test_existing_three_route_report_has_bound_media_and_unknown_sensory_checks(self):
        report = json.loads((self.task/'growth-report.json').read_text())
        self.assertEqual(set(report['routes']), {'2d','2.5d','3d'})
        self.assertEqual(report['status'], 'CANDIDATE_UNACCEPTED')
        for route, entry in report['routes'].items():
            self.assertTrue(Path(entry['media']['path']).is_file())
            self.assertEqual(gr.sha(entry['media']['path']), entry['media']['sha256'])
            self.assertEqual(entry['duration_seconds'], 2)
            self.assertTrue(any(v['status'] == 'UNKNOWN' for v in entry['dimensions'].values()))
        self.assertTrue((self.task/'growth-evidence/manifest.json').is_file())
        self.assertTrue((self.task/'version-comparison.md').is_file())

    def test_report_validation_detects_changed_report_dependency(self):
        report_path = self.task/'growth-report.json'
        original = report_path.read_bytes()
        try:
            data = json.loads(original)
            data['routes']['2d']['media']['sha256'] = 'changed'
            report_path.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, 'STALE'):
                gr.validate(self.task)
        finally:
            report_path.write_bytes(original)

    def test_missing_media_blocks_generation_before_frame_extraction(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            task = folder/'task'; task.mkdir()
            (task/'task.json').write_text(json.dumps({'id':'x','topic':'x','route_runs':{}}))
            with self.assertRaisesRegex(ValueError, 'missing actual media'):
                gr.generate(task, {'2d': folder/'a.mp4','2.5d':folder/'b.mp4','3d':folder/'c.mp4'}, folder/'compare.mp4')

    def test_report_generator_does_not_start_production_processes(self):
        # The report's only subprocess is frame extraction; no Blender/CAD/TTS argv is allowed.
        source = Path('mechanical_video_next/growth_report.py').read_text()
        self.assertNotIn('blender', source.lower())
        self.assertNotIn('cad run', source.lower())
        self.assertNotIn('tts', source.lower())


if __name__ == '__main__':
    unittest.main()
