import unittest
from fixture_fonts import require_approved_font
from mechanical_video_next.audio_timeline import speech_phrases
from mechanical_video_next.text_layout import measure_text,load_style


class AudioTimelineTests(unittest.TestCase):
    def test_width_checked_before_synthesis_preserves_words_and_terms(self):
        require_approved_font()
        text='按专利的设计，这个位移会减小环带的张紧和对轮缘的压紧作用，摩擦随之减小。'
        chunks=speech_phrases([text])
        self.assertEqual(''.join(chunks),text)
        style=load_style();box=style['subtitle']['safe_box']
        self.assertTrue(all(measure_text(c,style=style)['width']<=box[2]-box[0] for c in chunks))
        self.assertIn('按专利的设计，',chunks)
