"""Synthetic contracts exercise gates, never assert real perceptual acceptance."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from mechanical_video_next import growth as g, workflow as w, blueprint as b
from mechanical_video_next.feedback import ingest


class GrowthTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.evidence = self.root/'plan.txt'
        self.evidence.write_text('test-only planned next episode')
        self.ref = {'path': str(self.evidence), 'sha256': w.filehash(self.evidence)}
        self.data = {'content_policy_version': 1, 'duration_seconds': 180,
                     'duration_reason': 'supported transmission and direction explanations', 'shots': [], 'growth_goals': {}}
        for i in range(3):
            self.data['shots'].append(dict(shot_id=f's{i}', section_id=f'c{i}', start_time=i*60,
                end_time=(i+1)*60, time_range=[i*60,(i+1)*60], teaching_goal='cause',
                knowledge_goal='cause', new_information=f'relation {i}', mechanical_action='gear turns',
                narration=['input drives output'], subtitles=['input drives output'], overlays=['principle'],
                visual_proof='rotation marker', audience_takeaway='speed relationship', duration_reason='demonstrate relation',
                related_growth_goal=list(g.GOALS), asset='model', template='motion', existing_shot='motion',
                camera={'camera_view':'oblique'}))
        for category, keys in g.GOALS.items():
            self.data['growth_goals'][category] = {}
            for key in keys:
                row = dict(text=key, shot_id='s2' if key=='final_payoff' else 's0',
                           knowledge_point='transmission', mechanical_action='gear turns',
                           narration='input drives output', observable='marker moves', verification_method='watch exact media')
                if key=='next_episode_bridge': row['plan_evidence']=[self.ref]
                self.data['growth_goals'][category][key] = row
        self.data['growth_goals']['retention']['information_progression'] = [dict(
            self.data['growth_goals']['retention']['opening_action'], shot_id=s['shot_id']) for s in self.data['shots']]
        self.data['growth_goals']['retention']['first_answer_time']=5

    def test_contract_rejects_filler_and_misaligned_answer(self):
        self.assertEqual(g.validate_contract(self.data),180)
        for mutate in (lambda d: d['shots'][1].update(new_information='relation 0'),
                       lambda d: d['growth_goals']['retention'].update(first_answer_time=100),
                       lambda d: d['shots'][1].update(start_time=61)):
            data=copy.deepcopy(self.data); mutate(data)
            with self.assertRaises(ValueError): g.validate_contract(data)

    def test_compilation_preserves_executable_growth_requirements(self):
        self.data['status']='FROZEN'
        bp=self.root/'bp.json'; bp.write_text(json.dumps(self.data))
        base=self.root/'base.json'; base.write_text(json.dumps({'asset':'model','shots':{'motion':{'template':'motion'}}}))
        out=self.root/'config.json'
        with patch('mechanical_video_next.blueprint.validate_creative_blueprint'):
            binding=b.compile_config(bp,base,out)
        cfg=json.loads(out.read_text())
        self.assertEqual(cfg['growth_goals'],self.data['growth_goals'])
        self.assertEqual(cfg['storyboard'][1]['visual_proof'],'rotation marker')
        self.assertEqual(binding['shot_requirements'][2]['end_time'],180)

    def test_media_unknown_and_wrong_timecode_block(self):
        report={'media':[{'sha256':'exact'}]}
        for cat,keys in g.GOALS.items():
            report[cat+'_checks']=[dict(goal=k,shot_id='s2' if k=='final_payoff' else 's0',
                status='PASS',time_range=[121,122] if k=='final_payoff' else [1,2],
                evidence='synthetic review evidence',media_sha256='exact',continuous_viewing=True,listening=True) for k in keys]
        report['retention_checks'] += [dict(report['retention_checks'][0], goal='information_progression', shot_id=f's{i}', time_range=[i*60+1,i*60+2]) for i in (1,2)]
        g.validate_media_checks(self.data,report)
        row=report['engagement_checks'][0]
        for change in ({'status':'UNKNOWN'},{'time_range':[99,100]},{'media_sha256':'other'},{'continuous_viewing':'UNKNOWN'}):
            original=copy.deepcopy(row);row.update(change)
            with self.assertRaises(ValueError):g.validate_media_checks(self.data,report)
            row.clear();row.update(original)

    def test_new_handoff_cannot_omit_contract(self):
        task=w.create_task('test',root=self.root)
        with patch.object(w,'artifact',return_value={'selected_ids':['r']}), patch('mechanical_video_next.viral.validate_creative_blueprint'):
            # Satisfy immutable DAG prerequisites using a historical ledger fixture.
            data=w.load(task)
            for dep in w.V2_DEPENDENCIES['creative-blueprint']: data['handoffs'][dep]={'sha256':'unit'}
            w.write(task/'task.json',data)
            with self.assertRaisesRegex(ValueError,'content_policy_version'):
                w.put_handoff(task,'ViralResearch','creative-blueprint',{},sorted(w.V2_DEPENDENCIES['creative-blueprint']))

    def test_feedback_missing_zero_and_platform_separation(self):
        data=dict(video_id='1',platform='douyin',account_id='account',published_at='2026-11-12T10:00:00+08:00',
                  observed_at='2026-11-13T10:00:00+08:00',topic='gear',traffic_source='unknown',duration_seconds=180,
                  blueprint=self.ref,timeline=self.ref,views=100,likes=5)
        result=ingest(data)
        self.assertEqual(result['per_thousand_views']['likes'],50)
        self.assertIsNone(result['saves']);self.assertIsNone(result['per_thousand_views']['saves'])
        data['views']=0;self.assertIsNone(ingest(data)['per_thousand_views']['likes'])
        data['platform']='xiaohongshu';self.assertEqual(ingest(data)['platform'],'xiaohongshu')
        data['completion_rate']=2
        with self.assertRaises(ValueError):ingest(data)

    def test_old_task_and_media_not_migrated_on_load(self):
        for seconds in (38.2,90):
            task=self.root/str(seconds);task.mkdir()
            value={'duration':seconds,'state':'COMPLETED','schema_version':2,'protocol_version':2}
            w.write(task/'task.json',value); before=(task/'task.json').read_bytes()
            self.assertEqual(w.load(task)['duration'],seconds)
            self.assertEqual((task/'task.json').read_bytes(),before)

    def test_actual_media_duration_cannot_be_faked_by_blueprint(self):
        for duration, valid in ((180,True),(96.3,False),(301,False),(181,False)):
            result=type('Probe',(),{'stdout':json.dumps({'format':{'duration':str(duration)}})})()
            with patch('subprocess.run',return_value=result):
                if valid: g.check_media_duration(self.data,[{'path':'exact.mp4'}])
                else:
                    with self.assertRaises(ValueError): g.check_media_duration(self.data,[{'path':'exact.mp4'}])
