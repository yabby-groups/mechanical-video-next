import copy
from pathlib import Path
import tempfile
import unittest
import wave

from mechanical_video_next import director, joint_timeline as joint
from mechanical_video_next.director_audio import mix, sound_stems
from mechanical_video_next.viral import validate_shot_analysis


def candidate(route, accuracy, *, seconds=2):
    return dict(route=route, basis='The verified mechanism remains visible', accuracy=accuracy,
                expression=4, intent=4, availability=4, style=4,
                estimated_seconds=seconds, estimated_cost=0)


class CreativeDirectorTests(unittest.TestCase):
    def test_visual_selection_checks_scientific_eligibility_before_cost(self):
        self.assertEqual(director.select_route([
            candidate('scientific_visualization', 4, seconds=0),
            candidate('native_3d', 4, seconds=10),
        ], core=True), 'native_3d')
        self.assertEqual(director.select_route([
            candidate('scientific_visualization', 4, seconds=0),
            candidate('native_3d', 4, seconds=10),
        ], core=False), 'scientific_visualization')
        with self.assertRaisesRegex(ValueError, 'scientific'):
            director.select_route([candidate('native_3d', 3)], core=True)
        self.assertEqual(director.select_route([
            candidate('layered_animation', 4, seconds=1), candidate('native_3d', 4, seconds=10),
        ], core=True), 'native_3d')
        self.assertEqual(director.select_route([
            candidate('layered_animation', 4, seconds=1), candidate('native_3d', 4, seconds=10),
        ], core=False), 'layered_animation')

    def test_unchanged_hook_and_explanation_are_not_an_alternative(self):
        treatments = {name: {key: name for key in director.TREATMENT} for name in director.APPROACHES}
        plan = dict(treatments=treatments, selected='mystery', selection_reason='Observable clue')
        self.assertEqual(director.validate_treatments(plan), treatments['mystery'])
        treatments['direct_experiment']['hook'] = treatments['mystery']['hook']
        with self.assertRaisesRegex(ValueError, 'distinct'):
            director.validate_treatments(plan)

    def test_measured_speech_must_cross_the_j_cut(self):
        document = {director.FIELD: 1, 'shots': [
            {'director': {'edits': [dict(kind='j_cut', frame=15, speech_id='line')]}}
        ]}
        receipt = {'speech': [dict(id='line', start_sample=16000, end_sample=28000)]}
        director.validate_measured_edit(document, receipt)
        receipt['speech'][0]['end_sample'] = 20000
        with self.assertRaisesRegex(ValueError, 'does not cross'):
            director.validate_measured_edit(document, receipt)

    def test_presentation_rejects_changed_mechanical_truth(self):
        shot = {'template': 'motion', 'tracks': [{'object': 'Wheel', 'poses': []}]}
        changed = copy.deepcopy(shot)
        changed['tracks'][0]['object'] = 'Another wheel'
        with self.assertRaisesRegex(ValueError, 'mechanical program'):
            director.apply_strategy(changed, {'strategy': 'source_observation'}, 'blender', source=shot)
        with self.assertRaisesRegex(ValueError, 'presentation fields'):
            director.apply_strategy(shot, {'strategy': 'macro_reveal',
                                          'presentation': {'tracks': []}}, 'blender')

    def test_motion_comparison_requires_an_executable_graphic(self):
        with self.assertRaisesRegex(ValueError, 'renderer input'):
            director.apply_strategy({}, {'strategy': 'motion_comparison'}, 'remotion')
        graphic = {'type': 'angular_comparison'}
        compiled = director.apply_strategy({}, {'strategy': 'motion_comparison',
                                                  'presentation': {'graphic': graphic}}, 'remotion')
        self.assertEqual(compiled['graphic'], graphic)

    def test_sound_action_trigger_resolves_exact_samples_and_declared_lead(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            pcm = root / 'sample.wav'
            with wave.open(str(pcm), 'wb') as stream:
                stream.setparams((1, 2, 48000, 0, 'NONE', 'not compressed'))
                stream.writeframes(b'\x50\x00' * 48000)
            proof = root / 'rights.txt'
            proof.write_text('Owned Foley fixture')
            plan = dict(frame_count=30, shots=[], actions=[dict(id='contact', start_frame=12, end_frame=20)])
            event = dict(action_id='contact', offset_frames=1, lead_frames=2, duration_frames=3,
                         gain_db=-12, purpose='Paper enters the next shot', source=joint.binding(pcm),
                         source_type='OWNED', license_status='VERIFIED', credit='Studio', usage_restrictions=[],
                         license=dict(status='VERIFIED', name='Owned', holder='Studio',
                                      editing_and_distribution=True, commercial_use=True,
                                      proof=joint.binding(proof) | {'position': 'Ownership'}))
            stem = sound_stems(plan, [event])[0]
            self.assertEqual((stem['start_sample'], stem['end_sample']), (17600, 22400))
            mixed = mix(plan, [event], pcm, root/'mixed.wav')
            self.assertEqual(joint.pcm_frames(joint.bound(mixed['master'])), 48000)
            self.assertNotEqual(joint.binding(pcm)['sha256'], mixed['master']['sha256'])
            with self.assertRaisesRegex(ValueError, 'outside'):
                sound_stems(plan, [event | {'offset_frames': 9}])

    def test_reference_audio_requires_evidence_and_shots_require_viewed_coverage(self):
        with tempfile.TemporaryDirectory() as folder:
            note = Path(folder)/'observation.txt'
            note.write_text('Fixture observation')
            segment = dict(id='wide', time_range=[3, 4], composition='wide', subject_motion='rotation',
                           camera_motion='held', reveal='moving wheel', edit='hard cut', style='diagram')
            candidate = {'viewing': dict(status='PARTIAL_VIDEO_VIEWED', time_ranges=[[2, 5]],
                                         evidence=[joint.binding(note)]), 'shot_analysis': [segment]}
            validate_shot_analysis(candidate)
            segment['sound'] = 'Rattle'
            with self.assertRaisesRegex(ValueError, 'listening evidence'):
                validate_shot_analysis(candidate)
            segment.update(sound=None, time_range=[1, 4])
            with self.assertRaisesRegex(ValueError, 'observed sequence'):
                validate_shot_analysis(candidate)
