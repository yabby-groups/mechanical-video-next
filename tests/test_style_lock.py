import json
from pathlib import Path
import tempfile
import unittest
from PIL import Image
from mechanical_video_next.style_lock import compare_frames, sha256, verify_lock


class StyleLockTests(unittest.TestCase):
    def test_protected_actual_reference_and_scene(self):
        self.assertEqual(verify_lock('assets/style-reference/style-lock.json')['status'], 'PASS')

    def test_original_screenshot_recorded_honestly(self):
        lock = json.loads(Path('assets/style-reference/style-lock.json').read_text())
        self.assertEqual(sha256('assets/style-reference/approved-original.png'), lock['source']['sha256'])
        self.assertIn('UNKNOWN', lock['source']['exact_video_version'])

    def test_difference_and_text_mask(self):
        with tempfile.TemporaryDirectory() as folder:
            a, b = Path(folder) / 'a.png', Path(folder) / 'b.png'
            image = Image.new('RGB', (100, 100), '#aaaabb'); image.save(a)
            image.paste('white', (10, 90, 90, 100)); image.save(b)
            self.assertEqual(compare_frames(a, b, [])['status'], 'FAIL')
            self.assertEqual(compare_frames(a, b, [(10, 90, 90, 100)])['status'], 'PASS')
            image.paste('black', (40, 40, 60, 60)); image.save(b)
            self.assertEqual(compare_frames(a, b, [(10, 90, 90, 100)])['status'], 'FAIL')

    def test_small_codec_error_allowed(self):
        with tempfile.TemporaryDirectory() as folder:
            a, b = Path(folder) / 'a.png', Path(folder) / 'b.png'
            Image.new('RGB', (100, 100), (100, 100, 100)).save(a)
            Image.new('RGB', (100, 100), (101, 101, 101)).save(b)
            self.assertEqual(compare_frames(a, b, [])['status'], 'PASS')

    def test_cannot_mask_entire_image_or_resize(self):
        with tempfile.TemporaryDirectory() as folder:
            a, b = Path(folder) / 'a.png', Path(folder) / 'b.png'
            Image.new('RGB', (100, 100)).save(a)
            Image.new('RGB', (50, 50)).save(b)
            with self.assertRaises(ValueError): compare_frames(a, a, [(0, 0, 100, 100)])
            with self.assertRaises(ValueError): compare_frames(a, b, [])

    def test_lock_detects_changed_file(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'source').write_text('before')
            (root / 'lock.json').write_text(json.dumps({'protected_files': [{'path': 'source', 'sha256': sha256(root / 'source')}]}))
            self.assertEqual(verify_lock(root / 'lock.json', root)['status'], 'PASS')
            (root / 'source').write_text('after')
            self.assertEqual(verify_lock(root / 'lock.json', root)['status'], 'FAIL')
