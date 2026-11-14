"""Typography changes must invalidate composition only, including legacy audio."""
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import produce


class TextCacheBoundary(unittest.TestCase):
    def test_legacy_audio_cache_identity_is_preserved(self):
        shot = dict(id='cached', narration=['原理示意'], seconds=4)
        voice = 'legacy'
        expected = produce.digest(dict(cues=shot['narration'], voice=voice,
            seconds=4, rate=235, audio_pipeline=1,
            processing='499692624f28ded76480fdd5a7519bfd2d2095d73d9fccd50fae3ec1295fbade'))
        with patch.object(produce, 'cached', return_value=True), \
             patch.object(produce, 'run', side_effect=AssertionError('No TTS/FFmpeg allowed')), \
             patch.object(Path, 'read_text', return_value='[]'):
            class Metrics:
                def record(self, *args, **kwargs): pass
            self.assertEqual(produce.tts(shot, voice, Metrics())[2], expected)

    def test_shot_and_asset_keys_ignore_text_profile(self):
        # Real local assembly; text profile isn't a geometry dependency.
        cfg = json.loads((ROOT/'tests/fixtures/production/planetary-01.json').read_text())
        shot = next(iter(cfg['shots'].values()))
        baseline = produce.shot_key(shot, 'preview', cfg['render'], 'tests/fixtures/production/assembly.json')
        original = produce.codehash
        def changed(*paths):
            return 'changed' if 'config/text-style.json' in paths else original(*paths)
        with patch.object(produce, 'codehash', side_effect=changed):
            self.assertEqual(baseline, produce.shot_key(shot, 'preview', cfg['render'], 'tests/fixtures/production/assembly.json'))
            self.assertNotEqual(produce.composition_key({}, 'preview'),
                                self._old_composition(original))

    @staticmethod
    def _old_composition(original):
        with patch.object(produce, 'codehash', side_effect=original):
            return produce.composition_key({}, 'preview')
