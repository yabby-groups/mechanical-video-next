"""Real decoding guards removal of a regenerable full-film cache duplicate."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import clean
from scripts import produce


class CompositionExportCache(unittest.TestCase):
    def fixture(self, root):
        folder = root/'work/cache/compositions'/('a'*64)
        folder.mkdir(parents=True)
        (folder/'props.json').write_text('{"duration":0.1}')
        exported = root/'output/film.mp4'
        exported.parent.mkdir()
        subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i',
                        'color=c=blue:s=32x32:d=0.1:r=30', '-an', '-c:v', 'libx264',
                        '-pix_fmt', 'yuv420p', str(exported)], check=True)
        shutil.copy2(exported, folder/'video.mp4')
        produce.complete(folder, ['video.mp4'])
        return folder, exported

    def test_decoded_identical_export_replaces_duplicate_and_remains_cache_hit(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            folder, exported = self.fixture(root)
            original = exported.read_bytes()
            with patch.object(clean, 'ROOT', root), patch.object(produce, 'ROOT', root):
                dry = clean.retain_composition_export(folder, exported, remove_duplicate=True, apply=False)
                self.assertEqual(dry['deleted_bytes'], 0)
                self.assertTrue((folder/'video.mp4').exists())
                result = clean.retain_composition_export(folder, exported, remove_duplicate=True)
                self.assertEqual(result['deleted_bytes'], len(original))
                self.assertEqual(result['bytes'], len(original))
                self.assertFalse((folder/'video.mp4').exists())
                self.assertEqual(exported.read_bytes(), original)
                self.assertEqual(produce.composition_cached_media(folder), exported.resolve())
                exported.write_bytes(b'changed export')
                self.assertIsNone(produce.composition_cached_media(folder))

    def test_mismatch_or_bad_decode_keeps_all_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            folder, exported = self.fixture(root)
            original = (folder/'video.mp4').read_bytes()
            exported.write_bytes(b'not the same media')
            with patch.object(clean, 'ROOT', root):
                with self.assertRaisesRegex(ValueError, 'differs'):
                    clean.retain_composition_export(folder, exported, remove_duplicate=True)
                self.assertEqual((folder/'video.mp4').read_bytes(), original)
                self.assertFalse((folder/'external-media.json').exists())
                with self.assertRaises(subprocess.CalledProcessError):
                    clean.retain_composition_export(folder, exported)
                self.assertFalse((folder/'external-media.json').exists())

    def test_new_export_needs_no_full_video_in_work_and_props_are_bound(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            folder, exported = self.fixture(root)
            (folder/'video.mp4').unlink()
            with patch.object(clean, 'ROOT', root), patch.object(produce, 'ROOT', root):
                clean.retain_composition_export(folder, exported)
                self.assertEqual(produce.composition_cached_media(folder), exported.resolve())
                (folder/'props.json').write_text('{"duration":5}')
                self.assertIsNone(produce.composition_cached_media(folder))
                receipt = json.loads((folder/'external-media.json').read_text())
                self.assertEqual(receipt['media']['sha256'], clean.filehash(exported))
