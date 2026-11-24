import copy
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
import wave

from mechanical_video_next import directed_narration as directed
from mechanical_video_next import joint_timeline as joint
from mechanical_video_next import voice_direction, voice_engines, voice_quality
from scripts.common import ROOT, writejson


class VoiceDirectorTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.profile = voice_engines.load_profile(ROOT / 'config/voice-profile.json')
        motion = self.root / 'motion.json'
        motion.write_text('{}')
        self.plan = {
            'frame_count': 120,
            'shots': [{'id': 'wide', 'start_frame': 0, 'end_frame': 120, 'action_views': {'release': 0}}],
            'actions': [{'id': 'release', 'start_frame': 0, 'end_frame': 60, 'source_start_frame': 0,
                         'start_state': {'handle': 'pressed'}, 'end_state': {'handle': 'rest'},
                         'curve': 'native clock', 'constraints': ['fixed pivot'], 'source': joint.binding(motion)}],
            'narration': [{'id': 'hook', 'start_frame': 0, 'deadline_frame': 60,
                           'text': '门把手怎么回正？', 'knowledge_ids': ['hook']},
                          {'id': 'answer', 'start_frame': 61, 'deadline_frame': 120,
                           'text': '看看压簧。', 'knowledge_ids': ['reveal']}],
        }
        self.beats = [
            {'story_purpose': '提出问题', 'emotion': 'curious', 'emotion_intensity': .4,
             'pause_before_ms': 100, 'pause_after_ms': 50, 'speaking_rate': 1.05,
             'segments': [{'segment_id': 'hook', 'action_anchors': [
                 {'action_id': 'release', 'frame': 15, 'phrase': '回正'}]}]},
            {'story_purpose': '指向答案', 'emotion': 'explanatory', 'emotion_intensity': .2,
             'segments': [{'segment_id': 'answer'}]},
        ]

    def direction(self, engine='cosyvoice3'):
        return voice_direction.plan_direction(self.plan, self.beats, self.profile, engine)

    def test_story_defaults_and_anchor_validation(self):
        rows = self.direction()['segments']
        self.assertEqual(rows[0]['emphasis_words'], ['门把手'])
        self.assertEqual(rows[0]['target_duration_ms'], 1850)
        self.assertEqual(rows[1]['emphasis_words'], ['压簧'])
        self.beats[0]['segments'][0]['action_anchors'][0]['frame'] = 61
        with self.assertRaisesRegex(ValueError, 'Action anchor'):
            self.direction()

    def test_sensevoice_word_clock_ignores_punctuation_and_special_tokens(self):
        result = {
            'tokens': ['<|zh|>', '松', '开', '，', '松开'],
            'seconds': [0, .15, .27, .40, .75],
        }
        anchors = [{'phrase': '松开'}, {'phrase': '松开', 'occurrence': 2}, {'phrase': '方轴'}]
        self.assertEqual(voice_quality.phrase_observations(result, anchors), [
            {'phrase': '松开', 'offset_ms': 150}, {'phrase': '松开', 'offset_ms': 750},
        ])

    def test_adapters_map_controls_with_explicit_degradations(self):
        row = self.direction()['segments'][0]
        row['pronunciations'] = {'正': 'ZHENG4'}
        cosy, unsupported = voice_engines.controls(row, 'cosyvoice3')
        self.assertIn('好奇', cosy['instruction'])
        self.assertIn('门把手', cosy['instruction'])
        self.assertTrue(cosy['instruction'].endswith('<|endofprompt|>'))
        self.assertEqual(cosy['text'], row['text'])
        self.assertEqual(cosy['speed'], 1.05)
        self.assertIn('pronunciation_override_not_mapped_for_cosyvoice3', unsupported)
        self.assertEqual(voice_engines.controls(row, 'neil')[0], {'text': row['text']})

    def test_legacy_engine_rejected_before_loading_a_model(self):
        obsolete = 'indextts25'
        direction = self.direction()
        direction['segments'][0]['selected_tts'] = obsolete
        profile_path = self.root / 'old-profile.json'
        writejson(profile_path, dict(self.profile, engines={**self.profile['engines'], obsolete: {}}))
        with self.assertRaisesRegex(ValueError, 'IndexTTS 2.5 is no longer supported'):
            voice_engines.load_profile(profile_path)
        with self.assertRaisesRegex(ValueError, 'IndexTTS 2.5 is no longer supported'):
            voice_direction.validate(direction, self.plan, self.profile)

    @unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'requires FFmpeg')
    def test_render_fallback_pcm_subtitles_timing_and_single_replacement(self):
        sentence = self.root / 'clip.wav'
        directed.ffmpeg('-f', 'lavfi', '-i', 'sine=frequency=431:sample_rate=48000:duration=1.2', sentence)
        picture = self.root / 'picture.mp4'
        directed.ffmpeg('-f', 'lavfi', '-i', 'color=black:size=160x90:rate=30:duration=4',
                        '-c:v', 'libx264', picture)
        direction = self.direction()
        cache = {'inference': {'speaker_reference_cosine': .7}, 'runtime': {'reference_sha256': 'fixture'}}
        with voice_engines.Synthesizer(models=self.root / 'missing', cache=self.root / 'cache') as service:
            with patch.object(voice_engines.narration, 'sentence',
                              return_value=(sentence, {'processed_cache_hit': True})):
                fallback = directed.measure(self.plan, direction, self.profile, service,
                                            self.root / 'fallback.wav', fallback=True)
            self.assertEqual(fallback['actual_engine'], 'neil')
            self.assertIn('Model unavailable', fallback['fallback_reason'])
            with patch.object(service, 'synthesize', side_effect=[
                (sentence, cache), voice_engines.EngineError('worker inference failed'),
                (sentence, {'engine': 'neil'}), (sentence, {'engine': 'neil'}),
            ]) as adapter:
                fallback = directed.measure(self.plan, direction, self.profile, service,
                                            self.root / 'inference-fallback.wav', fallback=True)
                self.assertEqual([call.args[2] for call in adapter.call_args_list],
                                 ['cosyvoice3', 'cosyvoice3', 'neil', 'neil'])
                self.assertEqual(fallback['fallback_reason'], 'worker inference failed')
                self.assertTrue(all(row['cache']['engine'] == 'neil' for row in fallback['speech']))
            with patch.object(service, 'synthesize', return_value=(sentence, cache)) as adapter:
                first = directed.write_audition(self.plan, direction, self.profile, service,
                                                self.root / 'first', picture=picture)
                self.assertEqual(adapter.call_count, 2)
                prior = joint.receipt(self.plan, joint.binding(self.root / 'first/timeline.json'), directed=True)
                retimed = copy.deepcopy(direction)
                retimed['segments'][0]['pause_before_ms'] = 250
                retimed['segments'][0]['target_duration_ms'] = 1700
                adapter.reset_mock()
                replay = directed.write_audition(self.plan, retimed, self.profile, service,
                                                 self.root / 'retimed', prior=prior)
                adapter.assert_not_called()
                self.assertEqual([row['audio'] for row in replay['speech']],
                                 [row['audio'] for row in first['speech']])
                self.assertEqual(replay['speech'][0]['start_sample'], 12000)
                adjusted = copy.deepcopy(direction)
                adjusted['segments'][0]['take'] = 'alternate'
                second = directed.write_audition(self.plan, adjusted, self.profile, service,
                                                 self.root / 'second', prior=prior, segment_id='hook')
                self.assertEqual(adapter.call_count, 1)
        self.assertEqual(first['speech'][0]['start_sample'], 4800)
        self.assertEqual(first['speech'][0]['end_sample'], 62400)
        self.assertEqual(first['speech'][1]['audio'], second['speech'][1]['audio'])
        self.assertTrue(second['speech'][1]['cache']['reused_from_prior'])
        self.assertEqual(joint.pcm_frames(self.root / 'second/narration.wav'), 192000)
        self.assertIn('00:00:00,100 --> 00:00:01,300', (self.root / 'second/narration.srt').read_text())
        self.assertEqual(directed.decoded_video_hash(picture),
                         directed.decoded_video_hash(self.root / 'first/audition.mp4'))
        self.assertEqual(second['quality']['pronunciation'], 'UNKNOWN')
        observations = {'hook': {'audio_sha256': second['speech'][0]['audio']['sha256'],
                                 'text': '门把手怎么回整？', 'phrases': [{'phrase': '回正', 'offset_ms': 400}]}}
        quality = voice_quality.measure_quality(second, adjusted, observations)
        self.assertEqual(quality['rows'][0]['asr_status'], 'NEEDS_REVIEW')
        self.assertEqual(quality['rows'][0]['action_anchors'][0]['delta_ms'], 0)
        self.assertEqual(quality['pronunciation'], 'UNKNOWN')
        observations['hook']['audio_sha256'] = 'stale'
        with self.assertRaisesRegex(ValueError, 'different audio'):
            voice_quality.measure_quality(second, adjusted, observations)

    def test_cache_seals_and_checks_wav_and_receipt(self):
        direction = self.direction()
        row = direction['segments'][0]
        model = self.root / 'model'
        ref = self.root / 'reference.wav'
        identity = model, ref, {'reference_sha256': 'ref', 'weights_bytes': 1}

        def generate(engine, config, model, reference, args, scratch, wav, key, runtime):
            wav.write_bytes(b'fixture PCM')
            return {'key': key, 'samples': 310, 'inference': {}, 'runtime': runtime}

        with voice_engines.Synthesizer(cache=self.root / 'cache') as service:
            with patch.object(service, 'engine_identity', return_value=identity):
                with patch.object(service, '_generate', side_effect=generate) as engine:
                    wav, initial = service.synthesize(row, self.profile, 'cosyvoice3')
                    self.assertFalse(initial['cache_hit'])
                    _, repeat = service.synthesize(row, self.profile, 'cosyvoice3')
                    self.assertTrue(repeat['cache_hit'])
                    self.assertEqual(engine.call_count, 1)
                    wav.write_bytes(b'corrupted')
                    _, rebuilt = service.synthesize(row, self.profile, 'cosyvoice3')
                    self.assertFalse(rebuilt['cache_hit'])
                    self.assertEqual(engine.call_count, 2)
                    self.assertEqual(list(wav.parent.glob('tmp-*')), [])
