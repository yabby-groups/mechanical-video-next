import copy
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from produce import validate_stage_duration, shot_key


class MechanismPreviewDurationTests(unittest.TestCase):
    def test_only_identical_native_render_settings_share_preview_final_cache(self):
        shot = {'template':'motion','seconds':8}
        render = {'width':1920,'height':1080,'framing':'fullframe','preview_native':True}
        self.assertEqual(shot_key(shot,'preview',render),shot_key(shot,'final',render))
        render['preview_native'] = False
        self.assertNotEqual(shot_key(shot,'preview',render),shot_key(shot,'final',render))

    def test_preview_precedes_full_duration_without_authorizing_short_final(self):
        cfg = {'production_scope': 'mechanism-preview', 'content_policy_version': 1,
               'local_preview_shots': ['product', 'inside', 'return'],
               'shots': {name: {'seconds': 5, 'template': 'motion'}
                         for name in ['product', 'inside', 'return']},
               'storyboard': [{'seconds': 5}] * 3}
        validate_stage_duration(cfg, 'local')
        with self.assertRaises(AssertionError):
            validate_stage_duration(cfg, 'final')
        too_long = copy.deepcopy(cfg)
        too_long['shots']['return']['seconds'] = 6
        with self.assertRaises(AssertionError):
            validate_stage_duration(too_long, 'local')
        static = copy.deepcopy(cfg)
        static['shots']['inside']['template'] = 'overall'
        with self.assertRaises(AssertionError):
            validate_stage_duration(static, 'local')
