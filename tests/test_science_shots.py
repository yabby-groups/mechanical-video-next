import copy
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from mechanical_video_next import provenance, science_shots, three_d
from mechanical_video_next.science_information import information_props
from mechanical_video_next.remotion_build import SOURCES
from scripts.common import ROOT

sys.path.insert(0, str(ROOT/'scripts'))
from produce import asset_key, composition_key, shot_key


FIXTURES = ROOT/'tests/fixtures/production'


class ScienceShots(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((FIXTURES/'science-demo.json').read_text())
        self.assembly = json.loads((ROOT/self.config['assembly_config']).read_text())
        self.trace = self.config['shots']['trace']

    def test_demo_configuration_and_all_template_contracts(self):
        three_d.validate_config(self.config)
        science_shots.validate_asset(self.assembly, 'planetary-teaching-fixed-ring')
        for shot in self.config['shots'].values():
            science_shots.validate_assembly_shot(shot, self.assembly)
        examples = {
            'cutaway': {'section_plane': {'axis': 'x', 'side': 'positive'}},
            'micro_zoom': {'camera_focus_region': {'min': [-1, -1, -1], 'max': [1, 1, 1]}},
            'camera_follow': {'science': {'follow': 'Lever'}},
            'field_visualization': {'science': {'paths': [[[0, 0, 0], [1, 1, 1]]]}},
            'flow_visualization': {'science': {'paths': [[[0, 0, 0], [1, 1, 1]]]}},
            'state_transition': {'science': {'driver': 'data_tracks'}, 'tracks': [{'object': 'Lever', 'poses': [
                {'progress': 0, 'location': [0, 0, 0]}, {'progress': 1, 'location': [1, 0, 0]}]}]},
            'measurement': {},
        }
        for template, example in examples.items():
            with self.subTest(template=template):
                shot = {'template': template, 'seconds': 2, **example}
                shot['science'] = {**self.trace['science'], 'driver': 'static', **example.get('science', {})}
                science_shots.validate(shot, files=True)

    def test_stale_source_simulation_and_wrong_asset_control_rejected(self):
        shot = copy.deepcopy(self.trace)
        shot['science']['basis'][0]['sha256'] = '0'*64
        with self.assertRaisesRegex(ValueError, 'stale'):
            science_shots.validate_assembly_shot(shot, self.assembly)
        shot['science']['mode'] = 'physical_simulation'
        with self.assertRaisesRegex(ValueError, 'solver'):
            science_shots.validate(shot)
        shot = copy.deepcopy(self.trace)
        shot['science']['control'] = 'another_implementation'
        with self.assertRaisesRegex(ValueError, 'declared reusable control'):
            science_shots.validate_assembly_shot(shot, self.assembly)
        with self.assertRaisesRegex(ValueError, 'different implementation'):
            science_shots.validate_asset(self.assembly, 'wrong-product')
        self.assembly['reuse']['parts']['Carrier']['parent'] = 'Planet_1'
        with self.assertRaisesRegex(ValueError, 'hierarchy'):
            science_shots.validate_asset(self.assembly)

    def test_unknown_shot_and_2d_remain_ineligible(self):
        self.trace['evidence_status'] = 'RESEARCH_REQUIRED'
        with self.assertRaisesRegex(ValueError, 'Unverified mechanism'):
            three_d.validate_config(self.config)
        self.config['render_route'] = '2.5d'
        with self.assertRaisesRegex(ValueError, '3D-only'):
            three_d.validate_config(self.config)

    def test_editorial_pose_and_guides_are_part_scoped(self):
        science = self.trace['science']
        science.update(stage_rotation=[1.57,0,0], camera_path=[
            dict(progress=0,target=[0,0,0],direction=[0,-1,1],width=1),
            dict(progress=1,target=[1,0,0],direction=[1,-1,1],width=.2)], guides=[
            dict(kind='arrow',points=[dict(object='Hub'),dict(object='Ribbon',vertex=21)],
                 window=[.2,.9],width=.003,color=[0,.5,1])], print_marks=[
            dict(object='Surface',text='ABC',size=.003,color=[0,0,0],local=[0,0,0],rotation_euler=[0,0,0])])
        science_shots.validate(self.trace)
        self.assertTrue({'Planet_1','Hub','Ribbon','Surface'} <= science_shots.referenced_parts(self.trace))
        science['guides'][0]['points'][1]['vertex'] = -1
        with self.assertRaisesRegex(ValueError,'Guide requires'):
            science_shots.validate(self.trace)
        science['guides'] = []
        science['camera_path'][1]['direction'] = [0,1,-1]
        with self.assertRaisesRegex(ValueError,'intermediate camera key'):
            science_shots.validate(self.trace)
        science['camera_path'][1]['progress'] = .8
        with self.assertRaisesRegex(ValueError,'ordered endpoints'):
            science_shots.validate(self.trace)

    def test_editorial_changes_do_not_invalidate_3d(self):
        variant = copy.deepcopy(self.config)
        variant['storyboard'][1]['information'][0]['text'] = '行星轮中心'
        variant['storyboard'][1]['subtitles'] = ['新的字幕']
        variant['storyboard'][1]['narration'] = ['新的旁白']
        params = (self.config['render'], self.config['assembly_config'])
        original = shot_key(self.trace, 'final', *params)
        self.assertEqual(original, shot_key(variant['shots']['trace'], 'final', *params))
        self.assertNotEqual(composition_key(self.config['storyboard'], 'final'),
                            composition_key(variant['storyboard'], 'final'))
        variant['shots']['trace']['science']['anchors']['planet']['local'][2] += 0.1
        self.assertNotEqual(original, shot_key(variant['shots']['trace'], 'final', *params))
        self.assertEqual(asset_key(self.config['assembly_config']), asset_key(variant['assembly_config']))

    def test_label_requires_matching_sample_count_and_anchor(self):
        with tempfile.TemporaryDirectory() as temporary:
            media = Path(temporary)/'media.mp4'
            editorial = self.config['storyboard'][1]
            receipt = {'fps': 15, 'frame_count': 105, 'samples': {'planet': [[0.5, 0.5]]*104}}
            checks = media.with_name('checks.json')
            checks.write_text(json.dumps({'screen_anchors': receipt}))
            with self.assertRaisesRegex(ValueError, 'incompatible'):
                information_props(self.trace, editorial, media, 'video')
            receipt['samples']['planet'].append(None)
            checks.write_text(json.dumps({'screen_anchors': receipt}))
            props = information_props(self.trace, editorial, media, 'video')
            self.assertEqual(props['scienceLabel'], science_shots.MODE_LABEL['mathematical'])
            editorial['information'][0]['anchor'] = 'stale'
            with self.assertRaisesRegex(ValueError, 'missing'):
                information_props(self.trace, editorial, media, 'video')

    def test_replay_binds_chapters_to_the_exact_public_3d_and_audio(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            names = ('cache/scene.mp4', 'cache/voice.m4a')
            fixtures = [root/'remotion/public'/name for name in names]
            files = [root/name for name in SOURCES] + fixtures
            for index, path in enumerate(files):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(str(index).encode())
            props = root/'props.json'
            props.write_text(json.dumps(dict(width=1920, height=1080, fps=30, presentation='mechanism-fullframe',
                shots=[dict(id='chapter', seconds=4, kind='video', media=names[0], audio=names[1])])))
            build = dict(props=provenance.binding(props), render_sources=list(map(provenance.binding, files[:-2])),
                segments=[dict(chapter_id='chapter', frame_count=120,
                               render_output=provenance.binding(fixtures[0]), audio=provenance.binding(fixtures[1]))])
            with patch.object(provenance, 'ROOT', root):
                self.assertEqual(provenance.verify_remotion_inputs(build), props.resolve())
                build['segments'][0]['render_output'] = build['segments'][0]['audio']
                with self.assertRaisesRegex(ValueError, 'differs'):
                    provenance.verify_remotion_inputs(build)

    def test_remotion_replay_requires_every_frame_and_exact_audio(self):
        streams = {'streams': [{'codec_type': 'video', 'nb_frames': '2'}]}
        original, replayed = Path('original.mp4'), Path('replay.mp4')
        def hash_for(path, kind='v'):
            return 'same audio' if kind == 'a' else path.name
        frames = SimpleNamespace(stdout='n:1 psnr_avg:50.00\nn:2 psnr_avg:46.00\n')
        with (patch.object(provenance, 'probe', return_value=streams),
              patch.object(provenance, 'decoded_hash', side_effect=hash_for) as decoded,
              patch.object(provenance.subprocess, 'run', return_value=frames)):
            self.assertEqual(provenance.verify_remotion_replay(original, replayed, 2)['minimum_db'], 46)
            frames.stdout = 'n:1 psnr_avg:50.00\nn:2 psnr_avg:25.00\n'
            with self.assertRaisesRegex(ValueError, 'per-frame'):
                provenance.verify_remotion_replay(original, replayed, 2)
            frames.stdout = 'n:1 psnr_avg:50.00\n'
            with self.assertRaisesRegex(ValueError, 'per-frame'):
                provenance.verify_remotion_replay(original, replayed, 2)
            decoded.side_effect = lambda path, kind='v': path.name
            with self.assertRaisesRegex(ValueError, 'narration'):
                provenance.verify_remotion_replay(original, replayed, 2)
