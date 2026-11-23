"""Fault injection and real file-lock regressions for production execution."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from mechanical_video_next import workflow as w


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


if __name__ == '__main__':
    unittest.main()
