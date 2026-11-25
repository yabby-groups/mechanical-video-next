import json
from pathlib import Path
import tempfile
import unittest
import subprocess
from mechanical_video_next import growth_report as gr
from mechanical_video_next import pacing
from mechanical_video_next.growth import AUDIENCE_GOALS

from fixture_fonts import test_font


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
            font_path=test_font(), title=['Gear motion'], series='Mechanisms', copy_rationale='Test copy', frame_rationale='Test frame',
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
        self.assertEqual(gr.paths_for(self.task), {route: (self.task/'source.mp4').resolve() for route in gr.ROUTES})

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

    def test_opening_goals_lead_and_only_import_observations_bound_to_route_media(self):
        report = gr.read(self.task / 'growth-report.json')
        route = report['routes']['3d']
        text = gr.render_markdown(report)
        positions = [text.index(f'### {label}') for label in AUDIENCE_GOALS.values()]
        self.assertEqual(positions, sorted(positions))
        review = {'media_sha256': route['media']['sha256'],
                  'retention_2s': dict(coverage='sampled_picture', conclusion='The plate fills the frame',
                                      evidence=[dict(time_range=[0, 0], observation='Two red ports')],
                                      answers=dict.fromkeys(pacing.OPENING_QUESTIONS, 'UNKNOWN'),
                                      third_second_evidence=[],
                                      revision=dict(focus='Input', method='Show handle', candidate='Split view')),
                  'knowledge_progression': dict(
                      coverage='sampled_picture', conclusion='Ports stay visible as the valve turns',
                      evidence=[
                          dict(time_range=[0.25, 0.5], observation='The ports overlap'),
                          dict(time_range=[1, 1.5], observation='The cutaway shows the handle and valve together'),
                      ],
                      opportunities=[
                          dict(kind='follow', evidence=1, reason='The cutaway shows a hidden moving part'),
                          dict(kind='like', evidence=1, reason='The handle explains the motion'),
                          dict(kind='like', evidence=0, reason='Overlap explains the flow'),
                      ])}
        gr.write(self.task / 'opening-review.json', review)
        gr.write(self.task / 'opening-review-stale.json', review | {'media_sha256': 'stale'})
        goals = gr.opening_observations(gr.opening_documents(self.task), route['media'], route['duration_seconds'])
        self.assertEqual(len(goals['retention_2s']['editorial_review']), 1)
        self.assertEqual(goals['retention_2s']['editorial_review'][0]['revision']['candidate'], 'Split view')
        self.assertIsNone(goals['retention_5s']['editorial_review'])
        self.assertIsNone(goals['retention_2s']['actual_platform_rate'])
        route['opening_retention'] = goals
        text = gr.render_markdown(report)
        self.assertIn('首个潜在点赞点（sampled_picture） 0.25–0.5 秒。Overlap explains the flow', text)
        self.assertIn('首个潜在关注点（sampled_picture） 1–1.5 秒。The cutaway shows a hidden moving part', text)
        self.assertEqual(gr.snapshot(self.task), report['sources'])

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
