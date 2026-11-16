"""Low-cost full diagnostics are allowed before freeze, never final renders."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from mechanical_video_next import workflow as w


class AnimaticDiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.task = w.create_task('fixture', root=Path(self.tmp.name))
        data = w.load(self.task)
        data['state'] = 'RESEARCHING'
        w.write(self.task / 'task.json', data)
        self.source = self.task / 'part.stl'
        self.source.write_bytes(b'exact fixture source')
        self.assembly = self.task / 'assembly.json'
        w.write(self.assembly, {'source_files': [self.binding(self.source)]})
        self.config = self.task / 'config.json'
        self.cfg = {'render': {'width': 1920, 'height': 1080, 'fps': 30, 'framing': 'fullframe', 'preview_native': False},
                    'assembly_config': str(self.assembly), 'shots': {'first': {'seconds': 60}, 'last': {'seconds': 60}},
                    'storyboard': [{'id': 'one', 'shot': 'first', 'seconds': 60}, {'id': 'two', 'shot': 'last', 'seconds': 60}],
                    'local_preview_shots': ['first', 'last']}
        self.qa_path = self.task / 'qa.json'
        self.qa = {'task_id': data['id'], 'reviewer_role': 'QA', 'independent': True, 'reviewer_thread_id': 'independent-native-qa',
                   'decision': {'raw_full_low_cost_dynamic_animatic_allowed': True, 'expensive_render_allowed': False, 'final_acceptance': False}}
        self.save()

    def binding(self, path):
        return {'path': str(path), 'sha256': w.filehash(path)}

    def save(self):
        w.write(self.config, self.cfg)
        self.qa['input_bindings'] = [self.binding(self.config), self.binding(self.assembly)]
        w.write(self.qa_path, self.qa)

    def test_full_low_cost_permission_preserves_researching_and_gives_executable_next_action(self):
        w.require_animatic_diagnostic(self.task, self.config, self.qa_path)
        result = w.continuation(self.task)
        self.assertEqual(result['workflow_state'], 'RESEARCHING')
        self.assertIn('--animatic-diagnostic', result['next_action']['command'])
        self.assertEqual(result['next_action']['owner'], 'Producer')
        self.assertFalse(result['delivered'])
        self.assertTrue(result['remaining_work'])

    def test_independent_permission_not_final_or_expensive_authorization(self):
        self.qa['decision']['expensive_render_allowed'] = True
        self.save()
        with self.assertRaisesRegex(ValueError, 'not expensive'):
            w.require_animatic_diagnostic(self.task, self.config, self.qa_path)
        with self.assertRaisesRegex(ValueError, 'only permits'):
            w.run_stage(self.task, 'final', self.config, animatic_diagnostic=True, preproduction_qa=self.qa_path)

    def test_stale_config_or_transitive_model_dependency_blocks(self):
        self.config.write_text('{}')
        with self.assertRaisesRegex(ValueError, 'Stale'):
            w.require_animatic_diagnostic(self.task, self.config, self.qa_path)
        self.save()
        self.source.write_bytes(b'changed geometry')
        with self.assertRaisesRegex(ValueError, 'Stale assembly source'):
            w.require_animatic_diagnostic(self.task, self.config, self.qa_path)

    def test_hd_or_partial_storyboard_cannot_use_full_low_cost_entry(self):
        self.cfg['render']['preview_native'] = True
        self.save()
        with self.assertRaisesRegex(ValueError, 'downsampled'):
            w.require_animatic_diagnostic(self.task, self.config, self.qa_path)
        self.cfg['render']['preview_native'] = False
        self.cfg['local_preview_shots'] = ['first']
        self.save()
        with self.assertRaisesRegex(ValueError, 'all authored chapters'):
            w.require_animatic_diagnostic(self.task, self.config, self.qa_path)

    def test_completed_raw_chapters_schedule_composition_instead_of_rerender(self):
        w.require_animatic_diagnostic(self.task, self.config, self.qa_path)
        data = w.load(self.task)
        data['stages'].append({'animatic_diagnostic': True, 'command_success': True, 'config_sha256': w.filehash(self.config)})
        w.write(self.task / 'task.json', data)
        report = w.continuation(self.task)
        self.assertEqual(report['next_action']['owner'], 'Editor')
        self.assertIsNone(report['next_action']['command'])
