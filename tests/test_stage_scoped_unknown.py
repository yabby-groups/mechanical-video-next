"""Stage-scoped evidence gates, without claiming synthetic media perception."""
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mechanical_video_next import workflow as w, reference_policy as rp, comprehension as c
from tests.test_reference_policy import fixture
from tests.test_comprehension import valid_plan


class StageScopedUnknownTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.task = w.create_task('synthetic mechanism', root=Path(self.tmp.name), protocol_version=1)
        media = self.task / 'preview.mp4'
        media.write_bytes(b'synthetic binding; not real video acceptance')
        self.media = [dict(path=str(media), sha256=w.filehash(media))]
        self.qa = dict(media=self.media, checks={key: 'PASS' for key in w.QA_CHECKS},
                       independent_reviewer=True, reviewer_thread_id='independent', issues=[])

    def check(self, acceptance):
        with patch.object(w, 'artifact', side_effect=lambda task, name: self.qa if name.endswith('-qa') else dict(media=self.media)):
            return w.check_qa(self.task, 'preview-qa', acceptance=acceptance)

    def test_reference_video_unknown_does_not_erase_verified_drawing(self):
        _, research, _, _ = fixture()
        video = copy.deepcopy(research['references'][0])
        video.update(id='unwatched', type='video', viewed_scope=dict(status='UNKNOWN', evidence=['no continuous viewing capability']))
        research['references'].append(video)
        self.assertEqual(set(rp.validate_research(research)), {'manual'})
        research['references'] = [video]
        with self.assertRaisesRegex(ValueError, 'continue research'):
            rp.validate_research(research)

    def test_replacement_technical_basis_requires_new_bindings_and_current_sources(self):
        data = w.load(self.task)
        before = self.task / 'before.json'
        w.write(before, data)
        plan = self.task / 'plan.json'
        plan.write_text('{}')
        data['handoffs'] = {name: dict(path='new-' + name, sha256=name) for name in
                            ('research', 'asset-plan', 'creative-blueprint', 'mechanical-qa')}
        data['production_plan'] = dict(path=str(plan), sha256=w.filehash(plan))
        data['reference_remake'] = dict(old_scheme_status='REJECTED_BY_USER',
            previous_task_snapshot=str(before), preview_accepted=False,
            mechanism_basis=dict(status='PASS', mechanism_id='fixture implementation',
                scope='specified documented embodiment', evidence=['located technical drawing'],
                source_bindings=[dict(path=str(plan), sha256=w.filehash(plan))]),
            production_binding=dict(handoffs=data['handoffs'], production_plan=data['production_plan']))
        w.require_current_scheme(data)
        # A local mechanism preview precedes the full creative/growth blueprint
        # and its own media QA. Source-bound mechanical evidence still applies.
        candidate = copy.deepcopy(data)
        del candidate['handoffs']['creative-blueprint']
        del candidate['handoffs']['mechanical-qa']
        w.require_current_scheme(candidate, candidate_preview=True)
        w.require_current_scheme(candidate)
        data['reference_remake']['mechanism_basis']['status'] = 'UNKNOWN'
        with self.assertRaisesRegex(ValueError, 'User-rejected'):
            w.require_current_scheme(data)

    def test_documented_specific_mechanism_does_not_require_retail_model(self):
        plan = valid_plan()
        source = plan['product_references'][0]
        source.update(type='patent', depicts_real_product=False)
        source['observations'].update(embodiment='specific fixture embodiment', confirmed_actions=['input drives output'])
        plan['product_identity'].update(identity_basis='documented_mechanism', teaching_scope='principle illustration of specified embodiment')
        self.assertIn('real', c.validate_product_sources(plan))
        del plan['product_identity']['teaching_scope']
        with self.assertRaisesRegex(ValueError, 'scope'):
            c.validate_product_sources(plan)

    def test_sensory_unknown_allows_production_but_never_acceptance(self):
        for key in w.PERCEPTUAL_CHECKS & w.QA_CHECKS:
            with self.subTest(key=key):
                self.qa['checks'][key] = 'UNKNOWN'
                self.check(False)
                with self.assertRaisesRegex(ValueError, 'UNKNOWN'):
                    self.check(True)
                self.qa['checks'][key] = 'PASS'

    def test_mechanical_unknown_and_preview_fail_block_for_repair(self):
        for key, value in [('mechanics', 'UNKNOWN'), ('listening', 'FAIL')]:
            with self.subTest(key=key):
                self.qa['checks'][key] = value
                with self.assertRaisesRegex(ValueError, 'FAIL/UNKNOWN'):
                    self.check(False)
                self.qa['checks'][key] = 'PASS'

    def test_growth_and_comprehension_unknown_are_deferred_until_acceptance(self):
        data = w.load(self.task)
        data.update(content_policy_version=1, product_policy_version=1)
        w.write(self.task / 'task.json', data)
        with patch.object(w, 'artifact', side_effect=lambda task, name: self.qa if name.endswith('-qa') else dict(media=self.media)), \
                patch.object(c, 'validate_media_qa', side_effect=ValueError('UNKNOWN comprehension')) as comprehension, \
                patch('mechanical_video_next.growth.validate_media_checks', side_effect=ValueError('UNKNOWN growth')) as growth, \
                patch('mechanical_video_next.growth.check_media_duration'):
            w.check_qa(self.task, 'preview-qa', acceptance=False)
            comprehension.assert_not_called()
            growth.assert_not_called()
            with self.assertRaisesRegex(ValueError, 'UNKNOWN comprehension'):
                w.check_qa(self.task, 'preview-qa')

    def test_agent_completion_and_unknown_review_leave_producer_working(self):
        data = w.load(self.task)
        data['agent_runs'] = [dict(role='CAD', thread_id='cad', status='COMPLETED')]
        data['handoffs'] = {'preview-qa': {}}
        w.write(self.task / 'task.json', data)
        self.qa['checks']['listening'] = 'UNKNOWN'
        with patch.object(w, 'artifact', return_value=self.qa):
            report = w.continuation(self.task)
        self.assertFalse(report['delivered'])
        self.assertEqual(report['lifecycle'], 'WORKING')
        self.assertIsNotNone(report['next_action']['action'])

    def test_fail_points_to_repair_and_final_rendered_unknown_is_not_delivered(self):
        data = w.load(self.task)
        data.update(state='COMPLETED', handoffs={'preview-qa': {}}, route_runs={'3d': {'outputs': self.media[0]}})
        w.write(self.task / 'task.json', data)
        self.qa['checks']['listening'] = 'UNKNOWN'
        with patch.object(w, 'artifact', return_value=self.qa), patch.object(w, 'complete_media'):
            report = w.continuation(self.task)
            self.assertEqual(report['milestone'], 'FINAL_RENDERED')
            self.assertFalse(report['delivered'])
            self.qa['checks']['listening'] = 'FAIL'
            report = w.continuation(self.task)
            self.assertEqual(report['lifecycle'], 'REPAIRING')
            self.assertEqual(report['next_action']['qa_handoff'], 'preview-qa')
