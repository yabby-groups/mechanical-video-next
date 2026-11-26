"""The episode entry point supports graphics alongside original picture cuts."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from mechanical_video_next import episode


class EpisodeGraphicsTests(unittest.TestCase):
    def test_mixed_picture_uses_frame_exact_cache_and_keeps_legacy_path(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            graphic = {'type': 'timeline', 'title': 'Release', 'items': [
                {'label': 'Hold', 'detail': 'The carriage stays low'},
                {'label': 'Release', 'detail': 'The carriage rises'},
            ]}
            picture = {'path': 'original.mp4', 'sha256': 'fixture'}
            shots = [{'picture': picture}, {'graphic': graphic}]
            speech = [(None, [], 31), (None, [], 47)]
            original = root / 'original.mp4'

            def encode(props_path, candidate, _log, *, preview, visual):
                props = json.loads(props_path.read_text())
                self.assertEqual(props['frameCount'], 47)
                self.assertEqual(props['shots'][0]['graphic'], graphic)
                self.assertEqual(props['duration'], 47 / 30)
                self.assertFalse(preview)
                self.assertTrue(visual)
                candidate.write_bytes(b'encoded')

            video = {'codec_type': 'video', 'width': 1920, 'height': 1080,
                     'r_frame_rate': '30/1', 'nb_frames': '47'}
            with patch.object(episode, 'recut_picture', return_value=original) as recut, \
                    patch.object(episode, 'render', side_effect=encode) as render, \
                    patch.object(episode, 'probe', return_value={'streams': [video]}):
                pictures = episode.picture_sources(root, speech, root, shots=shots)
                self.assertEqual(pictures[0], original)
                self.assertEqual(pictures[1].read_bytes(), b'encoded')
                self.assertEqual(episode.picture_sources(root, speech, root, shots=shots), pictures)
                recut.assert_called_with(root, picture, 31, root)
                self.assertEqual(render.call_count, 1)

    def test_graphic_cannot_silently_override_scene_and_picture(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            edit = root / 'edit.json'
            for extra in ({'scene': 'scene.py'}, {'picture': {'path': 'clip.mp4'}}):
                edit.write_text(json.dumps({'output': 'episode.mp4',
                                            'shots': [dict(extra, graphic={})]}))
                with self.assertRaisesRegex(ValueError, 'no separate picture source'):
                    episode.produce(root)

    def test_invalid_graphic_fails_before_narration(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'edit.json').write_text(json.dumps({
                'output': 'episode.mp4',
                'shots': [{}, {'graphic': {'type': 'unknown'}}],
            }))
            with patch.object(episode, 'load_env') as load_env:
                with self.assertRaisesRegex(ValueError, 'Unknown information graphic'):
                    episode.produce(root)
                load_env.assert_not_called()


if __name__ == '__main__':
    unittest.main()
