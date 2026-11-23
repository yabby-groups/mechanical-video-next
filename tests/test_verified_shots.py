"""Scoped prerequisites use actual file bindings; no fabricated QA PASS."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from mechanical_video_next import workflow as w
from scripts import clean


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
        self.config=dict(id='scoped-stage-fixture', production_scope='verified-shots',assembly_config=model['path'],
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

    def test_stage_authorization_binds_actual_claim_source_and_model(self):
        config = Path(self.row['config']['path'])
        _, authorized = w.stage_authorization(self.task, 'local', config)
        for ref in [*self.row['claims'][0]['sources'], *self.row['model_bindings'], self.row['inventory']]:
            self.assertEqual(authorized['files'].get(str(Path(ref['path']).resolve())), ref['sha256'])
        source = Path(self.row['claims'][0]['sources'][0]['path'])
        original = source.read_bytes()
        for change in (lambda: source.write_bytes(b'edited source'), source.unlink):
            with self.subTest(change=change):
                change()
                with self.assertRaisesRegex(ValueError, 'Authorized stage dependency.*manual.json'):
                    w.verify_stage_authorization(authorized, self.task, 'local', config, config.read_bytes(),
                                                 w.load(self.task))
                source.write_bytes(original)

    def test_source_symlink_retargeting_invalidates_queued_authorization(self):
        config = Path(self.row['config']['path'])
        source = self.row['claims'][0]['sources'][0]
        link = self.task / 'manual-link.json'
        link.symlink_to(source['path'])
        source['path'] = str(link)
        self.bind()
        _, authorized = w.stage_authorization(self.task, 'local', config)
        other = self.save('other.json', {'operation': 'different'})
        link.unlink()
        link.symlink_to(other['path'])
        with self.assertRaisesRegex(ValueError, 'Authorized stage dependency.*manual-link.json'):
            w.verify_stage_authorization(authorized, self.task, 'local', config,
                                         config.read_bytes(), w.load(self.task))

    def test_successful_child_receipt_is_rejected_after_claim_change(self):
        root = Path(self.tmp.name)
        config = Path(self.row['config']['path'])
        source = Path(self.row['claims'][0]['sources'][0]['path'])
        original = source.read_bytes()
        output = root / 'output' / self.config['id']
        output.mkdir()
        rendered = {}
        for kind, name in (('media', 'shot.mp4'), ('scene', 'source.blend'), ('checks', 'checks.json')):
            path = output / name
            path.write_bytes(b'synthetic scope receipt input')
            rendered[kind] = dict(path=str(path), sha256=w.filehash(path))

        for changed in (True, False):
            def child(args, *, stdout, **kwargs):
                binding = json.loads(Path(args[args.index('--stage-authorization')+1]).read_text())
                w.verify_stage_authorization(binding, self.task, 'local', config,
                                             config.read_bytes(), w.load(self.task))
                stdout.write('synthetic subprocess completed\n')
                w.write(output/'verified-shots.json',
                        dict(config_sha256=w.filehash(config), shots={'exterior': rendered}))
                if changed:
                    source.write_bytes(b'changed during child execution')

            with self.subTest(changed=changed), patch.object(w, 'ROOT', root), \
                    patch.dict('sys.modules', {'clean': clean}), patch.object(clean, 'cleanup'), \
                    patch.object(w.subprocess, 'run', side_effect=child):
                if changed:
                    with self.assertRaisesRegex(ValueError, 'Authorized stage dependency.*manual.json'):
                        w.run_stage(self.task, 'local', config)
                    data = w.load(self.task)
                    self.assertEqual(data['stages'], [])
                    self.assertEqual(data['shot_production']['exterior']['status'], 'RENDER_READY')
                    self.assertTrue((output/'verified-shots.json').is_file())
                    self.assertIn('synthetic subprocess completed', next(self.task.glob('stage-local-*.log')).read_text())
                    events = [json.loads(line) for line in (self.task/'events.jsonl').read_text().splitlines()]
                    self.assertTrue(any(event['event'] == 'stage_output_rejected' and 'manual.json' in event['reason']
                                        for event in events))
                    source.write_bytes(original)
                else:
                    with patch('mechanical_video_next.multiroute.probe', return_value={'streams': [{'codec_type': 'video'}]}):
                        w.run_stage(self.task, 'local', config)
                    data = w.load(self.task)
                    self.assertTrue(data['stages'][-1]['command_success'])
                    self.assertEqual(data['shot_production']['exterior']['status'], 'QA_PENDING')

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

    def test_pending_full_revision_preserves_independent_preview_progress(self):
        # A newly edited full plan has not yet received its matching model
        # preview. It cannot render, but reconciliation must keep the valid
        # independently bound shot executable instead of raising after a stage.
        full = dict(self.config, production_scope='source-supported-film',
                    shot_evidence_version=1)
        full_binding = self.save('pending-full.json', full)
        self.data['config'] = full_binding['path']
        w.write(self.task/'task.json', self.data)
        with self.assertRaises(ValueError):
            w.require_source_supported_render(self.task, full_binding['path'])
        report = w.continuation(self.task)
        self.assertEqual(report['next_action']['shot_id'], 'exterior')
        self.assertEqual(report['next_action']['kind'], 'EXECUTABLE_COMMAND')
        self.assertFalse(report['delivered'])
