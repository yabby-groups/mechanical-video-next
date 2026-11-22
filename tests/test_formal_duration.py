"""Formal runtime applies to full edits and preserves historical tasks."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from mechanical_video_next import blueprint, growth, joint_timeline, production_contract, workflow


class FormalDurationTests(unittest.TestCase):
    def setUp(self):
        folder = TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.new = dict(formal_duration_version=1)

    def test_formal_create_uses_default_range_and_optional_target(self):
        def create(**kwargs):
            return workflow.load(workflow.create_task(
                'Door handle', root=self.root, visual_policy_version=2,
                media_policy_version=1, **kwargs))

        ledger = create()
        self.assertEqual(ledger['formal_duration_version'], 1)
        self.assertEqual(ledger['growth_policy_version'], 2)
        self.assertEqual(ledger['duration_policy'], dict(minimum=120, maximum=300,
                         mode='knowledge-driven', requested_seconds=None))
        for invalid in (119.99, 300.01):
            with self.assertRaisesRegex(ValueError, '120–300'):
                create(duration=invalid)
        for boundary in (120, 300):
            self.assertEqual(create(duration=boundary)['duration'], boundary)

    def test_complete_animatic_gate_excludes_short_clock(self):
        def draft(frame_count):
            return {'timeline': dict(frame_count=frame_count, narration=[], actions=[],
                       shots=[dict(id='test', start_frame=0, end_frame=frame_count,
                                   silence_reason='Observe the mechanism')])}
        media = [{'path': str(self.root / 'workprint.mp4')}]
        with patch.object(joint_timeline, 'validate_rendered_film') as check:
            for invalid in (627, 3599, 9001):
                with self.assertRaisesRegex(ValueError, '120–300'):
                    blueprint.validate_story_preview(draft(invalid), media, task=self.new)
            check.assert_not_called()
            for valid in (3600, 9000):
                blueprint.validate_story_preview(draft(valid), media, task=self.new)
            blueprint.validate_story_preview(draft(627), media, task={})
            self.assertEqual(check.call_count, 3)

    def test_final_checks_the_encoded_picture_duration_and_codec(self):
        movie = self.root / 'final.mp4'
        movie.write_bytes(b'fixture')
        path = self.root / 'timeline.json'
        path.write_text(json.dumps(dict(duration_seconds=120, shots=[dict(id='chapter')])))
        task = dict(self.new, duration_policy=dict(minimum=120, maximum=300),
                    shared_production=dict(timeline=joint_timeline.binding(path)))
        media = dict(joint_timeline.binding(movie), chapter_ids=['chapter'])
        video = dict(codec_type='video', width=1920, height=1080, avg_frame_rate='30/1',
                     codec_name='h264', duration='119.96667')
        audio = dict(codec_type='audio', codec_name='aac', duration='120.0')
        with patch('mechanical_video_next.multiroute.probe', return_value=dict(streams=[video, audio])):
            with self.assertRaisesRegex(ValueError, '120–300'):
                workflow.complete_media(task, media)
            video['duration'] = '120'
            self.assertEqual(workflow.complete_media(task, media)['duration'], 120)
            audio['codec_name'] = 'opus'
            with self.assertRaisesRegex(ValueError, 'H.264 video and AAC'):
                workflow.complete_media(task, media)

    def test_existing_media_and_diagnostics_keep_their_own_clocks(self):
        task = workflow.load(workflow.create_task(
            'Archived fixture', duration=20.9, visual_policy_version=2,
            media_policy_version=1, story_development_version=1, root=self.root))
        self.assertNotIn('formal_duration_version', task)
        production_contract.validate_formal_duration(task, 20.9)
        self.assertEqual(growth.duration_bounds(self.new), (120, 300))

    def test_all_five_growth_decisions_are_required(self):
        decisions = {key: 'Specific authored decision' for key in growth.GOALS_V2}
        growth.validate_growth_design(decisions)
        decisions.pop('comment')
        with self.assertRaisesRegex(ValueError, 'comment'):
            growth.validate_growth_design(decisions)
