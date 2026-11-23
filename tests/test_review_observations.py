"""Traceability tests with real synthetic AV; none records a sensory QA PASS."""
import copy
import json
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from mechanical_video_next import audio_acceptance as audio, joint_timeline as joint
from mechanical_video_next import media_policy, production_contract as contract, workflow
from scripts.common import codehash, digest, filehash, writejson


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

    def test_full_duration_film_requires_an_observed_payoff(self):
        blueprint = dict(self.blueprint, timeline=dict(film_integrity_version=1, frame_count=12, actions=[]),
                         narrative=dict(moments={'payoff': dict(shot_id='s1', start_frame=9, end_frame=12)}))
        report = self.report()
        joint.validate_rendered_film(self.media, blueprint['timeline'])
        with self.assertRaisesRegex(ValueError, 'story moment payoff'):
            contract.validate_review_observations(report, [self.binding], blueprint)
        with self.assertRaisesRegex(ValueError, 'story moment payoff'):
            contract.validate_review_observations(report, [self.binding], blueprint, workprint=True)
        for observation in report['review_observations']:
            if observation['dimension'] == 'narrative_comprehension':
                observation['story_moment_ids'] = ['payoff']
        contract.validate_review_observations(report, [self.binding], blueprint)

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


class TechnicalAudioTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.narration = audio.narration_module()
        store = self.root / 'tts'
        self.enterContext(patch.object(self.narration, 'STORE', store))
        profile = self.narration.effective_profile({'narration_profile': 'config/narration-neil.json'})
        line = 'Synthetic fixture'
        request = {'endpoint': profile['base_url'] + '/audio/speech',
                   'payload': self.narration.request_payload(line, profile)}
        raw_key = digest(request)
        raw = store / 'raw' / raw_key
        raw.mkdir(parents=True)
        source = raw / 'source.wav'
        self.ffmpeg('-f', 'lavfi', '-i', 'sine=f=400:r=48000:d=1.9', '-af', 'volume=7dB', source)
        writejson(raw / 'request.json', request)
        writejson(raw / 'response.json', {'http_status': 200, 'bytes': source.stat().st_size,
                                          'sample_rate': '48000', 'duration': 1.9})
        self.narration.seal(raw, ['source.wav', 'request.json', 'response.json'])
        self.raw = raw
        key = digest({'raw': raw_key, 'profile': profile, 'processing': codehash('scripts/narration.py')})
        processed = store / 'sentences' / key
        processed.mkdir(parents=True)
        clip = processed / 'narration.wav'
        self.narration.normalize(source, clip, profile)
        writejson(processed / 'processing.json', {'raw_key': raw_key, 'alignment': {'post_speed_factor': 1}})
        self.narration.seal(processed, ['narration.wav', 'processing.json'])
        self.plan = dict(frame_count=60, fps=30, shots=[dict(id='s1', start_frame=0, end_frame=60)],
                         narration=[dict(id='n1', text=line, start_frame=3, deadline_frame=60,
                                         knowledge_ids=['fact'])], actions=[])
        self.master = self.root / 'master.wav'
        self.measured = joint.measure(self.plan, lambda _line: (clip, {'raw_key': raw_key, 'key': key}), self.master)
        receipt = self.root / 'measured.json'
        writejson(receipt, self.measured)
        self.blueprint = dict(shots=[dict(shot_id='s1', time_range=[0, 2], knowledge_ids=['fact'])],
                              timeline=self.plan, measured_timeline=joint.binding(receipt))
        # Feed the verifier the same bound paths that the renderer uses.
        public = self.root / 'remotion/public/cache'
        public.mkdir(parents=True)
        self.public_master = public / 'master.wav'
        self.public_master.write_bytes(self.master.read_bytes())
        self.enterContext(patch.object(audio, 'ROOT', self.root))
        profile_path = audio.ROOT / 'config/narration-neil.json'
        profile_path.parent.mkdir()
        profile_path.write_bytes((media_policy.ROOT / 'config/narration-neil.json').read_bytes())
        approval = self.narration.DEFAULTS
        approval_value = json.loads(approval.read_text())
        approval_value['approved_audition'] = str(media_policy.ROOT / approval_value['approved_audition'])
        temp_approval = self.root / 'defaults.json'
        writejson(temp_approval, approval_value)
        self.enterContext(patch.object(self.narration, 'DEFAULTS', temp_approval))
        self.final = self.root / 'fixture.mp4'
        self.props = {'shots': [{}], 'narrationTrack': 'cache/master.wav', 'cues': joint.cues(self.measured)}
        self.data = {'schema_version': 2, 'protocol_version': 2,
                     'production_method': contract.PRODUCER_DIRECTED,
                     'production_contract_version': 6, 'production_contract': contract.CREATIVE_SELECTION_NAME,
                     'visual_policy_version': 2, 'media_policy_version': 1,
                     'audio_acceptance_policy': audio.MODE, 'agent_runs': [],
                     'handoffs': {'timeline': {'sha256': 'test-timeline'}},
                     'reference_policy_version': 1, 'requested_routes': ['3d'],
                     'route_runs': {'3d': {'outputs': {}}}}
        for name in ('research', 'script', 'creative-blueprint'):
            path = self.root / f'{name}.json'
            writejson(path, {})
            self.data['handoffs'][name] = {'path': path.name}
        self.encode()

    def ffmpeg(self, *args):
        subprocess.run(['ffmpeg', '-v', 'error', '-y', *map(str, args)], check=True)

    def encode(self, *, audio_input=True, audio_options=()):
        inputs = ('-i', self.master, *audio_options, '-c:a', 'aac') if audio_input else ()
        self.ffmpeg('-f', 'lavfi', '-i', 'color=c=gray:s=160x90:r=30:d=2', *inputs,
                    '-c:v', 'libx264', '-pix_fmt', 'yuv420p', self.final)
        self.bind_final()

    def bind_final(self):
        media = joint.binding(self.final)
        props = self.root / 'props.json'
        proof = self.root / 'proof.json'
        manifest = self.final.with_suffix('.media-provenance.json')
        writejson(props, self.props)
        writejson(proof, dict(media=media, build=dict(narration=self.measured['narration_audio'],
                  visual_config=self.blueprint, props=joint.binding(props))))
        writejson(manifest, dict(media=media, build_proof=joint.binding(proof)))
        self.timeline = {'media': [media], 'media_provenance': joint.binding(manifest)}
        self.data['route_runs']['3d']['outputs'] = media

    def report(self):
        media = self.timeline['media'][0]
        sha = media['sha256']
        manifest = self.timeline['media_provenance']
        finding = dict(status='PASS', observation='Synthetic test evidence.')
        rights = dict(media=media, manifest=manifest, independent=True, reviewer_thread_id='fixture')
        original_inputs = {key: joint.binding(self.root / self.data['handoffs'][name]['path'])
                           for key, name in [('research', 'research'), ('script', 'script'),
                                             ('blueprint', 'creative-blueprint')]}
        checks = {key: 'PASS' for key in workflow.QA_CHECKS - {'listening'}} | {'listening': 'UNKNOWN'}
        observation = dict(reviewer_thread_id='fixture', shot_id='s1', knowledge_ids=['fact'],
                           time_range=[0, 2], method='continuous_video', status='PASS',
                           observation='Synthetic unit fixture.', capability_boundary='Validation fixture.',
                           media_sha256=sha)
        return dict(media=self.timeline['media'], checks=checks, full_video_reviewed=True,
                    reviewer_thread_id='fixture', independent_reviewer=True,
                    copyright_review=dict(rights, checks=dict.fromkeys(media_policy.COPYRIGHT_CHECKS, finding)),
                    original_expression_review=dict(rights, input_bindings=original_inputs,
                        ratio_used_as_originality_verdict=False,
                        checks=dict.fromkeys(media_policy.ORIGINALITY_CHECKS, finding)),
                    hybrid_media_review=dict(continuous_video=True, manifest=manifest, media=media,
                        shots={'s1': dict.fromkeys(media_policy.QA_CHECKS, finding)}), full_audio_listened=False,
                    route_checks={'3d': {'media': media, 'checks': checks}},
                    review_observations=[dict(observation, dimension=name, id=name) for name in contract.DIMENSIONS],
                    quality_dimensions={name: dict(status='PASS', media_sha256=sha,
                        observation='Synthetic conclusion', observation_ids=[name]) for name in contract.DIMENSIONS})

    def validate_workflow(self, report):
        handoffs = {'timeline': self.timeline, 'creative-blueprint': self.blueprint,
                    'research': {}, 'script': {}}
        manifest = {'build_proof': joint.binding(self.root / 'proof.json'),
                    'media': self.timeline['media'][0], 'shots': [{'shot_id': 's1'}]}
        with patch.object(workflow, 'load', return_value=self.data), \
                patch.object(workflow, 'artifact', side_effect=lambda _task, name: handoffs[name]), \
                patch.object(workflow, 'continuation'), patch.object(workflow, 'event'), \
                patch.object(media_policy, 'validate_manifest', return_value=manifest), \
                patch('mechanical_video_next.reference_policy.validate_final_report'):
            handoffs['final-qa'] = workflow.put_handoff(self.root, 'QA', 'final-qa', report, ['timeline'])['payload']
            result = workflow.check_qa(self.root, 'final-qa')
            with patch.dict(self.data, {'three_d_policy_version': 1}), \
                    patch('mechanical_video_next.provenance.validate'), \
                    patch('mechanical_video_next.visual_narrative.match_policy'), \
                    patch('mechanical_video_next.visual_narrative.version', return_value=0), \
                    patch('mechanical_video_next.covers.validate'), patch('mechanical_video_next.growth_report.validate'), \
                    patch.object(workflow, 'complete_media'):
                workflow.check_requested_routes(self.root, self.data)
            return result

    def test_verified_neil_without_listening_passes_final_and_route_qa(self):
        result = self.validate_workflow(self.report())
        self.assertEqual(result['audio_technical_status'], 'PASS')
        self.assertEqual(result['audio_perceptual_review'], 'NOT_PERFORMED')
        self.assertFalse(result['full_audio_listened'])
        self.assertEqual(result['audio_technical_evidence']['last_utterance_end_sample'], 96000)

    def test_music_policy_requires_independent_listening_after_technical_pass(self):
        from mechanical_video_next import director_audio as music

        self.data[music.FIELD] = self.blueprint[music.FIELD] = music.VERSION
        direction, mix, _ = music.arrange(self.blueprint, self.measured, directory=self.root / 'direction',
                                          cache=self.root / 'mix-cache')
        self.blueprint.update(audio_direction=direction, audio_mix=mix)
        picture = self.root / 'picture.mp4'
        self.final.replace(picture)
        track = joint.bound(mix['master'])
        music.mux_picture(picture, track, self.final)
        self.public_master.write_bytes(track.read_bytes())
        self.bind_final()
        evidence = audio.verify(self.timeline, self.blueprint)
        self.assertEqual(evidence['mix_check']['music_status'], 'READY')
        with self.assertRaisesRegex(ValueError, 'full independent listening'):
            self.validate_workflow(self.report())

    def test_missing_and_truncated_audio_fail(self):
        self.encode(audio_input=False)
        with self.assertRaisesRegex(ValueError, 'AAC audio track'):
            audio.verify(self.timeline, self.blueprint)
        self.encode(audio_options=('-af', 'atrim=end=1.7'))
        with self.assertRaisesRegex(ValueError, 'duration|truncated'):
            audio.verify(self.timeline, self.blueprint)
        self.encode(audio_options=('-af', 'volume=0:enable=gte(t\\,1.6)'))
        with self.assertRaisesRegex(ValueError, 'differs from the bound audio'):
            audio.verify(self.timeline, self.blueprint)

    def test_invalid_tts_source_and_replaced_track_fail(self):
        self.encode(audio_options=('-af', 'asetrate=47900,aresample=48000,atrim=end=2'))
        with self.assertRaisesRegex(ValueError, 'differs from the bound audio'):
            audio.verify(self.timeline, self.blueprint)
        self.encode()
        writejson(self.raw / 'request.json', {'endpoint': 'unknown', 'payload': {}})
        with self.assertRaisesRegex(ValueError, 'synthesis output or source receipt'):
            audio.verify(self.timeline, self.blueprint)

    def test_subtitle_drift_fails(self):
        self.props['cues'][0]['start'] += .1
        self.bind_final()
        with self.assertRaisesRegex(ValueError, 'subtitle intervals'):
            audio.verify(self.timeline, self.blueprint)

    def test_provider_streaming_wav_header_uses_verified_response_length(self):
        source = self.raw / 'source.wav'
        data = bytearray(source.read_bytes())
        struct.pack_into('<I', data, data.index(b'data') + 4, 0x7fffff9b)
        source.write_bytes(data)
        self.narration.seal(self.raw, ['source.wav', 'request.json', 'response.json'])
        self.assertEqual(audio.verify(self.timeline, self.blueprint)['last_utterance_end_sample'], 96000)
        source.write_bytes(data[:-100])
        self.narration.seal(self.raw, ['source.wav', 'request.json', 'response.json'])
        with self.assertRaisesRegex(ValueError, 'raw WAV is incomplete'):
            audio.verify(self.timeline, self.blueprint)

    def test_open_targeted_audio_issue_blocks_gate(self):
        report = self.report()
        report['issues'] = [dict(requires_audio_review=True, status='OPEN', severity='review',
            issue_id='pronunciation', defect_key='pronunciation', shot_id='s1', time_range=[.5, .7],
            evidence='User-reported pronunciation', responsible_agent='QA', suggested_fix='Check the word',
            verification_method='Targeted listening')]
        with self.assertRaisesRegex(ValueError, 'Unresolved audio issue'):
            self.validate_workflow(report)

    def test_unverified_voice_cannot_use_technical_mode(self):
        self.raw.joinpath('complete.json').unlink()
        with self.assertRaisesRegex(ValueError, 'requires review.*synthesis output'):
            self.validate_workflow(self.report())

    def test_historical_producer_directed_task_still_requires_actual_listening(self):
        self.data.pop('audio_acceptance_policy')
        with self.assertRaisesRegex(ValueError, 'Complete actual viewing and listening'):
            self.validate_workflow(self.report())

    def test_technical_mode_rejects_listening_claims(self):
        report = self.report()
        report['checks']['listening'] = 'PASS'
        with self.assertRaisesRegex(ValueError, 'cannot claim a perceptual'):
            self.validate_workflow(report)

    def test_technical_audio_still_requires_complete_video_coverage(self):
        report = self.report()
        for row in report['review_observations']:
            row['time_range'][1] = 1.9
        with self.assertRaisesRegex(ValueError, 'complete actual video'):
            self.validate_workflow(report)

    def test_optional_preview_cannot_restore_full_listening_requirement(self):
        report = self.report()
        self.data['handoffs']['preview-qa'] = {}
        handoffs = {'preview-qa': report, 'animation-manifest': self.timeline}
        with patch.object(workflow, 'load', return_value=self.data), \
                patch.object(workflow, 'artifact', side_effect=lambda _task, name: handoffs[name]):
            workflow.check_qa(self.root, 'preview-qa')
            report['checks']['listening'] = 'FAIL'
            with self.assertRaisesRegex(ValueError, 'QA FAIL'):
                workflow.check_qa(self.root, 'preview-qa')

    def test_mix_source_gains_and_masking(self):
        source = self.root / 'bed.wav'
        mixed = self.root / 'mixed.wav'
        rights = self.root / 'license.txt'
        rights.write_text('Synthetic test audio rights')
        self.ffmpeg('-f', 'lavfi', '-i', 'sine=f=750:r=48000:d=2', source)
        self.ffmpeg('-i', self.master, '-i', source, '-filter_complex',
                    '[1:a]volume=-20dB[bed];[0:a][bed]amix=inputs=2:normalize=0', mixed)
        stem = dict(kind='bgm', source=joint.binding(source), start_sample=0, end_sample=96000,
                    source_start_sample=0, gain_db=-20, source_type='GENERATED', license_status='VERIFIED',
                    credit='Test fixture', usage_restrictions=[], license=dict(status='VERIFIED',
                    editing_and_distribution=True, commercial_use=True, name='Owned', holder='Fixture',
                    proof=dict(joint.binding(rights), position='test document')))
        mix = dict(master=joint.binding(mixed), stems=[stem])
        self.assertEqual(audio.verify_mix(mix, self.master, 96000)[0], mixed.resolve())
        stem['gain_db'] = 12
        with self.assertRaisesRegex(ValueError, 'Potential BGM or effect masking'):
            # Start in the speech window so the masking finding precedes other
            # expected sample differences in this high-gain fixture.
            stem.update(start_sample=4800, end_sample=96000)
            self.ffmpeg('-i', self.master, '-i', source, '-filter_complex',
                        '[1:a]atrim=end=1.9,volume=12dB,adelay=100:all=1[bed];'
                        '[0:a][bed]amix=inputs=2:normalize=0', mixed)
            mix['master'] = joint.binding(mixed)
            audio.verify_mix(mix, self.master, 96000)
