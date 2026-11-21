import copy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from mechanical_video_next import director, joint_timeline as joint, production_contract as story, remotion_build


class FilmIntegrityTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        source = self.root / 'driver.json'
        source.write_text('Verified source program fixture')
        binding = joint.binding(source)
        self.native = {'template': 'state_transition', 'seconds': 1,
                       'tracks': [{'object': 'Valve', 'poses': [{'progress': 0, 'location': [0, 0, 0]},
                                                               {'progress': 1, 'location': [1, 0, 0]}]}],
                       'science': {'driver': 'data_tracks', 'constraints': ['positive stroke']}}
        checksum = director.action_program_digest(self.native)
        self.action = dict(id='open', start_frame=3, end_frame=27, source_start_frame=3, source_end_frame=27,
                           start_state='closed', end_state='open', curve='linear', constraints=['positive stroke'],
                           input='push', direction='positive x', transmission='stem carries valve',
                           intermediate_state='partly open', contact='lifts off seat', knowledge_id='valve',
                           source=binding, evidence=dict(binding, position='Stroke specification'),
                           shot_programs={'wide': checksum, 'detail': checksum})
        self.plan = dict(film_integrity_version=1, frame_count=30, actions=[self.action],
                         shots=[dict(id='wide', start_frame=0, end_frame=15, action_views={'open': 3}),
                                dict(id='detail', start_frame=15, end_frame=30, source_start_frame=15,
                                     action_views={'open': 15})],
                         narration=[dict(id='setup', text='Watch the valve', start_frame=0, deadline_frame=12,
                                         knowledge_ids=['valve']),
                                    dict(id='end', text='The valve opens', start_frame=15, deadline_frame=30,
                                         knowledge_ids=['valve'])])
        self.config = dict(timeline=self.plan, storyboard=[dict(id=sid, shot=sid) for sid in ('wide', 'detail')],
                           shots={sid: copy.deepcopy(self.native) for sid in ('wide', 'detail')})

    def test_reversed_mechanical_driver_and_changed_constraint_are_rejected(self):
        director.validate_action_programs(self.config)
        for field, value in (('tracks', list(reversed(self.native['tracks'][0]['poses']))),
                             ('constraints', ['allow reverse stroke'])):
            with self.subTest(field=field):
                config = copy.deepcopy(self.config)
                shot = config['shots']['detail']
                if field == 'tracks':
                    for pose, previous in zip(shot['tracks'][0]['poses'], value, strict=True):
                        pose['location'] = previous['location']
                else:
                    shot['science']['constraints'] = value
                with self.assertRaisesRegex(ValueError, 'Mechanical program changed'):
                    director.validate_action_programs(config)

    def test_time_map_compression_and_source_cutoff_are_rejected(self):
        for mapping in ([[0, 0], [.25, .6], [1, 1]], [[0, 0], [.5, .75], [.75, .25], [1, 1]]):
            with self.subTest(mapping=mapping):
                self.config['shots']['wide']['science']['time_map'] = mapping
                with self.assertRaisesRegex(ValueError, 'Time map changes'):
                    director.validate_action_programs(self.config)
        self.action['end_frame'] = 23
        with self.assertRaisesRegex(ValueError, 'truncated'):
            joint.validate(self.plan)

    def test_same_event_cannot_restart_at_camera_cut(self):
        joint.validate(self.plan)
        self.plan['shots'][1].update(source_start_frame=0, action_views={'open': 0})
        with self.assertRaisesRegex(ValueError, 'Action clock discontinuity'):
            joint.validate(self.plan)

    def test_distinct_native_programs_cannot_claim_the_same_action_clock(self):
        detail = self.config['shots']['detail']
        detail['tracks'][0]['poses'][0]['location'] = [0.3, 0, 0]
        self.action['shot_programs']['detail'] = director.action_program_digest(detail)
        joint.validate(self.plan)
        with self.assertRaisesRegex(ValueError, 'native program and clock across cuts'):
            director.validate_action_programs(self.config)

    def test_relabeling_a_restarted_native_clock_cannot_hide_the_reset(self):
        self.plan['shots'][1].update(source_start_frame=0, source_clock_origin=15)
        joint.validate(self.plan)
        with self.assertRaisesRegex(ValueError, 'native program and clock across cuts'):
            director.validate_action_programs(self.config)

    def test_missing_mechanical_explanation_fails_story_lock(self):
        shots = [dict(shot_id=sid, mechanical_role='core', knowledge_ids=['valve'],
                      direction=dict.fromkeys(story.DIRECTION, 'Inspect the valve')) for sid in ('wide', 'detail')]
        moments = {}
        for key, sid, start, end in [('opening', 'wide', 0, 3), ('first_discovery', 'wide', 3, 7),
                                     ('causal_reveal', 'wide', 7, 11), ('scientific_explanation', 'wide', 11, 15),
                                     ('action_result', 'detail', 17, 22), ('payoff', 'detail', 22, 27)]:
            moments[key] = dict(shot_id=sid, start_frame=start, end_frame=end, observable='See the valve',
                                knowledge_id='valve', visual_evidence='Valve leaves its seat')
            if key in {'causal_reveal', 'action_result'}:
                moments[key]['mechanical_event_id'] = 'open'
        blueprint = dict(timeline=self.plan, shots=shots, core_question='Why does it open?')
        narrative = dict(question=blueprint['core_question'], moments=moments)
        story.validate_story_moments(blueprint, narrative)
        moments['causal_reveal'].pop('mechanical_event_id')
        with self.assertRaisesRegex(ValueError, 'causal_reveal'):
            story.validate_story_moments(blueprint, narrative)
