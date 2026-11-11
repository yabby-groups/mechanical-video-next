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
        # Isolate mechanical acceptance; reference-first admission is tested separately.
        data = w.load(self.task)
        data['autonomy_policy']['reference_first'] = False
        w.write(self.task / 'task.json', data)
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
        self.assertTrue(w.load(other)['autonomy_policy']['reference_first'])

    def test_missing_qualified_reference_blocks_cad_admission(self):
        other = w.create_task('new mechanical topic', root=self.root)
        w.put_handoff(other, 'MechanicalResearch', 'research', {'fixture': True})
        with self.assertRaisesRegex(ValueError, 'Missing handoff: viral-analysis'):
            w.put_handoff(other, 'CAD', 'cad-model', {'files': self.files}, ['research'])
        self.assertNotIn('cad-model', w.load(other)['handoffs'])

    def test_observed_physical_reference_without_metrics_allows_cad_admission(self):
        from mechanical_video_next import viral
        other = w.create_task('ordinary machine', root=self.root)
        w.put_handoff(other, 'MechanicalResearch', 'research', {'fixture': True})
        evidence = [self.files['source']]  # Schema fixture only, not a real viewing claim.
        report = viral.analyze({
            'topic': 'ordinary machine', 'task_id': other.name,
            'observed_at': '2026-11-11T08:00:00+00:00', 'candidates': [{
                'id': 'physical', 'url': 'https://www.douyin.com/video/123',
                'observed_at': '2026-11-11T08:00:00+00:00', 'duration_seconds': 30,
                'directly_related': True, 'deep_analysis': True, 'style': 'physical',
                'viewing': {'status': 'FULL_VIDEO_VIEWED', 'continuous_visual': True,
                            'covered_seconds': 30, 'evidence': evidence}}]})
        w.put_handoff(other, 'ViralResearch', 'viral-analysis', report)
        w.put_handoff(other, 'CAD', 'cad-model', {'files': self.files}, ['research'])
        self.assertIn('cad-model', w.load(other)['handoffs'])
        self.assertEqual(report['primary_reference_kind'], 'observed-reference')

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

    def register_defect(self):
        self.qa['issues'] = [{
            'issue_id': 'JOINT-1', 'defect_key': 'cad-pull-pin-anchor',
            'severity': 'major', 'shot_id': 'assembly', 'time_range': [0, 1],
            'evidence': 'test fixture', 'responsible_agent': 'CAD',
            'suggested_fix': 'repair measured assembly constraint',
            'verification_method': 'exact CAD intersections'}]
        self.handoff_qa()

    def test_repairs_continue_beyond_old_round_and_strategy_caps(self):
        self.register_defect()
        w.repair_attempt(self.task, 'JOINT-1', 'baseline', 20)
        for n in range(12):
            w.repair_attempt(self.task, 'JOINT-1', 'strategy-' + str(n // 3), 19 - n)
        issue = w.load(self.task)['repairs']['cad-pull-pin-anchor']
        self.assertEqual(issue['rounds_used'], 12)
        self.assertIsNone(issue['remaining_rounds'])
        self.assertFalse(issue['stopped'])
        self.assertEqual(w.load(self.task)['state'], 'REPAIRING')

    def test_no_improvement_changes_strategy_without_stopping_task(self):
        self.register_defect()
        w.repair_attempt(self.task, 'JOINT-1', 'baseline', 3)
        w.repair_attempt(self.task, 'JOINT-1', 'first', 3)
        self.assertEqual(w.load(self.task)['state'], 'REPAIRING')
        with self.assertRaisesRegex(ValueError, 'strategy must be replaced'):
            w.repair_attempt(self.task, 'JOINT-1', 'first', 2)
        w.repair_attempt(self.task, 'JOINT-1', 'different', 2)
        w.repair_attempt(self.task, 'JOINT-1', 'third', 1)

    def test_adoption_preserves_stopped_history_and_does_not_grant_acceptance(self):
        self.register_defect()
        w.repair_attempt(self.task, 'JOINT-1', 'baseline', 3)
        data = w.load(self.task)
        data.pop('autonomy_policy')
        issue = data['repairs']['cad-pull-pin-anchor']
        issue.update(stopped=True, strategies={'old-a': 1, 'old-b': 1})
        data['state'] = 'BLOCKED'
        w.write(self.task / 'task.json', data)
        w.adopt_autonomy(self.task, 'User removed numeric repair limits')
        self.assertTrue(w.load(self.task)['repairs']['cad-pull-pin-anchor']['stopped'])
        w.repair_attempt(self.task, 'JOINT-1', 'new-constraint', 2)
        issue = w.load(self.task)['repairs']['cad-pull-pin-anchor']
        self.assertEqual(issue['baseline'], 3)
        self.assertEqual(issue['rounds_used'], 3)
        self.assertEqual(len(issue['historical_stops']), 1)
        self.assertEqual(w.load(self.task)['state'], 'REPAIRING')


if __name__ == '__main__':
    unittest.main()
