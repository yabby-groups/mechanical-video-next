import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import produce


class SceneArtifactCacheTests(unittest.TestCase):
    def test_permanent_scene_change_and_loss_invalidate_render_cache(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cache = root/'cache'
            cache.mkdir()
            scene = root/'permanent-scene.blend'
            scene.write_bytes(b'inspectable scene bytes')
            (cache/'checks.json').write_text(json.dumps({'scene_artifact': {
                'path': str(scene), 'sha256': hashlib.sha256(scene.read_bytes()).hexdigest()}}))
            (cache/'media.mp4').write_bytes(b'encoded render')
            produce.complete(cache, ['checks.json', 'media.mp4'])
            self.assertTrue(produce.cached(cache, ['checks.json', 'media.mp4']))
            scene.write_bytes(b'changed geometry')
            self.assertFalse(produce.cached(cache, ['checks.json', 'media.mp4']))
            scene.unlink()
            self.assertFalse(produce.cached(cache, ['checks.json', 'media.mp4']))

    def test_historical_cache_without_external_scene_remains_readable(self):
        with tempfile.TemporaryDirectory() as temporary:
            cache = Path(temporary)
            (cache/'checks.json').write_text('{}')
            produce.complete(cache, ['checks.json'])
            self.assertTrue(produce.cached(cache, ['checks.json']))
