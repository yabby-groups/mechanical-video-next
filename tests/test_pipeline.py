"""Tests with independent failure cases and actual produced evidence where available."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import common
import produce
import clean

class CacheTests(unittest.TestCase):
    def setUp(self):
        self.cfg=json.loads((ROOT/'config/planetary-01.json').read_text())

    def test_narration_and_subtitles_do_not_invalidate_3d(self):
        before={n:produce.shot_key(s,'final') for n,s in self.cfg['shots'].items()}
        changed=copy.deepcopy(self.cfg)
        changed['storyboard'][0]['narration']=['替换解说']
        changed['storyboard'][0]['note']='替换屏幕标注'
        changed['storyboard'][0]['subtitles']=['独立修订字幕']
        after={n:produce.shot_key(s,'final') for n,s in changed['shots'].items()}
        self.assertEqual(before,after)

    def test_external_source_change_at_same_path_invalidates_asset(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)
            source=p/'owned.stl'
            cfg=p/'assembly.json'
            source.write_bytes(b'first source')
            cfg.write_text(json.dumps({'id':'owned','source_files':[{
                'path':str(source),'sha256':common.filehash(source)}]}))
            first=produce.asset_key(str(cfg))
            source.write_bytes(b'changed source')
            self.assertRaises(ValueError,produce.asset_key,str(cfg))
            cfg.write_text(json.dumps({'id':'owned','source_files':[{
                'path':str(source),'sha256':common.filehash(source)}]}))
            self.assertNotEqual(first,produce.asset_key(str(cfg)))

    def test_preview_using_final_shots_cannot_poison_full_resolution_composition(self):
        # A fullframe preview deliberately reuses final-quality 3D media. Its
        # props are identical to final; the 0.5 render scale must still differ.
        props={'width':1920,'height':1080,'shots':[{'media':'same-final-shot.mp4'}]}
        self.assertNotEqual(produce.composition_key(props,'preview'),
                            produce.composition_key(props,'final'))

    def test_one_shot_changes_only_that_cache_key(self):
        changed=copy.deepcopy(self.cfg['shots'])
        changed['explode']['distance']=2.2
        for name,s in changed.items():
            same=produce.shot_key(s,'final')==produce.shot_key(self.cfg['shots'][name],'final')
            self.assertEqual(same,name!='explode')

    def test_orientation_separates_3d_cache_but_not_story_text(self):
        shot=self.cfg['shots']['motion']
        portrait={'width':1080,'height':1920}
        wide={'width':1920,'height':1080}
        self.assertNotEqual(produce.shot_key(shot,'final',portrait),produce.shot_key(shot,'final',wide))
        self.assertEqual(produce.panel_spec(wide,'final'),(1120,720,30))
        self.assertEqual(produce.panel_spec(wide,'preview'),(560,360,15))

    def test_fullframe_renders_native_canvas_instead_of_stretching_old_panel(self):
        render={'width':1920,'height':1080,'framing':'fullframe'}
        self.assertEqual(produce.panel_spec(render,'preview'),(960,540,15))
        self.assertEqual(produce.panel_spec(render,'final'),(1920,1080,30))
        shot=self.cfg['shots']['motion']
        self.assertNotEqual(produce.shot_key(shot,'preview',render),
                            produce.shot_key(shot,'preview',{'width':1920,'height':1080}))

    def test_corrupt_or_missing_artifact_never_hits(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)
            (p/'media.mp4').write_bytes(b'original')
            (p/'keyframe.png').write_bytes(b'keyframe')
            produce.complete(p,['media.mp4','keyframe.png'])
            self.assertTrue(produce.cached(p,['media.mp4']))
            (p/'keyframe.png').write_bytes(b'corrupt-keyframe')
            self.assertFalse(produce.cached(p,['media.mp4']))
            (p/'keyframe.png').write_bytes(b'keyframe')
            (p/'media.mp4').write_bytes(b'tampered')
            self.assertFalse(produce.cached(p,['media.mp4']))
            (p/'media.mp4').unlink()
            self.assertFalse(produce.cached(p,['media.mp4']))

    def test_second_story_uses_same_shot_hashes(self):
        second=json.loads((ROOT/'config/planetary-02.json').read_text())
        self.assertNotEqual(self.cfg['storyboard'],second['storyboard'])
        self.assertEqual({produce.shot_key(s,'final') for s in self.cfg['shots'].values()},
                         {produce.shot_key(s,'final') for s in second['shots'].values()})

class LifecycleTests(unittest.TestCase):
    def test_disk_sampler_tolerates_removed_render_tempfiles(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            (root/'kept').write_bytes(b'1234')
            with patch.object(common.os,'walk',return_value=[(d,[],['kept','already-removed'])]):
                self.assertEqual(common.treebytes(root),4)


    def test_cleanup_only_old_completed_owned_cache(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            original=root/'assets/assemblies/original.glb'
            original.parent.mkdir(parents=True)
            original.write_bytes(b'user original')
            output=root/'output/final.mp4'
            output.parent.mkdir()
            output.write_bytes(b'user final')
            old=root/'work/cache/shots'/('a'*64)
            old.mkdir(parents=True)
            (old/'complete.json').write_text('{}')
            unrelated=root/'work/cache/shots/unrelated'
            unrelated.mkdir()
            (unrelated/'complete.json').write_text('{}')
            with patch.object(clean,'ROOT',root):
                self.assertEqual(clean.candidates(0),[old])
                self.assertEqual(clean.candidates(24),[])
            self.assertEqual(original.read_bytes(),b'user original')
            self.assertEqual(output.read_bytes(),b'user final')

    def test_cleanup_refuses_symlinked_cache(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            (root/'work').mkdir()
            (root/'elsewhere').mkdir()
            (root/'work/cache').symlink_to(root/'elsewhere',target_is_directory=True)
            with patch.object(clean,'ROOT',root):
                self.assertRaises(ValueError,clean.candidates,0)

class EvidenceTests(unittest.TestCase):
    def test_teaching_parameters_and_independent_motion_evidence(self):
        cfg=json.loads((ROOT/'config/assembly.json').read_text())
        self.assertEqual(cfg['sun_teeth']+2*cfg['planet_teeth'],cfg['ring_teeth'])
        self.assertEqual((cfg['sun_teeth']+cfg['ring_teeth'])%cfg['planet_count'],0)
        p=ROOT/'output/motion-independent-check.json'
        if not p.exists(): self.skipTest('Run documented Blender integration check first')
        r=json.loads(p.read_text())
        self.assertEqual(r['status'],'PASS')
        self.assertGreaterEqual(r['evaluated_frame_count'],240)
        self.assertLess(r['max_finite_difference_willis_residual'],2e-5)
        self.assertAlmostEqual(r['sun_total_turns']/r['carrier_total_turns'],4,places=5)

    def test_real_video_deliveries(self):
        for name in ['planetary-01','planetary-02']:
            p=ROOT/f'output/{name}-final.mp4'
            if not p.exists(): self.skipTest('Run both productions before delivery tests')
            evidence=json.loads(p.with_suffix('.validation.json').read_text())
            self.assertEqual(evidence['sha256'],common.filehash(p))
            self.assertEqual(evidence['status'],'TECHNICAL_PASS_UNACCEPTED_TEACHING_DEMO')
            self.assertTrue(evidence['unverified'])

if __name__=='__main__': unittest.main()
