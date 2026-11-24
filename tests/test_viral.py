import copy
import hashlib
from pathlib import Path
import tempfile
import unittest

from mechanical_video_next import viral as v


class ScreeningTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name)/'observation.json'
        self.path.write_text('unit fixture; not real video acceptance')
        self.evidence = [{'path': str(self.path), 'sha256': hashlib.sha256(self.path.read_bytes()).hexdigest()}]

    def candidate(self, i=1, viewed=True):
        return dict(id=str(i), url='https://www.douyin.com/video/'+str(i),
                    observed_at='2026-11-11T08:00:00+00:00', published_at='2026-10-11T08:00:00+00:00',
                    followers=9999, likes=1001, duration_seconds=30,
                    evidence=self.evidence, metrics_evidence={'followers': 'profile', 'likes': 'work page'},
                    viewing={'status': 'FULL_VIDEO_VIEWED' if viewed else 'VIDEO_NOT_VIEWED',
                             'continuous_visual': viewed, 'covered_seconds': 30, 'evidence': self.evidence},
                    directly_related=True, style='style'+str(i), deep_analysis=True,
                    scores=dict.fromkeys(v.WEIGHTS, 80), scores_evidence=dict.fromkeys(v.WEIGHTS, 'unit-evidence'))

    def data(self, rows):
        return dict(topic='拉链', observed_at='2026-11-11T08:00:00+00:00', candidates=rows)

    def test_static_local_reference_and_region_mapping(self):
        c = self.candidate(viewed=False)
        c.pop('url'); c.pop('duration_seconds')
        c.update(source_kind='diagram', source_files=self.evidence, observations=['lever connection'],
                 followers=None, likes=None, viewing={'status':'IMAGE_INSPECTED','evidence':self.evidence})
        result = v.analyze(self.data([c]))
        self.assertEqual(result['status'], 'READY')
        self.assertEqual(result['primary_reference_kind'], 'observed-reference')
        blueprint = {'reference_recreation':{'primary_reference_id':'1', 'shot_mapping':[
            {'shot_id':'s1','reference_region':'lever connection','adaptation':'layer rotation'}]},
            'shots':[{'shot_id':'s1'}], 'reference_principles':[{'reference_id':'1'}]}
        v.validate_reference_recreation(blueprint,result)
        blueprint['reference_recreation']['shot_mapping'][0]['reference_time_range']=[0,1]
        with self.assertRaisesRegex(ValueError,'Static'):
            v.validate_reference_recreation(blueprint,result)
        self.path.write_text('changed')
        self.assertEqual(v.analyze(self.data([c]))['status'],'BLOCKED')

    def test_unviewed_cannot_score_rhythm_or_qualify(self):
        c = self.candidate(viewed=False)
        r = v.analyze(self.data([c]))
        self.assertEqual(r['status'], 'BLOCKED')
        self.assertEqual(r['selected_ids'], [])
        self.assertEqual(r['candidates'][0]['screening']['coverage'], .6)
        self.assertNotIn('opening', r['candidates'][0]['screening']['available'])

    def test_directed_viewing_scope_and_cache_reuse(self):
        from mechanical_video_next.reference_library import ingest

        candidate = self.candidate()
        candidate.update(observations=['0–30s: close-up reveals the movement'],
                         transfer_rationale='Show the output from a matching camera angle')
        report = self.data([candidate]) | {'selected_ids': [candidate['id']]}
        v.validate_directed_analysis(report)
        for status in ('SCREENSHOTS_ONLY', 'PAGE_ONLY', 'VIDEO_NOT_VIEWED'):
            other = dict(candidate, viewing={'status': status, 'limitation': 'Playback unavailable'})
            with self.subTest(status=status), self.assertRaisesRegex(ValueError, 'Selected references'):
                v.validate_directed_analysis(report | {'candidates': [other]})
        short = dict(candidate, viewing=candidate['viewing'] | {'covered_seconds': 12})
        with self.assertRaisesRegex(ValueError, 'time coverage'):
            v.validate_directed_analysis(report | {'candidates': [short]})
        with self.assertRaisesRegex(ValueError, 'Public metrics'):
            v.validate_directed_analysis(report | {'candidates': [dict(candidate, metrics_evidence={})]})
        library = Path(self.tmp.name) / 'references'
        ingest(report, topic='拉链', root=library)

        def reusable():
            plan = v.directed_plan('拉链', library)
            return plan['local_references']['results'][0]['observations'][0]['reusable_expression']

        self.assertTrue(reusable())
        self.path.write_text('Changed evidence')
        self.assertFalse(reusable())

    def test_missing_metrics_remain_null_and_weights_renormalize(self):
        c = self.candidate(); c['followers'] = None
        r = v.analyze(self.data([c]))['candidates'][0]
        self.assertIsNone(r['followers']); self.assertIsNone(r['views'])
        self.assertIsNone(r['breakout_follower_cap'])
        self.assertEqual(r['screening']['coverage'], .8)
        self.assertAlmostEqual(sum(r['screening']['normalized_weights'].values()), 1, places=5)

    def test_observed_technique_reaches_only_its_authored_cut(self):
        candidate = self.candidate()
        candidate.update(observations=['The cover separates while the base stays in view.'],
                         transfer_rationale='Keep the original mount identifiable.',
                         techniques=[dict(id='fixed-base', source_range=[4, 8], visual_method='Hold the base',
                                          use_condition='Cover can separate', viewer_effect='Locate the mount',
                                          implementation='Fixed direction reveal')])
        analysis = self.data([candidate]) | {'selected_ids': ['1']}
        v.validate_directed_analysis(analysis, require_techniques=True)
        principle = dict(reference_id='1', technique_id='fixed-base', principle='Preserve assembly context',
                         production_requirement='Push in from the installed pose',
                         expected_observable_effect='Cover and mount stay recognizable')
        treatment = dict(scenes=[dict(id='reveal')], reference_principles=[dict(principle, scene_ids=['reveal'])])
        v.validate_reference_direction(treatment, analysis)
        cuts = [dict(id='intro', scene_id='reveal', start_frame=0, end_frame=30),
                dict(id='cover', scene_id='reveal', start_frame=30, end_frame=60)]
        plan = dict(timeline=dict(shots=cuts), reference_principles=[dict(principle, shot_ids=['cover'])])
        mapping = v.reference_shot_map(treatment, plan)
        effect = dict(reference_id='1', technique_id='fixed-base', shot_id='cover', time_range=[1, 2],
                      media_sha256='media-sha', status='PASS', observation='Mount stayed visible',
                      method='continuous_video')
        self.assertEqual(v.validate_reference_effects(mapping, {'reference_effects': [effect]}, 'media-sha'), {'PASS'})
        with self.assertRaisesRegex(ValueError, 'exact-media'):
            v.validate_reference_effects(mapping, {'reference_effects': [effect]}, 'other-sha')
        cuts[1]['scene_id'] = 'another'
        with self.assertRaisesRegex(ValueError, 'corresponding scenes'):
            v.reference_shot_map(treatment, plan)

    def test_one_qualified_primary_is_enough_without_supplementary_categories(self):
        rows = [self.candidate(i) for i in range(3)]
        self.assertEqual(v.analyze(self.data(rows[:1]))['status'], 'READY')
        rows[1].update(reference_class='B', transfer_rationale='locking geometry')
        rows[-1].update(reference_class='C', transfer_rationale='science narrative', professional_benchmark=True, followers=1000000)
        ready = v.analyze(self.data(rows))
        self.assertEqual(ready['status'], 'READY')
        v.validate_viral_analysis(ready)
        rows[1]['style'] = rows[0]['style']
        self.assertEqual(v.analyze(self.data(rows))['status'], 'READY')

    def test_recent_exact_thresholds_and_future_date(self):
        c = self.candidate(); c['followers'] = 10000
        self.assertEqual(v.analyze(self.data([c]))['candidates'][0]['breakout_follower_cap'], 50000)
        for key, val in [('followers', 100000), ('likes', 1000), ('published_at', None),
                         ('published_at', '2026-11-12T08:00:00+00:00'), ('published_at', '2020-01-01T00:00:00Z')]:
            row = self.candidate(); row[key] = val
            self.assertIsNone(v.analyze(self.data([row]))['candidates'][0]['breakout_follower_cap'])

    def test_dedupe_tracking_and_reject_search_links(self):
        a, b = self.candidate(), self.candidate(2)
        b['url'] = a['url']+'?tracking=abc'
        self.assertEqual(v.analyze(self.data([a,b]))['duplicates'], ['2'])
        with self.assertRaisesRegex(ValueError, 'Search URL'):
            v.identity('https://www.douyin.com/search/zipper')
        self.assertNotEqual(v.identity('https://youtube.com/watch?v=a'), v.identity('https://youtube.com/watch?v=b'))

    def test_budgets_and_nonfinite_data_rejected(self):
        with self.assertRaisesRegex(ValueError, 'candidate budget'):
            v.analyze(self.data([self.candidate(i) for i in range(31)]))
        with self.assertRaisesRegex(ValueError, 'deep-analysis budget'):
            v.analyze(self.data([self.candidate(i) for i in range(11)]))
        c = self.candidate(); c['likes'] = float('nan')
        with self.assertRaises(ValueError): v.analyze(self.data([c]))

    def test_changed_evidence_invalidates_full_view_and_score(self):
        c = self.candidate(); self.path.write_text('changed')
        self.assertFalse(v.full_view(c))
        self.assertNotIn('engagement', v.score_candidate(c)['available'])

    def test_analysis_preserves_per_video_task_binding(self):
        data = self.data([self.candidate()])
        data['task_id'] = 'video-123'
        self.assertEqual(v.analyze(data)['task_id'], 'video-123')

    def test_recreation_requires_selected_primary_and_complete_timed_mapping(self):
        research = {'selected_ids': ['1'], 'primary_reference_id': '1', 'candidates': [self.candidate()]}
        blueprint = {
            'shots': [{'shot_id': 's1'}, {'shot_id': 's2'}],
            'reference_principles': [{'reference_id': '1'}],
            'reference_recreation': {'primary_reference_id': '1', 'shot_mapping': [
                {'shot_id': 's1', 'reference_time_range': [0, 3], 'adaptation': 'Opening'},
                {'shot_id': 's2', 'reference_time_range': [3, 30], 'adaptation': 'Mechanism'}]}}
        v.validate_reference_recreation(blueprint, research)
        for change, error in [
                ('unselected', 'selected observed'), ('missing', 'every production shot'),
                ('duplicate', 'every production shot'), ('out_of_bounds', 'within the observed'),
                ('no_decision', 'adaptation decision')]:
            bad = copy.deepcopy(blueprint)
            recreation = bad['reference_recreation']
            if change == 'unselected': recreation['primary_reference_id'] = 'other'
            elif change == 'missing': recreation['shot_mapping'].pop()
            elif change == 'duplicate': recreation['shot_mapping'][1]['shot_id'] = 's1'
            elif change == 'out_of_bounds': recreation['shot_mapping'][1]['reference_time_range'] = [3, 31]
            else: recreation['shot_mapping'][1]['adaptation'] = ' '
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, error):
                v.validate_reference_recreation(bad, research)

    def test_ordinary_reference_can_replace_breakout_without_false_label(self):
        rows = [self.candidate(i) for i in range(3)]
        rows[1].update(reference_class='B', transfer_rationale='mechanism')
        rows[2].update(reference_class='C', transfer_rationale='narrative')
        qualified = v.analyze(self.data(rows))
        self.assertEqual(qualified['status'], 'READY')
        self.assertEqual(qualified['primary_reference_id'], '0')
        self.assertEqual(qualified['primary_reference_kind'], 'verified-breakout')
        rows[0].update(followers=1000000, professional_benchmark=True)
        fallback = v.analyze(self.data(rows))
        self.assertEqual(fallback['status'], 'READY')
        self.assertEqual(fallback['primary_reference_kind'], 'observed-reference')
        data = self.data([self.candidate(0), rows[1], rows[2]])
        data['primary_reference_id'] = '2'
        self.assertEqual(v.analyze(data)['status'], 'BLOCKED')

    def test_physical_video_needs_no_popularity_or_scoring_metadata(self):
        c = self.candidate()
        c.update(followers=None, likes=None, published_at=None,
                 metrics_evidence={}, scores={}, scores_evidence={},
                 style='physical demonstration', source_medium='physical')
        ready = v.analyze(self.data([c]))
        self.assertEqual(ready['status'], 'READY')
        self.assertFalse(ready['breakout_required'])
        self.assertEqual(ready['primary_reference_kind'], 'observed-reference')
        self.assertIsNone(ready['candidates'][0]['breakout_follower_cap'])
        self.assertEqual(ready['candidates'][0]['screening']['coverage'], 0)
        v.validate_viral_analysis(ready)
        ready['primary_reference_kind'] = 'verified-breakout'
        with self.assertRaisesRegex(ValueError, 'Reference kind'):
            v.validate_viral_analysis(ready)

    def test_old_low_interaction_video_is_still_usable(self):
        c = self.candidate()
        c.update(published_at='2020-01-01T00:00:00Z', likes=2, followers=500000)
        result = v.analyze(self.data([c]))
        self.assertEqual(result['status'], 'READY')
        self.assertEqual(result['primary_reference_kind'], 'observed-reference')

    def test_available_breakout_is_preferred_but_observed_reference_can_be_selected(self):
        ordinary = self.candidate(1)
        ordinary['followers'] = None
        result = v.analyze(self.data([ordinary, self.candidate(2)]))
        self.assertEqual(result['primary_reference_id'], '2')
        chosen = self.data([ordinary, self.candidate(2)])
        chosen['primary_reference_id'] = '1'
        self.assertEqual(v.analyze(chosen)['status'], 'READY')

    def test_search_plan_treats_breakout_thresholds_as_preferences(self):
        result = v.plan('指甲刀', '2026-11-11T08:00:00+00:00')
        self.assertFalse(result['breakout_required'])
        self.assertNotIn('published_after', result)
        self.assertIn('breakout_preferences', result)
        self.assertTrue(any('实物演示' in q['keyword'] for q in result['queries']))

    def test_blueprint_requires_actual_evidence_and_contiguous_timing(self):
        b = dict.fromkeys(v.BLUEPRINT_FIELDS, 'decision')
        b.update(status='FROZEN', first_motion_seconds=1,
                 duration_seconds=5,
                 shots=[dict(shot_id='s1', time_range=[0, 5], knowledge_goal='guide', asset='existing',
                             template='motion', feasibility_evidence=self.evidence)],
                 reference_principles=[dict(reference_id='1', principle='spatial continuity', evidence=self.evidence,
                                           production_requirement='hold guide in frame', shot_ids=['s1'],
                                           expected_observable_effect='visible guide', verification_method='actual visual',
                                           minimal_repair='camera only', decision_basis='observation', implementation_cost={'tier': 'low'})],
                 qa_requirements=[dict(requirement_id='q1',shot_id='s1',expected_observable_effect='guide',verification_method='actual visual',minimal_repair='camera')])
        v.validate_creative_blueprint(b)
        bad = copy.deepcopy(b); bad['shots'][0]['time_range'] = [1,5]
        with self.assertRaises(ValueError): v.validate_creative_blueprint(bad)
        b['status'] = 'PROVISIONAL'
        with self.assertRaises(ValueError): v.validate_creative_blueprint(b)


if __name__ == '__main__': unittest.main()
