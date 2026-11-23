import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from mechanical_video_next import joint_timeline as joint, video_review, workflow


class VideoReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        folder = tempfile.TemporaryDirectory()
        cls.addClassCleanup(folder.cleanup)
        cls.root = Path(folder.name)
        cls.plan = {
            'frame_count': 60,
            'shots': [dict(id='lever', start_frame=0, end_frame=30),
                      dict(id='return', start_frame=30, end_frame=60)],
            'narration': [dict(id='opening', text='Push', knowledge_ids=['stroke'],
                               start_frame=1, deadline_frame=27),
                          dict(id='last', text='The lever resets', knowledge_ids=['reset'],
                               start_frame=35, deadline_frame=58)],
            'actions': [],
        }
        cls.blueprint = {'shots': [
            dict(shot_id='lever', time_range=[0, 1], knowledge_ids=['stroke']),
            dict(shot_id='return', time_range=[1, 2], knowledge_ids=['reset']),
        ]}
        sentence = cls.root / 'sentence.wav'
        subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'sine=r=48000:d=0.5',
                        str(sentence)], check=True)
        cls.master = cls.root / 'master.wav'
        cls.measured = joint.measure(cls.plan, lambda _: (sentence, {}), cls.master)
        cls.baseline = cls.encode('baseline')
        cls.sources = {'lever': joint.binding(cls.baseline)}

    @classmethod
    def encode(cls, name, *, filters=(), duration=2):
        path = cls.root / f'{name}.mp4'
        command = ['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i',
                   'color=0x222222:s=160x90:r=30:d=2,'
                   'drawbox=x=12:y=18:w=56:h=48:c=white:t=fill:enable=lt(t\\,0.5),'
                   'drawbox=x=84:y=18:w=56:h=48:c=red:t=fill:enable=gte(t\\,0.5)',
                   '-i', str(cls.master), '-c:v', 'libx264', '-c:a', 'aac',
                   '-t', str(duration), *filters, str(path)]
        subprocess.run(command, check=True)
        return path

    def report(self, path, **overrides):
        args = dict(measured=self.measured, blueprint=self.blueprint,
                    required_ids=['stroke', 'reset'], sources=self.sources,
                    rendered_cues=joint.cues(self.measured))
        return video_review.inspect(joint.binding(path), self.plan, **(args | overrides))

    def assert_blocked(self, report, code):
        self.assertIn(code, [row['code'] for row in report['findings']])
        with self.assertRaisesRegex(ValueError, 'Video Review'):
            video_review.require_current({'media': [report['media']], 'video_review': report})

    def test_decodable_reverse_edit_fails_picture_review(self):
        film = self.encode('reverse', filters=('-vf', 'reverse'))
        joint.validate_rendered_film(film, self.plan)
        report = self.report(film)
        self.assert_blocked(report, 'picture_source_mismatch')
        self.assertEqual(report['findings'][0]['frame_range'], [0, 15])

    def test_complete_reference_passes_only_technical_review(self):
        report = self.report(self.baseline)
        video_review.require_current({'media': [report['media']], 'video_review': report})
        self.assertEqual(report['independent_acceptance'], 'UNKNOWN')

    def test_last_utterance_is_truncated_inside_full_duration_aac(self):
        film = self.encode('tail', filters=('-af', "volume=0:enable='gte(t,1.45)'"))
        joint.validate_rendered_film(film, self.plan)
        report = self.report(film)
        self.assert_blocked(report, 'audio_reference_mismatch')
        self.assertGreater(report['findings'][0]['time_range'][0], 1.2)

    def test_wrong_decodable_audio_and_premature_edit_are_blocked(self):
        self.assert_blocked(self.report(self.encode('wrong', filters=('-af', 'volume=0'))),
                            'audio_reference_mismatch')
        report = self.report(self.encode('short', duration=1.7))
        self.assert_blocked(report, 'picture_timeline')
        self.assertEqual(report['findings'][0]['frame_range'], [51, 60])

    def test_essential_story_and_caption_omissions_are_blocked(self):
        self.assert_blocked(self.report(self.baseline, required_ids=['unexplained']),
                            'story_missing_knowledge')
        self.assert_blocked(self.report(self.baseline, rendered_cues=joint.cues(self.measured)[:1]),
                            'caption_count')

    def test_reversed_state_missing_event_compression_and_cut_jump(self):
        check = dict(id='arm', shot_id='return', samples=[1] + [0] * 29, direction=1,
                     min_motion_frames=4, max_step=.5, continue_from='lever', max_cut_step=.1,
                     previous_samples=[0] * 30,
                     events=[dict(id='contact', range=[.4, .6])])
        report = self.report(self.baseline, states=[check])
        self.assertEqual({item['code'] for item in report['findings']}, {
            'mechanical_direction', 'mechanical_event_missing', 'mechanical_action_compressed',
            'mechanical_step', 'mechanical_cut_jump',
        })
        self.assert_blocked(report, 'mechanical_direction')

    def test_unknown_and_stale_exact_media_are_blocked(self):
        report = self.report(self.baseline, measured=None)
        self.assertEqual(report['technical_status'], 'UNKNOWN')
        self.assert_blocked(report, 'audio_reference_missing')
        with self.assertRaisesRegex(ValueError, 'Current exact-media'):
            video_review.require_current({'media': [joint.binding(self.baseline)],
                                          'video_review': dict(report, media={})})

    def test_default_task_routes_existing_qa_through_video_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            task = workflow.create_task('Pump review', root=Path(tmp), visual_policy_version=2, media_policy_version=1)
            data = workflow.load(task)
            self.assertEqual(data[video_review.FIELD], video_review.VERSION)
            self.assertIn('$video-review', (task / 'producer-prompt.md').read_text())
            # A rendered file without the required review cannot advance to QA.
            with self.assertRaisesRegex(ValueError, 'Missing handoff: diagnostic-qa'):
                workflow.check_qa(task, 'preview-qa', acceptance=False)

    def test_exact_render_source_and_props_are_used_for_composition_review(self):
        public = self.root
        media = joint.binding(self.baseline)
        extra_path = self.root / 'measured.json'
        extra_path.write_text(json.dumps(self.measured))
        blueprint = self.blueprint | {'timeline': self.plan, 'measured_timeline': joint.binding(extra_path)}
        cfg = {'timeline': self.plan, 'storyboard': [dict(id=row['id'], shot='native') for row in self.plan['shots']],
               'shots': {'native': {}}}
        props = self.baseline.with_suffix('.props.json')
        props.write_text(json.dumps({'cues': joint.cues(self.measured), 'shots': [
            {'id': 'lever', 'seconds': 1}, {'id': 'return', 'seconds': 1}]}))
        receipt = self.baseline.with_suffix('.review-sources.json')
        receipt.write_text(json.dumps({'media': media, 'props': joint.binding(props), 'shots': {}}))
        research = {'science': {'facts': [{'id': 'stroke', 'status': 'VERIFIED'}]}}
        report = video_review.for_composition(media, blueprint, research, cfg, public)
        video_review.require_technical_pass(report)
        props.write_text('{}')
        report = video_review.for_composition(media, blueprint, research, cfg, public)
        self.assert_blocked(report, 'composition_evidence_unavailable')

    def test_composition_verifies_editorial_separation_without_action_views(self):
        film = self.encode('disassembly-reversed', filters=('-vf', 'reverse'))
        media = joint.binding(film)
        measured = self.root / 'separation-measured.json'
        measured.write_text(json.dumps(self.measured))
        blueprint = self.blueprint | {'timeline': self.plan, 'measured_timeline': joint.binding(measured)}
        cfg = {'timeline': self.plan, 'no_patent_policy_version': 1,
               'storyboard': [dict(id='lever', shot='reveal'), dict(id='return', shot='other')],
               'shots': {'reveal': {'science': {'disassembly': {'operation': 'cycle'}}}, 'other': {}}}
        props = film.with_suffix('.props.json')
        props.write_text(json.dumps({'cues': joint.cues(self.measured), 'shots': [
            {'id': 'lever', 'seconds': 1, 'media': self.baseline.name}, {'id': 'return', 'seconds': 1}]}))
        receipt = film.with_suffix('.review-sources.json')
        payload = {'media': media, 'props': joint.binding(props), 'shots': {}}
        research = {'science': {'facts': [{'id': 'stroke', 'status': 'VERIFIED'}]}}
        receipt.write_text(json.dumps(payload))
        report = video_review.for_composition(media, blueprint, research, cfg, self.root)
        self.assert_blocked(report, 'composition_evidence_unavailable')
        payload['shots']['lever'] = {'video': joint.binding(self.baseline)}
        receipt.write_text(json.dumps(payload))
        report = video_review.for_composition(media, blueprint, research, cfg, self.root)
        self.assert_blocked(report, 'picture_source_mismatch')

    def test_full_media_scan_reports_an_ending_hold(self):
        report = video_review.scan_media(joint.binding(self.baseline))
        self.assertEqual(report['picture_seconds'], 2)
        self.assertTrue(report['audio_present'])
        self.assertEqual(report['candidate_intervals_seconds']['freeze'], [[.5, 2]])


if __name__ == '__main__':
    unittest.main()
