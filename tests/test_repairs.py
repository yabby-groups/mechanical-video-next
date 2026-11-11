import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from mechanical_video_next import repairs as r


def config():
    return {
        'id': 'fixture', 'asset': 'verified', 'render': {'width': 1920, 'height': 1080},
        'shots': {'overall': {'template': 'overall', 'seconds': 4}},
        'storyboard': [{'id': 's1', 'shot': 'overall', 'seconds': 4,
                        'narration': ['original'], 'subtitles': ['typo']}],
    }


class SubtitleConfigTests(unittest.TestCase):
    def test_changes_only_selected_caption_without_mutating_source(self):
        source = config()
        before = copy.deepcopy(source)
        fixed = r.subtitle_config(source, 's1', 0, 'typo', 'correct')
        self.assertEqual(source, before)
        self.assertEqual(fixed['shots'], before['shots'])
        self.assertEqual(fixed['storyboard'][0]['narration'], ['original'])
        expected = copy.deepcopy(before)
        expected['storyboard'][0]['subtitles'][0] = 'correct'
        self.assertEqual(fixed, expected)

    def test_falls_back_to_narration_without_overwriting_audio_text(self):
        source = config()
        del source['storyboard'][0]['subtitles']
        fixed = r.subtitle_config(source, 's1', 0, 'original', 'correct')
        self.assertEqual(fixed['storyboard'][0]['narration'], ['original'])
        self.assertEqual(fixed['storyboard'][0]['subtitles'], ['correct'])
        self.assertNotIn('subtitles', source['storyboard'][0])

    def test_refuses_stale_empty_and_noop_edits(self):
        for old, new in [('stale', 'correct'), ('typo', ''), ('typo', '  '), ('typo', 'typo')]:
            with self.subTest(old=old, new=new), self.assertRaises(ValueError):
                r.subtitle_config(config(), 's1', 0, old, new)

    def test_refuses_invalid_shot_and_cue_scope(self):
        for shot, cue in [('s1', -1), ('s1', 1), ('missing', 0)]:
            with self.subTest(shot=shot, cue=cue), self.assertRaises(ValueError):
                r.subtitle_config(config(), shot, cue, 'typo', 'correct')


class RepairExecutionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.cfg = self.root/'config.json'
        self.cfg.write_text(json.dumps(config()))
        self.issue = {
            'issue_id': 'SUBTITLE-1', 'responsible_agent': 'Editor', 'shot_id': 's1',
            'kind': 'subtitle_text', 'expected_current_text': 'typo',
            'config_sha256': r.w.filehash(self.cfg), 'cue_index': 0,
        }
        self.qa = {'media': [], 'issues': [self.issue]}
        self.state = {'schema_version': 1, 'protocol_version': 1,
                      'handoffs': {'preview-qa': {}}, 'repairs': {}}

    def test_wrong_owner_shot_and_kind_never_reaches_compose(self):
        import produce
        for field, value in [('responsible_agent', 'Animation'), ('shot_id', 's2'),
                             ('kind', 'mechanical_structure')]:
            qa = copy.deepcopy(self.qa)
            qa['issues'][0][field] = value
            with self.subTest(field=field), patch.object(r.w, 'load', return_value=self.state), \
                    patch.object(r.w, 'artifact', return_value=qa), \
                    patch.object(r.w, 'check_media'), patch.object(produce, 'compose') as compose:
                with self.assertRaises(ValueError):
                    r.repair(self.root/'task', self.cfg, 'SUBTITLE-1', 's1', 0, 'correct')
                compose.assert_not_called()

    def test_missing_shot_cache_stops_before_composition_or_blender(self):
        import produce
        with patch.object(r.w, 'load', return_value=self.state), \
                patch.object(r.w, 'artifact', return_value=self.qa), \
                patch.object(r.w, 'check_media'), patch.object(produce, 'cached', return_value=False), \
                patch.object(produce, 'asset') as asset, patch.object(produce, 'make_shot') as shot, \
                patch.object(produce, 'compose') as compose:
            with self.assertRaisesRegex(ValueError, 'cache missing'):
                r.repair(self.root/'task', self.cfg, 'SUBTITLE-1', 's1', 0, 'correct')
            asset.assert_not_called()
            shot.assert_not_called()
            compose.assert_not_called()

    def test_stale_config_or_wrong_cue_cannot_use_qa_authorization(self):
        import produce
        for field, value in [('config_sha256', '0'*64), ('cue_index', 1)]:
            qa = copy.deepcopy(self.qa)
            qa['issues'][0][field] = value
            with self.subTest(field=field), patch.object(r.w, 'load', return_value=self.state), \
                    patch.object(r.w, 'artifact', return_value=qa), patch.object(r.w, 'check_media'), \
                    patch.object(produce, 'compose') as compose:
                with self.assertRaisesRegex(ValueError, 'bound'):
                    r.repair(self.root/'task', self.cfg, 'SUBTITLE-1', 's1', 0, 'correct')
                compose.assert_not_called()

    def test_unsafe_issue_identifier_cannot_escape_repair_directory(self):
        with patch.object(r.w, 'load') as load:
            with self.assertRaisesRegex(ValueError, 'Unsafe'):
                r.repair(self.root/'task', self.cfg, '../../outside', 's1', 0, 'correct')
            load.assert_not_called()

    def test_exhausted_repair_budget_prevents_composition(self):
        import produce
        state = {'schema_version': 1, 'protocol_version': 1, 'handoffs': {'preview-qa': {}}, 'repairs': {
            'SUBTITLE-1': {'stopped': False, 'strategies': {'subtitle-only': 2}}}}
        with patch.object(r.w, 'load', return_value=state), \
                patch.object(r.w, 'artifact', return_value=self.qa), patch.object(r.w, 'check_media'), \
                patch.object(produce, 'cached', return_value=True), \
                patch.object(produce, 'shot_key', return_value='a'*64), \
                patch.object(produce, 'compose') as compose:
            with self.assertRaisesRegex(ValueError, 'budget exhausted'):
                r.repair(self.root/'task', self.cfg, 'SUBTITLE-1', 's1', 0, 'correct')
            compose.assert_not_called()

    def test_success_reuses_shots_and_does_not_invoke_blender(self):
        import produce
        import common
        state = {'schema_version': 1, 'protocol_version': 1, 'handoffs': {'preview-qa': {}}, 'repairs': {
            'SUBTITLE-1': {'stopped': False, 'strategies': {'subtitle-only': 0}}}}
        metrics = MagicMock()
        metrics.finish.return_value = {'full_shot_renders': 0}

        def compose(fixed, quality, media, observed_metrics):
            self.assertEqual(quality, 'preview')
            self.assertEqual(list(media), ['overall'])
            self.assertIs(observed_metrics, metrics)
            path = self.root/'output'/f'{fixed["id"]}-preview.props.json'
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps({'cues': [{'text': 'correct'}]}))

        with patch.object(r.w, 'ROOT', self.root), patch.object(r.w, 'load', return_value=state), \
                patch.object(r.w, 'artifact', return_value=self.qa), patch.object(r.w, 'check_media'), \
                patch.object(r.w, 'event'), patch.object(r.w, 'repair_attempt') as attempt, \
                patch.object(produce, 'cached', return_value=True), \
                patch.object(produce, 'shot_key', return_value='a'*64), \
                patch.object(produce, 'asset') as asset, patch.object(produce, 'make_shot') as shot, \
                patch.object(produce, 'compose', side_effect=compose) as rendered, \
                patch.object(common, 'Metrics', return_value=metrics):
            fixed = r.repair(self.root/'task', self.cfg, 'SUBTITLE-1', 's1', 0, 'correct', 'preview')
            self.assertEqual(fixed['storyboard'][0]['narration'], ['original'])
            self.assertEqual(fixed['storyboard'][0]['subtitles'], ['correct'])
            rendered.assert_called_once()
            asset.assert_not_called()
            shot.assert_not_called()
            attempt.assert_called_once_with(self.root/'task', 'SUBTITLE-1', 'subtitle-only', 0)


if __name__ == '__main__':
    unittest.main()
