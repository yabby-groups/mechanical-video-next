"""Fault injection and real file-lock regressions for production execution."""
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

from mechanical_video_next import blender_runtime, workflow as w
from scripts import common

sys.path.insert(0, str(common.ROOT / 'scripts'))
import clean
import environment
import produce


class HandoffRecoveryTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.task = w.create_task('restart fixture', root=Path(temp.name), protocol_version=1)
        self.enterContext(patch.object(w, 'continuation'))

    def submit(self, value):
        return w.put_handoff(self.task, 'Research', 'research',
                             {'task_id': self.task.name, 'topic': 'restart fixture', 'value': value})

    def interrupt(self, submit):
        original = w.write

        def fail_ledger(path, value):
            if Path(path).name == 'task.json':
                raise OSError('injected ledger commit interruption')
            original(path, value)

        with patch.object(w, 'write', side_effect=fail_ledger):
            with self.assertRaisesRegex(OSError, 'interruption'):
                submit()

    def test_first_and_later_orphans_are_recovered_or_preserved(self):
        self.interrupt(lambda: self.submit('first'))
        first = self.task / 'handoffs/research.v1.json'
        first_bytes = first.read_bytes()
        self.assertNotIn('research', w.load(self.task)['handoffs'])
        self.assertEqual(self.submit('first')['version'], 1)
        self.assertEqual(first.read_bytes(), first_bytes)
        self.interrupt(lambda: self.submit('orphan'))
        second = self.task / 'handoffs/research.v2.json'
        second_bytes = second.read_bytes()
        self.assertEqual(self.submit('replacement')['version'], 3)
        self.assertEqual(second.read_bytes(), second_bytes)
        self.assertEqual(w.artifact(self.task, 'research')['value'], 'replacement')
        events = [json.loads(line) for line in (self.task / 'events.jsonl').read_text().splitlines()]
        self.assertTrue(any(row.get('version') == 1 and row.get('recovered') for row in events))

    def test_changed_dependency_does_not_register_old_orphan(self):
        self.submit('first')

        def submit_script():
            return w.put_handoff(self.task, 'Research', 'script', {'text': 'fixture'},
                                 ['research'])

        self.interrupt(submit_script)
        orphan = self.task / 'handoffs/script.v1.json'
        original = orphan.read_bytes()
        updated = self.submit('updated')
        asset = submit_script()
        self.assertEqual(asset['version'], 2)
        self.assertEqual(asset['dependencies'], {'research': updated['sha256']})
        self.assertEqual(orphan.read_bytes(), original)

    def test_parallel_submissions_keep_distinct_versions(self):
        with ThreadPoolExecutor(max_workers=2) as pool:
            versions = sorted(row['version'] for row in pool.map(self.submit, ['one', 'two']))
        self.assertEqual(versions, [1, 2])
        self.assertEqual(w.load(self.task)['handoffs']['research']['version'], 2)

    def test_corrupt_orphan_is_never_registered_or_overwritten(self):
        self.interrupt(lambda: self.submit('first'))
        path = self.task / 'handoffs/research.v1.json'
        record = json.loads(path.read_text())
        record['payload']['value'] = 'tampered'
        w.write(path, record)
        with self.assertRaisesRegex(ValueError, 'Invalid orphan handoff identity or hash'):
            self.submit('first')
        self.assertEqual(json.loads(path.read_text()), record)
        self.assertNotIn('research', w.load(self.task)['handoffs'])


class StageQueueTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.task = w.create_task('queue fixture', root=self.root, protocol_version=1)
        self.config = self.root / 'config.json'
        self.config.write_text('{}')
        self.evidence = self.root / 'preview.mp4'
        self.evidence.write_bytes(b'first media')
        self.enterContext(patch.object(w, 'ROOT', self.root))
        self.enterContext(patch.object(clean, 'ROOT', self.root))
        self.enterContext(patch('mechanical_video_next.three_d.validate_config'))
        self.enterContext(patch.object(w, 'require_source_supported_render', return_value=False))
        self.enterContext(patch.object(w, 'check_production_config'))
        self.enterContext(patch.object(w, 'continuation'))
        self.run = self.enterContext(patch.object(w.subprocess, 'run'))
        data = w.load(self.task)
        data.update(state='EDITING', config=str(self.config), preview_status='PASS')
        w.write(self.task / 'task.json', data)
        self.enterContext(patch.object(w, 'check_qa', side_effect=self.qa))

    def qa(self, task, name, **kwargs):
        if w.load(task)['preview_status'] != 'PASS':
            raise ValueError('failed QA after waiting')
        w.filehash(self.evidence)

    def queue(self, change=None):
        work = self.root / 'work'
        work.mkdir(exist_ok=True)
        deferred = threading.Event()
        real_event = w.event

        def event(task, kind, **fields):
            real_event(task, kind, **fields)
            if kind == 'cleanup_deferred':
                deferred.set()

        with patch.object(w, 'event', side_effect=event), ThreadPoolExecutor(max_workers=1) as pool:
            with w.lock(work / 'production.lock'), w.lock(work / 'blender-render.lock'):
                future = pool.submit(w.run_stage, self.task, 'final', self.config)
                self.assertTrue(deferred.wait(5))
                self.run.assert_not_called()
                if change:
                    change()
            return future.result(timeout=5)

    def test_real_locks_allow_unchanged_queued_stage(self):
        self.queue()
        self.run.assert_called_once()
        self.assertTrue(w.load(self.task)['stages'][-1]['command_success'])

    def test_real_queue_rejects_changed_config_evidence_or_qa(self):
        def fail_qa():
            data = w.load(self.task)
            data['preview_status'] = 'FAIL'
            w.write(self.task / 'task.json', data)

        for change, reason in (
            (lambda: self.config.write_text('{"edit":1}'), 'changed while waiting'),
            (lambda: self.evidence.write_bytes(b'updated'), 'changed while waiting'),
            (fail_qa, 'failed QA'),
        ):
            with self.subTest(reason=reason), self.assertRaisesRegex(ValueError, reason):
                self.queue(change)
            self.run.assert_not_called()

    def test_child_rejects_bound_file_changed_after_authorization(self):
        _, approved = w.stage_authorization(self.task, 'final', self.config)
        binding = self.root / 'inputs.json'
        w.write(binding, approved)
        argv = ['produce.py', str(self.config), '--phase', 'final', '--task', str(self.task),
                '--stage-authorization', str(binding), w.digest(approved)]
        self.config.write_text('{"after":1}')
        with patch.object(sys, 'argv', argv), patch.object(produce, 'execute_stage') as render:
            with self.assertRaisesRegex(ValueError, 'differs from the authorized'):
                produce.main()
            render.assert_not_called()


class BudgetAndEnvironmentTests(unittest.TestCase):
    def test_sticky_budget_failure_on_all_successful_return_paths(self):
        fixtures = common.ROOT / 'tests/fixtures/production/planetary-01.json'
        with tempfile.TemporaryDirectory() as tmp, patch.object(common, 'ROOT', Path(tmp)), \
                patch.object(produce, 'ROOT', Path(tmp)), patch('narration.load_env'), \
                patch('narration.effective_profile'), patch.object(produce, 'assembly_spec', return_value={
                    'id': 'planetary-teaching-v1', 'required_parts': json.loads(fixtures.read_text())['components'],
                    'motion': {'template': json.loads(fixtures.read_text())['motion_template']},
                }):
            config = Path(tmp) / 'fixture.json'
            cfg = json.loads(fixtures.read_text())
            cfg['id'] = 'budget-fixture'
            config.write_text(json.dumps(cfg))
            task = w.create_task('budget fixture', root=Path(tmp), protocol_version=1)
            data = w.load(task)
            data['config'] = str(config)
            w.write(task / 'task.json', data)

            def overrun_then_recover(*args):
                guard = common.active_budget.get()
                try:
                    guard.sample()
                except common.BudgetExceeded:
                    pass

            for phase in ('asset', 'checks', 'keys', 'local', 'preview', 'final'):
                with self.subTest(phase=phase), patch.object(sys, 'argv', [
                    'produce.py', str(config), '--phase', phase, '--task', str(task), '--legacy-workprint'
                ]), patch.object(common, 'sample_budget', side_effect=[
                    10, common.BudgetExceeded('injected overrun', work_bytes=101, work_limit_bytes=100), 10,
                ]), patch.object(produce, 'execute_stage', side_effect=overrun_then_recover):
                    with self.assertRaisesRegex(common.BudgetExceeded, 'injected overrun'):
                        produce.main()
                    report = json.loads((Path(tmp) / f'output/budget-fixture-{phase}-metrics.json').read_text())
                    self.assertEqual(report['status'], 'failed')
                    self.assertEqual(report['budget_error']['work_bytes'], 101)

            def overrun_then_fail(*args):
                overrun_then_recover()
                raise ValueError('original source failure')

            with patch.object(sys, 'argv', ['produce.py', str(config), '--phase', 'asset']), \
                    patch.object(common, 'sample_budget', side_effect=[
                        10, common.BudgetExceeded('injected overrun', work_bytes=101),
                    ]), patch.object(produce, 'execute_stage', side_effect=overrun_then_fail):
                with self.assertRaisesRegex(ValueError, 'original source failure'):
                    produce.main()
                report = json.loads((Path(tmp) / 'output/budget-fixture-asset-metrics.json').read_text())
                self.assertEqual(report['error'], 'original source failure')
                self.assertEqual(report['budget_error']['reason'], 'injected overrun')

    def test_cancels_real_child_group_and_releases_blender_and_production_locks(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(blender_runtime, 'ROOT', Path(tmp)), \
                patch.dict(os.environ, {'BLENDER': sys.executable}):
            root = Path(tmp)
            pid_file = root / 'started'
            code = f'import os,time; open({str(pid_file)!r},"w").write(str(os.getpid())); time.sleep(30)'

            def observe():
                if pid_file.exists():
                    raise common.BudgetExceeded('injected during render', work_bytes=101)
                return 10

            metrics = common.Metrics('reliability-fixture', defer_budget=True)
            with patch.object(common, 'sample_budget', side_effect=observe), \
                    self.assertRaisesRegex(common.BudgetExceeded, 'during render'), \
                    w.lock(root / 'work/production.lock'), common.budgeted_stage(metrics):
                blender_runtime.run_blender(['-c', code], directory=root / 'diagnostics', timeout=10)
            result = json.loads((root / 'diagnostics/result.json').read_text())
            self.assertEqual(result['status'], 'CANCELLED')
            self.assertTrue(result['process_reaped'])
            with self.assertRaises(ChildProcessError):
                os.waitpid(int(pid_file.read_text()), os.WNOHANG)
            with w.lock(root / 'work/production.lock'), blender_runtime.blender_slot():
                pass
            with self.assertRaises(common.BudgetExceeded):
                with patch.object(common, 'sample_budget', side_effect=observe), common.budgeted_stage(metrics):
                    common.run([sys.executable, '-c', 'raise SystemExit(7)'])

    def test_ffmpeg_stops_before_the_next_process_can_start(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            log = root / 'ffmpeg.log'
            never = root / 'never-started'
            def observe():
                if log.exists() and log.stat().st_size:
                    raise common.BudgetExceeded('encoder overrun', work_bytes=101)
                return 10

            metrics = common.Metrics('fixture', defer_budget=True)
            with patch.object(common, 'sample_budget', side_effect=observe), \
                    self.assertRaisesRegex(common.BudgetExceeded, 'encoder overrun'), common.budgeted_stage(metrics):
                with self.assertRaises(common.BudgetExceeded):
                    common.run(['ffmpeg', '-re', '-f', 'lavfi', '-i', 'testsrc2=s=160x90:r=30:d=30',
                                '-f', 'null', '-'], log)
                common.run([sys.executable, '-c', f'open({str(never)!r},"w").close()'])
            self.assertTrue(log.exists())
            self.assertFalse(never.exists())

    def test_environment_report_reads_mock_blender_stdout(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(environment, 'ROOT', Path(tmp)):
            log = Path(tmp) / 'version.log'
            log.write_text('Blender fixture 5.x\n')
            with patch.object(environment, 'version', return_value={}), patch.object(
                    environment, 'run_blender', return_value=dict(command=['blender', '--version'],
                    returncode=0, stdout=str(log), report='fixture-report.json')):
                environment.main()
            report = json.loads((Path(tmp) / 'output/environment.json').read_text())
            self.assertEqual(report['tools']['blender']['output'], log.read_text())


if __name__ == '__main__':
    unittest.main()
