import json
from pathlib import Path
import tempfile
import subprocess
import sys
import unittest
from unittest.mock import patch
from mechanical_video_next import workflow as w


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.task = w.create_task('行星减速器', root=Path(self.temp.name))

    def research(self):
        w.put_handoff(self.task, 'Research', 'research', {'facts': []})
        w.put_handoff(self.task, 'Research', 'script', {'shots': []}, ['research'])

    def test_ownership_and_dependencies(self):
        with self.assertRaises(ValueError):
            w.put_handoff(self.task, 'QA', 'research', {})
        with self.assertRaises(ValueError):
            w.put_handoff(self.task, 'Research', 'script', {})
        self.research()
        w.put_handoff(self.task, 'Research', 'research', {'facts': ['new']})
        with self.assertRaisesRegex(ValueError, 'Stale'):
            w.artifact(self.task, 'script')
        self.assertTrue((self.task / 'handoffs/research.v1.json').exists())

    def test_modified_handoff_rejected(self):
        self.research()
        p = self.task / 'handoffs/research.v1.json'
        payload = json.loads(p.read_text())
        payload['payload']['facts'] = ['tampered']
        p.write_text(json.dumps(payload))
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            w.artifact(self.task, 'research')

    def test_unqualified_model_cannot_advance(self):
        self.research()
        w.put_handoff(self.task, 'Asset', 'asset-plan', {'qualified': False})
        w.advance(self.task, 'RESEARCHING')
        with self.assertRaisesRegex(ValueError, 'not qualified'):
            w.advance(self.task, 'ASSET_READY')
        self.assertEqual(w.load(self.task)['state'], 'RESEARCHING')

    def test_qualified_claim_without_model_evidence_rejected(self):
        self.research()
        w.put_handoff(self.task, 'Asset', 'asset-plan', {'qualified': True})
        w.advance(self.task, 'RESEARCHING')
        with self.assertRaisesRegex(ValueError, 'Verified model'):
            w.advance(self.task, 'ASSET_READY')

    def test_no_jumping_stages(self):
        with self.assertRaisesRegex(ValueError, 'Illegal transition'):
            w.advance(self.task, 'COMPLETED')

    def test_final_cannot_render_before_preview_gate(self):
        with patch.object(w.subprocess, 'run') as run:
            with self.assertRaisesRegex(ValueError, 'prerequisites'):
                w.run_stage(self.task, 'final', Path('config/planetary-01.json'))
            with self.assertRaisesRegex(ValueError, 'prerequisites'):
                w.run_stage(self.task, 'final', Path('config/planetary-01.json'), workprint=True)
            run.assert_not_called()

    def test_workprint_flag_cannot_bypass_changed_qa_in_editing(self):
        data = w.load(self.task)
        data['state'] = 'EDITING'
        w.write(self.task / 'task.json', data)
        with patch.object(w, 'check_qa', side_effect=ValueError('UNKNOWN')) as qa:
            with patch.object(w.subprocess, 'run') as run:
                with self.assertRaisesRegex(ValueError, 'UNKNOWN'):
                    w.run_stage(self.task, 'final', Path('config/planetary-01.json'), workprint=True)
                qa.assert_called_once_with(self.task, 'preview-qa')
                run.assert_not_called()

    def test_completion_rechecks_preview_qa(self):
        data = w.load(self.task)
        data['state'] = 'FINAL_CHECKING'
        w.write(self.task / 'task.json', data)
        with patch.object(w, 'check_qa', side_effect=ValueError('stale preview')) as qa:
            with self.assertRaisesRegex(ValueError, 'stale preview'):
                w.advance(self.task, 'COMPLETED')
            qa.assert_called_once_with(self.task, 'preview-qa')
        self.assertEqual(w.load(self.task)['state'], 'FINAL_CHECKING')

    def test_native_launcher_failure_is_recorded_without_retry(self):
        # No real CLI or production lock is touched by this failure-path test.
        with patch.object(w, 'create_task', return_value=self.task):
            with patch.object(sys, 'argv', ['mechanical_video_next', 'produce',
                                           '--topic', '行星减速器', '--codex']):
                with patch.object(w.subprocess, 'run', side_effect=FileNotFoundError('codex absent')) as run:
                    with self.assertRaises(FileNotFoundError):
                        w.main()
                    self.assertEqual(run.call_count, 1)
                    args, kwargs = run.call_args
                    self.assertIn('--strict-config', args[0])
                    self.assertEqual(kwargs['stdin'], subprocess.DEVNULL)
        self.assertEqual(w.load(self.task)['state'], 'FAILED')
        events = [json.loads(line) for line in (self.task / 'events.jsonl').read_text().splitlines()]
        self.assertEqual(events[-1]['event'], 'codex_launch_failed')
        self.assertTrue((self.task / 'codex.jsonl').exists())

    def test_arbitrary_dependencies_cannot_create_cycle(self):
        self.research()
        with self.assertRaisesRegex(ValueError, 'DAG'):
            w.put_handoff(self.task, 'Research', 'research', {}, ['script'])

    def test_qa_unknown_and_changed_media_block(self):
        self.research()
        w.put_handoff(self.task, 'Asset', 'asset-plan', {'qualified': True})
        movie = Path(self.temp.name) / 'preview.mp4'
        movie.write_bytes(b'test fixture only; no media quality claim')
        evidence = [{'path': str(movie), 'sha256': w.filehash(movie)}]
        w.put_handoff(self.task, 'Animation', 'animation-manifest',
                      {'media': evidence, 'keyframes_verified': True}, ['research', 'asset-plan'])
        qa = {'media': evidence, 'independent_reviewer': True, 'reviewer_thread_id': 'qa-thread',
              'checks': dict.fromkeys(w.QA_CHECKS, 'PASS'), 'issues': []}
        qa['checks']['listening'] = 'UNKNOWN'
        w.put_handoff(self.task, 'QA', 'preview-qa', qa, ['animation-manifest'])
        with self.assertRaisesRegex(ValueError, 'UNKNOWN'):
            w.check_qa(self.task, 'preview-qa')
        qa['checks']['listening'] = 'PASS'
        w.put_handoff(self.task, 'QA', 'preview-qa', qa, ['animation-manifest'])
        w.check_qa(self.task, 'preview-qa')
        unrelated = Path(self.temp.name) / 'unrelated.mp4'
        unrelated.write_bytes(b'unrelated')
        qa['media'] = [{'path': str(unrelated), 'sha256': w.filehash(unrelated)}]
        w.put_handoff(self.task, 'QA', 'preview-qa', qa, ['animation-manifest'])
        with self.assertRaisesRegex(ValueError, 'exact production'):
            w.check_qa(self.task, 'preview-qa')
        qa['media'] = evidence
        w.put_handoff(self.task, 'QA', 'preview-qa', qa, ['animation-manifest'])
        movie.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'changed'):
            w.check_qa(self.task, 'preview-qa')

    def test_repair_caps_and_no_improvement_stop(self):
        w.repair_attempt(self.task, 'occlusion', 'camera-a', 10)
        self.assertEqual(w.load(self.task)['repairs']['occlusion']['strategies'], {})
        w.repair_attempt(self.task, 'occlusion', 'camera-a', 8)
        w.repair_attempt(self.task, 'occlusion', 'camera-a', 5)
        with self.assertRaisesRegex(ValueError, 'two attempts'):
            w.repair_attempt(self.task, 'occlusion', 'camera-a', 4)
        w.repair_attempt(self.task, 'occlusion', 'camera-b', 4)
        with self.assertRaisesRegex(ValueError, 'two repair strategies'):
            w.repair_attempt(self.task, 'occlusion', 'camera-c', 3)
        w.repair_attempt(self.task, 'occlusion', 'camera-b', 4)
        self.assertEqual(w.load(self.task)['state'], 'BLOCKED')
        with self.assertRaisesRegex(ValueError, 'stopped'):
            w.repair_attempt(self.task, 'occlusion', 'camera-b', 2)

    def test_production_lock_nonblocking(self):
        path = Path(self.temp.name) / 'production.lock'
        with w.lock(path):
            with self.assertRaisesRegex(RuntimeError, 'already locked'):
                with w.lock(path):
                    self.fail('Overlapping heavy process')


if __name__ == '__main__':
    unittest.main()
