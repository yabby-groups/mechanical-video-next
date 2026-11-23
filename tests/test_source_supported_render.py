"""Technical production evidence is distinct from final sensory acceptance."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from contextlib import ExitStack
from mechanical_video_next import workflow as w


class SourceSupportedRenderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.task = w.create_task('fixture', root=Path(self.tmp.name), protocol_version=1)
        def save(name, obj):
            path = self.task / name
            path.write_text(json.dumps(obj))
            return dict(path=str(path), sha256=w.filehash(path))
        self.save = save
        self.assembly = save('assembly.json', dict(id='new verified fixture'))
        self.cfg = save('film.json', dict(production_scope='source-supported-film', assembly_config=self.assembly['path']))
        self.preview_cfg = save('preview.json', dict(assembly_config=self.assembly['path']))
        self.preview = save('preview.mp4', {})
        self.inventory = save('inventory.json', [dict(valid=True, solids=1, volume_mm3=4)])
        self.research = dict(mechanism_id='fixture-A')
        self.asset = dict(mechanism_id='fixture-A', selected_candidate_id='new', candidates=[dict(id='new', validation_evidence=self.inventory)])
        data = w.load(self.task)
        data['config'] = self.cfg['path']
        data['stages'] = [dict(phase='local', command_success=True, config_sha256=self.preview_cfg['sha256'])]
        data['reference_remake'] = dict(mechanism_basis=dict(status='PASS', mechanism_id='fixture-A', source_bindings=[self.assembly]),
            production_binding=dict(config=self.cfg, preview=self.preview, preview_config=self.preview_cfg))
        w.write(self.task/'task.json', data)
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(w, 'require_current_scheme'))
        self.stack.enter_context(patch.object(w, 'artifact', return_value=self.research))
        self.stack.enter_context(patch.object(w, 'check_asset', return_value=self.asset))
        self.stack.enter_context(patch('mechanical_video_next.reference_policy.validate_research'))
        self.stack.enter_context(patch('mechanical_video_next.comprehension.validate_product_research'))
        self.stack.enter_context(patch('mechanical_video_next.three_d.validate_config'))
        self.stack.enter_context(patch.object(w.subprocess, 'check_output', return_value=json.dumps(dict(
            format=dict(duration='15'), streams=[dict(codec_type='video')])).encode()))

    def test_verified_technical_basis_does_not_require_sensory_or_growth_qa(self):
        self.assertTrue(w.require_source_supported_render(self.task))
        w.require_animatic(self.task)
        w.require_reference_content(self.task)
        self.assertNotEqual(w.load(self.task)['state'], 'COMPLETED')
        with patch.object(w, 'artifact', return_value=dict(checks={'listening':'UNKNOWN'})):
            with self.assertRaises(ValueError):
                w.check_qa(self.task, 'final-qa')

    def test_actual_media_handoffs_use_current_technical_dependencies(self):
        data = w.load(self.task)
        dependencies = {'research', 'asset-plan', 'cad-model', 'mechanical-diagnostics', 'audio-preparation'}
        data['handoffs'] = {name: dict(sha256=name) for name in dependencies}
        w.write(self.task/'task.json', data)
        payload = dict(config=self.cfg, media=[self.preview], keyframes_verified=True)
        with patch.object(w, 'protocol_version', return_value=2):
            envelope = w.put_handoff(self.task, 'Animation', 'animation-manifest', payload,
                ['research', 'asset-plan', 'cad-model', 'mechanical-diagnostics'])
            self.assertNotIn('animatic-qa', envelope['dependencies'])
            envelope = w.put_handoff(self.task, 'Editor', 'timeline', payload,
                ['research', 'animation-manifest', 'audio-preparation'])
            self.assertEqual(set(envelope['dependencies']), {'research', 'animation-manifest', 'audio-preparation'})
            with self.assertRaisesRegex(ValueError, 'exact current film config'):
                w.put_handoff(self.task, 'Editor', 'timeline', dict(payload, config={'sha256':'stale'}),
                    ['research', 'animation-manifest', 'audio-preparation'])

    def test_unknown_mechanics_or_invalid_solids_cannot_render(self):
        self.asset['candidates'][0]['validation_evidence'] = self.save('invalid.json', [dict(valid=False, solids=1, volume_mm3=4)])
        with self.assertRaisesRegex(ValueError, 'CAD solids'):
            w.require_source_supported_render(self.task)
        self.asset['candidates'][0]['validation_evidence'] = self.inventory
        data = w.load(self.task)
        data['reference_remake']['mechanism_basis']['status'] = 'UNKNOWN'
        w.write(self.task/'task.json', data)
        with self.assertRaisesRegex(ValueError, 'continue research'):
            w.require_source_supported_render(self.task)

    def test_stale_config_or_preview_assembly_substitution_is_rejected(self):
        Path(self.cfg['path']).write_text(json.dumps(dict(production_scope='source-supported-film', assembly_config=self.assembly['path'], changed=True)))
        with self.assertRaisesRegex(ValueError, 'exact new config'):
            w.require_source_supported_render(self.task)
        data = w.load(self.task)
        data['reference_remake']['production_binding']['config']['sha256'] = w.filehash(self.cfg['path'])
        other = self.save('other-assembly.json', dict(id='different model'))
        new_preview = self.save('preview-config2.json', dict(assembly_config=other['path']))
        data['reference_remake']['production_binding']['preview_config'] = new_preview
        data['stages'] = [dict(phase='local', command_success=True, config_sha256=new_preview['sha256'])]
        w.write(self.task/'task.json', data)
        with self.assertRaisesRegex(ValueError, 'substitute'):
            w.require_source_supported_render(self.task)


class HistoricalScopedDeliveryTests(unittest.TestCase):
    def test_final_stage_rejoins_exact_qa_and_delivery_reconciliation(self):
        import subprocess
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            task = w.create_task('delivery fixture', root=root, protocol_version=1)
            config = root / 'film.json'
            w.write(config, dict(production_scope='source-supported-film', shot_evidence_version=1,
                                 storyboard=[{'id': 'core'}]))
            timeline = root / 'measured.json'
            w.write(timeline, dict(shots=[{'id': 'core'}], duration_seconds=1))
            final = root / 'final.mp4'
            subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'color=s=1920x1080:r=30:d=1',
                            '-f', 'lavfi', '-i', 'sine=d=1', '-c:v', 'libx264', '-preset', 'ultrafast',
                            '-c:a', 'aac', str(final)], check=True)
            media = dict(path=str(final), sha256=w.filehash(final))
            w.write(task / '3d-provenance.json', {'build': {}})
            w.write(task / 'growth-report.json', {})
            (task / 'reference.txt').write_text('synthetic reference')
            from mechanical_video_next.covers import SIZES
            covers = []
            for name in SIZES:
                cover = task / name
                cover.write_bytes(b'cover delivery binding fixture')
                covers.append(dict(path=str(cover), sha256=w.filehash(cover)))
            data = w.load(task)
            data.update(config=str(config), state='FINAL_CHECKING', duration_policy={'minimum': 1, 'maximum': 1},
                        shot_production={'core': {'status': 'RESEARCH_REQUIRED'}},
                        shared_production={'timeline': dict(path=str(timeline), sha256=w.filehash(timeline))},
                        stages=[dict(phase='final', command_success=True, config_sha256=w.filehash(config), media=media)],
                        reference_model_report=dict(path=str(task / 'reference.txt'),
                                                    sha256=w.filehash(task / 'reference.txt')))
            w.write(task / 'task.json', data)

            def submit(role, name, payload, *deps):
                return w.put_handoff(task, role, name, payload, deps)

            qa = dict(media=[media], checks=dict.fromkeys(w.QA_CHECKS, 'PASS'),
                      independent_reviewer=True, reviewer_thread_id='fixture-reviewer',
                      route_checks={'3d': {'media': media, 'checks': dict.fromkeys(w.QA_CHECKS, 'PASS')}})
            with patch.object(w, 'require_source_supported_render', return_value=True), \
                    patch('mechanical_video_next.provenance.validate'), \
                    patch('mechanical_video_next.growth_report.validate', return_value={}), \
                    patch('mechanical_video_next.covers.validate', return_value={'artifacts': covers}):
                self.assertEqual(w.continuation(task)['production_status'], 'FINAL_QA_PENDING')
                submit('Research', 'research', dict(task_id=data['id'], topic=data['topic']))
                submit('Research', 'script', {'text': 'fixture'}, 'research')
                submit('Asset', 'asset-plan', {'qualified': False})
                submit('Animation', 'animation-manifest', {'media': [media]}, 'research', 'asset-plan')
                submit('QA', 'preview-qa', qa, 'animation-manifest')
                submit('Editor', 'timeline', {'media': [media]}, 'script', 'animation-manifest')
                submit('QA', 'final-qa', dict(qa, checks=dict(qa['checks'], mechanics='FAIL')), 'timeline')
                self.assertFalse(w.continuation(task)['delivered'])
                with self.assertRaisesRegex(ValueError, 'QA FAIL'):
                    w.advance(task, 'COMPLETED')
                submit('QA', 'final-qa', qa, 'timeline')
                w.advance(task, 'COMPLETED')
                self.assertEqual(w.continuation(task)['milestone'], 'QA_ACCEPTED')
                with self.assertRaisesRegex(ValueError, 'Every required delivery file'):
                    w.record_delivery(task, [], 'fixture delivery')
                files = w.delivery_files(task, w.load(task), w.continuation(task)['rendered_routes'])
                self.assertTrue(w.record_delivery(task, [item['path'] for item in files], 'fixture delivery')['delivered'])
                submit('Research', 'script', {'text': 'updated dependency'}, 'research')
                self.assertFalse(w.continuation(task)['delivered'])
                self.assertEqual(w.continuation(task)['production_status'], 'FINAL_QA_PENDING')
