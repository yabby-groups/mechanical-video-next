import json
from pathlib import Path
import tempfile
import unittest

from mechanical_video_next.blueprint import compile_config
from mechanical_video_next.knowledge_progression import validate_media_evidence, validate_timeline
from mechanical_video_next.three_d import validate_config
from mechanical_video_next.visual_narrative import (
    QA_CHECKS, match_blueprint, match_policy, validate_design, validate_footage, validate_graphic, validate_review,
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
    def test_rig_camera_compiles_without_replacing_scientific_or_motion_inputs(self):
        camera_fields={
            'camera_path':[dict(progress=p,target=[0,0,0],direction=[0,-1,1],width=3-p) for p in (0,1)],
            'camera_rig':dict(version=1,mode='DOLLY',lens_mm=55,clip=[.001,100],
                              follow=dict(object='Carrier',weight=.4))}
        first=shot('contact',0,engine='blender',role='core',kind='annotated_detail',
                   camera=dict(preset='follow',scale='close',angle='oblique',settings=dict(science=camera_fields)),
                   knowledge='relative surface motion')
        tracks=[dict(object='Carrier',poses=[dict(progress=0,rotation_euler=[0,0,0]),
                                             dict(progress=1,rotation_euler=[0,0,1])])]
        science=dict(version=1,mode='mathematical',scope='Bounded source-specific motion',basis=[REF])
        base=dict(asset='planetary-teaching-v1',shots={'core':dict(template='motion',seconds=4,
                   tracks=tracks,science=science)},render=dict(width=1920,height=1080,fps=30,framing='fullframe'),
                  presentation='mechanism-fullframe')
        with tempfile.TemporaryDirectory() as tmp:
            bp,bp_base,result=(Path(tmp)/name for name in ('blueprint.json','base.json','out.json'))
            data=dict(visual_policy_version=2,shots=[first])
            bp.write_text(json.dumps(data)); bp_base.write_text(json.dumps(base))
            compile_config(bp,bp_base,result,draft=True)
            compiled=json.loads(result.read_text())['shots']['contact']
            self.assertEqual(compiled['tracks'],tracks)
            self.assertEqual(compiled['science']['basis'],science['basis'])
            self.assertEqual(compiled['science']['scope'],science['scope'])
            self.assertEqual(compiled['science']['camera_rig'],camera_fields['camera_rig'])
            self.assertNotIn('camera_rig',json.loads(bp_base.read_text())['shots']['core']['science'])
            camera_fields['driver']='data_tracks'
            bp.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError,'only change science camera fields'):
                compile_config(bp,bp_base,result,draft=True)

    def test_trace_requires_located_basis_and_visible_boundary(self):
        graphic = dict(type='data_animation', presentation='trace', title='Cooling', unit='C',
                       formula='Conceptual example', items=[
                           dict(label='Warm', detail='Example', keyframes=[[0, 75], [4, 10]]),
                           dict(label='Cool', detail='Example', keyframes=[[0, 30], [4, 2]])])
        with self.assertRaises(ValueError):
            validate_graphic(graphic)
        graphic['basis'] = REF
        validate_graphic(graphic)
        del graphic['formula']
        with self.assertRaises(ValueError):
            validate_graphic(graphic)

    def test_progression_requires_distinct_visual_states_and_links_prior_claim(self):
        def example(sid, prior, goal, states):
            return dict(shot_id=sid, knowledge_ids=[goal], knowledge_goal=goal, render_engine='blender',
                        duration=4, camera={'scale': 'wide', 'angle': 'front'}, visual_focus='Reel',
                        progression=dict(previous_ids=prior, kind='new', observable=[
                            dict(knowledge_id=goal, kind='change', proof='physical_action',
                                 frames=[10, 120], states=states)]))
        first = example('one', [], 'reel', ['empty', 'winding'])
        second = example('two', ['reel'], 'shaft', ['stationary', 'turned'])
        self.assertIn('reused_composition', {row['issue'] for row in validate_timeline([first, second])})
        second['progression']['previous_ids'] = []
        with self.assertRaisesRegex(ValueError, 'immediately preceding'):
            validate_timeline([first, second])
        second['progression']['previous_ids'] = ['reel']
        second['progression']['observable'][0]['states'] = ['Empty!', 'Winding.']
        with self.assertRaisesRegex(ValueError, 'already shown'):
            validate_timeline([first, second])

    def test_phone_graphic_rejects_unreadable_copy_and_validates_equal_arc_model(self):
        angular = dict(type='angular_comparison', title='Equal length', travel=3,
                       items=[{'label':'Small', 'radius':1}, {'label':'Large', 'radius':2}])
        validate_graphic(angular, progression=True)
        angular['items'][0]['label'] = 'Overlong label ' * 12
        with self.assertRaisesRegex(ValueError, 'minimum phone text size'):
            validate_graphic(angular, progression=True)

    def test_dynamic_qa_requires_continuity_and_exact_frame_range(self):
        blueprint = {'shots': [
            {'shot_id': 'shaft', 'time_range': [4, 8], 'progression': {'observable': [
                {'knowledge_id': 'slip', 'frames': [5, 100], 'kind': 'change'}]}}]}
        receipt = {'knowledge_id': 'slip', 'frames': [125, 220], 'status': 'PASS',
                   'observation': 'Marks separate', 'method': 'sampled_frames'}
        review = {'visual_evidence': {'shaft': {'media_sha256': 'film', 'observations': [receipt]}}}
        with self.assertRaisesRegex(ValueError, 'continuous viewing'):
            validate_media_evidence(blueprint, review, {'film': 'unused'}, acceptance=True)
        receipt['status'] = 'UNKNOWN'
        validate_media_evidence(blueprint, review, {'film': 'unused'}, acceptance=False)
        receipt['frames'] = [126, 220]
        with self.assertRaisesRegex(ValueError, 'visual evidence'):
            validate_media_evidence(blueprint, review, {'film': 'unused'}, acceptance=False)

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
