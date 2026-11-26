"""Exercise the decoded frame clock and the evidence attached to a diagnosis."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from PIL import Image

from mechanical_video_next import joint_timeline as joint, qa_images, video_review
from mechanical_video_next import visual_diagnosis as diagnosis
from scripts.common import run


class VisualDiagnosisTests(unittest.TestCase):
    def test_decode_crop_and_event_use_the_requested_frames(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            for index, red in enumerate((0, 32, 64, 96, 128)):
                image = Image.new('RGB', (48, 32), (red, 0, 0))
                image.putpixel((13, 11), (red, 250, 250))
                image.save(root / f'{index}.png')
            video = root / 'sample.mp4'
            run(['ffmpeg', '-v', 'error', '-framerate', 30, '-i', root / '%d.png',
                 '-c:v', 'libx264rgb', '-crf', 0, video])
            sheet = video_review.ordered_picture_evidence(joint.binding(video), [1, 3], cache_dir=root)
            self.assertEqual(sheet['frame_indices'], [1, 3])
            self.assertEqual(sheet['continuous_viewing'], 'UNKNOWN')
            self.assertTrue(Path(sheet['images'][0]['qa_path']).is_file())
            with qa_images.decoded_frames(video, 0, [1, 3], cache_dir=root) as frames:
                for path, red in zip(frames, (32, 96), strict=True):
                    with Image.open(path) as image:
                        self.assertEqual(image.size, (48, 32))
                        self.assertEqual(image.convert('RGB').getpixel((13, 11)), (red, 250, 250))
                ref = qa_images.prepare_image(frames[0], crop_region=(12, 10, 20, 17),
                                              zoom=4, quality=100, cache_dir=root)
                self.assertEqual(ref['native_size'], [8, 7])
                self.assertEqual((ref['width'], ref['height']), (32, 28))
                with Image.open(ref['qa_path']) as image:
                    self.assertGreater(image.getpixel((6, 6))[1], 200)
            event = diagnosis._event_clip(joint.binding(video), 0, root / 'event.mp4', 1, 4,
                                           (11, 7, 30, 22))
            self.assertEqual(event['frame_range'], [1, 4])
            with qa_images.decoded_frames(joint.bound(event), 0, [0, 2], cache_dir=root) as frames:
                for path, red in zip(frames, (32, 96), strict=True):
                    with Image.open(path) as image:
                        self.assertEqual(image.size, (19, 15))
                        self.assertAlmostEqual(image.convert('RGB').getpixel((0, 0))[0], red, delta=8)

    def test_episode_binding_maps_recut_and_preview_step(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            scene = root / 'scene.py'
            research = root / 'research.md'
            scene.write_text('scene')
            research.write_text('research')
            motion = {'binding': {'scene': joint.binding(scene)['sha256'], 'shot': 2, 'frames': 53,
                                  'mechanics': {'inputs': {
                                      str(path.resolve()): joint.binding(path)['sha256']
                                      for path in (scene, research)}}}}
            cut = {'mechanics': {'evidence': 'research.md'}}
            binding = diagnosis.shot_binding(cut, motion, root, direct=False, preview_step=5)
            row = dict(binding, id='shot-2', start_frame=10, source_start_frame=7)
            location = diagnosis.source_location(row, 16)
            self.assertEqual(location['source_frame'], 10)
            self.assertEqual(location['scene']['source'], joint.binding(scene))
            self.assertEqual(location['research'], joint.binding(research))
            self.assertEqual(diagnosis.shot_binding(cut, motion, root, direct=True, preview_step=None), {})

    def test_stale_receipt_cannot_attach_objects_to_a_different_export(self):
        with TemporaryDirectory() as folder:
            media = Path(folder) / 'film.mp4'
            media.write_bytes(b'current')
            media.with_suffix('.mechanics.json').write_text(json.dumps({'media': {'sha256': 'old'}}))
            with self.assertRaisesRegex(ValueError, 'different MP4'):
                diagnosis._intervals(media, joint.binding(media), 5)
