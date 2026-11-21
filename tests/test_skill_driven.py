import copy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from mechanical_video_next import blueprint, joint_timeline as joint, production_contract as contract
from mechanical_video_next import visual_narrative as visual, workflow
from scripts.common import writejson


class SkillDrivenTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.task = workflow.create_task(
            'Spring latch', root=self.root, visual_policy_version=2,
            media_policy_version=1, skill_driven_pilot=True, story_development_version=0)
        task = workflow.load(self.task)
        self.policy = {key: task[key] for key in (
            contract.FIELD, contract.PRODUCER_DIRECTION, 'production_contract',
            'production_method', 'visual_policy_version', 'media_policy_version',
        )}
        source = self.root / 'manual.txt'
        source.write_text('Beveled face approaches the strike.')
        self.evidence = dict(joint.binding(source), position='Installation instructions')
        fact = dict(id='bevel', status='VERIFIED', kind='observed',
                    claim=source.read_text(), sources=[self.evidence], scope='Latch orientation',
                    assumptions=[])
        self.research = dict(self.policy, mechanism_id='latch', science=dict(
            subject_kind='mechanical_implementation', question='Why does it catch?',
            answer=fact['claim'], scope='Passage latch', facts=[fact]), references=[dict(
                id='manual', mechanism_id='latch', location=str(source), source_name='Instructions',
                author='Manufacturer', type='manual', acquired_at='2026-11-21',
                viewed_scope=dict(status='DOCUMENT_READ', evidence=self.evidence),
                structure_evidence='Door edge and strike', motion_evidence='Closing orientation',
                license='REFERENCE_ONLY', usable_content='Verified source fact',
                unknowns=[], conflicts=[], unresolved_core_conflict=False)])

    def test_new_task_has_no_required_reference_search_or_director_treatments(self):
        historical = workflow.create_task(
            'Legacy default', root=self.root, visual_policy_version=2, media_policy_version=1,
            story_development_version=0)
        task = workflow.load(self.task)
        self.assertNotIn('reference_search_plan', task)
        self.assertNotIn('creative_direction_version', task)
        self.assertTrue(task['film_integrity_version'])
        self.assertTrue(task['video_review_version'])
        self.assertEqual(workflow.continuation(self.task, False)['next_action']['handoff'], 'research')
        self.assertEqual(workflow.continuation(historical, False)['next_action']['handoff'], 'viral-analysis')
        with self.assertRaisesRegex(ValueError, 'production method'):
            workflow.put_handoff(self.task, 'Producer', 'research',
                                 dict(self.research, production_method=contract.PRODUCER_DIRECTED))
        workflow.put_handoff(self.task, 'Producer', 'research', self.research)
        self.assertEqual(workflow.continuation(self.task, False)['next_action']['handoff'], 'diagnostic-animatic')
        with self.assertRaisesRegex(ValueError, 'Missing handoff: diagnostic-qa'):
            workflow.check_qa(self.task, 'preview-qa')

    def test_blueprint_observation_ids_are_authored_but_forward_links_are_checked(self):
        action = dict(id='contact', knowledge_id='bevel', start_frame=1, end_frame=27)
        cut = dict(id='same-room', start_frame=0, end_frame=30, action_views={'contact': 1})
        shot = dict(shot_id=cut['id'], mechanical_role='core', knowledge_ids=['bevel'])
        moment = dict(shot_id=cut['id'], start_frame=3, end_frame=20, observable='Watch the contact',
                      mechanical_event_id=action['id'], knowledge_id='bevel')
        data = dict(self.policy, core_question='Why does it catch?', shots=[shot],
                    timeline=dict(frame_count=30, film_integrity_version=1,
                                  shots=[cut], narration=[], actions=[action]),
                    narrative=dict(question='Why does it catch?', answer='See the two faces.',
                                   moments={'angle-compare': moment}))
        contract.validate_direction(data, self.research)
        with self.assertRaisesRegex(ValueError, 'Bind opening'):
            contract.validate_direction(dict(data, production_method=contract.PRODUCER_DIRECTED))
        altered = copy.deepcopy(data)
        altered['timeline']['shots'][0]['action_views'] = {}
        with self.assertRaisesRegex(ValueError, 'Core mechanical shot lacks'):
            contract.validate_direction(altered, self.research)

    def test_visual_expression_is_open_and_an_editorial_layer_cannot_prove_motion(self):
        shot = dict(visual_type='fictional corridor', knowledge_goal='Introduce a place',
                    visual_focus='Threshold', visual_action='A shadow moves',
                    render_engine='remotion', mechanical_role='support', assets=[],
                    knowledge_ids=[], evidence=[self.evidence], duration=1,
                    camera=dict(scale='wide', angle='Straight on'))
        visual.validate_design(shot, hybrid=True, flexible=True)
        self.assertEqual(visual.editorial_props({'visual': shot}), {})
        with self.assertRaises(ValueError):
            visual.validate_design(shot, hybrid=True)
        with self.assertRaisesRegex(ValueError, 'Core mechanical action'):
            visual.validate_design(dict(shot, mechanical_role='core'), hybrid=True, flexible=True)

    def test_real_draft_clock_and_qa_dependencies(self):
        workflow.put_handoff(self.task, 'Producer', 'research', self.research)
        mp4 = self.root / 'draft.mp4'
        subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i',
                        'testsrc2=size=160x90:rate=30', '-frames:v', '30',
                        '-c:v', 'libx264', str(mp4)], check=True)
        draft = self.root / 'draft.json'
        cut = dict(id='spatial-test', start_frame=0, end_frame=30,
                   silence_reason='Hold on the moving test rig.')
        timeline = dict(frame_count=30, shots=[cut], narration=[], actions=[])
        writejson(draft, dict(timeline=timeline))
        payload = dict(status='DRAFT_UNAPPROVED', media=[joint.binding(mp4)],
                       blueprint_evidence=joint.binding(draft))
        workflow.put_handoff(self.task, 'Producer', 'diagnostic-animatic', payload, ['research'])
        self.assertEqual(workflow.continuation(self.task, False)['milestone'], 'STORY_PREVIEW_RENDERED')
        review = dict(media=payload['media'], reviewer_thread_id='reviewer-thread',
                      independent_reviewer=True, visual_story_review=dict(
                          status='UNKNOWN', observation='Sample only', method='sampled_frames'))
        workflow.put_handoff(self.task, 'QA', 'diagnostic-qa', review, ['diagnostic-animatic'])
        with self.assertRaisesRegex(ValueError, 'must pass before HD'):
            workflow.check_qa(self.task, 'preview-qa')
        writejson(draft, dict(timeline=dict(timeline, frame_count=31, shots=[dict(cut, end_frame=31)])))
        self.assertRaises(ValueError, workflow.artifact, self.task, 'diagnostic-qa')
        with self.assertRaises(ValueError):
            blueprint.validate_story_preview(json.loads(draft.read_text()), payload['media'])


if __name__ == '__main__':
    unittest.main()
