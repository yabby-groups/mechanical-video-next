"""Traceability tests with real synthetic AV; none records a sensory QA PASS."""
import copy
from pathlib import Path
import subprocess
import tempfile
import unittest

from mechanical_video_next import production_contract as contract
from scripts.common import filehash


class ReviewObservationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.media = Path(cls.temp.name)/'fixture.mp4'
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i',
                        'color=c=gray:s=160x90:r=30:d=0.4', '-f', 'lavfi', '-i',
                        'sine=frequency=440:sample_rate=24000:duration=0.4',
                        '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac',
                        str(cls.media)], check=True)
        cls.binding = {'path': str(cls.media), 'sha256': filehash(cls.media)}
        cls.identity = contract.review_media_identity(cls.binding)
        cls.blueprint = {'shots': [dict(shot_id='s1', time_range=[0, .4], knowledge_ids=['fact-1'])]}

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def report(self):
        row = dict(reviewer_thread_id='independent-fixture', shot_id='s1', knowledge_ids=['fact-1'],
                   media_sha256=self.binding['sha256'], method='continuous_audiovisual',
                   time_range=[0, max(self.identity['durations'].values())], status='PASS',
                   observation='Synthetic validation fixture; no actual sensory attestation.',
                   capability_boundary='Unit test of record validation, not human perception.',
                   audio_pcm_sha256=self.identity['audio_pcm_sha256'],
                   audio_pcm_format=self.identity['audio_pcm_format'])
        return dict(independent_reviewer=True, reviewer_thread_id='independent-fixture',
                    production_thread_ids=['production-fixture'], full_video_reviewed=True,
                    full_audio_listened=True,
                    review_observations=[dict(row, id='fixture-'+name, dimension=name)
                                         for name in sorted(contract.DIMENSIONS)],
                    quality_dimensions={name: dict(status='PASS', media_sha256=self.binding['sha256'],
                        observation='Synthetic conclusion', observation_ids=['fixture-'+name])
                        for name in contract.DIMENSIONS})

    def validate(self, report):
        contract.validate_qa(report, [self.binding], acceptance=True, blueprint=self.blueprint)

    def test_actual_audio_identity_and_complete_observation_records(self):
        self.assertEqual(self.identity['audio_pcm_format'],
                         {'format': 's16le', 'sample_rate': 24000, 'channels': 1})
        self.assertEqual(len(self.identity['audio_pcm_sha256']), 64)
        self.validate(self.report())

    def test_flags_and_sampled_frames_cannot_establish_full_review(self):
        report = self.report()
        report.pop('review_observations')
        with self.assertRaisesRegex(ValueError, 'review observations'):
            self.validate(report)
        for method in ('sampled_frames', 'technical_decode', 'document_review', 'continuous_video'):
            with self.subTest(method=method):
                report = self.report()
                report['review_observations'][0]['method'] = method
                with self.assertRaisesRegex(ValueError, 'complete actual'):
                    self.validate(report)

    def test_gaps_and_missing_tail_fail_but_adjacent_segments_cover(self):
        report = self.report()
        first = report['review_observations'][0]
        second = copy.deepcopy(first)
        second.update(id='second', time_range=[.2, first['time_range'][1]])
        first['time_range'] = [0, .1]
        report['review_observations'].append(second)
        refs = report['quality_dimensions'][first['dimension']]['observation_ids']
        refs.append('second')
        with self.assertRaisesRegex(ValueError, 'unobserved interval'):
            self.validate(report)
        second['time_range'][0] = .1
        refs.remove('second')
        with self.assertRaisesRegex(ValueError, 'complete actual'):
            self.validate(report)
        refs.append('second')
        self.validate(report)
        second['time_range'][1] = .3
        with self.assertRaisesRegex(ValueError, 'complete actual'):
            self.validate(report)

    def test_stale_audio_missing_boundaries_self_review_and_unbound_conclusions_fail(self):
        for key, value in (
            ('audio_pcm_sha256', '0'*64), ('audio_pcm_format', {}),
            ('media_sha256', '0'*64), ('capability_boundary', ''),
            ('reviewer_thread_id', 'production-fixture'), ('status', 'UNKNOWN'),
            ('time_range', [0, float('nan')]), ('shot_id', 'unrelated-shot'), ('knowledge_ids', ['unrelated-fact']),
        ):
            with self.subTest(key=key):
                report = self.report()
                report['review_observations'][0][key] = value
                with self.assertRaises(ValueError):
                    self.validate(report)
        report = self.report()
        report['production_thread_ids'].append(report['reviewer_thread_id'])
        with self.assertRaisesRegex(ValueError, 'Production agents'):
            self.validate(report)
        report = self.report()
        report['quality_dimensions']['mechanical_motion']['observation_ids'] = ['unrelated']
        with self.assertRaisesRegex(ValueError, 'matching independent'):
            self.validate(report)
        with self.assertRaisesRegex(ValueError, 'missing or changed'):
            contract.review_media_identity(dict(self.binding, sha256='0'*64))

    def test_one_generic_record_cannot_supply_all_dimensions_or_other_shots(self):
        report = self.report()
        row = report['review_observations'][0]
        report['review_observations'] = [row]
        for conclusion in report['quality_dimensions'].values():
            conclusion['observation_ids'] = [row['id']]
        with self.assertRaisesRegex(ValueError, 'matching independent'):
            self.validate(report)
        with self.assertRaisesRegex(ValueError, 'current bound Blueprint'):
            contract.validate_qa(self.report(), [self.binding], acceptance=True)
        blueprint = {'shots': [dict(shot_id='s1', time_range=[0, .2], knowledge_ids=['fact-1']),
                               dict(shot_id='s2', time_range=[.2, .4], knowledge_ids=['fact-2'])]}
        report = self.report()
        for row in report['review_observations']:
            row['time_range'] = [0, .2]
        with self.assertRaisesRegex(ValueError, 'complete actual'):
            contract.validate_qa(report, [self.binding], acceptance=True, blueprint=blueprint)

    def test_workprint_keeps_unknown_without_fabricated_observations(self):
        report = self.report()
        report.pop('review_observations')
        report['full_video_reviewed'] = report['full_audio_listened'] = False
        for conclusion in report['quality_dimensions'].values():
            conclusion.update(status='UNKNOWN', observation='Continuous review unavailable.')
            conclusion.pop('observation_ids')
        contract.validate_qa(report, [self.binding], acceptance=False)
