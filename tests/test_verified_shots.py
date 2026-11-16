"""Scoped prerequisites use actual file bindings; no fabricated QA PASS."""
import json
import tempfile
import unittest
from pathlib import Path
from mechanical_video_next import workflow as w


class VerifiedShotsTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.task=w.create_task('fixture',root=Path(self.tmp.name),protocol_version=1)
        def save(name,value):
            p=self.task/name;p.write_text(json.dumps(value));return dict(path=str(p),sha256=w.filehash(p))
        self.save=save
        source=save('manual.json',{'manufacturer':'specific fixture','operation':'turn handle'})
        model=save('assembly.json',dict(required_parts=['handle'],source_files=[]))
        inventory=save('inventory.json',[dict(name='handle',valid=True,solids=1,volume_mm3=5)])
        self.shot=dict(template='motion',seconds=1,visible_parts=['handle'],tracks=[])
        self.config=dict(production_scope='verified-shots',assembly_config=model['path'],
            local_preview_shots=['exterior'],shots=dict(exterior=self.shot))
        self.row=dict(shot_id='exterior',mechanism_id='fixture-A',status='RENDER_READY',
            verified_parts=['handle'],inventory=inventory,
            model_bindings=[dict(model,license='CC0-1.0')],
            claims=[dict(status='VERIFIED',statement='exterior operation',sources=[dict(source,
                type='manual',position='operation',evidence='turn handle')])])
        self.data=w.load(self.task)
        self.data.update(mechanism_id='fixture-A',unknowns=[dict(kind='REFERENCE_VIEW_UNKNOWN'),
            dict(kind='PERCEPTUAL_QA_UNKNOWN')],shot_production=dict(exterior=self.row,
            gears=dict(status='RESEARCH_REQUIRED',unknown_type='MECHANISM_UNKNOWN')))
        self.bind()

    def bind(self):
        self.row.update(config=self.save('config.json',self.config),render_shot_sha256=w.digest(self.shot))
        w.write(self.task/'task.json',self.data)

    def test_unwatched_video_and_hidden_unknown_do_not_block_exterior(self):
        self.assertTrue(w.require_source_supported_render(self.task,self.row['config']['path']))
        report=w.continuation(self.task)
        self.assertEqual(report['next_action']['shot_id'],'exterior')
        self.assertEqual(report['production_status'],'PRODUCTION_IN_PROGRESS')
        self.assertFalse(report['delivered'])
        self.assertEqual(report['lifecycle'],'WORKING')

    def test_unverified_claim_and_unobserved_video_cannot_support_motion(self):
        self.row['claims'][0]['status']='UNKNOWN';self.bind()
        with self.assertRaisesRegex(ValueError,'MECHANISM_UNKNOWN'):
            w.require_source_supported_render(self.task,self.row['config']['path'])
        self.row['claims'][0]['status']='VERIFIED'
        self.row['claims'][0]['sources'][0]['type']='video';self.bind()
        with self.assertRaisesRegex(ValueError,'REFERENCE_VIEW_UNKNOWN'):
            w.require_source_supported_render(self.task,self.row['config']['path'])

    def test_unknown_parts_and_stale_model_never_render(self):
        self.shot['tracks']=[dict(object='unverified_gear',poses=[])];self.bind()
        with self.assertRaisesRegex(ValueError,'outside verified scope'):
            w.require_source_supported_render(self.task,self.row['config']['path'])
        self.shot['tracks']=[];self.bind()
        Path(self.row['model_bindings'][0]['path']).write_text('{}')
        with self.assertRaisesRegex(ValueError,'model missing, stale'):
            w.require_source_supported_render(self.task,self.row['config']['path'])

    def test_unknown_video_lead_does_not_invalidate_manual(self):
        lead=dict(self.row['claims'][0]['sources'][0],type='video',observation_status='UNKNOWN')
        self.row['claims'][0]['sources'].append(lead);self.bind()
        self.assertTrue(w.require_source_supported_render(self.task,self.row['config']['path']))

    def test_partial_cannot_authorize_full_film_or_2d(self):
        with self.assertRaisesRegex(ValueError,'cannot authorize a full film'):
            w.run_stage(self.task,'final',self.row['config']['path'])
        for route in ['2d','2.5d','all']:
            self.config['render_route']=route;self.bind()
            with self.assertRaisesRegex(ValueError,'3D-only'):
                w.require_source_supported_render(self.task,self.row['config']['path'])

    def test_full_scoped_film_requires_actual_preview_not_sensory_pass(self):
        self.config.update(production_scope='source-supported-film',shot_evidence_version=1,
            storyboard=[dict(id='exterior',shot='exterior',seconds=120,narration=['Verified input'])])
        self.shot['seconds']=120;self.bind()
        with self.assertRaises((ValueError,KeyError)):
            w.require_source_supported_render(self.task,self.row['config']['path'])
        self.row['claims'][0]['status']='UNKNOWN';self.bind()
        with self.assertRaisesRegex(ValueError,'MECHANISM_UNKNOWN'):
            w.require_source_supported_render(self.task,self.row['config']['path'])

    def test_completed_child_and_no_command_are_not_delivery(self):
        self.data['agent_runs']=[dict(status='COMPLETED',role='CAD',thread_id='real-test-fixture')]
        self.row['status']='RESEARCH_REQUIRED';self.bind()
        report=w.continue_production(self.task)
        self.assertTrue(report['execution']['returned_to_native_producer'])
        self.assertFalse(report['execution']['background_execution'])
        self.assertEqual(report['production_status'],'RESEARCH_PARTIAL')
        self.assertIn('alternative',report['next_action']['action'])
