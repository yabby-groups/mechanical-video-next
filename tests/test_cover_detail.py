"""Cover layout regression using synthetic local images and a stubbed video duration."""
import copy
import json
import shutil
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image, ImageDraw
from mechanical_video_next import covers


class CoverDetailTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.main = self.image('main.png', (170, 20, 20), (255, 220, 10))
        self.detail = self.image('detail.png', (20, 140, 20), (10, 230, 240))
        self.plan = {'title':['机械原理'], 'series':'科普系列', 'portrait_detail_label':'局部细节'}
        self.box = [0, 0, 1, 1]

    def image(self, name, bg, marker):
        path = self.root/name
        image = Image.new('RGB', (640,360), bg)
        draw = ImageDraw.Draw(image)
        draw.rectangle((0,0,30,30), fill=marker)
        draw.rectangle((609,329,639,359), fill=marker)
        image.save(path)
        return path

    def test_portrait_detail_preserves_frame_and_landscape_remains_one_panel(self):
        portrait = self.root/'portrait.png'
        result = covers.compose(self.main, portrait, (1080,1440), self.plan, self.box,
                                detail=(self.detail,self.box))
        self.assertEqual(result['status'], 'UNKNOWN')
        self.assertGreater(result['detail_subject_fraction'][0], .20)
        self.assertGreater(result['detail_subject_fraction'][1], .15)
        with Image.open(portrait) as im:
            self.assertEqual(im.size, (1080,1440))
            # Main frame at y=320; both corner markers survive containment.
            self.assertEqual(im.getpixel((45,325)), (255,220,10))
            self.assertEqual(im.getpixel((1034,877)), (255,220,10))
            self.assertEqual(im.getpixel((540,1100)), (20,140,20))
        a, b = self.root/'land-a.png', self.root/'land-b.png'
        covers.compose(self.main, a, (1440,1080), self.plan, self.box)
        result = covers.compose(self.main, b, (1440,1080), self.plan, self.box,
                                detail=(self.detail,self.box))
        self.assertIsNone(result['detail_subject_fraction'])
        self.assertEqual(a.read_bytes(), b.read_bytes())

    def test_legacy_center_and_explicit_top_positions(self):
        centered, top = self.root/'center.png', self.root/'top.png'
        legacy = covers.compose(self.main, centered, (1080,1440), self.plan, self.box)
        aligned = covers.compose(self.main, top, (1080,1440),
                                 {**self.plan,'image_alignment':{'portrait':'top'}}, self.box)
        self.assertEqual(legacy['image_alignment'], 'center')
        self.assertEqual(aligned['image_alignment'], 'top')
        with Image.open(centered) as a, Image.open(top) as b:
            self.assertEqual(a.getpixel((540,400)), (32,37,43))
            self.assertEqual(b.getpixel((540,400)), (170,20,20))
            self.assertEqual(a.getpixel((540,1000)), (170,20,20))
            self.assertEqual(b.getpixel((540,1000)), (32,37,43))

    def test_prepare_rejects_invalid_detail_pointer_crop_and_alignment(self):
        video = self.root/'clip.mp4'
        video.write_bytes(b'fixture')
        candidate = dict(id='wide',route='3d',seconds=0.5,shot_id='shot',mechanical_moment='motion',
                         subject_box=[.2,.2,.8,.8])
        detail = {**candidate,'id':'detail','seconds':1.0,'source_crop':[.1,.1,.9,.9]}
        plan = {**self.plan,'topic':'Test','recommended_route':'3d','recommendation_reason':'clear',
                'route_analysis':{'3d':{'suitability':'PASS','reason':'visible'}},
                'copy_rationale':'descriptive','frame_rationale':'mechanism',
                'selected_candidate':'wide','portrait_detail_candidate':'detail',
                'candidates':[candidate,detail]}
        (self.root/'task.json').write_text(json.dumps({'topic':'Test','three_d_policy_version':1}))
        def check(value):
            (self.root/'cover-plan.json').write_text(json.dumps(value))
            return covers.prepare(self.root, {'3d':video})
        with patch.object(covers, 'probe', return_value={'format':{'duration':'2'}}):
            selected, sources, chosen = check(plan)
            self.assertEqual(chosen['id'], 'wide')
            self.assertEqual(selected['portrait_detail_candidate'], 'detail')
            self.assertEqual(sources['3d'], covers.binding(video))
            for case in ('pointer','label','crop','alignment','time'):
                invalid = copy.deepcopy(plan)
                if case == 'pointer': invalid['portrait_detail_candidate'] = 'missing'
                elif case == 'label': invalid['portrait_detail_label'] = ''
                elif case == 'crop': invalid['candidates'][1]['source_crop'] = [.3,.3,.7,.7]
                elif case == 'alignment': invalid['image_alignment'] = {'portrait':'bottom'}
                else: invalid['candidates'][1]['seconds'] = 2
                with self.subTest(case=case), self.assertRaises(ValueError):
                    check(invalid)

    def test_unchanged_generation_preserves_exact_qa_and_changed_plan_regenerates(self):
        from mechanical_video_next import qa_images
        video = self.root/'clip.mp4'
        video.write_bytes(b'fixture video')
        plan = {**self.plan, 'topic':'Test', 'recommended_route':'3d', 'recommendation_reason':'clear',
                'route_analysis':{'3d':{'suitability':'PASS','reason':'visible'}},
                'copy_rationale':'descriptive', 'frame_rationale':'mechanism',
                'selected_candidate':'wide', 'candidates':[dict(id='wide',route='3d',seconds=0.5,
                    shot_id='shot',mechanical_moment='motion',subject_box=[0,0,1,1])]}
        (self.root/'task.json').write_text(json.dumps({'topic':'Test','three_d_policy_version':1}))
        plan_path = self.root/'cover-plan.json'
        plan_path.write_text(json.dumps(plan))
        paths = {'3d':video}
        real_preview = qa_images.prepare_cover_preview
        def extract(args, **kwargs):
            self.assertEqual(args[0], 'ffmpeg')
            shutil.copyfile(self.main, args[-1])
        def preview(path):
            return real_preview(path, cache_dir=self.root/'qa-cache')
        with patch.object(covers, 'probe', return_value={'format':{'duration':'2'}}), \
             patch.object(covers.subprocess, 'run', side_effect=extract) as ffmpeg, \
             patch.object(qa_images, 'prepare_cover_preview', side_effect=preview), \
             patch.object(covers, 'compose', wraps=covers.compose) as compose:
            covers.generate(self.root, paths)
            self.assertGreater(ffmpeg.call_count, 0)
            self.assertGreater(compose.call_count, 0)
            report_path = self.root/'cover/cover-report.json'
            initial = covers.sha(report_path)
            refs = [covers.binding(self.root/'cover'/name) for name in covers.SIZES]
            qa = dict(independent_reviewer=True, reviewer_thread_id='synthetic-test', report_sha256=initial,
                      cover_checks={key:dict(status='PASS', evidence='synthetic fixture',
                          visual_inspection=True, artifacts=refs) for key in covers.CHECKS})
            covers.write(self.root/'cover/cover-qa.json', qa)
            covers.validate(self.root, True, paths)
            ffmpeg.reset_mock()
            compose.reset_mock()
            covers.generate(self.root, paths)
            ffmpeg.assert_not_called()
            compose.assert_not_called()
            self.assertEqual(covers.sha(report_path), initial)
            covers.validate(self.root, True, paths)
            plan['title'] = ['新的问题']
            plan_path.write_text(json.dumps(plan))
            covers.generate(self.root, paths)
            self.assertGreater(ffmpeg.call_count, 0)
            self.assertGreater(compose.call_count, 0)
            self.assertNotEqual(covers.sha(report_path), initial)
            with self.assertRaisesRegex(ValueError, 'exact-report'):
                covers.validate(self.root, True, paths)


if __name__ == '__main__':
    unittest.main()
