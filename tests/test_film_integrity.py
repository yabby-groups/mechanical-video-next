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

    def wav(self, name, duration):
        path = self.root / (name + '.wav')
        subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i',
                        f'sine=f=440:r=48000:d={duration}', str(path)], check=True)
        return path

    def encode(self, name, audio, *, duration=1, extra=()):
        path = self.root / (name + '.mp4')
        subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i',
                        f'testsrc2=s=160x90:r=30:d={duration}', '-i', str(audio),
                        '-c:v', 'libx264', '-c:a', 'aac', *extra, str(path)], check=True)
        return path

    def test_overlong_measured_speech_does_not_change_approved_cut(self):
        utterance = self.wav('overrun', .41)
        with self.assertRaisesRegex(ValueError, 'Revise the dialogue'):
            joint.measure(self.plan, lambda text: (utterance, {}), self.root / 'master.wav')
        self.assertFalse((self.root / 'master.wav').exists())

    def test_last_line_truncation_fails_even_with_a_full_duration_aac_track(self):
        utterance = self.wav('line', .32)
        master = self.root / 'master.wav'
        measured = joint.measure(self.plan, lambda text: (utterance, {}), master)
        intact = self.encode('intact', master)
        joint.validate_rendered_audio(intact, self.plan, measured)
        clipped = self.encode('clipped', master, extra=('-af', "volume=0:enable='gte(t,0.65)'"))
        joint.validate_rendered_film(clipped, self.plan)
        with self.assertRaisesRegex(ValueError, 'differs from the bound audio'):
            joint.validate_rendered_audio(clipped, self.plan, measured)

    def test_shortest_output_and_missing_actual_payoff_fail(self):
        short = self.wav('short', .4)
        full = self.wav('full', 1)
        for video in (self.encode('shortest', short, extra=('-shortest',)),
                      self.encode('payoff-missing', full, duration=.7)):
            with self.subTest(video=video.name), self.assertRaisesRegex(ValueError, 'picture clock'):
                joint.validate_rendered_film(video, self.plan)

    def test_nominal_runtime_and_frame_count_can_hide_shifted_picture_times(self):
        full = self.wav('full', 1)
        video = self.encode('shifted', full, extra=(
            '-vf', "settb=1/90000,setpts=PTS+if(eq(N\\,10)\\,40\\,0)",
            '-fps_mode', 'passthrough', '-enc_time_base', '1:90000',
        ))
        with self.assertRaisesRegex(ValueError, 'Decoded picture timestamps'):
            joint.validate_rendered_film(video, self.plan)

    def test_remotion_rejects_disagreeing_composition_duration_before_render(self):
        props = self.root / 'props.json'
        props.write_text(json.dumps(dict(frameCount=30, fps=30, duration=.5, shots=[dict(seconds=1)])))
        with self.assertRaisesRegex(ValueError, 'composition duration'):
            remotion_build.render(props, self.root / 'out.mp4', self.root / 'render.log')
