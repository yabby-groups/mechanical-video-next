import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from mechanical_video_next import episode, episode_evidence as evidence, video_review
from scripts.common import filehash


class EpisodeEvidenceTests(unittest.TestCase):
    def setUp(self):
        workspace = TemporaryDirectory()
        self.addCleanup(workspace.cleanup)
        self.root = Path(workspace.name)
        self.source = self.root / 'research.md'
        self.claim = 'The drive moves the guided output and returns to its rest position.'
        self.source.write_text(self.claim)
        (self.root / 'scene.py').write_text('# scene')
        self.verifier = self.root / evidence.VERIFIER
        self.verifier.write_text('# independent evaluator')
        self.narration = 'The drive moves and returns.'
        (self.root / 'narration.txt').write_text(self.narration)
        self.cut = {'mechanics': {'evidence': 'research.md'}}
        self.relations = {'drive': {'channels': ['position', 'coupling'], 'events': [
            {'ranges': {'position': [.9, 1.1], 'coupling': [-.01, .01]}},
            {'ranges': {'position': [-.01, .01]}},
        ]}}
        self.row = {'kind': 'core', 'relations': self.relations}
        self.plan = {'evidence': {'path': 'research.md', 'sha256': filehash(self.source)},
                     'claims': {'drive': {'quote': self.claim, 'source': 'Fixture',
                                          'expectation': 'Drive, then return to rest.'}},
                     'verifier_sha256': filehash(self.verifier), 'shots': {}}

    def register(self, cut):
        self.plan['shots'][evidence.shot_signature(self.root, cut, 0, self.narration)] = self.row
        (self.root / evidence.PLAN).write_text(json.dumps(self.plan))

    def produce(self, cut):
        (self.root / 'edit.json').write_text(json.dumps({'output': 'film.mp4', 'shots': [cut]}))
        with patch.object(episode, 'measure_narration', return_value=[(None, [], 9)]), \
                patch.object(episode, 'load_env'):
            return episode.produce(self.root, work_dir=self.root, allow_short=True)

    def test_formal_core_needs_evaluation_even_if_renamed_auxiliary_or_omitted(self):
        self.register(self.cut)
        for cut in ({}, {'kind': 'auxiliary'}, dict(self.cut, name='Exterior detail', kind='display')):
            with self.subTest(cut=cut), patch.object(episode, 'picture_sources') as pictures:
                with self.assertRaisesRegex(ValueError, 'mechanical_coverage_unreviewed'):
                    self.produce(cut)
                pictures.assert_not_called()

    def test_recut_cannot_reuse_cache_without_current_independent_evaluation(self):
        path = self.root / 'source.mp4'
        path.write_bytes(b'cached picture')
        cut = dict(self.cut, picture={'path': path.name, 'sha256': filehash(path)})
        self.register(cut)
        legacy = {'status': 'PASS', 'frames': 9, 'substeps': 2, 'evaluated_poses': 17,
                  'samples': {'position': [0] * 17},
                  'binding': {'mechanics': {'inputs': {str(self.source): filehash(self.source)}}}}
        path.with_suffix('.motion.json').write_text(json.dumps({'picture_sha256': filehash(path),
                                                               'motion': legacy}))
        with patch.object(episode, 'recut_picture') as recut:
            with self.assertRaisesRegex(ValueError, 'mechanical_relation_unmeasured'):
                self.produce(cut)
            recut.assert_not_called()

    def test_verifier_edit_requires_renewed_source_review(self):
        self.register(self.cut)
        self.verifier.write_text('# same wrong assumption as the animation')
        with patch.object(episode, 'picture_sources') as pictures:
            with self.assertRaisesRegex(ValueError, 'Independent Blender verifier is missing or changed'):
                self.produce(self.cut)
            pictures.assert_not_called()

    def test_actual_channels_and_ordered_events_gate_acceptance(self):
        inputs = {str(path.resolve()): filehash(path) for path in (self.verifier, evidence.RELATIONS_RUNNER)}
        motion = {'status': 'PASS', 'frames': 9, 'substeps': 2, 'evaluated_poses': 17,
                  'samples': {'review.drive.position': [0, 1] + [0] * 15},
                  'binding': {'mechanics': {'inputs': inputs}, 'independent_relations': self.relations}}

        def findings():
            return video_review.episode_state_findings([self.cut], [9], [motion], self.root,
                                                       coverage=[self.row])[0]

        self.assertEqual(findings()[0]['status'], 'UNKNOWN')
        with self.assertRaisesRegex(ValueError, 'mechanical_relation_unmeasured'):
            episode.block_mechanical_errors(findings(), self.root / 'failure.json', formal=True)
        motion['samples']['review.drive.coupling'] = [0] * 17
        motion['samples']['review.drive.position'] = [0] * 16 + [1]
        self.assertEqual(findings()[0]['code'], 'mechanical_relation_event')
        motion['samples']['review.drive.position'] = [0, 1] + [0] * 15
        self.assertEqual(findings(), [])
        episode.block_mechanical_errors([{'scope': 'viewing', 'status': 'UNKNOWN'}],
                                        self.root / 'failure.json', formal=True)

    def test_graphic_reversed_science_fails_preflight(self):
        height = [[t, n] for t, n in enumerate([1, 1, 0, 0, 1, 1])]
        spring = [[t, 1 - n] for t, n in height]
        graphic = {'type': 'data_animation', 'qualitative': True, 'presentation': 'trace',
                   'items': [{'label': 'height', 'keyframes': height},
                             {'label': 'spring', 'keyframes': spring}]}
        row = {'kind': 'graphic', 'relations': {'cycle': {
            'type': 'opposed_traces', 'labels': ['height', 'spring']}}}
        shot = {'graphic': graphic}
        speech = [(None, [], 150)]
        with patch.object(episode, 'render_graphic') as renderer:
            episode.picture_sources(self.root, speech, self.root, shots=[shot], coverage=[row])
            renderer.assert_called_once()
            renderer.reset_mock()
            graphic['items'][1]['keyframes'] = height
            with self.assertRaisesRegex(ValueError, 'graphic_mechanical_relation'):
                episode.picture_sources(self.root, speech, self.root, shots=[shot], coverage=[row])
            renderer.assert_not_called()
