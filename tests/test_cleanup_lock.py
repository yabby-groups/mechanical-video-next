import fcntl
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import clean


class CleanupLockTests(unittest.TestCase):
    def make_entry(self, root, name):
        folder = root/'work/cache/shots'/name
        folder.mkdir(parents=True)
        (folder/'complete.json').write_text('{}')
        (folder/'media.mp4').write_bytes(b'regenerable')
        return folder

    def test_cleanup_retains_locked_protected_and_referenced_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            removable = self.make_entry(root, 'a'*64)
            locked = self.make_entry(root, 'b'*64)
            protected = self.make_entry(root, 'c'*64)
            referenced = self.make_entry(root, 'd'*64)
            (locked/'.lock').touch()
            (protected/'.protected').touch()
            handoff = root/'output/tasks/pilot/animation.json'
            handoff.parent.mkdir(parents=True)
            handoff.write_text(json.dumps({'cache_key':referenced.name}))
            original = root/'assets/original.blend'
            original.parent.mkdir()
            original.write_bytes(b'original')
            with patch.object(clean, 'ROOT', root):
                rows = clean.cleanup(0, apply=True)
            self.assertEqual(len(rows), 1)
            self.assertFalse(removable.exists())
            for path in [locked, protected, referenced, original, handoff]:
                self.assertTrue(path.exists())

    def test_cleanup_cannot_delete_while_renderer_holds_lock(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = self.make_entry(root, 'e'*64)
            with (root/'work/production.lock').open('a') as handle:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                with patch.object(clean, 'ROOT', root):
                    with self.assertRaisesRegex(RuntimeError, 'Production busy'):
                        clean.cleanup(0, apply=True)
                self.assertTrue(folder.exists())

    def test_symlink_inside_cache_is_refused_without_deleting_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = self.make_entry(root, 'f'*64)
            target = root/'original.blend'
            target.write_bytes(b'protected')
            (folder/'alias.blend').symlink_to(target)
            with patch.object(clean, 'ROOT', root):
                with self.assertRaisesRegex(ValueError, 'symlink'):
                    clean.cleanup(0, apply=True)
            self.assertEqual(target.read_bytes(), b'protected')
            self.assertTrue(folder.exists())

    def test_dry_run_does_not_delete(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = self.make_entry(root, '1'*64)
            with patch.object(clean, 'ROOT', root):
                rows = clean.cleanup(0)
            self.assertEqual(rows[0]['delete'], False)
            self.assertTrue(folder.exists())

    def test_only_keys_restricts_deletion_without_bypassing_protection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            selected = self.make_entry(root, '1'*64)
            unselected = self.make_entry(root, '2'*64)
            protected = self.make_entry(root, '3'*64)
            referenced = self.make_entry(root, '4'*64)
            failed = self.make_entry(root, '5'*64)
            (protected/'.protected').touch()
            (failed/'complete.json').unlink()
            handoff = root/'output/tasks/pilot/evidence.json'
            handoff.parent.mkdir(parents=True)
            handoff.write_text(json.dumps({'key': referenced.name}))
            with patch.object(clean, 'ROOT', root):
                rows = clean.cleanup(0, apply=True, only_keys=[p.name for p in [selected, protected, referenced, failed]])
            self.assertEqual([r['path'] for r in rows], [str(selected.relative_to(root))])
            self.assertFalse(selected.exists())
            self.assertTrue(all(p.exists() for p in [unselected, protected, referenced, failed]))

    def test_only_keys_retains_age_filter_and_rejects_paths_or_prefixes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = self.make_entry(root, '6'*64)
            with patch.object(clean, 'ROOT', root):
                self.assertEqual(clean.cleanup(24, apply=True, only_keys=[folder.name]), [])
                self.assertEqual(clean.cleanup(0, apply=True, only_keys=[]), [])
                for invalid in ['../shots', '6'*12, 'A'*64]:
                    with self.assertRaisesRegex(ValueError, 'SHA256'):
                        clean.cleanup(0, apply=True, only_keys=[invalid])
            self.assertTrue(folder.exists())


if __name__ == '__main__':
    unittest.main()
