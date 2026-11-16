"""3D-only policy regression and actual Blender scene/render counterexamples."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import sys

from mechanical_video_next.three_d import validate_config, migrate
from mechanical_video_next.workflow import create_task, load, select_route, check_requested_routes
from mechanical_video_next.provenance import binding, validate


class ThreeDOnlyTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)

    def test_default(self):
        data=load(create_task('test mechanism',root=self.root))
        self.assertEqual(data['requested_routes'],['3d'])
        self.assertEqual(data['render_route'],'3d')
        self.assertEqual(data['three_d_policy_version'],1)

    def test_rejections(self):
        for route in ['2d','2.5d','all']:
            with self.subTest(route=route),self.assertRaisesRegex(ValueError,'3D-only'):
                create_task('mechanism',root=self.root,routes=route)
        self.assertFalse((self.root/'output').exists())

    def test_no_fallback(self):
        configs=[{'render_route':'2d'},{'render_route':'2.5d'},
                 {'shots':{'core':{'template':'layered'}}},{'asset_strategy':'illustrated'},
                 {'shots':{'core':{'render_route':'2d'}}}]
        for config in configs:
            with self.subTest(config=config),self.assertRaises(ValueError):validate_config(config)

    def test_selection(self):
        task=create_task('mechanism',root=self.root)
        for route in ['2d','2.5d','all']:
            with self.subTest(route=route),self.assertRaisesRegex(ValueError,'3D-only'):
                select_route(task,route,'3D render failed')
        self.assertEqual(load(task)['requested_routes'],['3d'])

    def test_history_and_migration_preserve_cad_neil_cache(self):
        task=create_task('mechanism',root=self.root);p=task/'task.json';data=load(task)
        data.pop('three_d_policy_version');data['requested_routes']=['2d','2.5d','3d']
        data['route_runs']={'2d':{'outputs':{'path':'old.mp4'}},'3d':{'outputs':{'path':'cache.mp4'}}}
        data.update(config='valid-cad.json',shared_production={'narration':{'sha256':'neil'}},stages=[{'cache_hit':True}])
        p.write_text(json.dumps(data))
        self.assertEqual(load(task)['requested_routes'],['2d','2.5d','3d'])
        changed=migrate(task,'explicit authorized migration')
        for k in ['config','shared_production','stages']:self.assertEqual(changed[k],data[k])
        self.assertEqual(changed['route_scope_history'][0]['route_runs'],data['route_runs'])
        self.assertEqual(changed['route_runs']['3d'],data['route_runs']['3d'])
        self.assertTrue(changed['route_runs']['2d']['retired_from_delivery'])
        self.assertEqual(migrate(task,'repeat'),changed)

    def test_missing_film(self):
        task=create_task('mechanism',root=self.root)
        with self.assertRaises((ValueError,FileNotFoundError)):check_requested_routes(task,load(task))

    def test_fake_label_and_model_alone(self):
        movie=self.root/'3d.mp4';movie.write_bytes(b'2d footage')
        doc=self.root/'3d-provenance.json'
        doc.write_text(json.dumps({'media':binding(movie),'shots':[],'build':{'segments':[]}}))
        with self.assertRaisesRegex(ValueError,'core mechanical shots'):validate(doc)

    def test_reference_required(self):
        media=self.root/'3d.mp4';media.write_bytes(b'not a render')
        scene=self.root/'scene.blend';scene.write_bytes(b'not proof')
        shot={'shot_id':'core','scene':binding(scene),'motion_data':binding(scene),
              'render_output':binding(media),'model_assets':[],'product_references':[]}
        doc={'media':binding(media),'shots':[shot],'build':{'segments':[{'shot_id':'core'}]}}
        path=self.root/'3d-provenance.json';path.write_text(json.dumps(doc))
        with self.assertRaisesRegex(ValueError,'reference evidence'):validate(path)

    def test_actual_single_route_entry_has_no_comparison_dependency(self):
        from mechanical_video_next import workflow as w
        task=create_task('entry regression',root=self.root,protocol_version=1)
        movie=task/'unaccepted.mp4'
        # This deliberately flat input may be packaged as an unaccepted candidate;
        # it must never acquire 3D acceptance or delivery from a route name.
        subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i',
                        'color=gray:s=1920x1080:r=30:d=0.2','-c:v','libx264',str(movie)],check=True)
        plan=task/'plan.json'
        plan.write_text(json.dumps({'topic':'entry regression','task':str(task),
                                    'steps':[],'routes':{'3d':str(movie)}}))
        with patch.object(sys,'argv',['workflow','route-run',str(task),'--plan',str(plan)]),patch('builtins.print'):
            w.main()
        data=load(task)
        self.assertIn('three_d_build',data)
        self.assertNotIn('route_comparison',data)
        self.assertFalse((task/'3d/compare.mp4').exists())
        self.assertFalse(w.continuation(task)['delivered'])
        with self.assertRaises((ValueError,FileNotFoundError)):check_requested_routes(task,data)

    def test_spin_mop_existing_inputs_reused(self):
        from scripts.common import ROOT,filehash
        task=ROOT/'output/tasks/spin-mop-20261115'
        preservation=task/'recovery/3d-cache-preservation.v1.json'
        if not preservation.exists():self.skipTest('Task-local media are not tracked in Git')
        self.assertEqual(filehash(task/'shared/narration-v2/narration.wav'),
                         'dd74245cceb5e84e7a5a3b43a41b0d81b4a58125adf4bebdde3f70d76951b556')
        for row in json.loads(preservation.read_text()):
            self.assertTrue(Path(row['asset']).is_file())
            cache=Path(row['cache'])
            for name,digest in json.loads((cache/'complete.json').read_text()).items():
                self.assertEqual(filehash(cache/name),digest)
            assembly=json.loads(Path(row['assembly_config']).read_text())
            for asset in assembly['source_files']:
                self.assertEqual(filehash(asset['path']),asset['sha256'])

    @unittest.skipUnless(os.environ.get('RUN_BLENDER_TESTS')=='1','Requires actual Blender runtime')
    def test_blender(self):
        """Reopen and rerender solid motion + subtitles; reject a plane and substituted film."""
        from scripts.common import BLENDER,ROOT
        folder=Path(os.environ.get('MVN_BLENDER_FIXTURE_DIR',self.root))
        subprocess.run([BLENDER,'-b','--factory-startup','--python-exit-code','1','--python',
                        str(ROOT/'tests/fixtures/three_d_scenes.py'),'--',str(folder)],check=True)
        good=folder/'good-provenance.json';bad=folder/'bad-provenance.json'
        accepted=validate(good)
        self.assertEqual(accepted['status'],'PASS')
        (folder/'good-validation.json').write_text(json.dumps(accepted,indent=2))
        with self.assertRaises((ValueError,subprocess.CalledProcessError)):validate(bad)
        doc=json.loads(good.read_text());doc['media']=binding(folder/'flat-final.mp4')
        forged=folder/'forged-provenance.json';forged.write_text(json.dumps(doc))
        with self.assertRaises(ValueError):validate(forged)
