import json
from pathlib import Path
import tempfile
import unittest
from PIL import Image
from mechanical_video_next.qa_images import (prepare_image, prepare_crop, prepare_cover_preview,
    prepare_contact_sheet, visual_packet, handoff_visuals, sha)


class QAImagesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.cache = Path(self.tmp.name)/'cache'
        self.real = next(Path('output/nail-clipper/2d').glob('*key-*.png'))

    def prep(self, **kwargs):
        return prepare_image(self.real, cache_dir=self.cache, **kwargs)

    def test_real_render_formats_ratio_budget_source(self):
        original = sha(self.real)
        for fmt in ('webp','jpeg'):
            r = self.prep(format=fmt)
            with Image.open(self.real) as src:
                self.assertLess(abs(r['width']/r['height']-src.width/src.height), .005)
            self.assertLessEqual(max(r['width'],r['height']),1024)
            self.assertLessEqual(r['bytes'],300000)
            with Image.open(r['qa_path']) as im: self.assertEqual(im.format,fmt.upper())
        self.assertEqual(original,sha(self.real))

    def test_cache_and_invalidation(self):
        a=self.prep(); self.assertTrue(self.prep()['cache_hit'])
        self.assertNotEqual(a['cache_key'],self.prep(quality=70)['cache_key'])
        p=Path(self.tmp.name)/'changed.png'
        with Image.open(self.real) as im: im.save(p)
        a=prepare_image(p,cache_dir=self.cache)
        with Image.open(p) as im:
            im.putpixel((0,0),(255,0,0)); im.save(p)
        self.assertNotEqual(a['cache_key'],prepare_image(p,cache_dir=self.cache)['cache_key'])

    def test_crop(self):
        r=prepare_crop(self.real,(0,0,200,100),cache_dir=self.cache)
        self.assertEqual((r['width'],r['height']),(200,100))
        with self.assertRaises(ValueError): prepare_crop(self.real,(-1,0,10,10))

    def test_quality_adjustment(self):
        # Real rendered media; force a smaller budget than quality-80 encoding.
        a=self.prep()
        b=self.prep(target_bytes=max(1,a['bytes']-100))
        self.assertLess(b['quality'],80)

    def test_limits_missing_unknown(self):
        a=self.prep()
        with self.assertRaises(ValueError): visual_packet([a]*5)
        with self.assertRaises(ValueError): visual_packet([], [a]*2)
        with self.assertRaises(ValueError): prepare_contact_sheet([self.real]*17)
        self.assertEqual(visual_packet()['acceptance'],'UNKNOWN')
        self.assertEqual(a['readability'],'UNKNOWN')
        with self.assertRaises(ValueError): handoff_visuals({'image':'data:image/png;base64,AAAA'})
        with self.assertRaises(ValueError):
            visual_packet([dict(a,qa_path=str(self.real),qa_sha256=sha(self.real))])

    def test_corrupt_compressed_cache_is_rebuilt(self):
        a=self.prep()
        Path(a['qa_path']).write_bytes(b'not an image')
        b=self.prep()
        self.assertFalse(b['cache_hit'])
        with Image.open(b['qa_path']) as im:
            self.assertEqual(im.format,'WEBP')

    def test_contact_cache(self):
        a=prepare_contact_sheet([self.real],cache_dir=self.cache)
        b=prepare_contact_sheet([self.real],cache_dir=self.cache)
        self.assertTrue(b['cache_hit']); self.assertEqual(a['qa_path'],b['qa_path'])

    def test_covers_real(self):
        covers=list(Path('output').rglob('*cover_3x4.png'))+list(Path('output').rglob('*cover_4x3.png'))
        self.assertTrue(covers, 'Real covers required')
        for p in covers[:2]:
            before=sha(p); r=prepare_cover_preview(p,cache_dir=self.cache)
            with Image.open(p) as im: self.assertAlmostEqual(r['width']/r['height'],im.width/im.height,places=2)
            self.assertEqual(before,sha(p))


if __name__=='__main__': unittest.main()

class VideoEvidenceTests(unittest.TestCase):
    def test_real_video_event_cache_and_limits(self):
        from mechanical_video_next.qa_images import prepare_video_frames
        source=Path('output/nail-clipper/3d/final.mp4')
        before=sha(source)
        with tempfile.TemporaryDirectory() as folder:
            a=prepare_video_frames(source,[0,1],cache_dir=folder)
            b=prepare_video_frames(source,[0,1],cache_dir=folder)
            self.assertTrue(all(r['cache_hit'] for r in b))
            self.assertEqual(a[1]['source_time'],1)
            self.assertEqual(a[0]['video_sha256'],before)
            jpeg=prepare_video_frames(source,[0],format='jpeg',cache_dir=folder)[0]
            self.assertTrue(jpeg['qa_path'].endswith('.jpg'))
            self.assertNotEqual(jpeg['cache_key'],a[0]['cache_key'])
            with Image.open(jpeg['qa_path']) as im:
                self.assertEqual(im.format,'JPEG')
            with self.assertRaises(ValueError):
                prepare_video_frames(source,[0,1],shot_ids=['only-one'],cache_dir=folder)
            with self.assertRaises(ValueError): prepare_video_frames(source,range(5),cache_dir=folder)
        self.assertEqual(sha(source),before)

    def test_real_handoff_compressed(self):
        source=next(Path('output/nail-clipper/2d').glob('*.png'))
        packet=handoff_visuals({'path':str(source)})
        self.assertEqual(packet['image_count'],1)
        self.assertTrue(packet['images'][0]['qa_path'].endswith('.webp'))
        self.assertEqual(packet['acceptance'],'UNKNOWN')
