import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import wave

from mechanical_video_next import blueprint, episode, joint_timeline as joint, video_review, voice_direction
from mechanical_video_next import voice_engines


class JointTimelineTests(unittest.TestCase):
    def setUp(self):
        root = tempfile.TemporaryDirectory()
        self.addCleanup(root.cleanup)
        self.root = Path(root.name)
        source = self.root / 'motion.txt'
        source.write_text('Native motion fixture')
        self.plan = {
            'frame_count': 30,
            'shots': [
                {'id': 'wide', 'start_frame': 0, 'end_frame': 6, 'action_views': {'release': 0}},
                {'id': 'close', 'start_frame': 6, 'end_frame': 23,
                 'source_start_frame': 6, 'action_views': {'release': 6}},
                {'id': 'quiet', 'start_frame': 23, 'end_frame': 30, 'silence_reason': 'Observe the resting valve'},
            ],
            'actions': [{'id': 'release', 'start_frame': 0, 'end_frame': 19, 'source_start_frame': 0,
                         'start_state': {'valve': 'closed'}, 'end_state': {'valve': 'open'},
                         'curve': 'native linear', 'constraints': ['bounded stroke'], 'source': joint.binding(source)}],
            'narration': [
                {'id': 'opening', 'text': 'Observe the valve', 'start_frame': 1,
                 'deadline_frame': 11, 'knowledge_ids': ['valve']},
                {'id': 'second', 'text': 'It rises', 'start_frame': 13,
                 'deadline_frame': 21, 'knowledge_ids': ['lift']},
            ],
        }
        self.files = {text: self.make_wave(f'{index}.wav', length)
                      for index, (text, length) in enumerate([('Observe the valve', 12001), ('It rises', 8000)])}

    def make_wave(self, name, frames):
        path = self.root / name
        with wave.open(str(path), 'wb') as wav:
            wav.setparams((1, 2, 48000, 0, 'NONE', 'not compressed'))
            wav.writeframes(b'\x02\x01' * frames)
        return path

    def synthesize(self, text):
        return self.files[text], {'processed_cache_hit': True}

    def measure(self):
        result = joint.measure(self.plan, self.synthesize, self.root / 'master.wav')
        path = self.root / 'timeline.json'
        path.write_text(json.dumps(result))
        return joint.receipt(self.plan, joint.binding(path))

    def test_many_to_many_with_sample_exact_audio_and_silent_shot(self):
        result = self.measure()
        cues = joint.cues(result)
        self.assertLess(cues[0]['start'], 6 / 30)
        self.assertGreater(cues[0]['end'], 6 / 30)
        self.assertEqual(result['speech'][0]['end_sample'], 13601)
        self.assertEqual(joint.pcm_frames(self.root / 'master.wav'), 48000)
        self.assertEqual(joint.overlapping_texts(self.plan, 'close'), ['Observe the valve', 'It rises'])
        self.assertEqual(joint.overlapping_texts(self.plan, 'quiet'), [])

    def test_audio_overrun_does_not_extend_picture_or_overwrite_master(self):
        self.measure()
        master = self.root / 'master.wav'
        before = joint.binding(master)
        plan_before = copy.deepcopy(self.plan)
        self.files['Observe the valve'] = self.make_wave('overrun.wav', 16001)
        with self.assertRaisesRegex(ValueError, 'Revise the dialogue'):
            self.measure()
        self.assertEqual(self.plan, plan_before)
        self.assertEqual(joint.binding(master), before)

    def test_retiming_camera_cut_requires_consistent_source_frame(self):
        self.plan['shots'][0]['end_frame'] = 8
        self.plan['shots'][1]['start_frame'] = 8
        with self.assertRaisesRegex(ValueError, 'Action clock'):
            joint.validate(self.plan)
        self.plan['shots'][1].update(source_start_frame=8, action_views={'release': 8})
        joint.validate(self.plan)
        with self.assertRaisesRegex(ValueError, 'grid'):
            joint.frame_number(.21)

    def test_episode_uses_independent_picture_intervals_and_measured_narration(self):
        source = self.root / 'motion.txt'
        (self.root / 'research.md').write_text('Referenced mechanical evidence')
        (self.root / 'timeline.json').write_text(json.dumps({'plan': self.plan}))
        cuts = [{'id': name, 'scene': source.name, 'scene_shot': index, 'source_frames': 30,
                 'mechanics': {'evidence': 'research.md'}}
                for index, name in enumerate(('wide', 'close', 'quiet'))]
        edit = {'output': 'film.mp4', 'timeline': 'timeline.json', 'shots': cuts}
        (self.root / 'edit.json').write_text(json.dumps(edit))
        with patch.object(episode, 'sentence', side_effect=lambda text, profile: self.synthesize(text)), \
                patch.object(episode, 'load_env'), patch.object(episode, 'effective_profile'), \
                patch.object(episode, 'picture_sources') as pictures, patch.object(episode, 'assemble') as assembly:
            episode.produce(self.root, work_dir=self.root, preview_shots=3)
        self.assertEqual(pictures.call_args.kwargs['counts'], [6, 17, 7])
        self.assertEqual(pictures.call_args.kwargs['shots'][1]['source_start_frame'], 6)
        cues = joint.cues(assembly.call_args.kwargs['measured'])
        self.assertLess(cues[0]['start'], 6 / 30)
        self.assertGreater(cues[0]['end'], 6 / 30)
        self.assertLess(cues[-1]['end'], 23 / 30)

    def test_action_source_and_foley_follow_evaluated_camera_motion(self):
        source = self.plan['actions'][0]['source']
        channel = 'review.release.height'
        samples = list(range(30))
        binding = {'mechanics': {'inputs': {source['path']: source['sha256']}}}
        motion = {'samples': {channel: samples}, 'substeps': 1, 'binding': binding}
        cue = {'start_frame': 6, 'event': 'Valve begins to open',
               'witness': {'channel': channel, 'previous_range': [5, 5], 'range': [6, 6]}}
        document = {'plan': self.plan, 'sounds': [cue]}
        cuts = [{}, {}, {}]

        def codes(second):
            return [row['code'] for row in video_review.joint_action_findings(
                document, cuts, [motion, second, None], self.root)]

        self.assertTrue(video_review.valid_sound_witness(cue['witness']))
        self.assertEqual(codes(motion), [])
        self.assertEqual(codes(dict(motion, binding={})),
                         ['mechanical_action_source'])
        wrong_camera = dict(motion, samples={channel: [value + 1 for value in samples]})
        self.assertEqual(codes(wrong_camera), ['mechanical_camera_continuity', 'mechanical_foley_event'])

    def test_directed_recut_keeps_measured_takes_and_uses_local_action_source(self):
        source = self.root / 'motion.txt'
        self.plan['actions'][0]['source']['path'] = source.name
        edit = {'voice_direction': 'direction.json'}
        profile = voice_engines.load_profile(joint.ROOT / 'config/voice-profile.json')
        beats = [{'story_purpose': 'Reveal the valve', 'segments': [
            {'segment_id': 'opening', 'pause_before_ms': 10}, {'segment_id': 'second'},
        ]}]
        authored = copy.deepcopy(self.plan)
        authored['actions'][0]['source'] = joint.binding(source)
        direction = voice_direction.plan_direction(authored, beats, profile, 'neil')
        self.assertEqual(direction['segments'][1]['scene_id'], 'close')
        (self.root / edit['voice_direction']).write_text(json.dumps(direction))

        def synthesize(row, voice_profile, engine):
            self.assertEqual(engine, 'neil')
            return self.synthesize(row['text'])

        with patch.object(voice_engines.Synthesizer, 'synthesize', side_effect=synthesize):
            before = episode.measure_joint_narration(self.root, edit, self.plan, self.root / 'original.wav')
            self.plan['shots'][0]['end_frame'] = 14
            self.plan['shots'][1].update(start_frame=14, source_start_frame=14, action_views={'release': 14})
            after = episode.measure_joint_narration(self.root, edit, self.plan, self.root / 'recut.wav')
        self.assertEqual(after['voice_direction']['segments'][1]['scene_id'], 'wide')
        self.assertEqual(before['speech'], after['speech'])
        self.assertEqual(before['narration_audio']['sha256'], after['narration_audio']['sha256'])
        self.assertEqual(after['speech'][0]['start_sample'], 1600 + 480)

    def test_source_ranges_are_output_frames_for_lower_rate_preview(self):
        with patch.object(joint, 'probe', return_value={'streams': [
                {'codec_type': 'video', 'avg_frame_rate': '15/1', 'nb_frames': '7', 'duration': '0.466667'}
        ]}):
            joint.validate_source_clip('proxy.mp4', 2, 12)
            with self.assertRaisesRegex(ValueError, 'cover'):
                joint.validate_source_clip('proxy.mp4', 2, 13)

    def test_subtitle_revisions_keep_audio_and_actions_and_invalidate_receipt(self):
        result = self.measure()
        old = joint.binding(self.root / 'timeline.json')
        self.plan['narration'][0]['subtitle'] = 'Watch the valve'
        with self.assertRaisesRegex(ValueError, 'differs'):
            joint.receipt(self.plan, old)
        edited = self.measure()
        self.assertEqual(result['narration_audio'], edited['narration_audio'])
        self.assertEqual(result['shots'], edited['shots'])
        self.assertEqual(result['plan']['actions'], edited['plan']['actions'])
        self.assertNotEqual(joint.cues(result), joint.cues(edited))

    def test_blueprint_compiles_two_distinct_cuts_to_one_cached_source_program(self):
        rows = []
        for cut in self.plan['shots']:
            rows.append(dict(shot_id=cut['id'], existing_shot='motion', asset='assembly', template='motion',
                             knowledge_goal='Observe motion', mechanical_action='Visible action', overlays=[],
                             camera={'camera_view': 'top'}, time_range=[cut['start_frame']/30, cut['end_frame']/30]))
        plan = {'timeline_policy_version': 1, 'status': 'DRAFT', 'shots': rows, 'timeline': self.plan}
        cfg = {'id': 'fixture', 'asset': 'assembly', 'shots': {'motion': {'template': 'motion', 'seconds': 1}},
               'render': {'width': 1920, 'height': 1080}, 'storyboard': []}
        source, base, output = [self.root/p for p in ('source.json', 'base.json', 'render.json')]
        source.write_text(json.dumps(plan))
        base.write_text(json.dumps(cfg))
        blueprint.compile_config(source, base, output, draft=True)
        compiled = json.loads(output.read_text())
        self.assertEqual(compiled['shots']['wide'], compiled['shots']['close'])
        self.assertNotEqual(compiled['storyboard'][0]['seconds'], compiled['shots']['wide']['seconds'])
        self.assertEqual(compiled['storyboard'][-1]['narration'], [])
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
        from produce import shot_key
        with patch('produce.asset_key', return_value='fixture-model'):
            self.assertEqual(shot_key(compiled['shots']['wide'], 'final'),
                             shot_key(compiled['shots']['close'], 'final'))
