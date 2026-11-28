import json
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import unittest

from mechanical_video_next import joint_timeline as joint, pacing, video_review


class PacingTests(unittest.TestCase):
    def setUp(self):
        self.folder = TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.picture = self.root / 'edit.mp4'
        self.picture.write_bytes(b'picture fixture')
        self.media = joint.binding(self.picture)
        self.plan = dict(frame_count=180, narration=[], actions=[], shots=[
            dict(id='one', start_frame=0, end_frame=180, silence_reason='Study the mechanism')])
        self.row = dict.fromkeys(pacing.SHOT, 'Study the mechanism')
        self.row.update(events=[], increments=[], observation=[])
        self.design = {'one': self.row}

    def audit(self, **kwargs):
        joint.validate(self.plan)
        return pacing.analyze(self.media, self.plan, self.design, **kwargs)

    def add_action(self, first, last):
        action = dict(id='move', start_frame=first, end_frame=last, source_start_frame=first,
                      start_state='open', end_state='closed', curve='original', constraints=['guided'],
                      source=self.media)
        self.plan['actions'] = [action]
        self.plan['shots'][0]['action_views'] = {'move': first}
        return action

    def test_empty_camera_move_and_missing_opening_flagged_even_if_pixels_move(self):
        self.row['pixel_motion'] = [1] * 180
        result = self.audit()
        codes = {row['code'] for row in result['findings']}
        self.assertTrue({'no_directed_progress', 'camera_without_demonstration',
                         'opening_event_missing', 'early_progress_missing'} <= codes)
        self.assertEqual(result['sensory_status'], 'UNKNOWN')

    def test_necessary_static_comparison_keeps_its_registered_observation_time(self):
        self.row['observation'] = [dict(frames=[0, 90], task='Compare angles',
                                        evidence='Both states and the fixed reference appear together')]
        self.row['increments'] = [dict(frames=[90, 180], id='difference',
                                       discovery='One seat is fixed', evidence='Compare with the housing')]
        result = self.audit()
        self.assertNotIn('no_directed_progress', {row['code'] for row in result['findings']})
        self.assertEqual(len(result['shots'][0]['information_increments']), 1)

    def test_unaccounted_pause_and_repeated_knowledge_detected(self):
        first = dict(frames=[0, 30], id='difference', discovery='Seat is fixed', evidence='Show the housing')
        self.row['increments'] = [first, dict(first, frames=[90, 180])]
        result = self.audit()
        findings = {row['code']: row for row in result['findings']}
        self.assertEqual(findings['no_directed_progress']['frame_range'], [30, 180])
        self.assertEqual(findings['repeated_information']['frame_range'], [90, 180])

    def test_motion_clock_detects_delayed_event_and_measured_speech_early(self):
        self.add_action(45, 165)
        self.plan['narration'] = [dict(id='line', text='The latch moves', knowledge_ids=['contact'],
                                      start_frame=15, deadline_frame=54)]
        self.row['events'] = [dict(id='input', kind='input', action_id='move', state_id='throw',
                                   description='Visible latch moves', frames=[45, 165],
                                   speech_id='line', opening=True)]
        samples = [0] * 62 + list(range(1, 54)) + [53] * 65
        result = self.audit(measured={'speech': [
            {'id': 'line', 'start_sample': 15 * 1600, 'end_sample': 54 * 1600}]},
            states=[dict(shot_id='one', action_id='move', id='throw', samples=samples, source=self.media)])
        findings = {row['code']: row for row in result['findings']}
        self.assertEqual(findings['speech_action_mismatch']['status'], 'MEASURED')
        self.assertIn('opening_event_missing', findings)
        motion = result['shots'][0]['native_tracks'][0]
        self.assertEqual((motion['start_frame'], motion['completion_frame']), (62, 114))

    def test_mechanical_proof_cannot_be_timed_outside_locked_action(self):
        self.add_action(60, 90)
        self.row['events'] = [dict(id='input', kind='input', action_id='move',
                                   description='Visible latch moves', frames=[20, 100])]
        with self.assertRaisesRegex(ValueError, 'source-bound'):
            self.audit()

    def test_native_motion_is_not_a_trim_candidate_without_a_redundant_annotation(self):
        self.add_action(30, 150)
        samples = [0] * 30 + list(range(120)) + [119] * 30
        result = self.audit(states=[dict(shot_id='one', action_id='move', id='throw', samples=samples)])
        for row in result['findings']:
            if row['repair'] == 'trim_wait':
                start, stop = row['frame_range']
                self.assertTrue(stop <= 31 or start >= 150)

    def test_actual_qa_requires_full_picture_and_sound(self):
        report = self.audit()
        checks = {key: dict(observation='Located observation', frames=[0, 180], status='PASS')
                  for key in pacing.CHECKS}
        checks['opening_event']['frames'] = [0, 60]
        review = dict(pacing_checks=checks, full_video_reviewed=True)
        self.assertEqual(pacing.review_status(report, review), 'UNKNOWN')
        review['full_audio_listened'] = True
        self.assertEqual(pacing.review_status(report, review), 'PASS')
        checks['opening_event']['status'] = 'FAIL'
        self.assertEqual(pacing.review_status(report, review), 'FAIL')

    def test_opening_extracts_real_picture_and_default_audio_without_semantic_claim(self):
        clip = self.root / 'actual.mp4'
        subtitles = self.root / 'opening.srt'
        subtitles.write_text('1\n00:00:00,150 --> 00:00:01,750\nVisible ports\n')
        subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'color=s=64x64:r=30',
                        '-f', 'lavfi', '-i', 'sine=frequency=250',
                        '-f', 'lavfi', '-i', 'sine=frequency=500', '-i', subtitles,
                        '-map', '0:v', '-map', '1:a', '-map', '2:a', '-map', '3:s',
                        '-disposition:a:0', '0', '-disposition:a:1', 'default',
                        '-t', '3.4', '-c:v', 'libx264', '-c:a', 'aac', '-c:s', 'mov_text', clip], check=True)
        with self.assertRaisesRegex(ValueError, 'SHA-256'):
            pacing.opening_analysis(clip, expected_sha='wrong hash')
        analysis = pacing.opening_analysis(clip)
        self.assertEqual(analysis['audio_stream'], 2)
        self.assertEqual(analysis['subtitle_streams'], [3])
        self.assertEqual(analysis['retention_2s']['checkpoints'], [list(row) for row in pacing.OPENING_WINDOWS])
        self.assertEqual(analysis['retention_5s']['time_range'], [0, 3.4])
        pacing.extract_phone_preview(analysis, self.root / 'phone')
        phone = analysis['phone_preview']
        self.assertEqual(phone['resolution'], [384, 384])
        phone_info = pacing.opening_analysis(joint.bound(phone['playback']))
        self.assertEqual(phone_info['picture_duration'], analysis['picture_duration'])
        self.assertEqual(phone_info['audio_stream'], 1)
        self.assertEqual(phone_info['subtitle_streams'], [2])
        pacing.extract_opening(analysis, self.root / 'excerpts', through=3)
        for key, end in (('retention_2s', 2), ('retention_5s', 3.4),
                         ('early_series_value', 3.4), ('through', 3)):
            playback = joint.bound(analysis[key]['playback'])
            info = pacing.opening_analysis(playback)
            self.assertAlmostEqual(info['picture_duration'], end)
            self.assertEqual(info['audio_stream'], 1)
            self.assertEqual(info['subtitle_streams'], [2])
            self.assertIsNone(analysis[key].get('editorial_review'))
        self.assertEqual(analysis['continuous_viewing'], 'UNKNOWN')
        self.assertEqual(analysis['perceptual_listening'], 'UNKNOWN')

    def test_producer_checks_apply_only_to_the_reviewed_preview(self):
        analysis = {'media': self.media, 'picture_duration': 6}
        review = {'media_sha256': self.media['sha256']}
        for key in ('retention_2s', 'retention_5s', 'knowledge_progression'):
            review[key] = {'coverage': 'UNKNOWN', 'conclusion': 'Playback unavailable'}
        review['issues'] = [{'finding': 'Release precedes the result',
                             'next_step': 'Align the release animation',
                             'time_range': [3, 4], 'status': 'OPEN'}]
        checked = pacing.producer_observations(review, analysis)
        self.assertEqual(checked['issues'][0]['status'], 'OPEN')
        self.assertEqual(checked['audience_acceptance'], 'UNKNOWN')
        self.assertEqual(checked['perceptual_listening'], 'UNKNOWN')
        review['issues'][0].update(status='FIXED', before_sha256=analysis['media']['sha256'],
                                   recheck='Inspected matching decoded frames')
        with self.assertRaisesRegex(ValueError, 'prior version'):
            pacing.producer_observations(review, analysis)
        self.picture.write_bytes(b'revised picture fixture')
        with self.assertRaisesRegex(ValueError, 'exact MP4 hash'):
            pacing.producer_observations(review, dict(analysis, media=joint.binding(self.picture)))

    def test_two_second_review_cannot_cite_the_later_reveal_or_claim_missing_coverage(self):
        evidence = [{'time_range': [0, .25], 'observation': 'Open ports are visible'}]
        answers = dict.fromkeys(pacing.OPENING_QUESTIONS, 'UNKNOWN')
        answers['third_second'] = 'The orange marker reveals which plate moves'
        row = dict(coverage='sampled_picture', evidence=evidence, answers=answers,
                   conclusion='The viewer can compare hidden parts at the start',
                   third_second_evidence=[0])
        review = dict(media_sha256=self.media['sha256'], retention_2s=row)
        self.assertEqual(pacing.opening_review(review, self.media, 6), {'retention_2s': row})
        with self.assertRaisesRegex(ValueError, 'exact MP4'):
            pacing.opening_review(review | {'media_sha256': 'changed'}, self.media, 6)
        row['third_second_evidence'] = [1]
        with self.assertRaisesRegex(ValueError, 'Third-second'):
            pacing.opening_review(review, self.media, 6)
        row['third_second_evidence'] = [0]
        for late in ([2, 2], [2.8, 2.8]):
            evidence[0]['time_range'] = late
            with self.assertRaisesRegex(ValueError, 'outside'):
                pacing.opening_review(review, self.media, 6)
        evidence[0]['time_range'] = [0, .25]
        row['coverage'] = 'continuous_av'
        with self.assertRaisesRegex(ValueError, 'spanning'):
            pacing.opening_review(review, self.media, 6)

    def test_potential_opportunities_can_point_past_ten_seconds(self):
        row = {
            'coverage': 'sampled_picture',
            'conclusion': 'The later cutaway adds a separate mechanical relation.',
            'evidence': [{'time_range': [11.2, 12], 'observation': 'Both contacts become visible.'}],
            'opportunities': [{'kind': 'follow', 'reason': 'The cutaway links both contacts to the object.',
                               'evidence': 0}],
        }
        review = dict(media_sha256=self.media['sha256'], knowledge_progression=row)
        self.assertEqual(pacing.opening_review(review, self.media, 15), {'knowledge_progression': row})
        with self.assertRaisesRegex(ValueError, 'outside'):
            pacing.opening_review(review | {'early_series_value': row}, self.media, 15)
        row['opportunities'][0]['evidence'] = 1
        with self.assertRaisesRegex(ValueError, 'timed evidence'):
            pacing.opening_review(review, self.media, 15)
        row['opportunities'][0].update(kind='comment', evidence=0)
        row['takeaways'] = {'practical': 'UNKNOWN', 'early_knowledge': dict(reason='Too late', evidence=0)}
        with self.assertRaisesRegex(ValueError, 'Content takeaways'):
            pacing.opening_review(review, self.media, 15)
        row['takeaways']['early_knowledge'] = 'UNKNOWN'
        self.assertEqual(pacing.opening_review(review, self.media, 15), {'knowledge_progression': row})

    def test_recomposition_or_replaced_source_cannot_reuse_current_qa(self):
        audit = self.audit()
        evidence = self.root / 'receipt.json'
        evidence.write_text(json.dumps({'for': self.media}))
        ref = joint.binding(evidence)
        production = dict(media=[self.media], video_review=dict(schema_version=video_review.VERSION,
            media=self.media, technical_status='PASS', findings=[], pacing=audit,
            inputs={key: ref for key in ('composition', 'render_sources', 'measured_timeline')}))
        video_review.require_current(production, pacing_required=True)
        new_picture = self.root / 'new.mp4'
        new_picture.write_bytes(b'recomposition')
        production['media'] = [joint.binding(new_picture)]
        with self.assertRaisesRegex(ValueError, 'exact-media'):
            video_review.require_current(production, pacing_required=True)
        production['media'] = [self.media]
        evidence.write_text('{}')
        with self.assertRaisesRegex(ValueError, 'changed'):
            video_review.require_current(production, pacing_required=True)


if __name__ == '__main__':
    unittest.main()
