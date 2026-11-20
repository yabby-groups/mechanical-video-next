"""Boundary regressions: old tasks, license tampering and core-media substitution."""
import copy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from mechanical_video_next import media_policy as m
from mechanical_video_next.visual_narrative import match_policy, validate_design, validate_plan
from mechanical_video_next.workflow import create_task, load, producer_prompt
from tests.test_visual_narrative import shot


class MediaPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name)
        cls.video = cls.root / 'owned.mp4'
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i',
                        'color=gray:s=1920x1080:r=30:d=1', '-c:v', 'libx264', '-preset', 'ultrafast',
                        '-pix_fmt', 'yuv420p', str(cls.video)], check=True)
        cls.proof = cls.root / 'ownership.txt'
        cls.proof.write_text('Original project-generated test video. Commercial editing permitted.')

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def row(self):
        row = shot('use', 0, engine='footage', role='support', kind='real_use',
                   camera={'scale':'wide', 'angle':'front'}, knowledge='usage')
        row.update(duration=1, source_type='GENERATED', source_url=self.video.as_uri(),
                   source_time_range=[0,1], license_status='VERIFIED', usage_restrictions=[],
                   selected_asset=m.binding(self.video), reuse_decision='REUSE', generation_required=False,
                   content_verified=True, credit='Project test fixture',
                   matching={'attempts':[{'priority':1, 'status':'ELIGIBLE'}]},
                   license={'status':'VERIFIED', 'name':'Project-generated original', 'holder':'Project',
                            'editing_and_distribution':True, 'commercial_use':True,
                            'proof':dict(m.binding(self.proof),position='Complete ownership statement')})
        return row

    def test_reference_is_not_a_license_and_file_cache_is_not_permission(self):
        row = self.row()
        m.validate_shot(row, 1)
        row['source_type'] = 'REFERENCE_ONLY'
        with self.assertRaisesRegex(ValueError, 'rights'):
            m.validate_shot(row, 1)
        row = self.row()
        row['license']['name'] = 'CC-BY-NC-4.0'
        with self.assertRaisesRegex(ValueError, 'Noncommercial'):
            m.validate_shot(row, 1)
        row = self.row()
        row['license']['proof']['sha256'] = '0'*64
        with self.assertRaisesRegex(ValueError, 'changed'):
            m.validate_shot(row, 1)

    def test_source_interval_and_executable_media_must_match(self):
        row = self.row()
        footage = {**row['selected_asset'], 'start_frame':0, 'license':row['license'], 'credit':row['credit']}
        m.validate_shot(row, 1, footage=footage)
        footage['start_frame'] = 3
        with self.assertRaisesRegex(ValueError, 'interval'):
            m.validate_shot(row, 1, footage=footage)
        row['source_time_range'] = [0,2]
        with self.assertRaisesRegex(ValueError, 'interval'):
            m.validate_shot(row, 1)

    def test_core_footage_requires_independent_observed_mechanism(self):
        row = self.row()
        row['mechanical_role'] = 'core'
        row['visual_type'] = 'mechanical_cutaway'
        validate_design(row, hybrid=True)
        with self.assertRaisesRegex(ValueError, 'independent'):
            m.validate_shot(row, 1)
        with self.assertRaisesRegex(ValueError, 'Unsupported visual type'):
            validate_design(row)
        row['mechanism_verification'] = {'status':'PASS', 'independent':True,
            'continuous_video':True, 'reviewer_thread_id':'independent-test', 'observation':'Test fixture',
            'real_mechanism':True, 'source_sha256':row['selected_asset']['sha256'],
            'time_range':[0,1], 'confirmed_knowledge_ids':['usage'], 'report':m.binding(self.proof)}
        m.validate_shot(row, 1)
        row['mechanism_verification']['time_range'] = [1,2]
        with self.assertRaisesRegex(ValueError, 'exact source interval'):
            m.validate_shot(row, 1)

    def test_generation_records_search_gaps_and_cannot_relabel_reference(self):
        row = self.row()
        row.update(generation_required=True, reuse_decision='GENERATE', selected_asset=None,
                   source_time_range=None)
        with self.assertRaisesRegex(ValueError, 'all existing material tiers'):
            m.validate_shot(row, 1)
        row['matching'] = {'attempts':[{'priority':i,'status':'UNSUITABLE'} for i in range(1,6)],
                           'generation_reason':'Exact mechanism diagram needs original source-matched labels'}
        m.validate_shot(row, 1)

    def test_repeated_interval_rejected(self):
        row = self.row()
        doc = {'media_policy_version':1,'visual_policy_version':2, 'shots':[row,copy.deepcopy(row)]}
        with self.assertRaisesRegex(ValueError, 'Repeated source interval'):
            m.validate_document(doc)

    def test_historical_tasks_do_not_acquire_hybrid_policy(self):
        with tempfile.TemporaryDirectory() as tmp:
            old = load(create_task('Historical', root=Path(tmp), task_id='old'))
            self.assertFalse(m.enabled(old))
            new = load(create_task('New topic', root=Path(tmp), task_id='new',
                                   visual_policy_version=2, media_policy_version=1))
            self.assertTrue(m.enabled(new))
            self.assertEqual(new['production_method'], 'producer-directed')
            self.assertEqual(new['production_contract'], 'mechanical-story-v6')
            v4 = load(create_task('Pinned v4', root=Path(tmp), task_id='v4',
                                  visual_policy_version=2, media_policy_version=1, contract_version=4))
            self.assertEqual(v4['production_contract'], 'science-discovery-v4')
            v3 = load(create_task('Pinned v3', root=Path(tmp), task_id='v3',
                                  visual_policy_version=2, media_policy_version=1, contract_version=3))
            self.assertEqual(v3['production_contract_version'], 3)
            v2 = load(create_task('Pinned v2', root=Path(tmp), task_id='v2',
                                  visual_policy_version=2, media_policy_version=1, contract_version=2))
            self.assertEqual(v2['production_method'], 'asset-first-hybrid')
            self.assertEqual(v2['production_contract_version'], 2)
            self.assertIn('REFERENCE_ONLY', producer_prompt(new, Path(tmp)))
            with self.assertRaisesRegex(ValueError, 'creation policy'):
                match_policy(new, {'visual_policy_version':2,'knowledge_progression_version':1})
            with self.assertRaisesRegex(ValueError, 'explicit visual policy 2'):
                create_task('Bad legacy upgrade', root=Path(tmp),task_id='bad',media_policy_version=1)

    def test_physical_story_can_have_no_mechanical_shots(self):
        document = dict(visual_policy_version=2, media_policy_version=1,
                        production_contract_version=3, production_contract='science-story-v3',
                        subject_kind='physical_phenomenon', shots=[self.row()])
        validate_plan(document)
        with self.assertRaisesRegex(ValueError, 'core action'):
            validate_plan(document | {'subject_kind': 'mechanical_implementation'})
        with self.assertRaisesRegex(ValueError, 'core action'):
            validate_plan(document | {'production_contract_version': 2,
                                      'production_contract': 'creative-first-v2'})

    def test_reuse_native_graphic_requires_exact_definition(self):
        row = self.row()
        definition = {'type':'diagram','title':'Flow','items':[
            {'label':'Coating','detail':'Onto paper'}, {'label':'Backing','detail':'Onto take-up reel'}]}
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp)/'diagram.json'
            source.write_text(json.dumps(definition))
            row.update(render_engine='remotion', selected_asset=m.binding(source),source_time_range=None,
                       visual_type='abstract_phenomenon',source_url=source.as_uri())
            m.validate_shot(row, 1, graphic=definition)
            with self.assertRaisesRegex(ValueError,'exact graphic definition'):
                m.validate_shot(row, 1, graphic={**definition,'title':'Different claim'})

    def test_real_footage_asset_exception_is_versioned_and_keeps_observation_gate(self):
        from tests.test_reference_policy import fixture
        from mechanical_video_next.reference_policy import validate_asset
        _, research, asset, _ = fixture('existing-media')
        row = self.row()
        row.update(mechanical_role='core', visual_type='mechanical_cutaway')
        row['mechanism_verification'] = {'status':'PASS','independent':True,'continuous_video':True,
            'reviewer_thread_id':'contract-fixture-only','observation':'Synthetic schema fixture, no product acceptance',
            'real_mechanism':True,'source_sha256':row['selected_asset']['sha256'], 'time_range':[0,1],
            'confirmed_knowledge_ids':['usage'],'report':m.binding(self.proof)}
        asset.update(media_policy_version=1, visual_policy_version=2)
        candidate = asset['candidates'][0]
        candidate.update(source_files=[row['selected_asset']],mechanism_shots=[row])
        self.assertEqual(validate_asset(research,asset),('existing-media','existing-media'))
        candidate['mechanism_shots'][0]['mechanism_verification']['continuous_video'] = False
        with self.assertRaisesRegex(ValueError,'independent'):
            validate_asset(research,asset)
        del asset['media_policy_version']
        with self.assertRaisesRegex(ValueError,'executable 3D provenance'):
            validate_asset(research,asset)

    def test_copyright_pass_and_reuse_percentage_do_not_grant_originality(self):
        manifest = self.proof
        media = m.binding(self.video)
        section = lambda keys: {'media':media,'manifest':m.binding(manifest),'independent':True,
            'reviewer_thread_id':'qa-fixture-only','checks':{k:{'status':'PASS','observation':'Synthetic gate fixture'} for k in keys}}
        qa = {'hybrid_media_review':{'media':media,'manifest':m.binding(manifest),'continuous_video':True,
            'listening':True,'shots':{'use':{k:{'status':'PASS','observation':'Test gate only'} for k in m.QA_CHECKS}}},
            'copyright_review':section(m.COPYRIGHT_CHECKS),'original_expression_review':section(m.ORIGINALITY_CHECKS)}
        doc = {'media':media,'shots':[{'shot_id':'use'}]}
        with patch.object(m,'validate_manifest',return_value=doc):
            m.validate_qa(qa,manifest,acceptance=False)
            with self.assertRaisesRegex(ValueError,'this task research'):
                m.validate_qa(qa,manifest,acceptance=True)
            inputs = {k:m.binding(self.proof) for k in ('research','script','blueprint')}
            qa['original_expression_review'].update(input_bindings=inputs,ratio_used_as_originality_verdict=True)
            with self.assertRaisesRegex(ValueError,'percentage'):
                m.validate_qa(qa,manifest,acceptance=True,original_inputs=inputs)
            qa['original_expression_review']['ratio_used_as_originality_verdict'] = False
            qa['original_expression_review']['checks']['original_narration']['status'] = 'UNKNOWN'
            with self.assertRaisesRegex(ValueError,'original_expression_review'):
                m.validate_qa(qa,manifest,acceptance=True,original_inputs=inputs)


if __name__ == '__main__':
    unittest.main()
