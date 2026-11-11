"""Evidence ledger regression tests, not geometry or perceptual acceptance."""
import json
from pathlib import Path
import tempfile
import unittest

from mechanical_video_next import workflow as w


class CADWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.task = w.create_task('molded zipper', root=self.root,
                                  asset_strategy='autonomous-cad')
        w.put_handoff(self.task, 'MechanicalResearch', 'research', {'fixture': True})
        files = {}
        for key, ext in [('source', 'py'), ('parameters', 'json'), ('step', 'step'),
                         ('glb', 'glb'), ('inventory', 'json'), ('validation', 'json')]:
            path = self.root / (key + '.' + ext)
            path.write_text(json.dumps({'status': 'PASS'}) if key == 'validation'
                            else 'evidence gate fixture, not actual CAD')
            files[key] = {'path': str(path), 'sha256': w.filehash(path)}
        self.files = files
        w.put_handoff(self.task, 'CAD', 'cad-model', {'files': files}, ['research'])
        w.put_handoff(self.task, 'CAD', 'asset-plan', {
            'model': files['glb'], 'qualified': True, 'independent_meshes': True,
            'missing_required_parts': []})
        path = self.root / 'diagnostic.mp4'
        path.write_text('evidence gate fixture, not encoded video')
        self.qa = {'media': [{'path': str(path), 'sha256': w.filehash(path)}],
                   'checks': dict.fromkeys(w.MECHANICAL_CHECKS, 'PASS'),
                   'independent_reviewer': True, 'reviewer_thread_id': 'qa-fixture',
                   'issues': []}
        w.put_handoff(self.task, 'Animation', 'mechanical-diagnostics',
                      {'media': self.qa['media']}, ['research', 'asset-plan', 'cad-model'])

    def handoff_qa(self):
        return w.put_handoff(self.task, 'QA', 'mechanical-qa', self.qa,
                             ['research', 'asset-plan', 'cad-model', 'mechanical-diagnostics'])

    def test_unknown_motion_blocks_before_storyboard_gate(self):
        self.qa['checks']['motion'] = 'UNKNOWN'
        self.handoff_qa()
        with self.assertRaisesRegex(ValueError, 'Mechanical FAIL/UNKNOWN'):
            w.require_animatic(self.task)

    def test_source_or_parameters_change_invalidates_mechanical_acceptance(self):
        self.handoff_qa()
        w.require_mechanical(self.task)
        Path(self.files['parameters']['path']).write_text('changed dimension')
        with self.assertRaisesRegex(ValueError, 'CAD artifact missing or changed: parameters'):
            w.require_mechanical(self.task)

    def test_same_cad_author_cannot_approve_mechanics(self):
        data = w.load(self.task)
        data['agent_runs'].append({'role': 'CAD', 'thread_id': 'qa-fixture'})
        w.write(self.task / 'task.json', data)
        self.handoff_qa()
        with self.assertRaisesRegex(ValueError, 'Independent mechanical reviewer'):
            w.require_mechanical(self.task)

    def test_new_cad_revision_stales_qa(self):
        self.handoff_qa()
        w.put_handoff(self.task, 'CAD', 'cad-model',
                      {'files': self.files, 'revision': 2}, ['research'])
        with self.assertRaisesRegex(ValueError, 'Stale dependency: cad-model'):
            w.require_mechanical(self.task)

    def test_native_resolution_diagnostic_requires_mechanical_gate(self):
        config = self.root / 'native.json'
        config.write_text(json.dumps({'render': {'preview_native': True}}))
        with self.assertRaisesRegex(ValueError, 'Missing handoff: mechanical-qa'):
            w.run_stage(self.task, 'keys', config, diagnostic=True)

    def test_default_new_task_uses_autonomous_cad(self):
        other = w.create_task('new mechanical topic', root=self.root)
        self.assertEqual(w.load(other)['asset_strategy'], 'autonomous-cad')

    def test_failed_numerics_cannot_be_overridden_by_qa_flags(self):
        path = Path(self.files['validation']['path'])
        path.write_text(json.dumps({'status': 'NEEDS_REVIEW', 'numerical_status': 'FAIL'}))
        self.files['validation']['sha256'] = w.filehash(path)
        w.put_handoff(self.task, 'CAD', 'cad-model', {'files': self.files}, ['research'])
        w.put_handoff(self.task, 'Animation', 'mechanical-diagnostics',
                      {'media': self.qa['media']}, ['research', 'asset-plan', 'cad-model'])
        self.handoff_qa()
        with self.assertRaisesRegex(ValueError, 'CAD numerical validation not PASS'):
            w.require_mechanical(self.task)

    def test_two_total_repair_rounds_across_strategies(self):
        self.qa['issues'] = [{
            'issue_id': 'JOINT-1', 'defect_key': 'cad-pull-pin-anchor',
            'severity': 'major', 'shot_id': 'assembly', 'time_range': [0, 1],
            'evidence': 'test fixture', 'responsible_agent': 'CAD',
            'suggested_fix': 'repair measured assembly constraint',
            'verification_method': 'exact CAD intersections'}]
        self.handoff_qa()
        w.repair_attempt(self.task, 'JOINT-1', 'baseline', 3)
        w.repair_attempt(self.task, 'JOINT-1', 'first', 2)
        w.repair_attempt(self.task, 'JOINT-1', 'second', 1)
        with self.assertRaisesRegex(ValueError, 'at most two repair rounds'):
            w.repair_attempt(self.task, 'JOINT-1', 'second', 0)

    def test_unimproved_strategy_must_change_without_exceeding_total_cap(self):
        self.test_two_total_repair_rounds_across_strategies()
        # Separate task/fixture to avoid inheriting the intentionally exhausted test defect.
        data = w.load(self.task)
        data['repairs'] = {}
        w.write(self.task / 'task.json', data)
        w.repair_attempt(self.task, 'JOINT-1', 'baseline', 3)
        w.repair_attempt(self.task, 'JOINT-1', 'first', 3)
        with self.assertRaisesRegex(ValueError, 'strategy must be replaced'):
            w.repair_attempt(self.task, 'JOINT-1', 'first', 2)
        w.repair_attempt(self.task, 'JOINT-1', 'different', 2)
        with self.assertRaisesRegex(ValueError, 'at most two repair rounds'):
            w.repair_attempt(self.task, 'JOINT-1', 'third', 1)


if __name__ == '__main__':
    unittest.main()
