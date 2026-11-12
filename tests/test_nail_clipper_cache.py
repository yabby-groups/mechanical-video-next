import json
from contextlib import ExitStack
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import nail_clipper_video as video


class NailClipperCacheTests(unittest.TestCase):
    def test_changed_audio_and_glb_invalidate_route_receipts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = root / 'output'
            asset = root / 'assets/assemblies/nail-clipper-cad-v5'
            asset.mkdir(parents=True)
            (out / 'shared').mkdir(parents=True)
            (out / 'shared/timeline.json').write_text('{}')
            audio = out / 'shared/narration.wav'
            audio.write_bytes(b'original audio')
            for name in ('motion.json', 'assembly.glb'):
                (asset / name).write_bytes(b'original asset')
            (root / 'assembly.json').write_text('{}')
            (root / 'blender').mkdir()
            (root / 'scripts').mkdir()
            for name in ('blender/scene.py', 'blender/studio_style.py', 'scripts/produce.py'):
                (root / name).write_text('source')
            (out / '3d/config').mkdir(parents=True)
            (out / '3d/config/full.json').write_text('{"assembly_config": "assembly.json"}')
            style = root / 'style.json'
            style.write_text('{}')
            with patch.object(video, 'ROOT', root), patch.object(video, 'OUT', out), patch.object(video, 'STYLE_PATH', style):
                for route, render in (('2d', lambda: video.render('2d')),
                                      ('3d', lambda: video.render_3d('final'))):
                    with self.subTest(route=route):
                        folder = out / route
                        folder.mkdir(exist_ok=True)
                        target = folder / 'final.mp4'
                        target.write_bytes(b'cached media')
                        keys = []
                        original_digest = video.digest
                        def capture(value):
                            key = original_digest(value)
                            keys.append(key)
                            return key
                        with ExitStack() as stack:
                            stack.enter_context(patch.object(video, 'digest', side_effect=capture))
                            stack.enter_context(patch.object(video, 'budget', side_effect=RuntimeError('render required')))
                            stack.enter_context(patch('common.Metrics', side_effect=RuntimeError('render required')))
                            with self.assertRaisesRegex(RuntimeError, 'render required'):
                                render()
                            receipt = target.with_suffix('.json')
                            receipt.write_text(json.dumps({'key': keys[-1], 'sha256': video.filehash(target)}))
                            self.assertEqual(render(), target)
                            dependencies = [audio] + ([asset / 'assembly.glb'] if route == '3d' else [])
                            for dependency in dependencies:
                                before = dependency.read_bytes()
                                dependency.write_bytes(before + b'changed')
                                with self.assertRaisesRegex(RuntimeError, 'render required'):
                                    render()
                                self.assertNotEqual(keys[-1], keys[0])
                                dependency.write_bytes(before)
