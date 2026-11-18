"""Low-cost full diagnostics are allowed before freeze, never final renders."""
import copy
from contextlib import nullcontext
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import subprocess
import types

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

    def test_real_failed_stage_preserves_other_route_diagnostic_permission(self):
        self.cfg['render_route'] = '3d'
        self.save()
        other_config, other_qa = self.task / 'other-route.json', self.task / 'other-qa.json'
        other = copy.deepcopy(self.cfg)
        other['render_route'] = '3d'
        w.write(other_config, other)
        qa = copy.deepcopy(self.qa)
        qa['input_bindings'] = [self.binding(other_config), self.binding(self.assembly)]
        w.write(other_qa, qa)
        failure = subprocess.CalledProcessError(1, ['uv', 'run', 'python', 'produce.py'])
        with patch.dict('sys.modules', {'clean': types.SimpleNamespace(cleanup=lambda **kwargs: None)}), \
                patch.object(w, 'lock', side_effect=lambda path, **kwargs: nullcontext()), \
                patch.object(w.subprocess, 'run', side_effect=[failure, None]) as run:
            with self.assertRaises(subprocess.CalledProcessError):
                w.run_stage(self.task, 'local', self.config, animatic_diagnostic=True, preproduction_qa=self.qa_path)
            after = w.load(self.task)
            self.assertEqual(after['state'], 'RESEARCHING')
            self.assertEqual(after['candidate_failures'][0]['status'], 'REPAIRING')
            self.assertEqual(w.continuation(self.task)['lifecycle'], 'REPAIRING')
            self.assertIsNone(w.continuation(self.task)['next_action']['command'])
            # This executes the real independent task/config/QA binding gate,
            # then enters the second actual run_stage subprocess boundary.
            w.run_stage(self.task, 'local', other_config, animatic_diagnostic=True, preproduction_qa=other_qa)
            self.assertEqual(run.call_count, 2)
        events = [json.loads(row) for row in (self.task / 'events.jsonl').read_text().splitlines()]
        self.assertTrue(any(row['event'] == 'stage_failed' and row['isolated_candidate'] for row in events))
        self.assertEqual(w.load(self.task)['state'], 'RESEARCHING')

    def test_independent_permission_not_final_or_expensive_authorization(self):
        self.qa['decision']['expensive_render_allowed'] = True
        self.save()
        with self.assertRaisesRegex(ValueError, 'not expensive'):
            w.require_animatic_diagnostic(self.task, self.config, self.qa_path)
        with self.assertRaisesRegex(ValueError, 'only permits'):
            w.run_stage(self.task, 'final', self.config, animatic_diagnostic=True, preproduction_qa=self.qa_path)

    def test_constant_core_tracks_fail_before_expensive_render(self):
        shot = dict(science={'driver': 'data_tracks'}, visual={'mechanical_role': 'core'},
                    tracks=[dict(object='Core', poses=[dict(progress=0, location=[0, 0, 0]),
                                                      dict(progress=1, location=[0, 0, 0])])])
        cfg = dict(production_contract_version=1, production_contract='mixed-original-v1',
                   media_policy_version=1, visual_policy_version=2, shots={'hold': shot})
        with self.assertRaisesRegex(ValueError, 'constant data tracks.*hold'):
            w.check_core_motion_inputs(cfg)
        shot['tracks'][0]['poses'][1]['location'][0] = .001
        w.check_core_motion_inputs(cfg)

    def test_core_mesh_changes_count_but_opacity_and_camera_do_not(self):
        shot = dict(science={'driver': 'data_tracks', 'camera_path': [0, 1],
                             'opacity_tracks': [{'keys': [[0, 0], [1, 1]]}]},
                    visual={'mechanical_role': 'core'},
                    mesh_tracks=[dict(object='Belt', poses=[dict(progress=0, vertices=[[0, 0, 0]]),
                                                           dict(progress=1, vertices=[[0, 0, 0]])])])
        cfg = dict(production_contract_version=1, production_contract='mixed-original-v1',
                   media_policy_version=1, visual_policy_version=2, shots={'hold': shot})
        with self.assertRaisesRegex(ValueError, 'constant data tracks'):
            w.check_core_motion_inputs(cfg)
        shot['mesh_tracks'][0]['poses'][1]['vertices'][0][0] = .001
        w.check_core_motion_inputs(cfg)

    def test_static_preflight_preserves_legacy_and_structural_shots(self):
        shot = dict(science={'driver': 'data_tracks'}, visual={'mechanical_role': 'core'})
        w.check_core_motion_inputs(dict(shots={'historical': shot}))
        shot['visual']['mechanical_role'] = 'support'
        w.check_core_motion_inputs(dict(production_contract_version=1, production_contract='mixed-original-v1',
                                       media_policy_version=1, visual_policy_version=2, shots={'structure': shot}))

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
