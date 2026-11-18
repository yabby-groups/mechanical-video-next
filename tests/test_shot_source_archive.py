"""Archived executable inputs remain immutable and participate in cache validity."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from scripts import produce


class ShotSourceArchive(unittest.TestCase):
    def test_archived_input_is_immutable_and_hash_checked_on_cache_hit(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            folder = root/'work'/'key'
            folder.mkdir(parents=True)
            shot = {'scene_artifact_dir': str(root/'output'/'scenes'), 'mesh_tracks': [1, 2, 3]}
            source = produce.shot_input_file(folder, 'key', shot)
            self.assertFalse((folder/'shot.json').exists())
            self.assertEqual(json.loads(source.read_text()), shot)
            original = source.read_bytes()
            self.assertEqual(produce.shot_input_file(folder, 'key', shot), source)
            self.assertEqual(source.read_bytes(), original)
            (folder/'media.mp4').write_bytes(b'fixture media')
            (folder/'checks.json').write_text(json.dumps({'source_shot': {
                'path': str(source), 'sha256': produce.filehash(source)}}))
            produce.complete(folder, ['media.mp4', 'checks.json'])
            self.assertTrue(produce.cached(folder, ['media.mp4', 'checks.json']))
            source.write_text('{}')
            self.assertFalse(produce.cached(folder, ['media.mp4', 'checks.json']))
            with self.assertRaisesRegex(ValueError, 'preserve it'):
                produce.shot_input_file(folder, 'key', shot)
            self.assertEqual(source.read_text(), '{}')

    def test_default_input_location_remains_compatible(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            source = produce.shot_input_file(folder, 'key', {'seconds': 2})
            self.assertEqual(source, folder/'shot.json')
            self.assertEqual(json.loads(source.read_text()), {'seconds': 2})
