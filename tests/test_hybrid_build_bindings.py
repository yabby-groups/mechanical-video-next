"""Regression tests use temporary bytes and fake only ffprobe's media metadata."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from mechanical_video_next import media_policy, provenance
from mechanical_video_next.remotion_build import sources_for
from scripts.common import ROOT
from tests.test_visual_narrative import shot


class HybridBuildBindings(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.cache = self.root / 'remotion/public/cache'
        self.cache.mkdir(parents=True)
        self.policy = dict(production_contract_version=1, production_contract='mixed-original-v1',
                           subject_kind='mechanical_implementation', visual_policy_version=2,
                           media_policy_version=1)
        for name in sources_for(self.policy):
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.symlink_to(ROOT / name)
        self.final = self.file('final.mp4', b'final')
        audio = self.file('remotion/public/cache/audio.wav', b'audio')
        proof = self.file('rights.txt', b'owned and distributable')
        rights = dict(status='VERIFIED', name='Owned', holder='Owner',
                      editing_and_distribution=True, commercial_use=True,
                      proof={**media_policy.binding(proof), 'position':'ownership statement'})
        sources=[]
        for index in range(3):
            path = self.file(f'source{index}.mp4', f'source{index}'.encode())
            self.file(f'remotion/public/cache/source{index}.mp4', path.read_bytes())
            sources.append({**media_policy.binding(path), 'source_url':path.as_uri(),
                            'credit':f'Owner {index}', 'start_frame':index*15,
                            'license':copy.deepcopy(rights), 'source_type':'GENERATED'})
        visual = shot('use', 0, engine='footage', role='support', kind='real_use',
                      camera={'scale':'wide','angle':'front'}, knowledge='usage')
        visual.update(duration=1, source_type='GENERATED', source_url=sources[0]['source_url'],
                      source_time_range=[0,1], license_status='VERIFIED', usage_restrictions=[],
                      selected_asset=media_policy.binding(Path(sources[0]['path'])), reuse_decision='REUSE',
                      generation_required=False, content_verified=True, credit=sources[0]['credit'],
                      matching={'attempts':[{'priority':1,'status':'ELIGIBLE'}]}, license=rights)
        spec = dict(template='editorial', seconds=1, visual=visual, footage=sources[0],
                    split_screen={'sources':sources[:2]})
        core = copy.deepcopy(visual)
        core.update(shot_id='core', mechanical_role='core', visual_type='product_exterior',
                    knowledge_goal='mechanism', knowledge_ids=['mechanism'],
                    source_url=sources[2]['source_url'], selected_asset=media_policy.binding(Path(sources[2]['path'])),
                    source_time_range=[1,2], credit=sources[2]['credit'],
                    mechanism_verification={'status':'PASS','independent':True,'continuous_video':True,
                        'reviewer_thread_id':'independent-test','observation':'Fixture observation',
                        'real_mechanism':True,'source_sha256':sources[2]['sha256'],
                        'time_range':[1,2],'confirmed_knowledge_ids':['mechanism'],
                        'report':media_policy.binding(proof)})
        core_spec = dict(template='editorial',seconds=1,visual=core,footage=sources[2])
        self.config = {**self.policy, 'id':'test', 'presentation':'mechanism-fullframe',
                       'render':dict(width=1920,height=1080,fps=30,framing='fullframe'),
                       'storyboard':[dict(id='use',shot='use',seconds=1,narration=['usage']),
                                     dict(id='core',shot='core',seconds=1,narration=['mechanism'])],
                       'shots':{'use':spec,'core':core_spec}}
        row = dict(id='use',kind='video',seconds=1,audio='cache/audio.wav',media='cache/source0.mp4',
                   footage={'credit':sources[0]['credit'],'startFrame':0},
                   splitScreen={'sources':[dict(media=f'cache/source{i}.mp4',startFrame=s['start_frame'],
                                                 credit=s['credit']) for i,s in enumerate(sources[:2])]})
        core_row = dict(id='core',kind='video',seconds=1,audio='cache/audio.wav',media='cache/source2.mp4',
                        footage={'credit':sources[2]['credit'],'startFrame':sources[2]['start_frame']})
        props = {**self.policy, 'presentation':'mechanism-fullframe', 'width':1920,'height':1080,
                 'fps':30,'duration':2,'shots':[row,core_row]}
        self.props = self.file('props.json', json.dumps(props).encode())
        self.proof = self.root/'proof.json'
        self.manifest = self.root/'manifest.json'
        self.sources = sources
        self.patches = [patch.object(provenance, 'ROOT', self.root),
                        patch('mechanical_video_next.visual_narrative.probe', return_value={
                            'streams':[{'codec_type':'video','duration':'3'}], 'format':{'duration':'3'}}),
                        patch.object(media_policy, 'probe', return_value={'format':{'duration':'3'},'streams':[
                            {'codec_type':'video','width':1920,'height':1080,'avg_frame_rate':'30/1','nb_frames':'60'}]})]
        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)

    def file(self, name, data):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def write_proof(self):
        provenance.write_remotion_proof(self.proof, self.final, self.props, self.config,
                                        {'use':(Path(self.sources[0]['path']),'video','key'),
                                         'core':(Path(self.sources[2]['path']),'video','key')}, None, None)
        return json.loads(self.proof.read_text())

    def test_policy_survives_proof_and_rejects_omission_or_tamper(self):
        proof = self.write_proof()
        build = proof['build']
        for key in ('production_contract_version','production_contract'):
            self.assertEqual(build[key], self.policy[key])
        provenance.verify_remotion_inputs(build)
        for key, value in [('production_contract_version', None), ('production_contract', 'other')]:
            altered = copy.deepcopy(build)
            if value is None:
                altered.pop(key)
            else:
                altered[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                provenance.verify_remotion_inputs(altered)

    def test_manifest_binds_both_rights_and_source_intervals(self):
        self.write_proof()
        manifest = media_policy.write_manifest(self.manifest, self.final, self.config, self.proof)
        sources = manifest['shots'][0]['supplemental_sources']
        self.assertEqual([s['sha256'] for s in sources], [s['sha256'] for s in self.sources[:2]])
        self.assertEqual([s['source_time_range'] for s in sources], [[0,1],[0.5,1.5]])
        self.assertEqual([s['license'] for s in sources], [s['license'] for s in self.sources[:2]])
        for mutation in ('omit', 'rights', 'interval'):
            altered = copy.deepcopy(manifest)
            rows = altered['shots'][0]['supplemental_sources']
            if mutation == 'omit': rows.pop()
            elif mutation == 'rights': rows[1]['license']['holder'] = 'Other'
            else: rows[1]['source_time_range'] = [0,1]
            self.manifest.write_text(json.dumps(altered))
            with self.subTest(mutation=mutation), self.assertRaisesRegex(ValueError, 'every split-screen source'):
                media_policy.validate_manifest(self.manifest)


if __name__ == '__main__':
    unittest.main()
