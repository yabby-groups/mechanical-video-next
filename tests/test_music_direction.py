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
        return {music.FIELD: 1, 'audio_direction': ref, 'audio_mix': mix}, json.loads(Path(ref['path']).read_text()), hit

    def test_default_and_historical(self):
        task = workflow.create_task('Why does a latch spring back?', root=self.root,
                                    visual_policy_version=2, media_policy_version=1)
        self.assertTrue(music.enabled(workflow.load(task)))
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
        item = json.loads(next(audio_library.LIBRARY.glob('*.json')).read_text())
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
