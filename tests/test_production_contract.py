import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from mechanical_video_next import production_contract as c
from mechanical_video_next.workflow import create_task, load, producer_prompt


class ProductionContractTests(unittest.TestCase):
    def test_compose_filters_only_natural_fullframe_labels_and_preserves_credits(self):
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
        import produce

        class PropsReady(Exception):
            pass

        for style, caption, expected in (
                ('natural_science', '原理示意 · 摩擦力大小未模拟', '摩擦力大小未模拟'),
                ('natural_science', '原理示意', None),
                ('legacy', '原理示意', '原理示意')):
            cfg = dict(title='A concrete question', subtitle='A causal answer', voice={},
                       presentation='mechanism-fullframe', presentation_style=style,
                       fullframe_caption=caption, fullframe_credit='Source: original evidence',
                       render=dict(width=1920, height=1080), storyboard=[], shots={})
            with self.subTest(style=style, caption=caption), \
                    patch('narration.effective_profile', return_value={}), \
                    patch('mechanical_video_next.style_lock.verify_lock', return_value={'status': 'PASS'}), \
                    patch('mechanical_video_next.text_layout.prepare_text_props', side_effect=PropsReady) as prepare:
                with self.assertRaises(PropsReady):
                    produce.compose(cfg, 'preview', {}, None)
                props = prepare.call_args.args[0]
                self.assertEqual(props.get('fullframe_caption'), expected)
                self.assertEqual(props['fullframe_credit'], cfg['fullframe_credit'])

    def test_audience_decision_binds_the_opening_and_payoff(self):
        plan = dict(production_contract_version=1, production_contract=c.NAME,
                    media_policy_version=1, visual_policy_version=2,
                    narrative=dict(question='Why?', tension='A contradiction', answer='Because', arc_reason='Comparison'),
                    shots=[dict(shot_id=sid, direction={k:'Concrete decision' for k in c.DIRECTION})
                           for sid in ('opening', 'answer')])
        c.validate_direction(plan)
        decision = dict(daily_context='Everyday use', opening_visual='Visible action',
                        viewer_takeaway='A causal answer', selection_rationale='A familiar question',
                        opening_shot_id='opening', payoff_shot_id='answer')
        plan['narrative']['audience_decision'] = decision
        c.validate_direction(plan)
        for changes in ({'opening_shot_id': 'answer'}, {'payoff_shot_id': 'missing'},
                        {'selection_rationale': ''}):
            with self.subTest(changes=changes), self.assertRaisesRegex(ValueError, 'Audience decision'):
                plan['narrative']['audience_decision'] = decision | changes
                c.validate_direction(plan)

    def test_natural_copy_distinguishes_production_labels_from_scientific_limits(self):
        from mechanical_video_next.science_information import information_props
        c.validate_audience_copy({
            'narration': ['只看运动方向，摩擦力大小还要另测。'],
            'overlays': ['模型按等速带入计算', '压头'],
        })
        with self.assertRaisesRegex(ValueError, 'classroom'):
            c.validate_audience_copy({'narration': ['下面我们来学习修正带。']})
        with self.assertRaisesRegex(ValueError, 'production label'):
            c.validate_audience_copy({'science': {'print_marks': [{'text': '教学模型'}]}})
        shot = {'science': {'mode': 'conceptual'}}
        self.assertEqual(information_props(shot, {}, None, 'video')['scienceLabel'], '原理示意')
        self.assertIsNone(information_props(shot, {}, None, 'video', natural=True)['scienceLabel'])
        self.assertEqual(shot['science']['mode'], 'conceptual')

    def test_mechanical_review_reuse_tracks_only_its_real_dependencies(self):
        from mechanical_video_next.reference_policy import model_program_digest
        with tempfile.TemporaryDirectory() as folder:
            assembly=Path(folder)/'assembly.json';assembly.write_text('{"parts":["A"]}')
            cfg=dict(assembly_config=str(assembly),shots={'core':dict(template='state_transition',seconds=4,tracks=[{'object':'A','poses':[]}],visual={'knowledge_goal':'A'}),
                'chart':dict(template='editorial',graphic={'value':1})},storyboard=[{'narration':['Original']}])
            before=model_program_digest(cfg)
            cfg['storyboard'][0]['narration']=['Caption correction']
            cfg['shots']['chart']['graphic']['value']=2
            self.assertEqual(model_program_digest(cfg),before)
            cfg['shots']['core']['camera_direction']=[1,1,1]
            self.assertNotEqual(model_program_digest(cfg),before)
            changed=model_program_digest(cfg);assembly.write_text('{"parts":["A","B"]}')
            self.assertNotEqual(model_program_digest(cfg),changed)

    def test_new_hybrid_pins_contract_and_legacy_keeps_original(self):
        with tempfile.TemporaryDirectory() as folder:
            task = create_task('Why?', root=folder, task_id='mixed', visual_policy_version=2, media_policy_version=1)
            data = load(task)
            self.assertTrue(c.enabled(data))
            self.assertIn('mixed-original-v1', producer_prompt(data,task))
            legacy = load(create_task('Old',root=folder,task_id='old'))
            self.assertFalse(c.enabled(legacy))
            data['media_policy_version']=0
            with self.assertRaises(ValueError): c.enabled(data)

    def test_unknown_fact_is_local_and_cannot_enter_dependent_shot(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder)/'source.txt'; source.write_text('Located evidence')
            from scripts.common import filehash
            fact = dict(id='known',claim='A visible relationship',status='VERIFIED',kind='observed',
                        scope='This example',assumptions=[],sources=[dict(path=str(source),sha256=filehash(source),position='paragraph 1')])
            unknown = dict(fact,id='unknown',status='UNKNOWN',limitation='Hidden contact unobserved')
            research = {'science':dict(subject_kind='mechanical_implementation',question='Why?',answer='Because',scope='Example',facts=[fact,unknown])}
            c.validate_research(research)
            plan = dict(production_contract_version=1,production_contract=c.NAME,media_policy_version=1,visual_policy_version=2,
                        narrative=dict(question='Why?',tension='A contradiction',answer='Because',arc_reason='Comparison'),
                        shots=[dict(knowledge_ids=['known'],direction={k:'Concrete decision' for k in c.DIRECTION})])
            c.validate_direction(plan,research)
            plan['shots'][0]['knowledge_ids']=['unknown']
            with self.assertRaisesRegex(ValueError,'dependent shot'): c.validate_direction(plan,research)
            fact['sources'][0]['sha256']='0'*64
            with self.assertRaisesRegex(ValueError,'changed'): c.validate_research(research)

    def test_six_dimensions_never_grant_missing_senses(self):
        media=[dict(path='actual.mp4',sha256='a'*64)]
        report=dict(quality_dimensions={k:dict(status='PASS',media_sha256='a'*64,observation='Observation') for k in c.DIMENSIONS})
        c.validate_qa(report,media,acceptance=False)
        with self.assertRaisesRegex(ValueError,'viewing and listening'): c.validate_qa(report,media,acceptance=True)
        report.update(full_video_reviewed=True,full_audio_listened=True)
        with self.assertRaisesRegex(ValueError,'review observations'):
            c.validate_qa(report,media,acceptance=True)
        report['quality_dimensions']['mechanical_motion']['status']='UNKNOWN'
        with self.assertRaisesRegex(ValueError,'prevents acceptance'): c.validate_qa(report,media,acceptance=True)

    def test_physical_phenomenon_uses_bounded_subject_without_fake_product(self):
        from mechanical_video_next.comprehension import validate_product_plan
        from scripts.common import filehash
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)/'source.txt';source.write_text('Contract fixture for an ideal constant-speed mathematical model; not production evidence.')
            subject=dict(id='constant-speed',name='等速位移',scope='Ideal constant speed only',model_kind='mathematical')
            claims=['Distance equals speed times elapsed time','Equal time intervals give equal distances']
            refs=[dict(reference_id='physics',supported_claims=claims,evidence=[dict(path=str(source),sha256=filehash(source),position='Complete fixture')])]
            plan=dict(production_contract_version=1,production_contract=c.NAME,media_policy_version=1,visual_policy_version=2,
                subject_kind='physical_phenomenon',subject_identity=subject,subject_references=refs,
                subject_opening=dict(shot_id='a',time_range=[0,3],subject_reveal='等速位移',real_action='Equal distances',why_question='Why?',answer_promise='Constant speed'),shots=[])
            for i,sid in enumerate(('a','b')):
                row=dict(reference_ids=['physics'],product_parts=['model marker'],input_action=claims[i],transmission=claims[i],output_action=claims[i],
                    visual_evidence='Position changes',narration=claims[i],new_knowledge=claims[i],necessity='Isolate time',causal_link='s=vt',
                    recognition_relations=['phenomenon','conditions'] if i==0 else ['model','causal_test','return_to_question'],verification_method='Observe model and check assumptions',
                    causal_evidence={k:dict(reference_id='physics',claim=claims[i],position='Complete fixture') for k in ('input_action','transmission','output_action')})
                plan['shots'].append(dict(shot_id=sid,time_range=[i*3,(i+1)*3],narration=[claims[i]],comprehension=row))
            research=dict(science=dict(subject=subject))
            self.assertEqual(validate_product_plan(plan,research)['product_id'],'constant-speed')
            self.assertNotIn('product_identity',plan)
            plan['subject_identity']=dict(subject,scope='Unbounded real-world prediction')
            with self.assertRaisesRegex(ValueError,'scope differs'):validate_product_plan(plan,research)
