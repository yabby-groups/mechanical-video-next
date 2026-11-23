import unittest
from unittest.mock import patch

from fixture_fonts import test_font

from mechanical_video_next.remotion_build import validate_phone_text


class PhoneTextTests(unittest.TestCase):
    def test_rejects_multiline_overflow_and_small_type(self):
        from mechanical_video_next.text_layout import load_style
        style = dict(load_style(), font_candidates=[test_font()])
        self.enterContext(patch('mechanical_video_next.text_layout.load_style', return_value=style))
        validate_phone_text('A', 200)
        for text, width, size in [('A\nB', 200, 64), ('Very long text', 5, 64), ('A', 200, 32)]:
            with self.subTest(text=text, width=width, size=size), self.assertRaises(ValueError):
                validate_phone_text(text, width, size=size)


if __name__ == '__main__':
    unittest.main()
