import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from mechanical_video_next.multiroute import prepare, finalize, run_plan


class MultiRouteTests(unittest.TestCase):
    def test_resume_preserves_history_and_rejects_topic_collision(self):
        with tempfile.TemporaryDirectory() as tmp:
            prepare(tmp, '指甲刀')
            path = Path(tmp) / 'state.json'
            state = json.loads(path.read_text())
            state['history'].append({'event': 'research'})
            path.write_text(json.dumps(state))
            self.assertEqual(prepare(tmp, '指甲刀')['history'], [{'event': 'research'}])
            with self.assertRaises(ValueError):
                prepare(tmp, 'other')

    def test_missing_media_records_recoverable_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            prepare(tmp, '指甲刀')
            with patch('mechanical_video_next.multiroute.probe', side_effect=ValueError('missing')):
                with self.assertRaises(ValueError):
                    finalize(tmp, {'2d': 'missing'})
            state = json.loads((Path(tmp) / 'state.json').read_text())
            self.assertEqual(state['status'], 'FAILED')
            self.assertEqual(state['history'][-1]['error'], 'missing')

    def test_non_uv_python_command_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            prepare(tmp, '指甲刀')
            plan = Path(tmp) / 'plan.json'
            plan.write_text(json.dumps({'steps': [{'id': 'bad', 'command': ['python', 'x.py'], 'outputs': []}]}))
            with self.assertRaises(ValueError):
                run_plan(tmp, plan)

    def test_timeline_difference_is_not_silently_truncated(self):
        from mechanical_video_next.multiroute import validate_timeline
        media = {key: {'duration': duration, 'fps': 30, 'video_start': 0} for key, duration in [('2d', 12), ('2.5d', 12), ('3d', 11)]}
        with self.assertRaisesRegex(ValueError, 'Timeline mismatch'):
            validate_timeline(media)
        media['3d']['duration'] = 11.999
        validate_timeline(media)
        media['3d']['fps'] = 15
        with self.assertRaisesRegex(ValueError, '30fps'):
            validate_timeline(media)

    def test_new_workflow_defaults_all_routes_and_shared_contract(self):
        from mechanical_video_next import workflow
        with tempfile.TemporaryDirectory() as tmp:
            task = workflow.create_task('指甲刀', root=tmp)
            data = workflow.load(task)
            self.assertEqual(data['requested_routes'], ['2d', '2.5d', '3d'])
            self.assertIsNone(data['shared_production']['timeline']['sha256'])
            self.assertEqual(data['state'], 'CREATED')
            self.assertIn('Produce ALL requested routes', (task / 'producer-prompt.md').read_text())
            single = workflow.create_task('指甲刀', root=tmp, routes='2.5d')
            self.assertEqual(workflow.load(single)['requested_routes'], ['2.5d'])

    def test_metrics_sources_are_hash_bound(self):
        from mechanical_video_next.multiroute import supplemental_evidence, sha
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'shared').mkdir()
            source = root / 'shared/production-statistics.json'
            source.write_text('{"production_seconds": 3, "human_interventions": null}')
            evidence = supplemental_evidence(root / 'multiroute')
            self.assertEqual(evidence[0]['sha256'], sha(source))
            self.assertIsNone(evidence[0]['data']['human_interventions'])

    def test_workflow_resume_preserves_task_and_rejects_second_producer(self):
        import sys
        from mechanical_video_next import workflow
        with tempfile.TemporaryDirectory() as tmp:
            task = workflow.create_task('指甲刀', root=tmp)
            before = (task / 'task.json').read_bytes()
            with patch.object(sys, 'argv', ['workflow', 'produce', '--resume', str(task)]):
                workflow.main()
            self.assertEqual((task / 'task.json').read_bytes(), before)
            with patch.object(sys, 'argv', ['workflow', 'produce', '--resume', str(task), '--codex']):
                with self.assertRaisesRegex(ValueError, 'another Producer'):
                    workflow.main()

    def test_default_plan_contains_actual_routes_and_late_generated_inputs(self):
        root = Path(__file__).resolve().parents[1]
        plan = json.loads((root / 'config/nail-clipper-three-routes-plan.json').read_text())
        self.assertEqual(set(plan['routes']), {'2d', '2.5d', '3d'})
        steps = {step['id']: step for step in plan['steps']}
        self.assertIn('render-3d', steps['render-3d']['command'])
        self.assertIn('output/nail-clipper/3d/config/full.json', steps['render-3d']['inputs'])
        self.assertIn('output/nail-clipper/3d/config/full.json', steps['cad-prepare']['outputs'])
        self.assertNotIn('--env-file', steps['shared-audio']['command'])

    def test_multiroute_completion_requires_every_exact_route_qa(self):
        from mechanical_video_next import workflow
        with tempfile.TemporaryDirectory() as tmp:
            media = Path(tmp) / 'route.mp4'
            media.write_bytes(b'test evidence')
            digest = workflow.filehash(media)
            data = {'requested_routes': ['2d', '2.5d', '3d'], 'route_runs': {route: {'outputs': {'sha256': digest}} for route in ('2d', '2.5d', '3d')}}
            results = {route: {'media': {'path': str(media), 'sha256': digest}, 'checks': {check: 'PASS' for check in workflow.QA_CHECKS}} for route in data['requested_routes']}
            with patch.object(workflow, 'artifact', return_value={'route_checks': results}):
                workflow.check_requested_routes(tmp, data)
                results['3d']['checks']['listening'] = 'UNKNOWN'
                with self.assertRaisesRegex(ValueError, 'UNKNOWN'):
                    workflow.check_requested_routes(tmp, data)

    def test_plan_cad_does_not_require_its_own_generated_motion(self):
        root = Path(__file__).resolve().parents[1]
        plan = json.loads((root / 'config/nail-clipper-three-routes-plan.json').read_text())
        steps = {step['id']: step for step in plan['steps']}
        motion = 'assets/assemblies/nail-clipper-cad-v5/motion.json'
        self.assertNotIn(motion, steps['cad-prepare']['inputs'])
        self.assertIn(motion, steps['cad-prepare']['outputs'])
        self.assertIn('output/nail-clipper/shared/mechanical-research.json', steps['cad-prepare']['inputs'])
        for name in ('render-2d', 'render-2_5d'):
            self.assertIn(motion, steps[name]['inputs'])
            self.assertIn('assets/assemblies/nail-clipper-cad-v5/parameters.json', steps[name]['inputs'])
            self.assertIn('assets/assemblies/nail-clipper-cad-v5/assembly.json', steps[name]['inputs'])
        self.assertIn('output/nail-clipper/shared/qa*.json', plan['evidence_globs'])

    def test_missing_research_stops_before_paid_audio(self):
        with tempfile.TemporaryDirectory() as tmp:
            prepare(tmp, '指甲刀')
            plan = Path(tmp) / 'plan.json'
            plan.write_text(json.dumps({'prerequisite_inputs': [str(Path(tmp) / 'research.json')], 'steps': []}))
            with patch('mechanical_video_next.multiroute.command') as command:
                with self.assertRaisesRegex(ValueError, 'before any render or paid audio'):
                    run_plan(tmp, plan)
                command.assert_not_called()
            self.assertEqual(json.loads((Path(tmp) / 'state.json').read_text())['history'][-1]['event'], 'prerequisite_missing')

    def test_protocol2_duration_30_to_60_legacy_stays_45(self):
        from mechanical_video_next import workflow
        with tempfile.TemporaryDirectory() as tmp:
            for duration in (30, 45, 60):
                task = workflow.create_task('指甲刀', duration=duration, root=tmp)
                self.assertEqual(workflow.load(task)['duration'], duration)
            for duration in (29, 61):
                with self.assertRaisesRegex(ValueError, '30–60'):
                    workflow.create_task('指甲刀', duration=duration, root=tmp)
            with self.assertRaisesRegex(ValueError, '30–45'):
                workflow.create_task('历史模板', duration=60, root=tmp, protocol_version=1)

    def test_original_three_routes_keeps_legacy_single_recreation(self):
        from mechanical_video_next import workflow
        with tempfile.TemporaryDirectory() as tmp:
            task = workflow.create_task('指甲刀', root=tmp)
            self.assertEqual(workflow.load(task)['production_method'], 'original-shared-script-three-routes')
            prompt = (task / 'producer-prompt.md').read_text()
            self.assertIn('Write an original shared script and original shot order', prompt)
            self.assertNotIn("The selected video's shots, timing, actions and explanation are the production specification", prompt)
            with patch('mechanical_video_next.viral.validate_reference_recreation') as recreation:
                workflow.check_recreation(task, {})
                recreation.assert_not_called()
            legacy = workflow.create_task('单路历史约束', root=tmp, routes='3d')
            self.assertEqual(workflow.load(legacy)['production_method'], 'reference-recreation')
            self.assertIn("The selected video's shots, timing", (legacy / 'producer-prompt.md').read_text())

    def test_route_run_uses_registered_comparison_directory_without_advancing_state(self):
        import sys
        from mechanical_video_next import workflow
        with tempfile.TemporaryDirectory() as tmp:
            task = workflow.create_task('指甲刀', root=tmp)
            data = workflow.load(task)
            folder = Path(tmp) / 'delivery'
            data['shared_production']['comparison_directory'] = str(folder)
            workflow.write(task / 'task.json', data)
            plan = Path(tmp) / 'plan.json'
            plan.write_text(json.dumps({'topic': '指甲刀', 'routes': dict.fromkeys(data['requested_routes'], 'fixture.mp4')}))
            report = {'status': 'TECHNICAL_PASS_UNACCEPTED_COMPARISON', 'routes': {}}
            def fake_run(actual_folder, *args):
                self.assertEqual(actual_folder, folder)
                (folder / 'report.json').write_text(json.dumps(report))
                return report
            with patch('mechanical_video_next.multiroute.run_plan', side_effect=fake_run), patch.object(sys, 'argv', ['workflow', 'route-run', str(task), '--plan', str(plan)]):
                workflow.main()
            updated = workflow.load(task)
            self.assertEqual(updated['state'], 'CREATED')
            self.assertEqual(updated['multiroute_status'], report['status'])
            self.assertEqual(updated['route_comparison']['report'], str(folder / 'report.json'))
