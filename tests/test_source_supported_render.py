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
        from fixture_fonts import test_font
        from mechanical_video_next import covers, growth_report
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            task = w.create_task('delivery fixture', root=root, protocol_version=1)

            def bind(path):
                return dict(path=str(path.resolve()), sha256=w.filehash(path))

            def save(name, value):
                path = root / name
                w.write(path, value)
                return bind(path)

            manual = save('manual.json', {'operation': 'turn handle'})
            assembly = save('assembly.json', dict(required_parts=['handle'], source_files=[]))
            inventory = save('inventory.json', [dict(name='handle', valid=True, solids=1, volume_mm3=5)])
            shot = dict(template='motion', seconds=1, visible_parts=['handle'], tracks=[])
            requested = save('request.json', {'instruction': 'fixture short film'})
            config = root / 'film.json'
            w.write(config, dict(production_scope='source-supported-film', shot_evidence_version=1,
                                 assembly_config=assembly['path'], shots={'core': shot},
                                 duration_policy_override=dict(kind='user-requested-concise-recut', evidence=[requested]),
                                 storyboard=[dict(id='core', shot='core', seconds=1, narration=['Fixture'])]))
            timeline = root / 'measured.json'
            w.write(timeline, dict(shots=[{'id': 'core'}], duration_seconds=1))
            final = root / 'output' / 'scoped-fixture-final.mp4'
            subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'testsrc2=s=1920x1080:r=30:d=1',
                            '-f', 'lavfi', '-i', 'sine=d=1', '-c:v', 'libx264', '-preset', 'ultrafast',
                            '-c:a', 'aac', str(final)], check=True)
            media = bind(final)
            preview_config = save('preview-config.json', dict(assembly_config=assembly['path']))
            preview = root / 'preview.mp4'
            subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i',
                            'color=s=160x90:r=30:d=10', '-c:v', 'libx264', str(preview)], check=True)
            w.write(task / '3d-provenance.json', {'build': {}})
            (task / 'reference.txt').write_text('synthetic reference')
            data = w.load(task)
            data.update(config=str(config), state='FINAL_CHECKING', duration_policy={'minimum': 1, 'maximum': 1},
                        mechanism_id='fixture', route_runs={},
                        shot_production={'core': dict(
                            shot_id='core', mechanism_id='fixture', status='RENDER_READY', verified_parts=['handle'],
                            inventory=inventory, model_bindings=[dict(assembly, license='CC0-1.0')],
                            config=bind(config), render_shot_sha256=w.digest(shot),
                            claims=[dict(status='VERIFIED', statement='turn handle',
                                         sources=[dict(manual, type='manual', position='operation', evidence='turn')])])},
                        technical_preview=dict(media=bind(preview), config=preview_config,
                                               assembly_sha256=assembly['sha256']),
                        shared_production={'timeline': bind(timeline)},
                        stages=[dict(phase='local', command_success=True, config_sha256=preview_config['sha256']),
                                dict(phase='final', command_success=True, config_sha256=w.filehash(config), media=media)],
                        reference_model_report=bind(task/'reference.txt'))
            w.write(task / 'task.json', data)
            w.write(task/'cover-plan.json', dict(
                topic=data['topic'], recommended_route='3d', recommendation_reason='Fixture',
                route_analysis={'3d': dict(suitability='UNKNOWN', reason='fixture')},
                title=['Fixture'], series='Mechanisms', copy_rationale='Fixture', frame_rationale='Fixture',
                font_path=test_font(), selected_candidate='core',
                candidates=[dict(id='core', route='3d', seconds=0, shot_id='core', mechanical_moment='Fixture',
                                 subject_box=[0, 0, 1, 1])]))
            self.assertTrue(w.require_source_supported_render(task))
            self.assertEqual(growth_report.paths_for(task), {'3d': final.resolve()})
            self.assertEqual(covers.prepare(task)[1], {'3d': media})

            def submit(role, name, payload, *deps):
                return w.put_handoff(task, role, name, payload, deps)

            qa = dict(media=[media], checks=dict.fromkeys(w.QA_CHECKS, 'PASS'),
                      independent_reviewer=True, reviewer_thread_id='fixture-reviewer',
                      route_checks={'3d': {'media': media, 'checks': dict.fromkeys(w.QA_CHECKS, 'PASS')}})
            with patch('mechanical_video_next.provenance.validate') as validate_proof:
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
                growth = growth_report.generate(task)
                self.assertEqual(growth['routes']['3d']['media']['sha256'], media['sha256'])
                cover_report = covers.validate(task)
                self.assertEqual(cover_report['source_media'], {'3d': media})
                cover_paths = [bind(task/'cover'/name) for name in covers.SIZES]
                w.write(task/'cover/cover-qa.json', dict(
                    independent_reviewer=True, reviewer_thread_id='fixture-cover-reviewer',
                    report_sha256=w.filehash(task/'cover/cover-report.json'),
                    cover_checks={key: dict(status='PASS', evidence='isolated QA fixture',
                                            visual_inspection=True, artifacts=cover_paths) for key in covers.CHECKS}))
                w.advance(task, 'COMPLETED')
                self.assertEqual(validate_proof.call_args.args[1], dict(media, chapter_ids=['core']))
                self.assertEqual(w.continuation(task)['milestone'], 'QA_ACCEPTED')
                with self.assertRaisesRegex(ValueError, 'Every required delivery file'):
                    w.record_delivery(task, [], 'fixture delivery')
                files = w.delivery_files(task, w.load(task), w.continuation(task)['rendered_routes'])
                self.assertTrue(w.record_delivery(task, [item['path'] for item in files], 'fixture delivery')['delivered'])
                old = w.load(task)
                old['route_runs'] = {'3d': {'outputs': dict(media, chapter_ids=['core'])}}
                w.write(task/'task.json', old)
                for path in (config, final, Path(manual['path'])):
                    with self.subTest(stale=path.name):
                        content = path.read_bytes()
                        path.write_bytes(content + b' ')
                        try:
                            with self.assertRaises((ValueError, OSError)):
                                growth_report.paths_for(task)
                            with self.assertRaises((ValueError, OSError)):
                                growth_report.validate(task)
                            self.assertFalse(w.continuation(task)['delivered'])
                        finally:
                            path.write_bytes(content)
                config_bytes = config.read_bytes()
                try:
                    w.write(config, {'production_scope': 'verified-shots'})
                    with self.assertRaisesRegex(ValueError, 'superseded the source-supported final'):
                        growth_report.paths_for(task)
                    self.assertFalse(w.continuation(task)['delivered'])
                finally:
                    config.write_bytes(config_bytes)
                old['route_runs'] = {}
                w.write(task/'task.json', old)
                submit('Research', 'script', {'text': 'updated dependency'}, 'research')
                self.assertFalse(w.continuation(task)['delivered'])
                self.assertEqual(w.continuation(task)['production_status'], 'FINAL_QA_PENDING')
