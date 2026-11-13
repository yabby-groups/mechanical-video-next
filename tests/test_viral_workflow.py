"""Ledger gates only: byte fixtures do not claim actual media acceptance.

Viral payload validation has separate tests; these isolate DAG/version and
render authorization from research-content schemas and never invoke Blender.
"""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from mechanical_video_next import workflow as w


class ViralWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config = self.root / 'config.json'
        self.config.write_text(json.dumps({'shots': ['fixture']}))
        self.task = w.create_task('拉链原理', config=self.config, root=self.root,
                                  asset_strategy='verified-existing', routes='3d')
        # These fixtures isolate downstream DAG/media gates from reference-first admission.
        data = w.load(self.task)
        # Explicit historical v2 fixture: preserve pre-longform DAG coverage.
        data.pop('content_policy_version')
        data['duration'] = 90
        data['autonomy_policy']['reference_first'] = False
        w.write(self.task / 'task.json', data)

    def handoff(self, name, payload, dependencies=None):
        role = next(role for role, names in w.ROLES.items() if name in names)
        dependencies = (w.V2_DEPENDENCIES.get(name, set())
                        if dependencies is None else dependencies)
        return w.put_handoff(self.task, role, name, payload, sorted(dependencies))

    def blueprint(self, revision=1):
        with patch('mechanical_video_next.viral.validate_viral_analysis'), \
                patch('mechanical_video_next.viral.validate_creative_blueprint'):
            if 'viral-analysis' not in w.load(self.task)['handoffs']:
                self.handoff('viral-analysis', {
                    'status': 'READY', 'task_id': self.task.name, 'topic': '拉链原理',
                    'selected_ids': ['observed-1'], 'primary_reference_id': 'observed-1',
                    'candidates': [{'id': 'observed-1', 'duration_seconds': 10}]})
            blueprint = {
                'status': 'FROZEN', 'revision': revision,
                'reference_principles': [{'reference_id': 'observed-1'}],
                'shots': [{'shot_id': 's1'}],
                'reference_recreation': {
                    'primary_reference_id': 'observed-1',
                    'shot_mapping': [{'shot_id': 's1', 'reference_time_range': [0, 5],
                                      'adaptation': 'Recreate the opening with our CAD'}]}}
            self.config.write_text(json.dumps({'shots': ['fixture'],
                                              'blueprint_program_sha256': w.digest(blueprint)}))
            blueprint['production_config'] = {'path': str(self.config), 'sha256': w.filehash(self.config)}
            return self.handoff('creative-blueprint', blueprint)

    def prepare(self):
        self.handoff('research', {'facts': ['fixture only']})
        model = self.root / 'assembly.glb'
        model.write_bytes(b'ledger fixture, not a real asset qualification')
        self.handoff('asset-plan', {
            'qualified': True, 'independent_meshes': True, 'missing_required_parts': [],
            'model': {'path': str(model), 'sha256': w.filehash(model)}})

    def feasible(self):
        self.prepare()
        self.blueprint()
        self.handoff('script', {'shots': []})
        return self.handoff('feasibility', {'checks': dict.fromkeys(w.FEASIBILITY_CHECKS, 'PASS')})

    def media(self, filename):
        path = self.root / filename
        path.write_bytes(filename.encode())
        return [{'path': str(path), 'sha256': w.filehash(path)}]

    def animatic(self):
        self.feasible()
        self.evidence = self.media('animatic.mp4')
        self.handoff('animatic-manifest', {'media': self.evidence})
        self.qa = {'media': self.evidence, 'independent_reviewer': True,
                   'reviewer_thread_id': 'independent-qa', 'issues': [],
                   'checks': dict.fromkeys(w.ANIMATIC_CHECKS, 'PASS')}
        self.handoff('animatic-qa', self.qa)

    def state(self, state):
        data = w.load(self.task)
        data['state'] = state
        w.write(self.task / 'task.json', data)

    def test_defaults_and_removed_protocol_fail_closed(self):
        data = w.load(self.task)
        self.assertEqual(data['protocol_version'], 2)
        self.assertEqual(data['production_method'], 'reference-recreation')
        del data['protocol_version']
        w.write(self.task / 'task.json', data)
        with self.assertRaisesRegex(ValueError, 'protocol_version'):
            w.load(self.task)
        data['protocol_version'] = 1
        w.write(self.task / 'task.json', data)
        with self.assertRaisesRegex(ValueError, 'New tasks require'):
            w.load(self.task)

    def test_existing_schema_one_task_is_explicit_legacy_compatibility(self):
        data = w.load(self.task)
        data['schema_version'] = 1
        del data['protocol_version']
        w.write(self.task / 'task.json', data)
        self.assertEqual(w.protocol_version(w.load(self.task)), 1)
        self.handoff('research', {})
        self.handoff('script', {}, ['research'])
        w.require_animatic(self.task)

    def test_preparation_allowed_but_script_requires_blueprint(self):
        self.prepare()
        with self.assertRaisesRegex(ValueError, 'Required dependencies'):
            self.handoff('script', {}, ['research'])
        self.blueprint()
        self.handoff('script', {})
        with self.assertRaisesRegex(ValueError, 'does not own'):
            w.put_handoff(self.task, 'Research', 'creative-blueprint', {})

    def test_viral_validation_is_not_bypassed_at_handoff(self):
        with patch('mechanical_video_next.viral.validate_viral_analysis',
                   side_effect=ValueError('Reference observation incomplete')) as validate:
            with self.assertRaisesRegex(ValueError, 'observation incomplete'):
                self.handoff('viral-analysis', {'status': 'BLOCKED'})
            validate.assert_called_once_with({'status': 'BLOCKED'})
        self.assertNotIn('viral-analysis', w.load(self.task)['handoffs'])

    def test_blueprint_cannot_use_unselected_reference(self):
        self.blueprint()
        with patch('mechanical_video_next.viral.validate_creative_blueprint'):
            with self.assertRaisesRegex(ValueError, 'selected observed references'):
                self.handoff('creative-blueprint', {
                    'status': 'FROZEN', 'reference_principles': [{'reference_id': 'invented'}]})

    def test_other_video_research_cannot_be_reused_as_this_video_handoff(self):
        self.blueprint()
        research = w.artifact(self.task, 'viral-analysis')
        before = w.load(self.task)['handoffs']['viral-analysis']
        with patch('mechanical_video_next.viral.validate_viral_analysis'):
            for key, value in [('task_id', 'other-video'), ('topic', 'another mechanism')]:
                with self.subTest(field=key), self.assertRaisesRegex(ValueError, 'own task_id and topic'):
                    self.handoff('viral-analysis', dict(research, **{key: value}))
        self.assertEqual(w.load(self.task)['handoffs']['viral-analysis'], before)

    def test_recreation_missing_mapping_cannot_freeze(self):
        self.blueprint()
        blueprint = w.artifact(self.task, 'creative-blueprint')
        del blueprint['reference_recreation']
        with patch('mechanical_video_next.viral.validate_creative_blueprint'):
            with self.assertRaisesRegex(ValueError, 'primary reference and shot mapping'):
                self.handoff('creative-blueprint', blueprint)

    def test_production_gate_rechecks_task_research_binding(self):
        self.animatic()
        data = w.load(self.task)
        data['topic'] = 'Changed topic after research approval'
        w.write(self.task / 'task.json', data)
        with patch.object(w.subprocess, 'run') as run:
            self.state('ANIMATING')
            with self.assertRaisesRegex(ValueError, 'own task_id and topic'):
                w.run_stage(self.task, 'preview', self.config)
            run.assert_not_called()

    def test_feasibility_requires_every_explicit_check_pass_and_asset(self):
        self.prepare()
        self.blueprint()
        checks = dict.fromkeys(w.FEASIBILITY_CHECKS, 'PASS')
        for name in sorted(w.FEASIBILITY_CHECKS):
            for value in ('UNKNOWN', 'FAIL', None):
                with self.subTest(check=name, value=value):
                    failed = dict(checks, **{name: value})
                    with self.assertRaisesRegex(ValueError, 'every check PASS'):
                        self.handoff('feasibility', {'checks': failed})
        self.handoff('feasibility', {'checks': checks})
        (self.root / 'assembly.glb').write_bytes(b'changed model')
        with self.assertRaisesRegex(ValueError, 'Verified model evidence'):
            self.handoff('feasibility', {'checks': checks})

    def test_blueprint_update_preserves_old_version_and_invalidates_approvals(self):
        self.animatic()
        old_blueprint = (self.task / 'handoffs/creative-blueprint.v1.json').read_bytes()
        w.require_animatic(self.task)
        self.blueprint(revision=2)
        self.assertEqual((self.task / 'handoffs/creative-blueprint.v1.json').read_bytes(), old_blueprint)
        with self.assertRaisesRegex(ValueError, 'Stale dependency: creative-blueprint'):
            w.require_animatic(self.task)
        with self.assertRaisesRegex(ValueError, 'Stale'):
            w.artifact(self.task, 'script')

    def test_animatic_dag_has_no_full_animation_cycle(self):
        self.feasible()
        evidence = self.media('animatic.mp4')
        with self.assertRaisesRegex(ValueError, 'DAG'):
            self.handoff('animatic-manifest', {'media': evidence},
                         w.V2_DEPENDENCIES['animatic-manifest'] | {'script'})
        self.handoff('animatic-manifest', {'media': evidence})
        with self.assertRaisesRegex(ValueError, 'Required dependencies'):
            self.handoff('animation-manifest', {'media': evidence}, ['research', 'asset-plan'])

    def test_no_image_only_animatic_or_missing_media(self):
        self.feasible()
        with self.assertRaisesRegex(ValueError, 'Actual media'):
            self.handoff('animatic-manifest', {})
        with self.assertRaisesRegex(ValueError, 'actual MP4'):
            self.handoff('animatic-manifest', {'media': self.media('still.png')})

    def test_unknown_wrong_media_and_producer_identity_block_animatic(self):
        self.animatic()
        self.qa['checks']['blueprint_fidelity'] = 'UNKNOWN'
        self.handoff('animatic-qa', self.qa)
        with self.assertRaisesRegex(ValueError, 'FAIL/UNKNOWN'):
            w.require_animatic(self.task)
        self.qa['checks']['blueprint_fidelity'] = 'PASS'
        self.qa['media'] = self.media('unrelated.mp4')
        self.handoff('animatic-qa', self.qa)
        with self.assertRaisesRegex(ValueError, 'exact production MP4'):
            w.require_animatic(self.task)
        self.qa['media'] = self.evidence
        self.handoff('animatic-qa', self.qa)
        data = w.load(self.task)
        data['agent_runs'].append({'role': 'ViralResearch', 'thread_id': 'independent-qa'})
        w.write(self.task / 'task.json', data)
        with self.assertRaisesRegex(ValueError, 'also produced'):
            w.require_animatic(self.task)

    def test_changed_animatic_and_new_manifest_invalidate_qa(self):
        self.animatic()
        (self.root / 'animatic.mp4').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'missing or changed'):
            w.require_animatic(self.task)
        evidence = self.media('new-animatic.mp4')
        self.handoff('animatic-manifest', {'media': evidence})
        with self.assertRaisesRegex(ValueError, 'Stale dependency: animatic-manifest'):
            w.require_animatic(self.task)

    def test_no_full_render_or_workprint_before_animatic_approval(self):
        self.feasible()
        with patch.object(w.subprocess, 'run') as run:
            for phase, state, workprint in [('preview', 'ANIMATING', False),
                                            ('final', 'EDITING', False),
                                            ('final', 'PREVIEW_CHECKING', True)]:
                self.state(state)
                # A provisional preview report cannot bypass the earlier gate.
                original = w.artifact
                with patch.object(w, 'artifact', wraps=w.artifact) as artifact:
                    if workprint:
                        artifact.side_effect = lambda task, name: (
                            {'media': self.media('provisional.mp4'), 'checks': {'listening': 'UNKNOWN'}}
                            if name == 'preview-qa' else original(task, name))
                    with self.assertRaisesRegex(ValueError, 'Missing handoff: animatic-qa'):
                        w.run_stage(self.task, phase, self.root / 'config.json', workprint=workprint)
            run.assert_not_called()

    def test_approved_animatic_unlocks_manifest_but_unknown_reblocks_it(self):
        self.animatic()
        self.handoff('animation-manifest', {'media': self.media('preview.mp4'),
                                             'keyframes_verified': True})
        self.state('ANIMATING')
        w.advance(self.task, 'PREVIEW_READY')
        self.qa['checks']['listening'] = 'UNKNOWN'
        self.handoff('animatic-qa', self.qa)
        with self.assertRaisesRegex(ValueError, 'FAIL/UNKNOWN'):
            w.advance(self.task, 'PREVIEW_CHECKING')
        with self.assertRaisesRegex(ValueError, 'FAIL/UNKNOWN'):
            self.handoff('animation-manifest', {'media': self.evidence})

    def test_cli_handoff_fails_without_dependency_and_writes_nothing(self):
        self.prepare()
        source = self.root / 'script.json'
        source.write_text(json.dumps({'shots': []}))
        with patch.object(sys, 'argv', ['mechanical_video_next', 'handoff', str(self.task),
                                      '--role', 'Research', '--name', 'script',
                                      '--input', str(source), '--depends', 'research']):
            with self.assertRaisesRegex(ValueError, 'Required dependencies'):
                w.main()
        self.assertNotIn('script', w.load(self.task)['handoffs'])

    def test_changed_executable_config_invalidates_prior_animatic_qa(self):
        self.animatic()
        w.require_animatic(self.task)
        self.config.write_text(json.dumps({'shots': ['changed after QA']}))
        with self.assertRaisesRegex(ValueError, 'config missing or changed'):
            w.require_animatic(self.task)
        self.state('ANIMATING')
        with patch.object(w.subprocess, 'run') as run:
            with self.assertRaisesRegex(ValueError, 'config missing or changed'):
                w.run_stage(self.task, 'preview', self.config)
            run.assert_not_called()

    def test_full_stage_cannot_use_another_config_even_with_identical_bytes(self):
        self.animatic()
        other = self.root / 'other.json'
        other.write_bytes(self.config.read_bytes())
        self.state('ANIMATING')
        with patch.object(w.subprocess, 'run') as run:
            with self.assertRaisesRegex(ValueError, 'config path differs'):
                w.run_stage(self.task, 'preview', other)
            run.assert_not_called()

    def test_unbound_blueprint_or_task_config_cannot_unlock_full_render(self):
        self.animatic()
        blueprint = w.artifact(self.task, 'creative-blueprint')
        del blueprint['production_config']
        with patch('mechanical_video_next.viral.validate_creative_blueprint'):
            self.handoff('creative-blueprint', blueprint)
        with self.assertRaisesRegex(ValueError, 'production_config path/hash'):
            w.require_animatic(self.task)

    def test_bound_config_must_compile_exact_blueprint_program(self):
        self.animatic()
        blueprint = w.artifact(self.task, 'creative-blueprint')
        compiled = json.loads(self.config.read_text())
        compiled['blueprint_program_sha256'] = 'another frozen plan'
        self.config.write_text(json.dumps(compiled))
        blueprint['production_config']['sha256'] = w.filehash(self.config)
        with patch('mechanical_video_next.viral.validate_creative_blueprint'):
            self.handoff('creative-blueprint', blueprint)
        with self.assertRaisesRegex(ValueError, 'exact frozen blueprint program'):
            w.require_animatic(self.task)

    def report_defect(self, issue_id, defect_key='interpenetration:chain_teeth'):
        issue = {'issue_id': issue_id, 'defect_key': defect_key, 'severity': 'major',
                 'shot_id': 's1', 'time_range': [0, 1], 'evidence': self.evidence,
                 'responsible_agent': 'Animation', 'suggested_fix': 'Correct tooth movement',
                 'verification_method': 'Inspect the same movement interval'}
        self.qa['issues'] = [issue]
        self.handoff('animatic-qa', self.qa)
        return issue

    def test_v2_qa_requires_persistent_defect_key_without_media_hash(self):
        self.animatic()
        for defect_key in (None, '', self.evidence[0]['sha256']):
            with self.subTest(defect_key=defect_key):
                with self.assertRaisesRegex(ValueError, 'persistent failure type/component'):
                    self.report_defect('ISSUE-1', defect_key)

    def test_v2_repair_rejects_unreported_issue(self):
        self.animatic()
        with self.assertRaisesRegex(ValueError, 'actual QA issue'):
            w.repair_attempt(self.task, 'INVENTED-ISSUE', 'a', 10)
        self.assertEqual(w.load(self.task)['repairs'], {})

    def test_renamed_qa_issues_share_strategy_and_attempt_caps(self):
        data = w.load(self.task)
        data.pop('autonomy_policy')  # Recorded historical policy retains its original caps.
        w.write(self.task / 'task.json', data)
        self.animatic()
        self.report_defect('TOOTH-1')
        w.repair_attempt(self.task, 'TOOTH-1', 'existing-constraint', 10)
        w.repair_attempt(self.task, 'TOOTH-1', 'existing-constraint', 9)
        self.report_defect('TOOTH-RENAMED')
        w.repair_attempt(self.task, 'TOOTH-RENAMED', 'existing-constraint', 8)
        with self.assertRaisesRegex(ValueError, 'two attempts'):
            w.repair_attempt(self.task, 'TOOTH-RENAMED', 'existing-constraint', 7)
        w.repair_attempt(self.task, 'TOOTH-RENAMED', 'qualified-asset', 7)
        self.report_defect('TOOTH-THIRD-ID')
        w.repair_attempt(self.task, 'TOOTH-THIRD-ID', 'qualified-asset', 6)
        with self.assertRaisesRegex(ValueError, 'two repair strategies'):
            w.repair_attempt(self.task, 'TOOTH-THIRD-ID', 'third-strategy', 5)
        repairs = w.load(self.task)['repairs']
        self.assertEqual(set(repairs), {'interpenetration:chain_teeth'})
        self.assertEqual(repairs['interpenetration:chain_teeth']['strategies'],
                         {'existing-constraint': 2, 'qualified-asset': 2})
        self.assertEqual(w.repair_key(self.task, 'TOOTH-1'), 'interpenetration:chain_teeth')

    def test_renaming_stopped_defect_cannot_create_another_baseline(self):
        data = w.load(self.task)
        data.pop('autonomy_policy')
        w.write(self.task / 'task.json', data)
        self.animatic()
        self.report_defect('TOOTH-1')
        w.repair_attempt(self.task, 'TOOTH-1', 'a', 10)
        w.repair_attempt(self.task, 'TOOTH-1', 'a', 10)
        self.report_defect('TOOTH-RENAMED')
        with self.assertRaisesRegex(ValueError, 'Issue stopped'):
            w.repair_attempt(self.task, 'TOOTH-RENAMED', 'b', 9)
        self.assertEqual(w.load(self.task)['state'], 'BLOCKED')

    def test_relabeling_same_issue_as_another_defect_is_rejected(self):
        self.animatic()
        self.report_defect('TOOTH-1')
        w.repair_attempt(self.task, 'TOOTH-1', 'a', 10)
        self.report_defect('TOOTH-1', 'different:requirement')
        with self.assertRaisesRegex(ValueError, 'conflicting persistent'):
            w.repair_attempt(self.task, 'TOOTH-1', 'a', 9)

    def diagnostic(self):
        self.handoff('research', {'facts': ['diagnostic only']})
        self.handoff('asset-plan', {'qualified': False, 'reason': 'Motion unverified'})
        self.evidence = self.media('diagnostic.mp4')
        blueprint = self.root / 'provisional-blueprint.json'
        blueprint.write_text(json.dumps({'status': 'PROVISIONAL', 'shots': []}))
        self.diagnostic_manifest = {
            'status': 'DRAFT_UNAPPROVED', 'media': self.evidence,
            'blueprint_evidence': {'path': str(blueprint), 'sha256': w.filehash(blueprint)}}
        self.handoff('diagnostic-animatic', self.diagnostic_manifest)
        self.qa = {'media': self.evidence, 'independent_reviewer': True,
                   'reviewer_thread_id': 'diagnostic-independent-qa', 'issues': [],
                   'checks': {'encoding': 'PASS', 'mechanics': 'UNKNOWN'}}
        self.handoff('diagnostic-qa', self.qa)

    def test_diagnostic_handoffs_allow_failed_asset_without_approval_bypass(self):
        self.diagnostic()
        self.assertFalse(w.artifact(self.task, 'asset-plan')['qualified'])
        self.assertEqual(w.artifact(self.task, 'diagnostic-animatic')['status'], 'DRAFT_UNAPPROVED')
        with self.assertRaisesRegex(ValueError, 'cannot grant production acceptance'):
            w.check_qa(self.task, 'diagnostic-qa')
        with self.assertRaisesRegex(ValueError, 'Missing handoff: creative-blueprint'):
            w.require_animatic(self.task)
        self.state('ANIMATING')
        with patch.object(w.subprocess, 'run') as run:
            with self.assertRaisesRegex(ValueError, 'Missing handoff: creative-blueprint'):
                w.run_stage(self.task, 'preview', self.config)
            run.assert_not_called()

    def test_diagnostic_media_blueprint_and_qa_evidence_are_mandatory(self):
        self.diagnostic()
        for update, message in [({'status': 'PASS'}, 'DRAFT_UNAPPROVED'),
                                ({'media': self.media('screenshot.png')}, 'actual MP4'),
                                ({'blueprint_evidence': {}}, 'JSON evidence')]:
            with self.subTest(update=update), self.assertRaisesRegex(ValueError, message):
                self.handoff('diagnostic-animatic', dict(self.diagnostic_manifest, **update))
        self.qa['media'] = self.media('other-diagnostic.mp4')
        with self.assertRaisesRegex(ValueError, 'exact diagnostic MP4'):
            self.handoff('diagnostic-qa', self.qa)

    def test_diagnostic_repair_budget_survives_new_media_and_renamed_issue(self):
        data = w.load(self.task)
        data.pop('autonomy_policy')
        w.write(self.task / 'task.json', data)
        self.diagnostic()
        issue = {'issue_id': 'CAPTION-1', 'defect_key': 'caption_contrast:bottom_subtitles',
                 'severity': 'major', 'shot_id': 's1', 'time_range': [0, 2],
                 'evidence': self.evidence, 'responsible_agent': 'Editor',
                 'suggested_fix': 'Improve caption contrast',
                 'verification_method': 'Inspect subtitle interval'}
        self.qa['issues'] = [issue]
        self.handoff('diagnostic-qa', self.qa)
        w.repair_attempt(self.task, 'CAPTION-1', 'existing-subtitle-style', 10)
        w.repair_attempt(self.task, 'CAPTION-1', 'existing-subtitle-style', 8)
        new_media = self.media('diagnostic-v2.mp4')
        self.diagnostic_manifest['media'] = new_media
        self.handoff('diagnostic-animatic', self.diagnostic_manifest)
        self.qa['media'] = new_media
        self.qa['issues'] = [dict(issue, issue_id='CAPTION-RENAMED', evidence=new_media)]
        self.handoff('diagnostic-qa', self.qa)
        w.repair_attempt(self.task, 'CAPTION-RENAMED', 'existing-subtitle-style', 6)
        with self.assertRaisesRegex(ValueError, 'two attempts'):
            w.repair_attempt(self.task, 'CAPTION-RENAMED', 'existing-subtitle-style', 4)
        self.assertEqual(set(w.load(self.task)['repairs']), {'caption_contrast:bottom_subtitles'})
        self.assertEqual(w.repair_key(self.task, 'CAPTION-1'), 'caption_contrast:bottom_subtitles')

    def test_legacy_task_cannot_register_diagnostic_artifacts(self):
        data = w.load(self.task)
        data.update(schema_version=1, protocol_version=1)
        w.write(self.task / 'task.json', data)
        self.handoff('research', {})
        self.handoff('asset-plan', {})
        with self.assertRaisesRegex(ValueError, 'protocol_version=2'):
            self.handoff('diagnostic-animatic', {}, ['research', 'asset-plan'])


if __name__ == '__main__':
    unittest.main()
