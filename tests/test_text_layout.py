import copy
import unittest
from mechanical_video_next.text_layout import (load_style, measure_text, split_text,
                                               normalize_cues, scaled_style, validate_layout, prepare_text_props,
                                               resolved_font_family, font_path, measured_font)


class TextLayoutTests(unittest.TestCase):
    def test_original_font_collection_resolves_correct_family(self):
        style = load_style()
        path = font_path(style)
        if 'PingFang' in path:
            self.assertEqual(measured_font(64, style).getname(), ('PingFang SC', 'Medium'))
            self.assertEqual(resolved_font_family(style), 'PingFang SC')

    def test_measured_split_exact_text_and_terms(self):
        text = '推块持续把订书钉向前顶，回位弹簧让整个机构回到初始位置。'
        chunks = split_text(text)
        self.assertEqual(''.join(chunks), text)
        self.assertTrue(all(len(c) <= 14 for c in chunks))
        self.assertTrue(all(measure_text(c)['width'] <= 1740 for c in chunks))
        self.assertTrue(any('回位弹簧' in c for c in chunks))

    def test_actual_font_width_blocks_overflow(self):
        style = load_style()
        style['subtitle']['safe_box'][2] = 350
        chunks = split_text('金属零件持续向前运动', style=style)
        self.assertTrue(all(measure_text(c, style=style)['width'] <= 260 for c in chunks))
        with self.assertRaisesRegex(ValueError, 'Protected term'):
            split_text('回位弹簧', style=style)

    def test_no_guessed_timing_or_audio_mutation(self):
        cues = [{'start': 0., 'end': 5., 'text': '推块持续把订书钉向前顶，弹簧推动整个机构回到初始位置，然后开始下一个动作。'}]
        original = copy.deepcopy(cues)
        with self.assertRaisesRegex(ValueError, 'verified segment alignment'):
            normalize_cues(cues)
        self.assertEqual(cues, original)
        short = [{'start': 0., 'end': 5., 'text': '推块持续把订书钉向前顶然后开始下一个动作'}]
        self.assertEqual(normalize_cues(short), short)
        chunks = split_text(cues[0]['text'])
        segments = [{'text': text, 'start': i, 'end': i+1} for i, text in enumerate(chunks)]
        alignment = {'verified': True, 'method': 'fixture measured utterance boundaries',
                     'source_sha256': 'a'*64, 'cues': [{'index': 0, 'segments': segments}]}
        with self.assertRaisesRegex(ValueError, 'actual audio SHA256'):
            normalize_cues(cues, alignment=alignment)
        with self.assertRaisesRegex(ValueError, 'actual audio SHA256'):
            normalize_cues(cues, alignment=alignment, audio_sha256='b'*64)
        self.assertEqual([c['text'] for c in normalize_cues(cues, alignment=alignment, audio_sha256='a'*64)], chunks)
        alignment['cues'][0]['segments'][0]['end'] = 6
        with self.assertRaises(ValueError):
            normalize_cues(cues, alignment=alignment, audio_sha256='a'*64)

    def test_single_active_cue(self):
        with self.assertRaises(ValueError):
            normalize_cues([{'start': 0, 'end': 2, 'text': '推块向前移动'},
                            {'start': 1, 'end': 3, 'text': '弹簧推动钉条'}])
        with self.assertRaises(ValueError):
            normalize_cues([{'start': 0, 'end': 2, 'text': '推块\n向前移动'}])

    def test_routes_sizes_safe_areas_collision(self):
        for route in ('2d', '2.5d', '3d'):
            self.assertEqual(scaled_style(route=route)['subtitle']['font_size'], 64)
            items = [{'layer': 'subtitle', 'text': '持续把钉条向前顶。', 'box': [90, 940, 1830, 1040]}]
            self.assertEqual(validate_layout(items, route=route), [])
            self.assertTrue(validate_layout([{**items[0], 'font_size': 30}], route=route))
            self.assertTrue(validate_layout(items, route=route, critical_boxes=[[100, 950, 200, 1000]]))
            self.assertTrue(validate_layout(items*2, route=route))
            self.assertTrue(validate_layout(items, platform_insets={'left': 0, 'top': 0, 'right': 0, 'bottom': 160}))
        with self.assertRaises(ValueError):
            scaled_style(390, 390)

    def test_prepare_all_routes_and_credit_share_region_by_time(self):
        props = {'title': '02 从送料到折脚', 'duration': 6., 'fps': 30,
                 'shots': [{'seconds': 3}, {'seconds': 3}],
                 'fullframe_caption': '原理示意', 'fullframe_credit': '资料来源已记录',
                 'cues': [{'start': 0, 'end': 2, 'text': '持续把钉条向前顶。'}],
                 'annotations': [{'layer': 'part', 'text': '推块', 'start': 0, 'end': 3},
                                 {'layer': 'part', 'text': '钉条', 'start': 3, 'end': 6}]}
        original = copy.deepcopy(props)
        for route in ('2d', '2.5d', '3d'):
            result = prepare_text_props({**props, 'route': route})
            auxiliary = [i for i in result['text_layout_items'] if i['layer'] == 'auxiliary']
            self.assertEqual([(i['start'], i['end']) for i in auxiliary], [(0, 3), (3, 6)])
            self.assertEqual(result['cues'], props['cues'])
            self.assertEqual(result['text_style']['font_family'], resolved_font_family())
        self.assertEqual(props, original)

    def test_prepare_rejects_crowding_and_unmeasured_text(self):
        props = {'title': '机械原理', 'duration': 6., 'cues': [], 'annotations': [
            {'layer': 'part', 'text': '推块', 'start': 0, 'end': 4},
            {'layer': 'part', 'text': '钉条', 'start': 3, 'end': 6}]}
        with self.assertRaisesRegex(ValueError, 'overlapping text'):
            prepare_text_props(props)
        with self.assertRaisesRegex(ValueError, 'single line'):
            prepare_text_props({**props, 'annotations': [], 'title': '机械原理'*20})
        with self.assertRaisesRegex(ValueError, 'critical mechanism'):
            prepare_text_props({**props, 'annotations': []}, critical_boxes=[[70, 40, 100, 100]])
        with self.assertRaisesRegex(ValueError, 'composition duration'):
            prepare_text_props({**props, 'annotations': [], 'cues': [{'start': 1, 'end': 7, 'text': '推块'}]})


if __name__ == '__main__':
    unittest.main()
