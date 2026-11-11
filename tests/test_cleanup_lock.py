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


if __name__ == '__main__':
    unittest.main()
