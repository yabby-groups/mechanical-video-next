import copy
from pathlib import Path
import tempfile
import unittest

from mechanical_video_next import production_contract as c
from mechanical_video_next.workflow import create_task, load, producer_prompt


class ProductionContractTests(unittest.TestCase):
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
