"""Synthetic contracts exercise gates, never assert real perceptual acceptance."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from mechanical_video_next import growth as g, workflow as w, blueprint as b
from mechanical_video_next.feedback import comparable_observations, ingest


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

    def test_concise_recut_requires_intact_instruction_and_retains_growth_checks(self):
        data = copy.deepcopy(self.data)
        data['duration_seconds'] = 60
        for i, shot in enumerate(data['shots']):
            shot.update(start_time=i*20, end_time=(i+1)*20,
                        time_range=[i*20, (i+1)*20])
        with self.assertRaises(ValueError):
            g.validate_contract(data)
        data['duration_policy_override'] = {
            'kind': 'user-requested-concise-recut', 'evidence': [self.ref]}
        self.assertEqual(g.validate_contract(data), 60)
        data['status'] = 'FROZEN'
        bp = self.root/'compact.json'; bp.write_text(json.dumps(data))
        base = self.root/'compact-base.json'
        base.write_text(json.dumps({'asset':'model','shots':{'motion':{'template':'motion'}}}))
        out = self.root/'compact-config.json'
        with patch('mechanical_video_next.blueprint.validate_creative_blueprint'):
            b.compile_config(bp, base, out)
        compiled = json.loads(out.read_text())
        self.assertEqual(compiled['duration_policy_override'], data['duration_policy_override'])
        self.assertEqual(g.duration_bounds(compiled), (1, 300))
        data['shots'][1]['new_information'] = 'relation 0'
        with self.assertRaisesRegex(ValueError, 'Repeated new_information'):
            g.validate_contract(data)
        data['shots'][1]['new_information'] = 'relation 1'
        self.evidence.write_text('changed instruction after freeze')
        with self.assertRaisesRegex(ValueError, 'instruction evidence'):
            g.validate_contract(data)

    def test_payoff_can_precede_only_a_final_specific_bridge(self):
        data = copy.deepcopy(self.data)
        following = data['growth_goals']['following']
        following['final_payoff']['shot_id'] = 's1'
        with self.assertRaisesRegex(ValueError, 'Final payoff'):
            g.validate_contract(data)
        following['next_episode_bridge']['shot_id'] = 's2'
        self.assertEqual(g.validate_contract(data), 180)
        following['final_payoff']['shot_id'] = 's0'
        with self.assertRaisesRegex(ValueError, 'Final payoff'):
            g.validate_contract(data)

    def test_blueprint_cannot_self_authorize_duration_override(self):
        blueprint = copy.deepcopy(self.data)
        blueprint['duration_policy_override'] = {
            'kind': 'user-requested-concise-recut', 'evidence': [self.ref]}
        task_data = {'protocol_version': 2, 'content_policy_version': 1}
        with patch.object(w, 'load', return_value=task_data), patch.object(w, 'artifact', return_value=blueprint):
            with self.assertRaisesRegex(ValueError, 'task authorization'):
                w.check_production_config(self.root)

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
            data.pop('reference_policy_version')
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
        self.assertIsNone(result['featured'])
        self.assertIsNone(result['average_watch_ratio'])
        data.update(average_watch_seconds=63, featured={'value': False, 'source': 'Douyin creator dashboard'},
                    featured_feedback={'value': 'Recorded reply', 'source': 'Douyin creator dashboard'})
        observed = ingest(data)
        self.assertEqual(observed['average_watch_ratio'], .35)
        self.assertIs(observed['featured']['value'], False)
        self.assertIsNone(observed['extra_distribution'])
        with self.assertRaisesRegex(ValueError, 'extra_distribution requires a value and source'):
            ingest(dict(data, extra_distribution={'value': 'Traffic boost'}))
        self.assertIsNone(result['saves']);self.assertIsNone(result['per_thousand_views']['saves'])
        data['views']=0;self.assertIsNone(ingest(data)['per_thousand_views']['likes'])
        data['platform']='xiaohongshu';self.assertEqual(ingest(data)['platform'],'xiaohongshu')
        data['completion_rate']=2
        with self.assertRaises(ValueError):ingest(data)

    def test_feedback_comparison_keeps_one_observation_per_matching_video(self):
        target = dict(video_id='new', platform='douyin', account_id='a', topic='gear',
                      traffic_source='feed', duration_seconds=160,
                      published_at='2026-11-12T10:00:00+08:00',
                      observed_at='2026-11-13T10:00:00+08:00')
        match = dict(target, video_id='match', views=200)
        older = dict(match, observed_at='2026-11-13T11:00:00+08:00')
        foreign = dict(match, video_id='foreign', platform='wechat')
        self.assertEqual(comparable_observations(
            [older, match, foreign, target], target, duration_tolerance=15,
            age_tolerance=7200, publication_window=86400), [match])

    def test_historical_cohorts_keep_age_format_and_platform_separate(self):
        from mechanical_video_next.feedback import domain_cohorts

        base = dict(video_id='post', platform='douyin', account_id='a', format='video',
                    published_at='2026-11-21T10:00:00+08:00',
                    selection_domain={'primary': 'tool', 'basis': 'Pawl drives gear'})
        first = ingest(dict(base, observed_at='2026-11-22T10:00:00+08:00', views=100,
                            likes=0, bounce_2s=.2))
        latest = ingest(dict(base, observed_at='2026-11-28T10:00:00+08:00', views=2200))
        other = ingest(dict(base, platform='xiaohongshu',
                            observed_at=first['observed_at'], views=800, impressions=4000))
        gallery = ingest(dict(base, video_id='gallery', format='gallery', views=6000))
        rows = domain_cohorts([first, latest, other, gallery], first_weekday=5,
                              thresholds={'douyin': 2000})
        self.assertEqual(first['production_binding'], 'partial')
        self.assertEqual(len(rows), 3)
        _, videos, notes = rows
        self.assertEqual(videos['latest']['posts'], 1)
        self.assertEqual(videos['by_age_hours'][24]['over_threshold'], 0)
        self.assertEqual(videos['by_age_hours'][72]['threshold_sample'], 0)
        self.assertEqual(videos['by_age_hours'][168]['over_threshold'], 1)
        self.assertEqual(videos['by_age_hours'][168]['over_threshold_rate'], 1)
        self.assertEqual(videos['by_age_hours'][168]['traffic_sources'], {'UNKNOWN': 1})
        self.assertEqual(videos['by_age_hours'][24]['metrics']['likes']['median'], 0)
        self.assertIsNone(notes['by_age_hours'][24]['over_threshold'])
        self.assertIsNone(notes['by_age_hours'][24]['over_threshold_rate'])
        self.assertIsNone(notes['by_age_hours'][24]['metrics']['recommendation_impressions']['median'])

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
