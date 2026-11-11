"""No billed requests in tests: cache safety, timing, processing and approval boundaries."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import narration as n
from common import probe,writejson

class NarrationTests(unittest.TestCase):
    def setUp(self):
        (ROOT/'work').mkdir(exist_ok=True)
        self.profile=n.load_profile(ROOT/'config/narration-kai.json')

    def test_unsupported_native_controls_are_not_silently_sent(self):
        p=n.request_payload('关键在这里：行星架输出。',self.profile)
        self.assertEqual(p,{'model':'qwen3-tts-flash','voice':'Kai','input':'关键在这里：行星架输出。','response_format':'wav'})
        self.assertNotIn('instructions',p)
        self.assertNotIn('speed',p)

    def test_reference_voice_neil_has_distinct_request_cache(self):
        neil=n.load_profile(ROOT/'config/narration-neil.json')
        self.assertEqual(neil['voice'],'Neil')
        self.assertEqual(neil['model'],'qwen3-tts-flash')
        self.assertEqual(neil['target_speed'],1.0)
        kai_request=n.request_payload('相同的试听文字。',self.profile)
        neil_request=n.request_payload('相同的试听文字。',neil)
        self.assertNotEqual(n.digest(kai_request),n.digest(neil_request))

    def test_explicit_reference_selection_enables_default_without_claiming_listening(self):
        neil=n.load_profile(ROOT/'config/narration-neil.json')
        with tempfile.TemporaryDirectory(dir=ROOT/'work') as d:
            folder=Path(d);audio=folder/'audition.wav';audio.write_bytes(b'reference-voice-fixture')
            receipt=folder/'audition.json'
            writejson(receipt,{'profile':'config/narration-neil.json','profile_sha256':n.profile_hash(neil),
                              'audio_sha256':n.filehash(audio)})
            with patch.object(n,'DEFAULTS',folder/'default.json'):
                n.activate(receipt,'explicit_reference_voice_selection')
                settings=json.loads(n.DEFAULTS.read_text())
                self.assertEqual(settings['approval_basis'],'explicit_reference_voice_selection')
                self.assertEqual(n.effective_profile({'channel':'视频号'})['voice'],'Neil')
                self.assertIsNone(n.effective_profile({'channel':'抖音'}))

    def test_extreme_post_speed_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            for speed in [0.8,1.2,float('nan')]:
                p=Path(d)/'profile.json'
                p.write_text(json.dumps(dict(self.profile,target_speed=speed)))
                with self.assertRaises(ValueError): n.load_profile(p)

    def test_pending_generation_never_resubmits(self):
        with tempfile.TemporaryDirectory() as d,patch.object(n,'STORE',Path(d)),patch.dict(n.os.environ,{'OPENAI_API_KEY':'fake-test-key','OPENAI_BASE_URL':'https://example.invalid/v1'}):
            payload=n.request_payload('测试句子。',self.profile)
            key=n.digest({'endpoint':'https://example.invalid/v1/audio/speech','payload':payload})
            folder=Path(d)/'raw'/key
            writejson(folder/'submitted.json',{'status':'submitted'})
            with patch.object(n.urllib.request,'build_opener') as http:
                with self.assertRaisesRegex(RuntimeError,'unresolved'): n.raw_sentence('测试句子。',self.profile)
                http.assert_not_called()

    def test_subtitle_or_shot_id_edit_does_not_regenerate_speech(self):
        with tempfile.TemporaryDirectory() as d,patch.object(n,'STORE',Path(d)):
            # Cache a completed local shot; no provider invoked.
            s={'id':'one','seconds':4,'narration':['说明文字。'],'subtitles':['修改字幕前']}
            key=n.digest({'narration':s['narration'],'seconds':s['seconds'],'profile':self.profile,'processing':n.codehash('scripts/narration.py')})
            folder=Path(d)/'shots'/key
            folder.mkdir(parents=True)
            for f in ['narration.wav','audio.m4a','processing.json']: (folder/f).write_bytes(b'fixture')
            writejson(folder/'cues.json',[{'start':0.15,'end':3,'text':'说明文字。'}])
            n.seal(folder,['narration.wav','audio.m4a','processing.json','cues.json'])
            s['id']='two';s['subtitles']=['只修改字幕']
            with patch.object(n,'sentence') as provider:
                _,_,actual,hit=n.synthesize_shot(s,self.profile)
                self.assertTrue(hit);self.assertEqual(key,actual);provider.assert_not_called()

    def test_unconfirmed_profile_cannot_be_used_in_production(self):
        with tempfile.TemporaryDirectory() as d:
            defaults=Path(d)/'default.json'
            writejson(defaults,{'default_profile':None,'status':'awaiting_user_audition_confirmation'})
            with patch.object(n,'DEFAULTS',defaults):
                self.assertIsNone(n.effective_profile({}))
                with self.assertRaisesRegex(RuntimeError,'not been confirmed'):
                    n.effective_profile({'narration_profile':'config/narration-kai.json'})

    def test_approval_survives_cache_metadata_changes_but_rejects_changed_audio(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'work') as d:
            folder=Path(d);audio=folder/'audition.wav';audio.write_bytes(b'approved-audio-fixture')
            receipt=folder/'audition.json'
            data={'profile':'config/narration-kai.json','profile_sha256':n.profile_hash(self.profile),
                  'audio_sha256':n.filehash(audio),'shots':[{'cache_hit':False}]}
            writejson(receipt,data)
            with patch.object(n,'DEFAULTS',folder/'default.json'):
                n.activate(receipt)
                data['shots'][0]['cache_hit']=True;writejson(receipt,data)
                self.assertEqual(n.effective_profile({'channel':'视频号'})['voice'],'Kai')
                self.assertIsNone(n.effective_profile({'channel':'抖音'}))
                audio.write_bytes(b'changed-audio-fixture')
                with self.assertRaisesRegex(RuntimeError,'integrity mismatch'):
                    n.effective_profile({'channel':'视频号'})

    def test_cannot_speed_fit_a_short_shot(self):
        with tempfile.TemporaryDirectory() as d,patch.object(n,'STORE',Path(d)):
            wav=Path(d)/'voice.wav'
            subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','sine=frequency=330:duration=2','-c:a','pcm_s16le',str(wav)],check=True)
            with patch.object(n,'sentence',return_value=(wav,{'raw_cache_hit':True})):
                with self.assertRaisesRegex(RuntimeError,'no automatic acceleration'):
                    n.synthesize_shot({'narration':['必须留足自然语速。'],'seconds':1},self.profile)

    def test_normalization_and_timing_operate_on_actual_pcm(self):
        with tempfile.TemporaryDirectory() as d:
            original=Path(d)/'original.wav';trim=Path(d)/'trim.wav';normal=Path(d)/'normal.wav'
            subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','sine=frequency=220:duration=3.4',
                '-af','volume=0.5,adelay=300:all=1,apad=pad_dur=0.4','-ar','48000','-c:a','pcm_s16le',str(original)],check=True)
            info=n.silence_trim(original,trim,self.profile)
            self.assertEqual(info['post_speed_factor'],1.0)
            self.assertGreater(info['trim_start'],0.15)
            self.assertLess(float(probe(trim)['format']['duration']),float(probe(original)['format']['duration']))
            levels=n.normalize(trim,normal,self.profile)
            self.assertAlmostEqual(float(levels['after']['input_i']),-16,delta=1)
            self.assertLessEqual(float(levels['after']['input_tp']),-1.3)

if __name__=='__main__': unittest.main()
