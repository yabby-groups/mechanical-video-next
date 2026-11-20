"""Opt-in browser render regression for the actual encoded audience picture."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from scripts.common import ROOT, run, writejson
from mechanical_video_next.remotion_build import render


@unittest.skipUnless(os.getenv('MVN_TEST_AUDIENCE_RENDER') == '1', 'needs the local Remotion browser')
class AudienceRenderTests(unittest.TestCase):
    def test_badge_and_title_visibility_in_decoded_picture(self):
        public = ROOT/'remotion/public'
        with tempfile.TemporaryDirectory(dir=public) as directory:
            folder = Path(directory)
            media, audio = folder/'fixture.mp4', folder/'silence.wav'
            run(['ffmpeg','-v','error','-f','lavfi','-i','color=0x405061:s=960x540:r=30:d=4',
                 '-c:v','libx264',media])
            run(['ffmpeg','-v','error','-f','lavfi','-i','anullsrc=r=48000','-t','4',audio])
            shot = dict(id='fixture', kind='video', seconds=4,
                        media=str(media.relative_to(public)), audio=str(audio.relative_to(public)))
            props = dict(title='雨伞为什么一推就开？', cues=[], duration=4, fps=30, width=1920, height=1080)
            images = {}
            for name, badge, style in (
                    ('control', '', None), ('default', '教学级运动学 · 原理示意', None),
                    ('legacy', '原理示意', 'legacy'),
                    ('limited', '模型示意 · 仅比较角度', None), ('condition', '仅比较角度', None)):
                config = folder/f'{name}.json'
                writejson(config, dict(props, shots=[dict(shot, scienceLabel=badge)],
                                       **({'presentation_style': style} if style else {})))
                movie = folder/f'{name}.mp4'
                render(config, movie, folder/f'{name}.log', preview=True, progression=True, frame_range=[88,91])
                images[name] = [subprocess.check_output(['ffmpeg','-v','error','-i',str(movie),
                            '-vf',crop,'-f','rawvideo','-pix_fmt','rgb24','-'])
                            for crop in ('crop=220:40:710:140', 'crop=400:72:20:0')]
            self.assertEqual(images['control'], images['default'])
            self.assertEqual(images['condition'], images['limited'])
            self.assertNotEqual(images['default'][0], images['legacy'][0])
            self.assertNotEqual(images['default'][0], images['condition'][0])
            frame_bytes = 400*72*3
            _, titles = images['default']
            self.assertNotEqual(titles[:frame_bytes], titles[2*frame_bytes:3*frame_bytes])
