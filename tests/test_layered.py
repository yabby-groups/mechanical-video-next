import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image, ImageChops
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import layered
import produce
from common import filehash, probe, Metrics
from mechanical_video_next import director, workflow as w

class LayeredTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root/'part.png'
        Image.new('RGBA', (24,12), '#ef4444').save(self.source)
        self.shot = {'template':'layered','render_route':'2d','seconds':1,
            'layers':[{'path':str(self.source),'sha256':filehash(self.source),
                       'from':{'x':.2,'width':.2},'to':{'x':.8,'rotation':45}, 'depth':1}]}

    def test_motion_and_parallax(self):
        a = layered.frame(self.shot,(160,90),0)
        b = layered.frame(self.shot,(160,90),1)
        self.assertIsNotNone(ImageChops.difference(a,b).getbbox())
        self.shot['layers'][0]['to'] = self.shot['layers'][0]['from']
        self.shot['camera_motion'] = {'to':{'x':.2}}
        self.assertIsNone(ImageChops.difference(layered.frame(self.shot,(160,90),0),layered.frame(self.shot,(160,90),1)).getbbox())
        self.shot['render_route']='2.5d'
        self.assertIsNotNone(ImageChops.difference(layered.frame(self.shot,(160,90),0),layered.frame(self.shot,(160,90),1)).getbbox())

    def test_hash_changes_rejected(self):
        self.source.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'changed'):
            layered.sources(self.shot)

    def test_supporting_clips_render_in_both_dimensions(self):
        for route in ('2d', '2.5d'):
            with self.subTest(route=route), patch.object(layered, 'budget'):
                shot = dict(self.shot, render_route=route, mechanical_role='support')
                folder = self.root / route
                layered.render_supporting_clip(shot, folder, 160, 90, 30, 'final')
                video = probe(folder / 'media.mp4')['streams'][0]
                self.assertEqual((video['width'], video['height'], video['nb_frames']),
                                 (160, 90, '30'))
                program = folder / 'program.json'
                program.write_text(json.dumps(shot))
                receipt = folder / 'layered-receipt.json'

                def binding(path):
                    return {'path': str(path), 'sha256': filehash(path)}

                media = binding(folder / 'media.mp4')
                receipt_data = {'render_route': route, 'program': binding(program),
                                'media': media, 'checks': binding(folder / 'checks.json')}
                receipt.write_text(json.dumps(receipt_data))
                director.validate_layered_source(binding(receipt), media)
                receipt_data['render_route'] = '2d' if route == '2.5d' else '2.5d'
                receipt.write_text(json.dumps(receipt_data))
                with self.assertRaisesRegex(ValueError, 'match its supporting layer program'):
                    director.validate_layered_source(binding(receipt), media)

    def test_layered_generation_rejected_even_if_cached(self):
        with patch.object(produce,'CACHE',self.root/'cache'), patch.object(produce,'asset_key') as asset:
            for route in ('2d','2.5d'):
                self.shot['render_route']=route
                with self.assertRaisesRegex(ValueError,'3D-only'):
                    produce.make_shot(self.shot,'final',None,Metrics('layer-test'),{'width':160,'height':90,'framing':'fullframe'})
            asset.assert_not_called()
        with self.assertRaisesRegex(ValueError,'retired'):
            layered.render(self.shot,self.root,160,90,30,'final')

    def test_producer_cannot_choose_illustrated_route(self):
        task=w.create_task('test',root=self.root)
        with self.assertRaisesRegex(ValueError,'3D-only'):
            w.select_route(task,'2.5d','structure illustration')
        self.assertEqual(w.load(task)['requested_routes'],['3d'])

if __name__=='__main__': unittest.main()
