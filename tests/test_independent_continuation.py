"""A failed route preserves independent work and never repeats an unchanged failure."""
import json
import subprocess
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from mechanical_video_next import multiroute as m, workflow as w


class IndependentContinuationTests(unittest.TestCase):
    def test_real_subprocess_failure_preserves_independent_work_and_resume_cache(self):
        """Run real child processes: no subprocess/command/finalize mocks."""
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            m.prepare(root, 'real-process-fixture')
            bad, dependent, good = [root / name for name in ('bad.dat', 'dependent.dat', 'good.dat')]
            failed_count, good_count = root / 'failed-count.txt', root / 'good-count.txt'
            def argv(code):
                return ['uv', 'run', 'python', '-c', code]
            def increment(path):
                return f'p=Path({str(path)!r}); p.write_text(str(int(p.read_text())+1) if p.exists() else "1"); '
            steps = [
                dict(id='actual-failure', command=argv('from pathlib import Path; import sys; ' +
                     increment(failed_count) + 'sys.exit(7)'), outputs=[str(bad)]),
                dict(id='actual-dependent', command=argv(f'from pathlib import Path; Path({str(dependent)!r}).write_text("must not execute")'),
                     inputs=[str(bad)], outputs=[str(dependent)]),
                dict(id='actual-independent', command=argv('from pathlib import Path; ' + increment(good_count) +
                     f'Path({str(good)!r}).write_text("real independent output")'), outputs=[str(good)])]
            plan = root / 'plan.json'
            plan.write_text(json.dumps(dict(steps=steps, routes={})))
            for _ in range(2):
                with self.assertRaisesRegex(ValueError, 'independent work retained'):
                    m.run_plan(root, plan, legacy_workprint=True)
            self.assertEqual(good.read_text(), 'real independent output')
            self.assertFalse(dependent.exists())
            self.assertEqual(failed_count.read_text(), '1')
            self.assertEqual(good_count.read_text(), '1')
            state = json.loads((root / 'state.json').read_text())
            self.assertEqual(state['last_run']['cache_hits'], 1)
            self.assertEqual(state['last_run']['executed_steps'], 0)
            self.assertIn('unchanged_failure_blocked', [row['event'] for row in state['history']])

    def test_lifecycle_distinguishes_work_repair_external_block_and_delivery(self):
        with tempfile.TemporaryDirectory() as folder:
            task = w.create_task('fixture', root=Path(folder), protocol_version=1)
            self.assertEqual(w.continuation(task)['lifecycle'], 'WORKING')
            data = w.load(task)
            data.pop('three_d_policy_version', None)
            data['state'] = 'FAILED'
            w.write(task / 'task.json', data)
            self.assertEqual(w.continuation(task)['lifecycle'], 'REPAIRING')
            data['production_blockers'] = [dict(status='OPEN', kind='resource', reason='Actual disk space below production minimum',
                                                evidence=['disk usage measured below required minimum'],
                                                alternatives=['no owned encoded frames available to clean'],
                                                alternatives_checked=True, remaining_executable_work=False)]
            w.write(task / 'task.json', data)
            self.assertEqual(w.continuation(task)['lifecycle'], 'BLOCKED')

    def test_draft_plan_cannot_start_commands(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            plan = root / 'plan.json'
            plan.write_text(json.dumps({'execution_ready': False}))
            with patch.object(m, 'command') as command:
                with self.assertRaisesRegex(ValueError, 'QA authorization'):
                    m.run_plan(root, plan, legacy_workprint=True)
                command.assert_not_called()

    def test_failed_route_skips_dependents_continues_others_and_reuses_them(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            m.prepare(root, 'fixture')
            bad, good, downstream = [root / name for name in ('bad.mp4', 'good.mp4', 'comparison.mp4')]
            # Even a stale existing output from the failed producer is unsafe.
            bad.write_bytes(b'stale')
            steps = [dict(id='bad', command=['render', 'bad'], outputs=[str(bad)]),
                     dict(id='dependent', command=['compose'], inputs=[str(bad)], outputs=[str(downstream)]),
                     dict(id='independent', command=['render', 'good'], outputs=[str(good)])]
            plan = root / 'plan.json'
            plan.write_text(json.dumps(dict(steps=steps, routes={})))
            calls = []

            def run(args, log):
                calls.append(args)
                if args == ['render', 'bad']:
                    raise ValueError('actual failure')
                good.write_bytes(b'validated independent media')

            with patch.object(m, 'command', side_effect=run), patch.object(m, 'finalize') as finalize:
                for _ in range(2):
                    with self.assertRaisesRegex(ValueError, 'independent work retained'):
                        m.run_plan(root, plan, legacy_workprint=True)
                self.assertEqual(calls, [['render', 'bad'], ['render', 'good']])
                finalize.assert_not_called()
                state = json.loads((root / 'state.json').read_text())
                self.assertEqual(state['last_run']['cache_hits'], 1)
                self.assertIn('unchanged_failure_blocked', [row['event'] for row in state['history']])
                steps[0]['retry_reason'] = 'Corrected external renderer configuration after diagnosis'
                plan.write_text(json.dumps(dict(steps=steps, routes={})))
                with self.assertRaises(ValueError):
                    m.run_plan(root, plan, legacy_workprint=True)
                self.assertEqual(calls.count(['render', 'bad']), 2)

    def test_new_content_failure_revokes_previously_recorded_delivery(self):
        with tempfile.TemporaryDirectory() as folder:
            task = w.create_task('fixture', root=Path(folder), protocol_version=1, routes='3d')
            media = task / 'final.mp4'
            media.write_bytes(b'accepted fixture')
            data = w.load(task)
            data.pop('three_d_policy_version', None)
            binding = dict(path=str(media), sha256=w.filehash(media))
            data.update(state='COMPLETED', route_runs={'3d': {'outputs': binding}},
                        delivery_receipt=dict(routes={'3d': binding}, provided_to_user=True, files=[binding]))
            w.write(task / 'task.json', data)
            with patch.object(w, 'complete_media'), patch.object(w, 'check_qa'), patch.object(w, 'check_requested_routes'):
                self.assertTrue(w.continuation(task)['delivered'])
                self.assertEqual(w.continuation(task)['lifecycle'], 'DELIVERED')
                data['content_repairs'] = [dict(status='OPEN', defect_key='actual-content-failure', suggested_fix='Repair visible mechanism')]
                w.write(task / 'task.json', data)
                result = w.continuation(task)
                self.assertFalse(result['delivered'])
                self.assertEqual(result['next_action']['defect_key'], 'actual-content-failure')

    def test_qa_fail_enters_repair_and_unknown_is_work_not_global_block(self):
        with tempfile.TemporaryDirectory() as folder:
            task = w.create_task('fixture', root=Path(folder), protocol_version=1)
            data = w.load(task)
            data.pop('three_d_policy_version', None)
            data['handoffs'] = {'preview-qa': {}}
            # An undiagnosed blocker label cannot freeze all useful work.
            data['production_blockers'] = [dict(status='OPEN', kind='qa', reason='UNKNOWN listening')]
            w.write(task / 'task.json', data)
            for status, lifecycle in [('FAIL', 'REPAIRING'), ('UNKNOWN', 'WORKING')]:
                with self.subTest(status=status), patch.object(w, 'artifact', return_value={'checks': {'listening': status}}):
                    result = w.continuation(task)
                self.assertEqual(result['lifecycle'], lifecycle)
                self.assertFalse(result['delivered'])
                if status == 'FAIL':
                    self.assertEqual(result['next_action']['qa_handoff'], 'preview-qa')

    def test_execute_continues_after_each_success_until_native_work(self):
        with tempfile.TemporaryDirectory() as folder:
            task = w.create_task('fixture', root=Path(folder), protocol_version=1)
            def report(command):
                return dict(delivered=False, milestone='MODEL_READY', rendered_routes={},
                            next_action=dict(command=command), lifecycle='WORKING')
            with patch.object(w, 'continuation', side_effect=[report(['first-stage']), report(['second-stage']), report(None)]), \
                    patch.object(w.subprocess, 'run') as execute:
                result = w.continue_production(task)
            self.assertEqual([call.args[0] for call in execute.call_args_list], [['first-stage'], ['second-stage']])
            self.assertEqual(result['execution']['commands_executed'], 2)
            self.assertTrue(result['execution']['returned_to_native_producer'])

    def test_unchanged_success_does_not_loop_forever(self):
        with tempfile.TemporaryDirectory() as folder:
            task = w.create_task('fixture', root=Path(folder), protocol_version=1)
            report = dict(delivered=False, milestone='MODEL_READY', rendered_routes={},
                          next_action=dict(command=['same-stage']), lifecycle='WORKING')
            original = w.continuation
            calls = iter([report, report])
            def reconcile(task):
                return next(calls, None) or original(task)
            with patch.object(w, 'continuation', side_effect=reconcile), patch.object(w.subprocess, 'run') as execute:
                result = w.continue_production(task)
            execute.assert_called_once()
            self.assertTrue(result['execution']['no_progress'])
            self.assertEqual(result['lifecycle'], 'REPAIRING')
            self.assertEqual(w.continuation(task)['lifecycle'], 'REPAIRING')

    def test_verified_candidate_previews_are_not_reported_as_only_diagnostics(self):
        with tempfile.TemporaryDirectory() as folder:
            task = w.create_task('fixture', root=Path(folder), protocol_version=1)
            data = w.load(task)
            data.pop('three_d_policy_version', None)
            data['requested_routes'] = ['3d']
            data['stages'] = [dict(phase='local', diagnostic=True)]
            candidate = dict(path=str(task / 'preview.mp4'), sha256='exact-preview')
            data['route_runs'] = {'3d': {'outputs': {'candidate': candidate}}}
            w.write(task / 'task.json', data)
            def check(data, media, final=True):
                if final:
                    raise ValueError('Not final')
            with patch.object(w, 'complete_media', side_effect=check):
                result = w.continuation(task)
            self.assertEqual(result['milestone'], 'PREVIEW_READY')
            self.assertFalse(result['diagnostic_clips_only'])
            self.assertEqual(result['preview_routes']['3d'], candidate)
            self.assertFalse(result['delivered'])

    def test_audio_and_verified_cad_cache_survive_resume(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            m.prepare(root, 'fixture')
            audio, cad, video = [root / name for name in ('neil.wav', 'assembly.glb', 'video.mp4')]
            plan = root / 'plan.json'
            steps = [dict(id='audio', command=['tts'], outputs=[str(audio)]),
                     dict(id='cad', command=['cad'], outputs=[str(cad)]),
                     dict(id='video', command=['render'], inputs=[str(audio), str(cad)], outputs=[str(video)])]
            plan.write_text(json.dumps(dict(steps=steps, routes={})))
            paths = {'tts': audio, 'cad': cad, 'render': video}
            def execute(args, log):
                paths[args[0]].write_bytes(args[0].encode())
            with patch.object(m, 'command', side_effect=execute) as command, patch.object(m, 'finalize'):
                m.run_plan(root, plan, legacy_workprint=True)
                m.run_plan(root, plan, legacy_workprint=True)
            self.assertEqual(command.call_count, 3)
            self.assertEqual(json.loads((root / 'state.json').read_text())['last_run']['cache_hits'], 3)

    def test_cad_completion_keeps_remaining_production_work(self):
        with tempfile.TemporaryDirectory() as folder:
            task = w.create_task('fixture', root=Path(folder), protocol_version=1)
            w.put_handoff(task, 'Research', 'research', {'facts': []})
            w.put_handoff(task, 'Asset', 'asset-plan', {'qualified': True})
            result = w.continuation(task)
            self.assertEqual(result['milestone'], 'MODEL_READY')
            self.assertEqual(result['lifecycle'], 'WORKING')
            self.assertEqual(result['next_action']['handoff'], 'script')
            self.assertFalse(result['delivered'])

    def test_unknown_qa_preserves_independent_approved_plan(self):
        with tempfile.TemporaryDirectory() as folder:
            task = w.create_task('fixture', root=Path(folder), protocol_version=1)
            plan = task / 'plan.json'
            plan.write_text('{}')
            data = w.load(task)
            data.pop('three_d_policy_version', None)
            data['production_plan'] = dict(path=str(plan), sha256=w.filehash(plan))
            data['handoffs'] = {name: {} for name in ('feasibility', 'animatic-manifest', 'animatic-qa')}
            w.write(task / 'task.json', data)
            with patch.object(w, 'artifact', return_value={'checks': {'listening': 'UNKNOWN'}}):
                result = w.continuation(task)
            self.assertIn('route-run', result['next_action']['command'])
            self.assertEqual(result['lifecycle'], 'WORKING')

    def test_execution_failure_is_durable_repair_not_unchanged_retry(self):
        with tempfile.TemporaryDirectory() as folder:
            task = w.create_task('fixture', root=Path(folder), protocol_version=1)
            report = dict(delivered=False, milestone='MODEL_READY', rendered_routes={},
                          next_action=dict(command=['actual-failed-command']), lifecycle='WORKING')
            with patch.object(w, 'continuation', return_value=report), \
                    patch.object(w.subprocess, 'run', side_effect=subprocess.CalledProcessError(1, ['actual-failed-command'])):
                with self.assertRaises(subprocess.CalledProcessError):
                    w.continue_production(task)
            result = w.continuation(task)
            self.assertEqual(result['lifecycle'], 'REPAIRING')
            self.assertIsNone(result['next_action']['command'])
            self.assertIn('actual-failed-command', result['next_action']['evidence']['command'])

    def test_resolved_major_qa_history_does_not_block_current_pass_report(self):
        with tempfile.TemporaryDirectory() as folder:
            task = w.create_task('fixture', root=Path(folder), protocol_version=1)
            media = task / 'reviewed.mp4'
            media.write_bytes(b'exact-media-binding-fixture')
            binding = dict(path=str(media), sha256=w.filehash(media))
            issue = dict(severity='MAJOR', status='OPEN')
            qa = dict(checks=dict.fromkeys(w.QA_CHECKS, 'PASS'), media=[binding],
                      independent_reviewer=True, reviewer_thread_id='independent-reviewer', issues=[issue])
            def artifact(task, name):
                return qa if name == 'preview-qa' else {'media': [binding]}
            with patch.object(w, 'artifact', side_effect=artifact):
                with self.assertRaisesRegex(ValueError, 'blocking QA defects'):
                    w.check_qa(task, 'preview-qa')
                issue['status'] = 'RESOLVED'
                self.assertEqual(w.check_qa(task, 'preview-qa'), qa)

    def test_complete_route_media_prioritizes_acceptance_over_old_animatic_work(self):
        with tempfile.TemporaryDirectory() as folder:
            task = w.create_task('fixture', root=Path(folder), protocol_version=1)
            data = w.load(task)
            data.pop('three_d_policy_version', None)
            data['state'] = 'RESEARCHING'
            data['requested_routes'] = ['2d', '2.5d', '3d']
            data['route_runs'] = {}
            for route in data['requested_routes']:
                path = task / (route + '.mp4')
                path.write_bytes(('exact complete media fixture ' + route).encode())
                data['route_runs'][route] = {'outputs': dict(path=str(path), sha256=w.filehash(path))}
            config, qa = task / 'old-animatic.json', task / 'old-animatic-qa.json'
            config.write_text('{}')
            qa.write_text('{}')
            data['low_cost_animatic_approval'] = {
                name: dict(path=str(path), sha256=w.filehash(path))
                for name, path in [('config', config), ('qa', qa)]}
            for low_cost_rendered in [False, True]:
                data['stages'] = [dict(animatic_diagnostic=True, command_success=True,
                                       config_sha256=w.filehash(config))] if low_cost_rendered else []
                w.write(task / 'task.json', data)
                with self.subTest(low_cost_rendered=low_cost_rendered), \
                        patch.object(w, 'complete_media', side_effect=lambda data, media, **kwargs: w.check_media([media])):
                    result = w.continuation(task)
                    self.assertEqual(result['milestone'], 'FINAL_RENDERED')
                    self.assertEqual(result['next_action']['owner'], 'QA/Producer')
                    self.assertIsNone(result['next_action']['command'])
                    self.assertIn('research', result['next_action']['missing_handoffs'])
                    self.assertTrue(result['remaining_work'])
                    self.assertFalse(result['delivered'])
                    with self.assertRaisesRegex(ValueError, 'independent QA'):
                        w.record_delivery(task, [], 'Not accepted')
            # Even a stale COMPLETED state cannot substitute for current QA.
            data['state'] = 'COMPLETED'
            w.write(task / 'task.json', data)
            with patch.object(w, 'complete_media'), \
                    patch.object(w, 'check_qa', side_effect=ValueError('Missing provenance and final QA')):
                result = w.continuation(task)
            self.assertFalse(result['delivered'])
            self.assertEqual(result['next_action']['owner'], 'QA/Producer')
            self.assertIn('Missing provenance', result['invalid_evidence']['delivery-qa'])
