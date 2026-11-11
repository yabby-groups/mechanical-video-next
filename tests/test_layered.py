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
from mechanical_video_next import workflow as w

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

    def test_encode_and_cache_without_blender(self):
        with patch.object(produce,'CACHE',self.root/'cache'), patch.object(produce,'asset_key',side_effect=AssertionError('No Blender asset')):
            for route in ('2d','2.5d'):
                self.shot['render_route']=route
                path,kind,key=produce.make_shot(self.shot,'final',None,Metrics('layer-test'),{'width':160,'height':90,'framing':'fullframe'})
                self.assertEqual(kind,'video')
                stream=probe(path)['streams'][0]
                self.assertEqual(int(stream['nb_frames']),30)
                self.assertEqual(stream['width'],160)
                with patch.object(layered,'render',side_effect=AssertionError('Cache miss')):
                    self.assertEqual(produce.make_shot(self.shot,'final',None,Metrics('cached'),{'width':160,'height':90,'framing':'fullframe'})[2],key)

    def test_producer_route_and_illustrated_asset(self):
        task=w.create_task('test',root=self.root)
        w.select_route(task,'2.5d','structure illustration')
        payload={'qualified':True,'render_route':'2.5d','source_files':[{'path':str(self.source),'sha256':filehash(self.source)}]}
        with patch.object(w,'artifact',return_value=payload):
            self.assertEqual(w.check_asset(task),payload)
            self.source.write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError,'changed'):
                w.check_asset(task)

if __name__=='__main__': unittest.main()
