import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from mechanical_video_next import blueprint as b


class BlueprintTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.blueprint, self.base, self.output = [self.root/n for n in ('blueprint.json', 'base.json', 'compiled.json')]
        self.data = {'status': 'FROZEN', 'shots': [dict(
            shot_id='opening', time_range=[0, 3], knowledge_goal='看清链牙', mechanical_action='静态细节',
            asset='source-model', template='detail', existing_shot='detail',
            camera={'camera_view': 'oblique', 'camera_direction': [1, -2, 3], 'camera_roll': 10},
            narration=['新的旁白'], subtitles=['新的字幕'], overlays=['原理示意'])]}
        evidence = self.root/'evidence.txt'; evidence.write_text('Unit fixture, not real scientific acceptance')
        refs = [{'path': str(evidence), 'sha256': b.filehash(evidence)}]
        self.data.update({k: 'unit fixture' for k in ('core_question', 'opening_0_3', 'disassembly_order',
                         'closeups', 'annotations', 'narration_structure', 'sound_design', 'causal_ending')})
        self.data.update(first_motion_seconds=0, reference_principles=[dict(reference_id='unit', principle='fixture', evidence=refs)])
        self.data.update({k: 'unit fixture' for k in ('original_topic', 'knowledge_goals', 'pacing',
                         'voice_requirements', 'subtitle_requirements', 'creative_decisions', 'sources')})
        self.data.update(duration_seconds=3, qa_requirements=[dict(requirement_id='unit', shot_id='opening',
                         expected_observable_effect='fixture', verification_method='fixture', minimal_repair='fixture')])
        self.data['reference_principles'][0].update({k: 'unit fixture' for k in ('production_requirement',
            'expected_observable_effect', 'verification_method', 'minimal_repair', 'decision_basis', 'implementation_cost')})
        self.data['reference_principles'][0]['shot_ids'] = ['opening']
        self.data['shots'][0]['feasibility_evidence'] = refs
        self.config = dict(id='original', asset='source-model', voice='Neil', render={'width': 1920, 'height': 1080},
                           shots={'detail': {'template': 'detail', 'seconds': 5, 'camera_view': 'top',
                                             'tracks': [{'object': 'tooth', 'poses': []}],
                                             'visual_profile': 'printer-ep03-studio-v1'}},
                           storyboard=[dict(id='old', shot='detail', narration=['old'], label='old', note='old')])
        self.save()

    def save(self):
        self.blueprint.write_text(json.dumps(self.data, ensure_ascii=False))
        self.base.write_text(json.dumps(self.config))

    def test_compiler_binds_real_camera_storyboard_without_mutating_sources(self):
        original = self.blueprint.read_bytes()
        binding = b.compile_config(self.blueprint, self.base, self.output)
        cfg = json.loads(self.output.read_text())
        self.assertEqual(cfg['storyboard'][0]['narration'], ['新的旁白'])
        self.assertEqual(cfg['storyboard'][0]['subtitles'], ['新的字幕'])
        self.assertEqual(cfg['storyboard'][0]['note'], '原理示意')
        self.assertEqual(cfg['shots']['opening']['camera_roll'], 10)
        self.assertEqual(cfg['shots']['opening']['camera_direction'], [1, -2, 3])
        self.assertEqual(cfg['shots']['opening']['seconds'], 3)
        self.assertEqual(cfg['shots']['opening']['tracks'], self.config['shots']['detail']['tracks'])
        self.assertEqual(cfg['render'], self.config['render']); self.assertEqual(cfg['voice'], 'Neil')
        self.assertNotEqual(cfg['id'], self.config['id'])
        self.assertTrue(cfg['id'].startswith('original-blueprint-'))
        self.assertEqual(binding['config_sha256'], b.filehash(self.output))
        self.assertEqual(binding['blueprint_sha256'], b.filehash(self.blueprint))
        self.assertEqual(binding['shot_requirements'][0]['motion_validation'], 'UNKNOWN')
        self.assertEqual(self.blueprint.read_bytes(), original)

    def test_unfrozen_fails_closed_but_explicit_draft_is_marked(self):
        self.data['status'] = 'PROVISIONAL'; self.save()
        with self.assertRaisesRegex(ValueError, 'FROZEN'):
            b.compile_config(self.blueprint, self.base, self.output)
        self.assertFalse(self.output.exists())
        self.assertEqual(b.compile_config(self.blueprint, self.base, self.output, draft=True)['status'], 'DRAFT_UNAPPROVED')

    def test_unknown_mappings_rejected(self):
        for field, value in [('existing_shot', 'missing'), ('template', 'new-engine'), ('asset', 'other-model')]:
            with self.subTest(field=field):
                data = copy.deepcopy(self.data); data['shots'][0][field] = value
                self.blueprint.write_text(json.dumps(data))
                with self.assertRaises(ValueError):
                    b.compile_config(self.blueprint, self.base, self.output)

    def test_timeline_and_utterance_mismatch_rejected(self):
        for patch in ({'time_range': [1, 3]}, {'time_range': [0, 121]}, {'time_range': [0, 0]},
                      {'subtitles': []}, {'camera': {'zoom': 4}}):
            with self.subTest(patch=patch):
                data = copy.deepcopy(self.data); data['shots'][0].update(patch)
                with self.assertRaises(ValueError):
                    b.validate(data)

    def test_ninety_second_production_timeline_is_supported(self):
        data = copy.deepcopy(self.data)
        data['shots'][0]['time_range'] = [0, 90]
        self.assertEqual(b.validate(data), 90)

    def test_image_hash_is_verified_before_any_generation(self):
        image = self.root/'frame.png'; image.write_bytes(b'fixture')
        shot = self.data['shots'][0]
        shot['animatic'] = {'image': 'frame.png', 'sha256': b.filehash(image)}
        self.assertEqual(b.image_source(shot, self.root), image.resolve())
        image.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            b.image_source(shot, self.root)
        self.save()
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            b.animatic(self.blueprint, self.root/'animatic')
        self.assertFalse((self.root/'animatic').exists())

    def test_no_source_overwrite(self):
        with self.assertRaises(ValueError):
            b.compile_config(self.blueprint, self.base, self.blueprint)

    def test_frozen_requires_full_research_validation(self):
        del self.data['core_question']; self.save()
        with self.assertRaisesRegex(ValueError, 'FROZEN'):
            b.compile_config(self.blueprint, self.base, self.output)

    def test_subprocess_budget_failure_stops_child_and_retains_log(self):
        metrics = type('MetricsFixture', (), {'peak': 0, 'temp_samples': []})()
        process = unittest.mock.MagicMock()
        process.__enter__.return_value = process
        process.wait.side_effect = [b.subprocess.TimeoutExpired('unit', .5), 0]
        with patch.object(b.subprocess, 'Popen', return_value=process), patch.object(b, 'budget', side_effect=RuntimeError('budget exceeded')):
            with self.assertRaisesRegex(RuntimeError, 'budget exceeded'):
                b.sampled_run(['unit'], self.root/'logs'/'failed.log', metrics)
        process.terminate.assert_called_once()
        self.assertTrue((self.root/'logs'/'failed.log').is_file())


if __name__ == '__main__':
    unittest.main()
