"""A user rejection invalidates production use, while retaining audit pointers."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from mechanical_video_next import workflow as w
from mechanical_video_next import multiroute as m


class RejectedSchemeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.task = w.create_task('fixture', root=Path(self.tmp.name), protocol_version=1)
        data = w.load(self.task)
        data.update(state='COMPLETED', production_complete_rendered=True,
                    production_plan={'path': 'old-plan.json', 'sha256': 'old'},
                    handoffs={'research': {'path': 'old-research.json', 'sha256': 'old'}},
                    final_artifacts={'mp4': 'old-final.mp4'},
                    reference_remake={'version': 1, 'old_scheme_status': 'REJECTED_BY_USER',
                                     'status': 'BLOCKED_CAPABILITY', 'primary_reference': None,
                                     'preview_accepted': False})
        w.write(self.task / 'task.json', data)

    def test_rejected_old_success_never_resumes_or_counts_as_delivery(self):
        with patch.object(w.subprocess, 'run') as run, patch.object(w, 'complete_media') as media:
            report = w.continue_production(self.task)
        self.assertEqual(report['milestone'], 'SCHEME_REJECTED')
        self.assertEqual(report['lifecycle'], 'BLOCKED')
        self.assertFalse(report['delivered'])
        self.assertEqual(report['rendered_routes'], {})
        self.assertIsNone(report['next_action']['command'])
        run.assert_not_called()
        media.assert_not_called()
        self.assertTrue(w.load(self.task)['production_complete_rendered'])
        self.assertEqual(w.load(self.task)['handoffs']['research']['sha256'], 'old')
        with self.assertRaisesRegex(ValueError, 'independent QA'):
            w.record_delivery(self.task, [], 'old file supplied')

    def test_all_stage_modes_and_state_advancement_reject_old_plan(self):
        with patch.object(w.subprocess, 'run') as run:
            for phase in ['asset', 'checks', 'keys', 'local', 'preview', 'final']:
                with self.subTest(phase=phase), self.assertRaisesRegex(ValueError, 'newly watched'):
                    w.run_stage(self.task, phase, 'old-config.json')
            with self.assertRaisesRegex(ValueError, 'User-rejected'):
                w.advance(self.task, 'COMPLETED')
        run.assert_not_called()

    def test_route_plan_rejects_even_legacy_policy_before_any_command(self):
        plan = self.task / 'old-plan.json'
        plan.write_text(json.dumps({'routes': {'3d': 'old.mp4'}, 'task': str(self.task),
                                    'steps': []}))
        with patch.object(m, 'command') as command:
            with self.assertRaisesRegex(ValueError, 'User-rejected'):
                m.run_plan(self.task, plan, legacy_workprint=True)
        command.assert_not_called()

    def test_readiness_strings_and_old_bindings_cannot_unlock(self):
        data = w.load(self.task)
        snapshot = self.task / 'task.before-remake.json'
        w.write(snapshot, data)
        remake = data['reference_remake']
        remake.update(status='READY', primary_reference='claimed reference', preview_accepted=True,
                      previous_task_snapshot=str(snapshot),
                      production_binding={'handoffs': data['handoffs'],
                                          'production_plan': data['production_plan']})
        with self.assertRaisesRegex(ValueError, 'production_binding'):
            w.require_current_scheme(data)

    def test_new_candidate_bindings_allow_preview_before_acceptance_but_not_final(self):
        data = w.load(self.task)
        snapshot = self.task / 'task.before-remake.json'
        w.write(snapshot, data)
        data['handoffs'] = {name: {'path': 'new-' + name + '.json', 'sha256': name}
                            for name in ['research', 'asset-plan', 'creative-blueprint']}
        plan = self.task / 'replacement-plan.json'
        plan.write_text('{}')
        data['production_plan'] = {'path': str(plan), 'sha256': w.filehash(plan)}
        data['reference_remake'].update(primary_reference='new observed reference',
            previous_task_snapshot=str(snapshot), preview_accepted=False,
            production_binding={'handoffs': data['handoffs'], 'production_plan': data['production_plan']})
        # The new preview can be generated before its QA exists: no circular gate.
        w.require_current_scheme(data, candidate_preview=True)
        with self.assertRaisesRegex(ValueError, 'independent 10-15 second preview QA'):
            w.require_current_scheme(data)
        w.write(self.task / 'task.json', data)
        with patch.object(w.subprocess, 'run') as run:
            with self.assertRaisesRegex(ValueError, 'independent 10-15 second preview QA'):
                w.run_stage(self.task, 'final', 'old-config.json')
        run.assert_not_called()
