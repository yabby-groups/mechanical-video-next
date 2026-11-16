"""Producer regressions: subtask/session success never means video delivery."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from mechanical_video_next import workflow as w


class ProducerContinuationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.task = w.create_task('fixture mechanism', root=Path(self.tmp.name), protocol_version=1)

    def test_agent_completed_and_two_diagnostics_keep_next_producer_action(self):
        data = w.load(self.task)
        data.pop('three_d_policy_version', None)
        data['agent_runs'] = [{'role': 'Research', 'thread_id': 'done', 'seconds': 1}]
        data['stages'] = [dict(phase='local', diagnostic=True, command_success=True)] * 2
        w.write(self.task / 'task.json', data)
        report = w.continuation(self.task)
        self.assertEqual(report['milestone'], 'SUBTASK_COMPLETED')
        self.assertFalse(report['delivered'])
        self.assertTrue(report['diagnostic_clips_only'])
        self.assertEqual(report['next_action']['handoff'], 'research')
        self.assertFalse(report['background_execution'])
        self.assertEqual(w.load(self.task)['state'], 'CREATED')

    def test_research_handoff_automatically_schedules_remaining_work(self):
        w.put_handoff(self.task, 'Research', 'research', {'facts': []})
        report = w.load(self.task)['continuation']
        self.assertEqual(report['milestone'], 'RESEARCH_READY')
        self.assertEqual(report['next_action']['handoff'], 'asset-plan')
        self.assertTrue(report['remaining_work'])

    def test_resume_outputs_exact_action_and_preserves_existing_work(self):
        sentinel = self.task / 'narration.wav'
        sentinel.write_bytes(b'existing paid narration')
        with patch.object(sys, 'argv', ['workflow', 'produce', '--resume', str(self.task)]), patch('builtins.print') as output, \
                patch.object(w, 'create_task') as create:
            w.main()
        create.assert_not_called()
        report = json.loads(output.call_args.args[0])
        self.assertEqual(report['next_action']['owner'], 'Research')
        self.assertEqual(sentinel.read_bytes(), b'existing paid narration')
        self.assertEqual(report['resume_command'][-1], str(self.task))

    def test_successful_codex_exit_without_delivery_is_not_success(self):
        with patch.object(w, 'create_task', return_value=self.task), patch.object(w.subprocess, 'run'):
            with patch.object(sys, 'argv', ['workflow', 'produce', '--topic', 'fixture mechanism', '--codex']):
                with self.assertRaisesRegex(SystemExit, 'ended without delivery'):
                    w.main()
        events = [json.loads(line) for line in (self.task / 'events.jsonl').read_text().splitlines()]
        self.assertEqual(events[-1]['event'], 'producer_session_ended')
        self.assertFalse(events[-1]['delivered'])
        self.assertNotEqual(w.load(self.task)['state'], 'COMPLETED')

    def test_unaccepted_render_cannot_be_marked_delivered(self):
        video = self.task / 'final.mp4'
        video.write_bytes(b'fixture mp4 binding')
        data = w.load(self.task)
        data.pop('three_d_policy_version', None)
        data['requested_routes'] = ['3d']
        data['route_runs'] = {'3d': {'outputs': {'path': str(video), 'sha256': w.filehash(video)}}}
        w.write(self.task / 'task.json', data)
        with patch.object(w, 'complete_media'):
            self.assertEqual(w.continuation(self.task)['milestone'], 'FINAL_RENDERED')
        with self.assertRaisesRegex(ValueError, 'independent QA'):
            w.record_delivery(self.task, [video], 'provided file')

    def test_approved_plan_is_executed_through_original_gates(self):
        plan = self.task / 'plan.json'
        plan.write_text(json.dumps({'topic': 'fixture mechanism', 'routes': {'3d': 'final.mp4'}}))
        data = w.load(self.task)
        data.pop('three_d_policy_version', None)
        data['requested_routes'] = ['3d']
        data['production_plan'] = {'path': str(plan), 'sha256': w.filehash(plan)}
        data['handoffs'] = {key: {} for key in ['feasibility', 'animatic-manifest', 'animatic-qa']}
        w.write(self.task / 'task.json', data)
        with patch.object(w, 'artifact', return_value={}):
            report = w.continuation(self.task)
            self.assertIn('route-run', report['next_action']['command'])
            with patch.object(sys, 'argv', ['workflow', 'continue', str(self.task), '--execute']), patch.object(w.subprocess, 'run') as run:
                w.main()
            run.assert_called_once_with(report['next_action']['command'], cwd=w.ROOT, check=True)
        plan.write_text('{}')
        with patch.object(w, 'artifact', return_value={}):
            self.assertIsNone(w.continuation(self.task)['next_action'].get('command'))

    def test_new_tasks_require_reference_model_policy_without_migrating_old(self):
        task = w.create_task('new mechanism', root=Path(self.tmp.name), task_id='new')
        self.assertEqual(w.load(task)['reference_model_policy_version'], 1)
        self.assertNotIn('reference_model_policy_version', w.load(self.task))
        with patch.object(w, 'artifact', side_effect=ValueError('Missing handoff: reference-model-qa')):
            with self.assertRaisesRegex(ValueError, 'reference-model-qa'):
                w.require_reference_content(task)

    def test_delivery_receipt_binds_all_routes_and_rejects_changed_files(self):
        video = self.task / 'final.mp4'
        video.write_bytes(b'exact accepted fixture')
        data = w.load(self.task)
        data.pop('three_d_policy_version', None)
        data['state'] = 'COMPLETED'
        data['requested_routes'] = ['3d']
        data['route_runs'] = {'3d': {'outputs': {'path': str(video), 'sha256': w.filehash(video)}}}
        w.write(self.task / 'task.json', data)
        with patch.object(w, 'check_qa'), patch.object(w, 'check_requested_routes'), patch.object(w, 'complete_media', side_effect=lambda data, media: w.check_media([media])):
            self.assertEqual(w.continuation(self.task)['milestone'], 'QA_ACCEPTED')
            result = w.record_delivery(self.task, [video], 'Actual file link provided')
            self.assertEqual(result['milestone'], 'DELIVERED')
            video.write_bytes(b'changed')
            self.assertFalse(w.continuation(self.task)['delivered'])

    def test_four_second_diagnostic_registered_as_final_is_rejected(self):
        video = self.task / 'diagnostic.mp4'
        video.write_bytes(b'diagnostic fixture')
        data = w.load(self.task)
        data.pop('three_d_policy_version', None)
        data['requested_routes'] = ['3d']
        data['route_runs'] = {'3d': {'outputs': {'path': str(video), 'sha256': w.filehash(video)}}}
        w.write(self.task / 'task.json', data)
        info = {'streams': [{'codec_type': 'video', 'duration': '4', 'width': 1920, 'height': 1080, 'avg_frame_rate': '30/1'}], 'format': {'duration': '4'}}
        with patch('mechanical_video_next.multiroute.probe', return_value=info):
            result = w.continuation(self.task)
        self.assertNotEqual(result['milestone'], 'FINAL_RENDERED')
        self.assertIn('duration outside', result['invalid_evidence']['route:3d'])

    def test_empty_route_scope_cannot_claim_final_render(self):
        data = w.load(self.task)
        data.pop('three_d_policy_version', None)
        data['requested_routes'] = []
        w.write(self.task / 'task.json', data)
        self.assertNotEqual(w.continuation(self.task)['milestone'], 'FINAL_RENDERED')

    def test_failed_stage_exposes_diagnosed_recovery_without_blind_execution(self):
        data = w.load(self.task)
        data.pop('three_d_policy_version', None)
        data['state'] = 'FAILED'
        w.write(self.task / 'task.json', data)
        report = w.continuation(self.task)
        self.assertIn('resume-stage', report['next_action']['recovery_command'])
        self.assertIsNone(report['next_action']['command'])

    def test_existing_task_scope_expansion_preserves_assets_and_history(self):
        data = w.load(self.task)
        data.pop('three_d_policy_version', None)
        data['requested_routes'] = ['3d']
        data['route_runs'] = {'3d': {'status': 'PENDING', 'outputs': {}}}
        w.write(self.task / 'task.json', data)
        w.event(self.task, 'existing_failure', evidence='retained')
        with patch.object(sys, 'argv', ['workflow', 'extend-routes', str(self.task), '--routes', 'all', '--reason', 'User explicitly requested all three existing-task routes']), patch('builtins.print'):
            with self.assertRaisesRegex(ValueError,'3D-only'):
                w.main()
        self.assertEqual(w.load(self.task)['requested_routes'], ['3d'])
        self.assertIn('existing_failure', (self.task / 'events.jsonl').read_text())
        self.assertNotIn('route_scope_extended', (self.task / 'events.jsonl').read_text())

    def test_three_route_receipt_requires_comparison_covers_and_both_reports(self):
        def binding(name):
            path = self.task / name
            path.write_bytes(name.encode())
            return {'path': str(path), 'sha256': w.filehash(path)}
        routes = {route: binding(route.replace('.', '_') + '.mp4') for route in ['2d', '2.5d', '3d']}
        comparison = binding('compare.mp4')
        covers = [binding('portrait_cover_3x4.png'), binding('landscape_cover_4x3.png')]
        growth = binding('growth-report.json')
        reference = binding('reference-model-report.json')
        data = w.load(self.task)
        data.pop('three_d_policy_version', None)
        data.update(state='COMPLETED', requested_routes=list(routes),
                    route_runs={route: {'outputs': media} for route, media in routes.items()},
                    growth_report=growth, reference_model_report=reference)
        w.write(self.task / 'task.json', data)
        required = [*routes.values(), comparison, *covers, growth, reference]
        with patch.object(w, 'complete_media', side_effect=lambda data, media: w.check_media([media])), patch.object(w, 'check_qa'), patch.object(w, 'check_requested_routes'), \
                patch('mechanical_video_next.growth_report.validate', return_value={'comparison': comparison}), \
                patch('mechanical_video_next.covers.validate', return_value={'artifacts': covers}):
            for omitted in [comparison, *covers, growth, reference]:
                with self.subTest(omitted=omitted['path']), self.assertRaisesRegex(ValueError, 'Every required delivery file'):
                    w.record_delivery(self.task, [item['path'] for item in required if item != omitted], 'Files provided')
            self.assertEqual(w.record_delivery(self.task, [item['path'] for item in required], 'All actual files provided')['milestone'], 'DELIVERED')
            Path(reference['path']).write_bytes(b'changed report')
            self.assertFalse(w.continuation(self.task)['delivered'])
