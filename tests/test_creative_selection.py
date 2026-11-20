from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from mechanical_video_next import creative_selection as editorial
from mechanical_video_next import production_contract as contract
from mechanical_video_next import workflow as w


class CreativeSelectionTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.task = w.create_task('Mechanical object', root=tmp.name, visual_policy_version=2,
                                  media_policy_version=1, contract_version=contract.CREATIVE_SELECTION_VERSION)
        w.advance(self.task, 'RESEARCHING')
        source = self.task / 'reference.txt'
        source.write_text('Test fixture')
        self.binding = dict(path=str(source), sha256=w.filehash(source), position='paragraph 1')
        self.research = {k: w.load(self.task)[k] for k in (contract.FIELD, 'production_contract',
                         'visual_policy_version', 'media_policy_version')}
        self.research.update(science=dict(subject_kind='mechanical_implementation', answer='Two possible stories',
                             question='Why move?', scope='Fixture', facts=[dict(
                                 id='observed', kind='observed', claim='a motion', status='VERIFIED',
                                 scope='Fixture', assumptions=[], sources=[self.binding])]))
        self.research['audience_decision'] = dict.fromkeys(
            contract.CREATIVE_DECISION + ('visual_approach',), 'Specific choice')
        self.research['story_exploration'] = dict(phase='EDITORIAL', selected_id=None, candidates=[
            dict(id=key, question=f'Why {key}?', angle=key, visual_test=f'Test {key}', premise=f'Cause {key}',
                 mechanical_focus=f'Choice {key}', editorial_case='Observed use case', decision_reason='Distinct case',
                 editorial=dict.fromkeys(editorial.EDITORIAL_FIELDS, 'Specific observation') | {'role': 'STANDALONE'},
                 fact_ids=['observed']) for key in ('a', 'b')],
            angles={'a':'Use','b':'Tradeoff'}, editorial_order_reason='A stronger observable comparison')
        for target in ('mechanical_video_next.reference_policy.validate_research',
                       'mechanical_video_next.comprehension.validate_product_research'):
            mock = patch(target)
            mock.start()
            self.addCleanup(mock.stop)
        for target in ('scripts.common.probe', 'mechanical_video_next.visual_narrative.probe'):
            probe = patch(target, return_value={
                'streams': [{'codec_type':'video','duration':'2'}], 'format': {'duration':'2'}})
            probe.start()
            self.addCleanup(probe.stop)
        data = w.load(self.task)
        data['agent_runs'] = [{'role':'Producer','thread_id':'producer'}, {'role':'QA','thread_id':'reviewer'}]
        w.write(self.task/'task.json',data)

    def select(self, choice, *, feasible=True):
        payload = deepcopy(self.research)
        payload['audience_decision']['question'] = f'Why {choice}?'
        story = payload['story_exploration']
        story.update(phase='DECISION', selected_id=choice)
        if choice is None:
            story['stop_reason'] = 'The viable directions were rejected.'
        for row in story['candidates']:
            row['scientific_basis'] = dict(status='VERIFIED', finding='Source describes the action', sources=[self.binding])
            row['production'] = dict(status='READY', approach='Cutaway', finding='Action is visible', evidence=[self.binding])
            if row['id'] == choice and not feasible:
                row['production'] = dict(status='NOT_ASSESSED')
        return w.put_handoff(self.task, 'Producer', 'research', payload)

    def draft(self, story, tag, revision=None, action=None):
        media = self.task / f'{tag}.mp4'
        media.write_text(tag)
        picture = self.task / f'{tag}.json'
        scene = dict.fromkeys(('event','subject','setting','change','focus','camera','transition',
                              'purpose','planned_medium','actual_medium'), 'Specific shot')
        scene.update(id='shot', role='story', time_range=[0,2], sources=[self.binding], event=action or tag)
        plan = dict(story_id=story, scenes=[scene])
        if revision:
            plan['revision'] = dict(review_sha256=revision, story_change='Changed causal comparison')
        w.write(picture,plan)
        media_ref = dict(path=str(media), sha256=w.filehash(media))
        w.put_handoff(self.task,'Producer','diagnostic-animatic',dict(status='DRAFT_UNAPPROVED',media=[media_ref],
            blueprint_evidence=dict(path=str(picture),sha256=w.filehash(picture))),['research'])
        return media_ref

    def review(self, story, media, outcome, reviewer='reviewer'):
        verdict = dict(outcome=outcome, story_id=story, method='sampled_frames', reason='Located finding',
            capability_boundary='Fixture samples', findings=dict.fromkeys(editorial.QUESTIONS,'Specific finding'),
            next_step='Show a different cause', evidence=dict(media_sha256=media['sha256'], time_range=[0,2],
            observation='Missing comparison'))
        visual = dict(status='UNKNOWN',method='sampled_frames',observation='One sample')
        issues = [dict(issue_id='light',defect_key='poor-light',severity='major',shot_id='shot',
            time_range=[0,2],evidence='Dark sample',responsible_agent='Animation',suggested_fix='Light part',
            verification_method='New sample')] if outcome == 'LOCAL_REPAIR' else []
        return w.put_handoff(self.task,'QA','diagnostic-qa',dict(media=[media],independent_reviewer=True,
            reviewer_thread_id=reviewer,story_review=verdict,visual_story_review=visual,issues=issues),
            ['diagnostic-animatic'])

    def shortlist(self):
        return w.put_handoff(self.task,'Research','research',self.research)

    def test_order_is_recorded_before_feasibility(self):
        with self.assertRaisesRegex(ValueError,'Register the editorial shortlist'):
            self.select('a')
        self.shortlist()
        with self.assertRaisesRegex(ValueError,'evidenced visual feasibility'):
            self.select('b', feasible=False)
        decision = self.select('b')
        self.assertEqual(decision['payload']['story_exploration']['selected_id'], 'b')
        self.assertEqual(w.load(self.task)['handoffs']['research']['version'],2)

    def test_local_repair_and_sampled_unknown_keep_the_story(self):
        self.shortlist()
        self.select('a')
        media = self.draft('a','original')
        with self.assertRaisesRegex(ValueError,'independent reviewer'):
            self.review('a',media,'LOCAL_REPAIR','producer')
        with self.assertRaisesRegex(ValueError,'separately recorded QA'):
            self.review('a',media,'LOCAL_REPAIR','unregistered')
        with self.assertRaisesRegex(ValueError,'continuous viewing'):
            self.review('a',media,'PASS')
        self.review('a',media,'LOCAL_REPAIR')
        self.assertEqual(w.continuation(self.task)['next_action']['owner'],'Animation')
        self.assertNotIn('creative_history',w.load(self.task))
        media = self.draft('a','local-fix')
        self.review('a',media,'UNKNOWN')
        self.assertEqual(w.continuation(self.task)['next_action']['creative_status'],'UNKNOWN')
        with self.assertRaisesRegex(ValueError,'creative PASS'):
            w.require_visual_story_review(self.task)

    def test_structural_budget_retires_approvals_and_exhausts_shortlist(self):
        self.shortlist()
        self.select('a')
        media = self.draft('a','first')
        first = self.review('a',media,'REVISE_STORY')
        data = w.load(self.task)
        self.assertEqual(set(data['handoffs']),{'research'})
        self.assertEqual(data['state'],'RESEARCHING')
        self.assertTrue((self.task/'handoffs/diagnostic-qa.v1.json').is_file())
        with self.assertRaisesRegex(ValueError,'different visible story actions'):
            self.draft('a','recode',first['sha256'],action='first')
        media = self.draft('a','different-causal-cut',first['sha256'])
        second = self.review('a',media,'REVISE_STORY')
        self.assertEqual(w.continuation(self.task)['next_action']['creative_status'],'RESELECT_STORY')
        with self.assertRaisesRegex(ValueError,'shot repairs'):
            w.repair_attempt(self.task,'obsolete','camera',1)
        with self.assertRaisesRegex(ValueError,'vetoed story'):
            self.draft('a','retry',second['sha256'])
        self.select('b')
        media = self.draft('b','new-story',second['sha256'])
        self.review('b',media,'RESELECT_STORY')
        self.select(None)
        self.assertEqual(w.continuation(self.task)['next_action']['creative_status'],'SHORTLIST_EXHAUSTED')
