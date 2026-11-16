"""Temporary ledger integration: no historic production or rendering is run."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from contextlib import ExitStack
from mechanical_video_next import workflow as w, reference_policy as p
from tests.test_reference_policy import fixture


class ReferenceWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.task = w.create_task('synthetic two gear', root=self.root)
        # Exercise the preserved reference-policy-v1 contract. New reference-
        # model-policy ledgers are covered by test_producer_continuation.
        data = w.load(self.task)
        data.pop('reference_model_policy_version')
        data.pop('product_policy_version')
        data.pop('growth_policy_version')
        w.write(self.task / 'task.json', data)
        self.blueprint,self.research,self.asset,self.qa = fixture()
        self.qa['reviewer_thread_id']='independent-fixture-qa'
        # These independent contracts have their own suites. Keep real handoff,
        # reference-policy validation, dependency hashes and production gates.
        self.stack=ExitStack(); self.addCleanup(self.stack.close)
        for name in ('validate_viral_analysis','validate_creative_blueprint'):
            self.stack.enter_context(patch('mechanical_video_next.viral.'+name))
        self.stack.enter_context(patch('mechanical_video_next.growth.validate_contract'))
        self.viral={'task_id':w.load(self.task)['id'],'topic':'synthetic two gear','selected_ids':['manual']}
        self.blueprint['reference_principles']=[{'reference_id':'manual'}]
        self.blueprint['content_policy_version']=1
        self.blueprint['reference_policy_version']=1
        self.qa['plan_sha256']=p.plan_digest(self.blueprint,self.research,self.asset)

    def prepare(self):
        w.put_handoff(self.task,'MechanicalResearch','research',self.research)
        w.put_handoff(self.task,'ViralResearch','viral-analysis',self.viral)
        w.put_handoff(self.task,'Asset','asset-plan',self.asset)
        w.put_handoff(self.task,'ViralResearch','creative-blueprint',self.blueprint,
                      ['viral-analysis','research','asset-plan'])

    def test_new_default_and_historical_ledger_preserved(self):
        current = w.create_task('current product defaults', root=self.root)
        self.assertEqual(w.load(current)['product_policy_version'], 1)
        self.assertEqual(w.load(current)['growth_policy_version'], 2)
        data=w.load(self.task)
        self.assertNotIn('product_policy_version', data)
        self.assertNotIn('growth_policy_version', data)
        self.assertEqual(data['asset_strategy'],'reference-first')
        self.assertEqual(data['reference_policy_version'],1)
        historic=w.create_task('historic fixture',protocol_version=1,root=self.root)
        before=(historic/'task.json').read_bytes()
        self.assertNotIn('reference_policy_version',w.load(historic))
        w.require_reference_content(historic)
        self.prepare()
        self.assertEqual((historic/'task.json').read_bytes(),before)

    def test_research_handoff_rejects_appearance_only(self):
        self.research['references'][0]['viewed_scope']['status']='COVER_ONLY'
        with self.assertRaisesRegex(ValueError,'Title, cover'):
            w.put_handoff(self.task,'MechanicalResearch','research',self.research)
        self.assertNotIn('research',w.load(self.task)['handoffs'])

    def test_new_blueprint_cannot_omit_policy_version(self):
        self.prepare()
        bad=copy.deepcopy(self.blueprint); bad.pop('reference_policy_version')
        with self.assertRaisesRegex(ValueError,'reference_policy_version'):
            w.put_handoff(self.task,'ViralResearch','creative-blueprint',bad,
                          ['viral-analysis','research','asset-plan'])

    def test_unreviewed_route_plan_never_executes_commands(self):
        from mechanical_video_next.multiroute import run_plan
        plan=self.root/'unreviewed.json'; plan.write_text('{"steps":[]}')
        with patch.object(w,'require_animatic'), patch.object(w,'artifact',return_value={}), \
                patch('mechanical_video_next.multiroute.command') as command:
            with self.assertRaisesRegex(ValueError,'reviewed commands'):
                run_plan(self.root,plan,extra_evidence=[self.task/'task.json'])
            command.assert_not_called()

    def test_public_multiroute_cli_cannot_omit_task_review(self):
        import sys
        from mechanical_video_next import multiroute
        plan=self.root/'plan.json'; plan.write_text('{"steps":[]}')
        with patch.object(sys,'argv',['multiroute','run',str(self.root),'--plan',str(plan)]), \
                patch.object(multiroute,'command') as command:
            with self.assertRaisesRegex(ValueError,'Task context required'): multiroute.main()
            command.assert_not_called()
        plan.write_text(json.dumps({'task':str(self.task),'steps':[]}))
        with patch.object(w,'require_animatic'), patch.object(w,'artifact',return_value={}), \
                patch.object(multiroute,'command') as command:
            with self.assertRaisesRegex(ValueError,'reviewed commands'): multiroute.run_plan(self.root,plan)
            command.assert_not_called()

    def test_reference_layered_config_binds_approved_source(self):
        from PIL import Image
        for route in ('2d','2.5d'):
            b,r,a,q=fixture('existing-media')
            b['content_policy_version']=b['reference_policy_version']=1
            image=self.root/'layer.webp'; Image.new('RGB',(2,2)).save(image)
            source={'path':str(image),'sha256':w.filehash(image)}
            a['candidates'][0]['source_files']=[source]; a['render_route']=route
            compiled={'render_route':route,'evidence_map':b['evidence_map'],
                      'content_timing':b['content_timing'],
                      'blueprint_program_sha256':w.digest(b),
                      'shots':{'s1':{'template':'layered','render_route':route,'layers':[source]}}}
            config=self.root/'compiled.json'; config.write_text(json.dumps(compiled))
            b['production_config']={'path':str(config),'sha256':w.filehash(config)}
            data=w.load(self.task); data.update(config=str(config),asset_strategy='existing-media',render_route=route)
            with patch.object(w,'load',return_value=data), \
                    patch.object(w,'artifact',side_effect=lambda task,name: {'creative-blueprint':b,'asset-plan':a,'research':r}[name]), \
                    patch.object(w,'require_reference_content'):
                w.check_production_config(self.task)
                compiled['shots']['s1']['layers'][0]=dict(source,path=str(self.root/'unapproved.webp'))
                config.write_text(json.dumps(compiled)); b['production_config']['sha256']=w.filehash(config)
                with self.assertRaisesRegex(ValueError,'not in approved'):
                    w.check_production_config(self.task)

    def test_asset_handoff_enforces_priority_and_registers_strategy(self):
        self.prepare()
        self.assertEqual(w.load(self.task)['asset_strategy'],'verified-existing')
        bad=copy.deepcopy(self.asset)
        bad['candidates'][0]['qualified']=True
        with self.assertRaisesRegex(ValueError,'prefer qualified'):
            w.put_handoff(self.task,'Asset','asset-plan',bad)

    def test_content_qa_requires_exact_dependencies_and_no_unknowns(self):
        self.prepare()
        with self.assertRaisesRegex(ValueError,'Required dependencies'):
            w.put_handoff(self.task,'QA','content-qa',self.qa,['research','asset-plan'])
        bad=copy.deepcopy(self.qa)
        bad['content_checks']['reliable_sources']['status']='UNKNOWN'
        with self.assertRaisesRegex(ValueError,'FAIL/UNKNOWN'):
            w.put_handoff(self.task,'QA','content-qa',bad,['creative-blueprint','research','asset-plan'])
        w.put_handoff(self.task,'QA','content-qa',self.qa,['creative-blueprint','research','asset-plan'])
        self.assertEqual(w.require_reference_content(self.task)['knowledge_points'],1)

    def test_new_reference_revision_stales_approved_content(self):
        self.prepare()
        w.put_handoff(self.task,'QA','content-qa',self.qa,['creative-blueprint','research','asset-plan'])
        revised=copy.deepcopy(self.research)
        revised['references'][0]['unknowns']=['new bounded uncertainty']
        w.put_handoff(self.task,'MechanicalResearch','research',revised)
        with self.assertRaisesRegex(ValueError,'Stale dependency: research'):
            w.require_reference_content(self.task)

    def test_production_config_gate_blocks_missing_content_qa(self):
        self.prepare()
        with self.assertRaisesRegex(ValueError,'Missing handoff: content-qa'):
            w.check_production_config(self.task)

    def test_changed_existing_source_rejected_before_model_admission(self):
        b,r,a,q=fixture()
        path=self.root/'source.step'; path.write_text('synthetic bytes, no geometric claim')
        a['candidates'][1]['source_files']=[{'path':str(path),'sha256':w.filehash(path)}]
        a['model']=copy.deepcopy(a['candidates'][1]['source_files'][0])
        p.validate_asset(r,a)
        path.write_text('changed bytes')
        with self.assertRaisesRegex(ValueError,'source missing or changed'):
            p.validate_asset(r,a)

    def test_timeline_duration_cannot_be_disconnected_from_evidence(self):
        self.blueprint['shots'][0]['time_range']=[0,119]
        with self.assertRaisesRegex(ValueError,'timeline must match duration'):
            p.validate_plan(self.blueprint,self.research,self.asset)
