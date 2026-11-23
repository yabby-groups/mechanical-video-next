from array import array
import json
import math
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
import wave

from mechanical_video_next import audio_acceptance, audio_library, director_audio as music
from mechanical_video_next import ducking, joint_timeline as joint, workflow
from scripts import clean
from scripts import produce
from scripts.common import execute, filehash, writejson


class MusicDirectionTests(unittest.TestCase):
    def setUp(self):
        folder = TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.cache = self.root / 'mix-cache'
        self.master = self.root / 'neil.wav'
        self.clip = self.root / 'clip.wav'
        self.plan = {'frame_count': 180, 'actions': [], 'shots': [
            {'id': 'question', 'start_frame': 0, 'end_frame': 60},
            {'id': 'reveal', 'start_frame': 60, 'end_frame': 180},
        ], 'narration': [{'id': 'utterance', 'start_frame': 45, 'deadline_frame': 87,
                          'text': '看里面', 'knowledge_ids': ['parts']}]}
        self.blueprint = {music.FIELD: music.VERSION, 'timeline': self.plan,
                          'core_question': 'Why does the spring return?',
                          'shots': [{'shot_id': cut['id'], 'time_range': [cut['start_frame'] / 30,
                                     cut['end_frame'] / 30]} for cut in self.plan['shots']],
                          'narrative': {'moments': {'opening': {'shot_id': 'question'},
                                                    'causal_reveal': {'shot_id': 'reveal'}}}}
        self.tone(self.clip, 48000, 6500)
        self.measure()

    def tone(self, path, samples, amplitude):
        with wave.open(str(path), 'wb') as wav:
            wav.setparams((1, 2, 48000, 0, 'NONE', 'not compressed'))
            wav.writeframes(array('h', (round(amplitude * math.sin(i * .06)) for i in range(samples))).tobytes())

    def measure(self):
        self.measured = joint.measure(self.plan, lambda text: (self.clip, {}), self.master)
        writejson(self.root / 'timing.json', self.measured)
        self.blueprint['measured_timeline'] = joint.binding(self.root / 'timing.json')

    def arrange(self, **kwargs):
        ref, mix, hit = music.arrange(self.blueprint, self.measured, directory=self.root / 'design',
                                       cache=self.cache, **kwargs)
        config = {music.FIELD: 1, 'audio_direction': ref, 'audio_mix': mix}
        config.update({key: self.blueprint[key] for key in music.POLICY_FIELDS if key in self.blueprint})
        return config, json.loads(Path(ref['path']).read_text()), hit

    def test_default_and_historical(self):
        task = workflow.create_task('Why does a latch spring back?', root=self.root,
                                    visual_policy_version=2, media_policy_version=1)
        self.assertTrue(music.enabled(workflow.load(task)))
        self.assertEqual(workflow.load(task)[music.MIX_MODE_FIELD], ducking.CONSTANT_BED)
        self.assertEqual(workflow.load(task)[music.DEFAULT_BGM_FIELD], 'junge-theme-v4')
        self.assertEqual(music.mix_mode(self.blueprint), ducking.ADAPTIVE_V2)
        self.assertFalse(music.enabled({}))
        self.assertIsNone(music.validate_arrangement({}, require_ready=True))
        self.assertEqual(music.story_intent({'scenes': [{'id': 'hook', 'story_purpose': '开场问异常'}]})[0]['mode'], 'curiosity')

    def test_cross_cut_duck_and_narration_gaps(self):
        config, design, hit = self.arrange()
        self.assertFalse(hit)
        self.assertEqual([row['mode'] for row in design['segments']], ['curiosity', 'discovery'])
        speech = self.measured['speech'][0]
        self.assertLess(speech['start_sample'], 96000)
        self.assertGreater(speech['end_sample'], 96000)
        bed = config['audio_mix']['stems']
        self.assertTrue(all(row['kind'] == 'bgm' for row in bed))
        first, second = bed
        self.assertGreater(ducking.interpolate(first['envelope'], 85000), .1)
        self.assertGreater(ducking.interpolate(second['envelope'], 120000), .1)
        self.assertLess(ducking.interpolate(second['envelope'], 120000), .75)
        self.assertEqual(ducking.interpolate(second['envelope'], 184000), 1.)
        self.assertEqual(second['envelope'][-1], [180 * 1600 - 1, 0])
        self.assertEqual(music.validate_arrangement(config, blueprint=self.blueprint, measured=self.measured,
                                                    require_ready=True)[0]['status'], 'READY')
        with patch.object(audio_library, 'choose', side_effect=AssertionError('Selection must stay cached')):
            self.measured['speech'][0]['subtitle'] = '新字幕'
            self.assertTrue(self.arrange()[2])

    def test_short_pause_and_source_silence(self):
        music_source = self.root / 'music.wav'
        voice = self.root / 'voice.wav'
        count = 3 * joint.SAMPLE_RATE
        tone = array('h', [1000, -1000]) * (count // 2)
        bed = tone[:]
        bed[48000:67200] = array('h', [0]) * 19200
        foreground = array('h', [0]) * count
        foreground[24000:48000] = (array('h', [16000, -16000]) * 12000)
        foreground[57600:96000] = (array('h', [16000, -16000]) * 19200)
        for path, data in [(music_source, bed), (voice, foreground)]:
            with wave.open(str(path), 'wb') as wav:
                wav.setparams((1, 2, 48000, 0, 'NONE', 'not compressed'))
                wav.writeframes(data.tobytes())
        speech = [{'start_sample': 24000, 'end_sample': 48000},
                  {'start_sample': 57600, 'end_sample': 96000}]
        rights = audio_library.records()[0][0]
        stem = dict(rights, source=joint.binding(music_source), kind='bgm', gain_db=0.,
                    cue_id='cue', start_sample=0, end_sample=count, source_start_sample=0,
                    envelope=[[0, 0.], [1000, 1.], [count-1000, 1.], [count-1, 0.]])
        adaptive = ducking.apply([stem], [], voice, count, speech)
        points = adaptive[0]['envelope']
        self.assertEqual(points[0], [0, 0.])
        self.assertEqual(points[-1], [count-1, 0.])
        self.assertLess(ducking.interpolate(points, 18000), 1.)
        self.assertAlmostEqual(ducking.interpolate(points, 52800), ducking.amplitude(-4))
        self.assertGreater(ducking.interpolate(points, 120000), ducking.amplitude(-4))
        self.assertGreater(min(gain for _, gain in points[1:-1]), 0)
        evidence = ducking.describe(ducking.measurements([stem], voice, count),
                                   ducking.measurements(adaptive, voice, count), speech)
        self.assertGreater(ducking.review_metrics(evidence)['bgm_continuity']['speech_windows_with_quiet_source'], 0)

    def test_legacy_automation_and_cache_keys(self):
        ref, old, _ = music.arrange(self.blueprint, self.measured, directory=self.root / 'design',
                                   cache=self.cache, ducking_version=1)
        config, current, _ = self.arrange()
        self.assertNotEqual(old['cache_key'], config['audio_mix']['cache_key'])
        self.assertEqual(current['ducking'], ducking.DEFAULT)
        music.validate_arrangement({music.FIELD: 1, 'audio_direction': ref, 'audio_mix': old},
                                   blueprint=self.blueprint, measured=self.measured, require_ready=True)

    def test_constant_bed_crosses_cuts_narration_and_pauses(self):
        legacy_config, legacy, _ = self.arrange()
        self.assertEqual(legacy['ducking']['version'], 2)
        self.blueprint[music.MIX_MODE_FIELD] = ducking.CONSTANT_BED
        config, direction, hit = self.arrange()
        self.assertFalse(hit)
        self.assertEqual(len(direction['segments']), 1)
        self.assertEqual(direction['segments'][0]['shot_ids'], ['question', 'reveal'])
        stem, = config['audio_mix']['stems']
        self.assertEqual(stem['source_start_sample'], 0)
        self.assertEqual(config['audio_mix'][music.MIX_MODE_FIELD], ducking.CONSTANT_BED)
        self.assertNotEqual(config['audio_mix']['cache_key'], legacy_config['audio_mix']['cache_key'])
        self.assertEqual(stem['envelope'], [[0, 0.], [16800, 1.], [247199, 1.], [287999, 0.]])
        self.assertTrue(all(ducking.interpolate(stem['envelope'], point) == 1.
                            for point in range(24000, 240000, 480)))
        self.assertEqual(music.validate_arrangement(config, blueprint=self.blueprint, measured=self.measured,
                                                    require_ready=True)[0], direction)
        self.assertTrue(self.arrange()[2])
        altered = dict(direction, constant_bed_calibration=direction['constant_bed_calibration'] | {'neil_lufs': -8})
        receipt = self.root / 'altered.json'
        writejson(receipt, altered)
        with self.assertRaisesRegex(ValueError, 'calibration differs'):
            music.validate_arrangement(config | {'audio_direction': joint.binding(receipt)}, blueprint=self.blueprint,
                                       measured=self.measured)
        with self.assertRaisesRegex(ValueError, 'pinned mix mode'):
            music.validate_arrangement(config | {music.MIX_MODE_FIELD: ducking.ADAPTIVE_V2})

    def pin_theme(self):
        self.blueprint.update({music.MIX_MODE_FIELD: ducking.CONSTANT_BED,
                               music.DEFAULT_BGM_FIELD: music.DEFAULT_BGM})

    def test_v4_registration_and_verified_waveform(self):
        path = audio_library.LIBRARY / 'junge-theme-v4.json'
        row = json.loads(path.read_text())
        self.assertEqual(row['id'], music.DEFAULT_BGM)
        self.assertEqual(row['source']['sha256'], 'dee1879199239573889bfddba5fa3bfeb07c7a9398127c6893a80e70db3a18c3')
        self.assertEqual((row['duration_seconds'], row['channels'], row['sample_rate']), (80, 2, 48000))
        self.assertEqual(row['license_status'], audio_library.RIGHTS_REVIEW_REQUIRED)
        self.assertEqual(len(audio_library.records()[0]), 4)
        if not (audio_library.ROOT / row['source']['path']).is_file():
            self.skipTest('Original V4 WAV is kept local pending redistribution rights')
        track = audio_library.inspect_audio(row)
        seam = track['loop_analysis']
        self.assertEqual(seam['period_beats'], 96)
        self.assertGreater(seam['correlation'], .98)
        self.assertGreater(seam['bass_correlation'], .99)
        with self.assertRaisesRegex(ValueError, 'beat alignment'):
            audio_library.analyze_loop(joint.bound(row['source']), [960000, 3269760 - 9600], 5760, 120,
                                       downmix=row['pcm_downmix'])
        cue = dict(id='wide', asset_id=row['id'], start_frame=0, end_frame=5400, film_samples=5400 * 1600,
                   fade_in_seconds=.4, fade_out_seconds=1., target_lufs=-34)
        stems = list(music.lay_music(cue, track, -20, [], []))
        self.assertEqual([stem['start_sample'] // 48000 for stem in stems], [0, 68, 116, 164])
        self.assertEqual(stems[0]['envelope'][:2], [[0, 0.], [19200, 1.]])
        self.assertEqual(stems[-1]['envelope'][-2:], [[cue['film_samples'] - 48001, 1.], [cue['film_samples'] - 1, 0.]])
        for outgoing, incoming in zip(stems, stems[1:]):
            self.assertEqual(incoming['source_start_sample'], 960000)
            for point in range(incoming['start_sample'], outgoing['end_sample'], 117):
                self.assertAlmostEqual(sum(ducking.interpolate(stem['envelope'], point)
                                           for stem in (outgoing, incoming)), 1., places=7)

    def test_v4_pending_or_missing_does_not_fall_back_to_other_catalog_music(self):
        self.pin_theme()
        catalog = self.root / 'library'
        rights = json.loads((audio_library.LIBRARY / 'quiet-link-curiosity.json').read_text())
        writejson(catalog / (rights['id'] + '.json'), rights)
        config, design, _ = self.arrange(catalog=catalog)
        self.assertEqual(design['status'], 'BLOCKED')
        self.assertEqual(design['selections'], [])
        with self.assertRaisesRegex(ValueError, 'catalog record missing.*junge-theme-v4'):
            music.validate_arrangement(config, require_ready=True)
        path = catalog / (music.DEFAULT_BGM + '.json')
        record = dict(rights, id=music.DEFAULT_BGM, license_status=audio_library.RIGHTS_REVIEW_REQUIRED,
                      source=joint.binding(self.clip))
        writejson(path, record)
        config, design, _ = self.arrange(catalog=catalog)
        with self.assertRaisesRegex(ValueError, audio_library.RIGHTS_REVIEW_REQUIRED):
            music.validate_arrangement(config, require_ready=True)
        self.clip.unlink()
        self.assertIn('Music source missing', audio_library.records(catalog, selected=music.DEFAULT_BGM)[1][0]['reason'])

    def test_v4_exact_override_silence_clock_and_source_cache(self):
        self.pin_theme()
        catalog = self.root / 'library'
        record = json.loads((audio_library.LIBRARY / 'quiet-link-curiosity.json').read_text())
        original = record['id']
        writejson(catalog / (original + '.json'), record)
        self.blueprint['music_direction'] = {'asset_id': original,
            'shots': {'question': {'mode': 'silence', 'reason': 'Let the contact speak'}}}
        config, direction, _ = self.arrange(catalog=catalog)
        self.assertEqual(direction['status'], 'READY')
        self.assertNotIn('ducking', direction)
        stem, = config['audio_mix']['stems']
        self.assertEqual(stem['source_start_sample'], 96000)
        self.assertEqual(stem['envelope'], [[96000, 0.], [115200, 1.], [239999, 1.], [287999, 0.]])
        self.assertEqual(config['audio_mix']['output_gain_db'], 0.)
        self.assertTrue(self.arrange(catalog=catalog)[2])
        changed = self.root / 'replacement.wav'
        self.tone(changed, 6 * joint.SAMPLE_RATE, 1200)
        writejson(catalog / (original + '.json'), record | {'source': joint.binding(changed)})
        new, _, hit = self.arrange(catalog=catalog)
        self.assertFalse(hit)
        self.assertNotEqual(new['audio_mix']['cache_key'], config['audio_mix']['cache_key'])

    def test_retired_pixabay_record_and_alias_are_excluded(self):
        record = json.loads((audio_library.LIBRARY / 'quiet-link-curiosity.json').read_text())
        retired_id, retired_sha = next(iter(json.loads(audio_library.RETIREMENTS.read_text()).items()))
        catalog = self.root / 'library'
        writejson(catalog / (record['id'] + '.json'), record)
        writejson(catalog / (retired_id + '.json'), record | {'id': retired_id})
        writejson(catalog / 'alias.json', dict(record, id='alias', source=record['source'] | {'sha256': retired_sha}))
        active, rejected = audio_library.records(catalog)
        self.assertEqual([item['id'] for item in active], [record['id']])
        self.assertEqual(len(rejected), 2)
        self.assertTrue(all('retired from active selection' in row['reason'] for row in rejected))
        self.pin_theme()
        self.blueprint['music_direction'] = {'asset_id': retired_id}
        config, _, _ = self.arrange(catalog=catalog)
        with self.assertRaisesRegex(ValueError, 'retired from active selection'):
            music.validate_arrangement(config, require_ready=True)

    def test_constant_gain_uses_actual_speech_and_preserves_masking(self):
        count = 3 * joint.SAMPLE_RATE
        foreground, music_source, effect_source = (self.root / name for name in ('speech.wav', 'bed.wav', 'foley.wav'))
        voice = array('h', (round((4000 if i < 48000 or i >= 96000 else 9000) * math.sin(i * .06))
                            if not 60000 <= i < 72000 else 0 for i in range(count)))
        with wave.open(str(foreground), 'wb') as wav:
            wav.setparams((1, 2, 48000, 0, 'NONE', 'not compressed'))
            wav.writeframes(voice.tobytes())
        self.tone(music_source, count, 6000)
        self.tone(effect_source, 1600, 8000)
        rights = audio_library.records()[0][0]
        stem = dict(rights, source=joint.binding(music_source), kind='bgm', gain_db=-8., cue_id='bed',
                    start_sample=0, end_sample=count, source_start_sample=0,
                    envelope=music.constant_envelope(0, count, 1000, 1000))
        effect = dict(rights, source=joint.binding(effect_source), kind='sfx', gain_db=-6.,
                      start_sample=64000, end_sample=65600, source_start_sample=0)
        kwargs = dict(neil_lufs=-17., cue_lufs={'bed': -24.})
        dry, before = ducking.constant_bed([stem], [], foreground, count, **kwargs)
        fixed, after = ducking.constant_bed([stem], [effect], foreground, count, **kwargs)
        self.assertEqual(fixed, dry)
        self.assertEqual(after, before)
        self.assertLess(after['masking_trim_db'], 0)
        self.assertEqual(fixed[0]['envelope'], stem['envelope'])
        with self.assertRaisesRegex(ValueError, 'masking'):
            audio_acceptance.process_mix([stem, effect], foreground, count)
        audio_acceptance.process_mix(fixed + [effect], foreground, count)
        unfit, conflict = ducking.constant_bed([stem], [], foreground, count,
                                              neil_lufs=-17., cue_lufs={'bed': -44.})
        self.assertEqual(unfit, [])
        self.assertFalse(conflict['usable'])
        with self.assertRaisesRegex(ValueError, 'SFX alone'):
            ducking.constant_bed([stem], [dict(effect, start_sample=0, end_sample=1600, gain_db=0)],
                                 foreground, count, **kwargs)

    def test_constant_loop_preserves_equal_power_at_each_seam(self):
        cue = {'id': 'loop', 'start_frame': 0, 'end_frame': 132, 'fade_in_seconds': .35, 'fade_out_seconds': .85}
        track = {'sample_count': 48000, 'loopable': True, 'loop_samples': [0, 48000]}
        stems = list(music.lay_constant_music(cue, track, -10))
        self.assertGreater(len(stems), 4)
        for outgoing, incoming in zip(stems, stems[1:]):
            for sample in range(incoming['start_sample'], outgoing['end_sample'], 37):
                gains = [ducking.interpolate(stem['envelope'], sample) for stem in (outgoing, incoming)]
                self.assertAlmostEqual(sum(gain**2 for gain in gains), 1., delta=.0005)
        self.assertEqual(stems[0]['envelope'][0], [0, 0.])
        self.assertEqual(stems[-1]['envelope'][-1], [132 * 1600 - 1, 0.])
        source, silence, output = (self.root / name for name in ('loop.wav', 'silence.wav', 'rendered.wav'))
        count = 132 * 1600
        period = stems[1]['start_sample']
        phase_step = 2 * math.pi * 100.25 / period
        for path, data in ((source, array('h', (round(9000 * math.sin(phase_step * i)) for i in range(48000)))),
                           (silence, array('h', [0]) * count)):
            with wave.open(str(path), 'wb') as wav:
                wav.setparams((1, 2, 48000, 0, 'NONE', 'not compressed'))
                wav.writeframes(data.tobytes())
        rights = audio_library.records()[0][0]
        prepared = [dict(rights, **stem, source=joint.binding(source)) for stem in stems]
        audio_acceptance.process_mix(prepared, silence, count, destination=output)
        with wave.open(str(output), 'rb') as wav:
            for boundary in (stem['start_sample'] for stem in stems[1:]):
                for offset in range(-1200, 8400, 1200):
                    wav.setpos(boundary + offset)
                    samples = audio_acceptance.wav_samples(wav, 1200)
                    gain = 10 * math.log10(math.sumprod(samples, samples) / len(samples) / (9000**2 / 2))
                    self.assertAlmostEqual(gain, -10., delta=.25)

    def test_constant_cue_change_has_equal_power_crossfade(self):
        self.blueprint[music.MIX_MODE_FIELD] = ducking.CONSTANT_BED
        self.blueprint['music_direction'] = {'shots': {'question': {'mode': 'curiosity', 'reason': 'Opening question'}}}
        config, direction, _ = self.arrange()
        outgoing, incoming = config['audio_mix']['stems']
        self.assertEqual(direction['segments'][1]['start_frame'], 60)
        self.assertEqual(outgoing['end_sample'], 60 * 1600)
        self.assertLess(incoming['start_sample'], outgoing['end_sample'])
        for sample in range(incoming['start_sample'], outgoing['end_sample'], 223):
            powers = [ducking.interpolate(stem['envelope'], sample)**2 for stem in (outgoing, incoming)]
            self.assertAlmostEqual(sum(powers), 1., delta=.0005)

    def test_persistent_action_and_multiple_effects(self):
        source = self.root / 'contact.json'
        writejson(source, {'inspected_contact_frames': [30, 70]})
        action = {'id': 'spring', 'start_frame': 0, 'end_frame': 120, 'source_start_frame': 0,
                  'start_state': 'closed', 'end_state': 'returned', 'curve': 'continuous',
                  'constraints': ['held pivot'], 'source': joint.binding(source)}
        self.plan['actions'] = [action]
        for shot in self.plan['shots']:
            shot.update(action_views={'spring': shot['start_frame']}, source_start_frame=shot['start_frame'])
        valid, _ = audio_library.records()
        rights = {key: valid[0][key] for key in ('license', 'license_status', 'credit', 'source_type', 'usage_restrictions')}
        self.blueprint['sound_events'] = [dict(rights, action_id='spring', offset_frames=frame, duration_frames=2,
            trigger_evidence=dict(joint.binding(source), frame=frame, position='inspected_contact_frames'),
            source=joint.binding(self.clip), purpose='Contact alignment test', gain_db=-30) for frame in (30, 70)]
        self.measure()
        config, design, _ = self.arrange()
        self.assertEqual(len(design['segments']), 1)
        self.assertEqual([row['start_sample'] for row in design['segments'][0]['sfx_to_feature']], [48000, 112000])
        self.assertEqual([row['kind'] for row in config['audio_mix']['stems']], ['bgm', 'sfx', 'sfx'])
        music.validate_arrangement(config, blueprint=self.blueprint, measured=self.measured, require_ready=True)
        self.blueprint['sound_events'][0]['offset_frames'] += 1
        with self.assertRaisesRegex(ValueError, 'contact timing'):
            self.arrange()

    def test_short_asset_and_wholly_unvoiced(self):
        self.plan['narration'] = []
        for cut in self.plan['shots']:
            cut['silence_reason'] = 'Observe the mechanism continuously'
        self.measure()
        catalog = self.root / 'library'
        eligible, _ = audio_library.records()
        record = json.loads(Path(eligible[0]['catalog_record']['path']).read_text())
        record.update(style=['curiosity', 'discovery'], source=joint.binding(self.clip), tier='local', loopable=False)
        path = catalog / (record['id'] + '.json')
        writejson(path, record)
        config, design, _ = self.arrange(catalog=catalog)
        self.assertEqual(design['status'], 'BLOCKED')
        with self.assertRaisesRegex(ValueError, 'BGM BLOCKED'):
            music.validate_arrangement(config, require_ready=True)
        record['loopable'] = True
        writejson(path, record)
        config, design, _ = self.arrange(catalog=catalog)
        self.assertEqual(design['status'], 'READY')
        self.assertEqual(design['speech'], [])
        stems = config['audio_mix']['stems']
        self.assertGreater(len(stems), 2)
        self.assertLess(stems[1]['start_sample'], stems[0]['end_sample'])
        self.assertTrue(all(row['envelope'][-1][1] == 0 for row in stems))

    def test_missing_rights_and_tampered_audio(self):
        item = json.loads((audio_library.LIBRARY / 'quiet-link-curiosity.json').read_text())
        catalog = self.root / 'library'
        record = catalog / (item['id'] + '.json')
        item['source'] = joint.binding(self.clip)
        writejson(record, item | {'license': item['license'] | {'proof': {}}})
        self.assertEqual(len(audio_library.records(catalog)[1]), 1)
        writejson(record, item)
        self.assertEqual(len(audio_library.records(catalog)[0]), 1)
        self.clip.write_bytes(b'changed')
        self.assertEqual(len(audio_library.records(catalog)[1]), 1)

    def test_cache_invalidation_and_sample_verification(self):
        config, _, _ = self.arrange()
        receipt = config['audio_mix']
        path = Path(receipt['master']['path'])
        path.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'Missing or changed'):
            audio_acceptance.verify_mix(receipt, self.master, 180 * 1600)
        recovered, _, hit = self.arrange()
        self.assertFalse(hit)
        self.assertEqual(recovered, config)
        self.blueprint['music_direction'] = {'shots': {'question': {'mode': 'curiosity', 'reason': 'Hold suspense',
                                                                     'gain_adjustment_db': -3}}}
        changed, _, hit = self.arrange()
        self.assertFalse(hit)
        self.assertNotEqual(changed['audio_mix']['cache_key'], receipt['cache_key'])
        changed['audio_mix']['stems'][0]['envelope'][1][1] = .1
        with self.assertRaisesRegex(ValueError, 'gain'):
            audio_acceptance.verify_mix(changed['audio_mix'], self.master, 180 * 1600)

    def test_clipping_is_rejected(self):
        eligible, _ = audio_library.records()
        source = self.root / 'overload.wav'
        self.tone(source, 48000, 27000)
        row = dict(eligible[0], source=joint.binding(source), kind='sfx', gain_db=5,
                   start_sample=0, end_sample=48000, source_start_sample=0)
        with self.assertRaisesRegex(ValueError, 'clips'):
            audio_acceptance.process_mix([row], self.master, 180 * 1600, destination=self.root / 'mix.wav')

    def test_audio_only_picture_and_aac_timecode(self):
        self.blueprint[music.MIX_MODE_FIELD] = ducking.CONSTANT_BED
        source = self.root / 'picture.mp4'
        execute(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'testsrc2=s=160x90:r=30:d=6',
                 '-c:v', 'libx264', str(source)], check=True)
        original = filehash(source)
        film = self.root / 'music.mp4'
        with patch('scripts.produce.run_blender', side_effect=AssertionError('Blender must stay idle')):
            evidence = music.postprocess(source, self.blueprint, film, cache=self.cache)
            self.blueprint['music_direction'] = {'mode': 'silence', 'reason': 'Compare the exact same picture'}
            off = music.postprocess(source, self.blueprint, self.root / 'off.mp4', cache=self.cache)
        self.assertEqual(original, filehash(source))
        self.assertEqual(evidence['picture_stream'], off['picture_stream'])
        self.assertNotEqual(evidence['audio']['pcm']['audio_pcm_sha256'], off['audio']['pcm']['audio_pcm_sha256'])
        self.assertEqual(evidence['audio_perceptual_review'], 'UNKNOWN')
        decoded = audio_acceptance.narration_module().measure_loudness(film, audio_acceptance.narration_module().effective_profile(
            {'narration_profile': 'config/narration-neil.json'}))
        self.assertLessEqual(float(decoded['input_tp']), -1.5)
        self.assertGreater(evidence['audio']['waveform']['minimum_reference_snr_db'], 12)
        delayed = self.root / 'delayed.mp4'
        execute(['ffmpeg', '-v', 'error', '-i', str(source), '-itsoffset', '0.2', '-i', str(film),
                 '-map', '0:v', '-map', '1:a', '-c', 'copy', str(delayed)], check=True)
        with self.assertRaisesRegex(ValueError, 'AAC start, format or duration'):
            audio_acceptance.decode_aac(delayed, 180 * 1600)
        media = [joint.binding(film)]
        self.assertEqual(audio_acceptance.music_review({}, media), 'UNKNOWN')
        alleged = dict(full_audio_listened=False, music_listening_review=dict(media_sha256=media[0]['sha256'],
                      method='continuous_audio', time_range=[0, 6], checks={key: {'status': 'PASS',
                      'observation': 'Fixture assertion'} for key in audio_acceptance.MUSIC_LISTENING}))
        self.assertEqual(audio_acceptance.music_review(alleged, media), 'UNKNOWN')

    def test_audio_cache_cleanup_preserves_evidence(self):
        shared_cache = self.root / 'assets/audio/mixes'
        self.cache = shared_cache
        config, _, _ = self.arrange()
        keep = config['audio_mix']['cache_key']
        writejson(self.root / 'output/final.json', {'cache_key': keep})
        self.blueprint['music_direction'] = {'mode': 'silence', 'reason': 'Cleanup fixture'}
        self.arrange()
        with patch.object(clean, 'ROOT', self.root):
            rows = clean.cleanup(0, apply=True)
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]['delete'])
        self.assertTrue((shared_cache / keep / 'mix.wav').exists())

    def test_production_composition_reuses_picture_after_music_change(self):
        self.blueprint[music.MIX_MODE_FIELD] = ducking.CONSTANT_BED
        self.plan['film_integrity_version'] = 1
        self.measure()
        source = self.root / 'picture.mp4'
        execute(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'testsrc2=s=160x90:r=30:d=6',
                 '-c:v', 'libx264', str(source)], check=True)
        pub = self.root / 'public'
        output = self.root / 'output'
        output.mkdir()
        media = {row['id']: (source, 'video', filehash(source)) for row in self.plan['shots']}
        configuration = {
            music.FIELD: 1, joint.FIELD: 1, 'timeline': self.plan, 'title': '', 'subtitle': '',
            'visual_policy_version': 2, 'measured_timeline': self.blueprint['measured_timeline'],
            'render': {'width': 1920, 'height': 1080},
            'storyboard': [{'id': row['id'], 'shot': row['id'], 'label': '', 'note': '', 'accent': '#8dc4dc',
                            'seconds': (row['end_frame'] - row['start_frame']) / 30} for row in self.plan['shots']],
            'shots': {row['id']: {'visual': {}} for row in self.plan['shots']},
        }
        from unittest.mock import Mock
        with (patch.object(produce, 'ROOT', self.root), patch.object(produce, 'CACHE', self.root / 'composition'),
              patch.object(produce, 'PUBLIC', pub), patch('mechanical_video_next.style_lock.verify_lock',
                                                       return_value={'status': 'PASS'}),
              patch('mechanical_video_next.remotion_build.render',
                    side_effect=lambda props, target, log, **kwargs: shutil.copyfile(source, target)) as render):
            for variant in ('off', 'on'):
                if variant == 'off':
                    self.blueprint['music_direction'] = {'mode': 'silence', 'reason': 'Audio-only reuse fixture'}
                else:
                    del self.blueprint['music_direction']
                config, _, _ = self.arrange()
                produce.compose(configuration | config | {'id': variant}, 'preview', media, Mock())
            self.assertEqual(render.call_count, 1)
        changed = output / 'on-preview.mp4'
        self.assertEqual(music.picture_hash(changed), music.picture_hash(output / 'off-preview.mp4'))
        self.assertTrue(json.loads(changed.with_suffix('.audio-direction.json').read_text())['picture_reused'])


if __name__ == '__main__':
    unittest.main()
