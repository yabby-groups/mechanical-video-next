from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from mechanical_video_next import visual_narrative as visual, workflow


class VisualStoryDirectionTests(unittest.TestCase):
    def test_a_still_hold_can_serve_an_observation_and_a_fallback_discloses_the_gap(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp)/'reference.txt'
            source.write_text('Scoped teaching example')
            evidence = {'path': str(source), 'sha256': workflow.filehash(source), 'position': 'Example'}
            story = dict(
                id='observation', role='story', event='A fixed observation',
                subject='Coin', setting='Water tank', change='Hold the original position for comparison',
                focus='Rim', camera='Fixed view', transition='Return to the same vessel',
                purpose='Establish what is concealed', planned_medium='3D refraction',
                actual_medium='3D refraction', time_range=[0, 2], sources=[evidence],
            )
            explanation = story | dict(id='explanation', role='explanation', time_range=[2, 4])
            plan = {'scenes': [story, explanation]}
            media = [{'path': 'picture.mp4'}]
            picture = {'streams': [{'codec_type': 'video', 'duration': '4'}]}
            with patch.object(visual, 'probe', return_value=picture):
                with self.assertRaisesRegex(ValueError, 'carry'):
                    visual.validate_scene_direction(plan, media)
                explanation.update(carry='Use the identical rim to locate the crossing point')
                self.assertEqual(visual.validate_scene_direction(plan, media), [])
                story['actual_medium'] = 'static diagram'
                with self.assertRaisesRegex(ValueError, 'replaced'):
                    visual.validate_scene_direction(plan, media)
                story.update(substitution_reason='Renderer startup failed', capability_gap='Coin reveal is absent')
                self.assertEqual(visual.validate_scene_direction(plan, media), ['observation'])

    def test_new_task_pre_voice_gate_requires_complete_picture_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            task = workflow.create_task('Optical phenomenon', root=root, visual_policy_version=2,
                                        media_policy_version=1)
            self.assertTrue(visual.scene_direction_enabled(workflow.load(task)))
            with self.assertRaisesRegex(ValueError, 'Missing handoff: diagnostic-animatic'):
                workflow.require_visual_story_review(task)
        with self.assertRaisesRegex(ValueError, 'continuous viewing'):
            visual.validate_scene_review(dict(status='PASS', method='sampled_frames',
                                              observation='Sampled the reveal'))
        self.assertEqual(visual.validate_scene_review(dict(status='UNKNOWN', method='sampled_frames',
                                                          observation='Sampled the reveal')), 'UNKNOWN')


if __name__ == '__main__':
    unittest.main()
