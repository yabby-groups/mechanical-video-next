"""Exercise the default creative vetoes through the existing task and handoff APIs."""
from pathlib import Path
import subprocess
import tempfile
import unittest

from mechanical_video_next import creative_selection as creative
from mechanical_video_next import joint_timeline as joint
from mechanical_video_next import production_contract as contract
from mechanical_video_next import workflow


class StoryDevelopmentTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.task = workflow.create_task(
            'Cabinet latch', root=self.root, visual_policy_version=2, media_policy_version=1, story_development_version=1)
        ledger = workflow.load(self.task)
        self.assertTrue(contract.story_development(ledger))
        self.assertNotIn('reference_search_plan', ledger)
        self.assertIsNone(ledger['asset_strategy'])
        self.assertEqual(ledger['continuation']['next_action']['handoff'], 'research')
        self.policy = {key: ledger[key] for key in (
            contract.FIELD, contract.PRODUCER_DIRECTION, contract.STORY_DEVELOPMENT,
            'production_contract', 'production_method', 'visual_policy_version', 'media_policy_version',
        )}
        ledger['agent_runs'] = [dict(role='Producer', thread_id='producer'),
                                dict(role='QA', thread_id='independent')]
        workflow.write(self.task / 'task.json', ledger)
        source = self.root / 'instructions.txt'
        source.write_text('The sloped catch retracts when it meets the strike.')
        evidence = dict(joint.binding(source), position='Installation paragraph')
        fact = dict(id='slope', status='VERIFIED', kind='observed',
                    claim=source.read_text(), scope='One cabinet catch', assumptions=[],
                    sources=[evidence])
        self.research = dict(self.policy, mechanism_id='latch', science=dict(
            subject_kind='mechanical_implementation', question='Why does it catch?',
            answer=fact['claim'], scope=fact['scope'], facts=[fact]),
            design_research={key: dict(fact_ids=['slope'], finding=fact['claim'])
                             for key in contract.DESIGN_RESEARCH},
            references=[dict(id='instructions', mechanism_id='latch', location=str(source),
                             source_name='Instructions', author='Fixture', type='manual',
                             acquired_at='2026-11-21', viewed_scope=dict(
                                 status='DOCUMENT_READ', evidence=evidence),
                             structure_evidence='Sloped catch', motion_evidence='Retraction',
                             license='REFERENCE_ONLY', usable_content='Verified orientation',
                             unknowns=[], conflicts=[], unresolved_core_conflict=False)])
        self.treatment = dict.fromkeys(creative.TREATMENT_FIELDS, 'The slope makes the closure automatic.')
        self.treatment.update(positioning='拆开机器，看见发明背后的智慧。', question='Why does it catch?',
                              user_requirements=['Keep the scene causal'],
                              scenes=[dict(id='counter', visual_form='Original experiment',
                                           visible_change='The door stays shut after release',
                                           story_purpose='See the restraint',
                                           causal_link='Follow the restraint back to the contact',
                                           fact_ids=['slope'])])

    def put(self, role, name, payload, *deps):
        return workflow.put_handoff(self.task, role, name, payload, deps)

    def prepare(self):
        self.put('Producer', 'research', self.research)
        self.put('Producer', 'story-treatment', self.treatment, 'research')

    @staticmethod
    def review(status, method='document_review', reviewer='independent'):
        findings = {key: dict(status='PASS', observation='Fixture observation',
                              location='Counter scene') for key in creative.CREATIVE_CRITERIA}
        findings['design_story']['status'] = status
        return dict(independent_reviewer=True, reviewer_thread_id=reviewer,
                    creative_decision=dict(status=status, method=method, findings=findings,
                                           revision='Change the design progression.'))

    def draft(self, name):
        media = self.root / f'{name}.mp4'
        subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i',
                        f'color=c={name}:size=160x90:rate=30', '-frames:v', '30',
                        '-c:v', 'libx264', str(media)], check=True)
        path = self.root / 'draft.json'
        workflow.write(path, dict(timeline=dict(frame_count=30, narration=[], actions=[],
                                               shots=[dict(id='test', start_frame=0, end_frame=30,
                                                           silence_reason='Isolate the picture test')])))
        return dict(status='DRAFT_UNAPPROVED', media=[joint.binding(media)],
                    blueprint_evidence=joint.binding(path), story_treatment_sha256=workflow.digest(
                        workflow.artifact(self.task, 'story-treatment')))

    def test_default_requires_design_findings_and_independent_story_pass(self):
        with self.assertRaisesRegex(ValueError, 'historical_context'):
            research = dict(self.research, design_research={
                key: val for key, val in self.research['design_research'].items() if key != 'historical_context'})
            self.put('Producer', 'research', research)
        self.prepare()
        with self.assertRaisesRegex(ValueError, 'independent QA reviewer'):
            self.put('QA', 'story-qa', self.review('PASS', reviewer='producer'), 'story-treatment')
        self.put('QA', 'story-qa', self.review('REJECT'), 'story-treatment')
        draft = self.draft('red')
        with self.assertRaisesRegex(ValueError, 'story-qa requires PASS'):
            self.put('Producer', 'diagnostic-animatic', draft, 'research', 'story-treatment', 'story-qa')
        with self.assertRaisesRegex(ValueError, 'vetoed story'):
            self.put('Producer', 'story-treatment', dict(self.treatment, metadata='new'), 'research')

    def test_visual_unknown_holds_formal_work_and_reject_returns_to_story(self):
        self.prepare()
        self.put('QA', 'story-qa', self.review('PASS'), 'story-treatment')
        draft = self.draft('blue')
        self.put('Producer', 'diagnostic-animatic', draft, 'research', 'story-treatment', 'story-qa')
        report = dict(self.review('PASS', 'sampled_frames'), media=draft['media'])
        with self.assertRaisesRegex(ValueError, 'viewing the complete'):
            self.put('QA', 'diagnostic-qa', report, 'diagnostic-animatic')
        report = dict(self.review('UNKNOWN', 'sampled_frames'), media=draft['media'])
        self.put('QA', 'diagnostic-qa', report, 'diagnostic-animatic')
        with self.assertRaisesRegex(ValueError, 'diagnostic-qa requires PASS'):
            self.put('CAD', 'cad-model', {}, 'research', 'diagnostic-qa')
        report = dict(self.review('REJECT', 'sampled_frames'), media=draft['media'])
        self.put('QA', 'diagnostic-qa', report, 'diagnostic-animatic')
        self.assertEqual(workflow.continuation(self.task, False)['next_action']['handoff'], 'story-treatment')
        with self.assertRaisesRegex(ValueError, 'revised Treatment'):
            self.put('QA', 'story-qa', self.review('PASS'), 'story-treatment')
        with self.assertRaisesRegex(ValueError, 'revised Treatment'):
            self.put('Producer', 'diagnostic-animatic', self.draft('green'),
                     'research', 'story-treatment', 'story-qa')
        self.put('Producer', 'story-treatment', dict(self.treatment, conflict='The catch jams with a flat edge'),
                 'research')
        with self.assertRaisesRegex(ValueError, 'Stale dependency'):
            workflow.artifact(self.task, 'story-qa')

    def test_visual_revise_requires_new_media_then_pass_unlocks_next_stage(self):
        self.prepare()
        self.put('QA', 'story-qa', self.review('PASS'), 'story-treatment')
        draft = self.draft('blue')
        self.put('Producer', 'diagnostic-animatic', draft, 'research', 'story-treatment', 'story-qa')
        report = dict(self.review('REVISE', 'sampled_frames'), media=draft['media'])
        self.put('QA', 'diagnostic-qa', report, 'diagnostic-animatic')
        self.assertEqual(workflow.continuation(self.task, False)['next_action']['handoff'], 'diagnostic-animatic')
        with self.assertRaisesRegex(ValueError, 'vetoed moving picture'):
            self.put('Producer', 'diagnostic-animatic', draft, 'research', 'story-treatment', 'story-qa')
        revision = self.draft('green')
        self.put('Producer', 'diagnostic-animatic', revision, 'research', 'story-treatment', 'story-qa')
        report = dict(self.review('PASS', 'continuous_video'), media=revision['media'])
        report['creative_decision']['covered_seconds'] = 1
        self.put('QA', 'diagnostic-qa', report, 'diagnostic-animatic')
        workflow.require_visual_story_review(self.task)
        self.assertEqual(workflow.continuation(self.task, False)['next_action']['handoff'], 'asset-plan')

    def test_current_scope_keeps_user_question_and_core_native_3d(self):
        approved = 'Why does this latch return?'
        self.task = workflow.create_task(
            'Cabinet latch', root=self.root, visual_policy_version=2, media_policy_version=1,
            core_question=approved)
        ledger = workflow.load(self.task)
        self.assertTrue(contract.mechanism_first(ledger))
        self.assertEqual(ledger['mechanical_object'], 'Cabinet latch')
        self.assertEqual(ledger['core_question'], approved)
        science = self.research['science']
        self.research[contract.STORY_DEVELOPMENT] = 2
        self.research['mechanical_object'] = 'Door lock cylinder'
        with self.assertRaisesRegex(ValueError, 'requested mechanical object'):
            self.put('Producer', 'research', self.research)
        self.research['mechanical_object'] = 'Cabinet latch'
        with self.assertRaisesRegex(ValueError, 'core question'):
            self.put('Producer', 'research', self.research)
        science['question'] = approved
        self.research.pop('design_research')
        self.put('Producer', 'research', self.research)
        self.treatment.update(question=approved, mechanical_object='Cabinet latch',
                              positioning=contract.POSITIONING)
        core = self.treatment['scenes'][0]
        core.update(mechanical_role='core', render_engine='remotion')
        with self.assertRaisesRegex(ValueError, 'source-supported Blender'):
            self.put('Producer', 'story-treatment', self.treatment, 'research')
        core['render_engine'] = 'blender'
        self.put('Producer', 'story-treatment', self.treatment, 'research')

        reviewer = dict(role='QA', thread_id='independent')
        ledger = workflow.load(self.task)
        ledger['agent_runs'] = [reviewer]
        workflow.write(self.task / 'task.json', ledger)
        review = self.review('PASS')
        findings = {key: dict(status='PASS', observation='Fixture observation', location='Counter')
                    for key in creative.MECHANICAL_CRITERIA}
        review['creative_decision']['findings'] = findings
        findings['internal_3d']['status'] = 'REVISE'
        review['creative_decision']['status'] = 'REVISE'
        with self.assertRaisesRegex(ValueError, 'requires REJECT'):
            self.put('QA', 'story-qa', review, 'story-treatment')
        findings['internal_3d']['status'] = 'PASS'
        review['creative_decision']['status'] = 'PASS'
        self.put('QA', 'story-qa', review, 'story-treatment')
        with self.assertRaisesRegex(ValueError, 'native Blender scenes'):
            self.put('Producer', 'diagnostic-animatic', self.draft('red'),
                     'research', 'story-treatment', 'story-qa')
