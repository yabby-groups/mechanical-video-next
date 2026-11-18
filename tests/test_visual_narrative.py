import json
from pathlib import Path
import tempfile
import unittest

from mechanical_video_next.blueprint import compile_config
from mechanical_video_next.three_d import validate_config
from mechanical_video_next.visual_narrative import (
    QA_CHECKS, match_blueprint, match_policy, validate_design, validate_footage, validate_review,
)
from scripts.common import filehash


FIXTURES = Path(__file__).resolve().parent / 'fixtures/production'
BASIS = FIXTURES / 'science-basis.md'
REF = {'path': str(BASIS), 'sha256': filehash(BASIS), 'position': 'Fixed-ring teaching relation'}


def shot(shot_id, start, *, engine, role, kind, camera, knowledge):
    return {
        'shot_id': shot_id, 'time_range': [start, start+4], 'knowledge_goal': knowledge,
        'mechanical_action': 'Motion shown in the verified scene',
        'asset': 'planetary-teaching-v1', 'assets': ['planetary-teaching-v1'],
        'template': 'motion' if engine == 'blender' else 'editorial',
        'existing_shot': 'core', 'narration': [knowledge], 'subtitles': [knowledge],
        'overlays': [], 'visual_type': kind, 'visual_focus': 'Carrier',
        'visual_action': 'Show the input followed by the output', 'render_engine': engine,
        'camera': camera, 'transition': {'kind': 'cut', 'link': 'Keep the carrier as the subject'},
        'evidence': [REF], 'duration': 4, 'mechanical_role': role, 'knowledge_ids': [knowledge],
        'progression': {'kind': 'new', 'reason': 'Shows the next verified relationship'},
    }


class VisualNarrativeTests(unittest.TestCase):
    def test_compiles_one_timeline_and_keeps_native_motion(self):
        first = shot('motion', 0, engine='blender', role='core', kind='mechanical_cutaway',
                     camera={'preset': 'establish', 'scale': 'wide', 'angle': 'front'}, knowledge='rotation')
        second = shot('chart', 4, engine='remotion', role='support', kind='parameter_chart',
                      camera={'scale': 'diagram', 'angle': 'straight'}, knowledge='ratio')
        second['graphic'] = {'type': 'chart', 'title': 'Angle', 'unit': '°',
                             'items': [{'label': 'Input', 'detail': 'Sun', 'value': 40},
                                       {'label': 'Output', 'detail': 'Carrier', 'value': 10}]}
        base = {'asset': 'planetary-teaching-v1',
                'shots': {'core': {'template': 'motion', 'seconds': 4,
                                   'science': {'version': 1, 'mode': 'mathematical', 'scope': 'Fixed ring',
                                               'basis': [REF]}}},
                'render': {'width': 1920, 'height': 1080, 'fps': 30, 'framing': 'fullframe'},
                'presentation': 'mechanism-fullframe'}
        with tempfile.TemporaryDirectory() as tmp:
            blueprint, base_path, output = (Path(tmp) / name for name in ('blueprint.json', 'base.json', 'out.json'))
            blueprint.write_text(json.dumps({'visual_policy_version': 2, 'shots': [first, second]}))
            base_path.write_text(json.dumps(base))
            compile_config(blueprint, base_path, output, draft=True)
            cfg = json.loads(output.read_text())
            self.assertEqual([s['id'] for s in cfg['storyboard']], ['motion', 'chart'])
            self.assertEqual(cfg['shots']['motion']['template'], 'motion')
            self.assertEqual(cfg['shots']['chart']['graphic'], second['graphic'])
            self.assertFalse(cfg['shots']['motion']['studio_lighting']['camera_push'])
            match_blueprint({'shots': [first, second]}, cfg)
            self.assertRaisesRegex(ValueError, 'versioned visual', validate_config,
                                   {k: v for k, v in cfg.items() if k != 'visual_policy_version'})
            self.assertRaisesRegex(ValueError, 'creation policy', match_policy, {}, cfg)
            cfg['shots']['motion']['visual']['mechanical_role'] = 'support'
            with self.assertRaisesRegex(ValueError, 'differs from Blueprint'):
                match_blueprint({'shots': [first, second]}, cfg)

    def test_core_action_cannot_be_declared_as_a_graphic(self):
        data = shot('fake', 0, engine='remotion', role='core', kind='abstract_phenomenon',
                    camera={'scale': 'diagram', 'angle': 'front'}, knowledge='relative motion')
        with self.assertRaisesRegex(ValueError, 'requires real Blender'):
            validate_design(data)

    def test_footage_requires_permission_and_current_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'footage.mov'
            path.write_bytes(b'unit test digest only')
            data = {'path': str(path), 'sha256': filehash(path), 'source_url': 'file:///footage.mov',
                    'credit': 'Original footage', 'start_frame': 15,
                    'license': {'name': 'Owned footage', 'holder': 'Video owner',
                                'status': 'VERIFIED', 'editing_and_distribution': True, 'proof': REF}}
            self.assertEqual(validate_footage(data), path)
            data['license']['editing_and_distribution'] = False
            with self.assertRaisesRegex(ValueError, 'license'):
                validate_footage(data)
            path.write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError, 'changed visual source'):
                validate_footage(data)

    def test_sampled_qa_cannot_accept_unknown_motion_visibility(self):
        checks = {key: {'status': 'PASS', 'observation': 'Reviewed'} for key in QA_CHECKS}
        checks['motion_visibility']['status'] = 'UNKNOWN'
        validate_review({'motion': checks}, ['motion'], acceptance=False)
        with self.assertRaisesRegex(ValueError, 'UNKNOWN'):
            validate_review({'motion': checks}, ['motion'], acceptance=True)
