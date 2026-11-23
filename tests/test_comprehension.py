"""Contract counterexamples plus encoded-video binding checks; not audience tests."""
import copy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from mechanical_video_next import comprehension as c


def valid_plan():
    observation = dict(observed_product='fixture mop', identified_parts=['handle', 'head'],
                       assembly_positions='handle above head', unknowns=[], figure_or_region='whole product', internal_structure_visible=True)
    source = dict(reference_id='real', product_id='mop-A', mechanism_id='mop-A', type='photo', location='fixture://photo',
                  observations=observation, supported_claims=['identity', 'press handle', 'fixture transmission', 'head rotates'],
                  evidence_files=[dict(path=__file__, sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())], relationship_status='CONFIRMED',
                  relationship_evidence='same fixture product', depicts_real_product=True)
    shot = dict(shot_id='s1', time_range=[0, 1], narration=['press handle'], comprehension=dict(
        reference_ids=['real'], product_parts=['handle', 'head'], input_action='press handle',
        transmission='fixture transmission', output_action='head rotates', visual_evidence='fixture only',
        narration='press handle', new_knowledge='fixture input and output', necessity='show relation',
        causal_link='operation explains output', recognition_relations=sorted(c.RELATIONS),
        verification_method='independent continuous audiovisual inspection'))
    shot['comprehension']['causal_evidence'] = {stage: dict(reference_id='real', claim=shot['comprehension'][stage], position='fixture region') for stage in ('input_action', 'transmission', 'output_action')}
    return dict(product_policy_version=1, product_identity={k: 'mop-A' for k in c.PRODUCT_FIELDS},
                product_references=[source], shots=[shot], product_opening=dict(shot_id='s1', time_range=[0, 1],
                product_reveal='whole mop', real_action='press handle', why_question='why rotate?', answer_promise='conversion'))


def valid_report(plan, media):
    report = dict(independent=True, reviewer_role='QA', reviewer_thread_id='reviewer', production_thread_ids=['maker'], media=[media])
    row = dict(shot_id='s1', media_sha256=media['sha256'], observed_object='fixture', observed_action='fixture',
               observed_causal_chain='fixture', heard_narration='press handle', evidence='synthetic contract fixture only',
               answers={k: 'fixture answer' for k in c.QUESTIONS}, status='PASS', continuous_viewing=True,
               listening=True, viewing_method='continuous_video', time_range=[0, 1], narration_matches_action=True,
               product_identified=True, reference_ids=['real'], blind_observation=dict(script_withheld=True,
               object='fixture', action='fixture', observation_order=1), script_review_order=2)
    for category in ('product_recognition', 'mechanism_comprehension', 'viewer_comprehension'):
        item = copy.deepcopy(row)
        receipt = dict(item, reviewer_thread_id='reviewer', category=category,
                       limitation='SYNTHETIC_CONTRACT_FIXTURE_NOT_ACTUAL_PERCEPTUAL_REVIEW')
        path = Path(media['path']).parent / (category + '.review.json')
        path.write_text(json.dumps(receipt))
        item['actual_media_evidence'] = [dict(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest())]
        report[category] = [item]
    return report


class ComprehensionContracts(unittest.TestCase):
    def test_research_source_gate_runs_before_blueprint_or_cad(self):
        from tests.test_reference_workflow import ReferenceWorkflowTests
        from mechanical_video_next import workflow as w
        fixture = ReferenceWorkflowTests(); fixture.setUp()
        try:
            plan = valid_plan()
            fixture.research.update(product_identity=plan['product_identity'], product_references=plan['product_references'])
            fixture.research['mechanism_id'] = 'mop-A'
            fixture.research['references'][0]['mechanism_id'] = 'mop-A'
            task = w.load(fixture.task); task['product_policy_version'] = 1; w.write(fixture.task/'task.json', task)
            c.validate_product_research(fixture.research)  # no shots are required in research
            patent = fixture.research['product_references'][0]
            patent['type'] = 'patent'; patent['observations']['embodiment'] = 'specific fixture'
            with self.assertRaisesRegex(ValueError, 'PATENT_SOURCE_FORBIDDEN'):
                w.put_handoff(fixture.task, 'MechanicalResearch', 'research', fixture.research)
            self.assertNotIn('research', w.load(fixture.task)['handoffs'])
        finally:
            fixture.doCleanups()

    def test_asset_gate_rechecks_previously_accepted_legacy_research(self):
        from tests.test_reference_workflow import ReferenceWorkflowTests
        from mechanical_video_next import workflow as w
        fixture = ReferenceWorkflowTests(); fixture.setUp()
        try:
            w.put_handoff(fixture.task, 'MechanicalResearch', 'research', fixture.research)
            w.put_handoff(fixture.task, 'ViralResearch', 'viral-analysis', fixture.viral)
            data = w.load(fixture.task); data['product_policy_version'] = 1; w.write(fixture.task/'task.json', data)
            with self.assertRaisesRegex(ValueError, 'Real product identity'):
                w.put_handoff(fixture.task, 'Asset', 'asset-plan', fixture.asset)
        finally:
            fixture.doCleanups()

    def test_product_research_rejects_mixed_mechanisms(self):
        plan = valid_plan(); plan['mechanism_id'] = 'different-implementation'
        with self.assertRaisesRegex(ValueError, 'researched implementation'):
            c.validate_product_research(plan)
        plan['mechanism_id'] = 'mop-A'; plan['product_references'][0]['mechanism_id'] = 'other-patent'
        with self.assertRaisesRegex(ValueError, 'source mechanism'):
            c.validate_product_research(plan)

    def test_normal_plan_is_only_planning_validation(self):
        self.assertEqual(c.validate_product_plan(valid_plan())['status'], 'PLAN_VALIDATED_NOT_MEDIA_ACCEPTED')

    def test_reference_and_product_counterexamples(self):
        mutations = [
            lambda p: p.update(product_references=[]),
            lambda p: p['product_references'][0].update(type='cad'),
            lambda p: p['product_references'][0].update(type='patent'),
            lambda p: p['product_references'][0].update(relationship_status='UNKNOWN'),
            lambda p: p['product_references'][0].update(product_id='other-model'),
            lambda p: p['shots'][0]['comprehension'].update(recognition_relations=['mechanism']),
            lambda p: p['shots'][0]['comprehension'].update(transmission=''),
            lambda p: p['shots'][0]['comprehension'].update(narration='different action'),
            lambda p: p['product_references'][0]['observations'].update(internal_structure_visible=False),
            lambda p: p['shots'][0]['comprehension']['causal_evidence'].update(transmission={}),
            lambda p: p['product_opening'].update(time_range=[5, 6]),
        ]
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                p = valid_plan(); mutate(p)
                with self.assertRaises(ValueError): c.validate_product_plan(p)

    def test_duplicate_knowledge_rejected(self):
        p = valid_plan(); second = copy.deepcopy(p['shots'][0]); second.update(shot_id='s2', time_range=[1, 2]); p['shots'].append(second)
        with self.assertRaisesRegex(ValueError, 'Repeated'): c.validate_product_plan(p)

    def test_screenshots_cannot_prove_continuous_source_motion(self):
        p = valid_plan(); ref = p['product_references'][0]; ref['type'] = 'video'
        ref['observations'].update(viewed_ranges=[[0, 1]], key_timecodes=[0], confirmed_actions=['press'],
                                   viewing_method='frames_only', continuous_motion_verified=True)
        with self.assertRaisesRegex(ValueError, 'Screenshots'): c.validate_product_plan(p)

    def test_current_mop_cannot_bypass_with_missing_version(self):
        self.assertTrue(c.enabled({'task_id': 'spin-mop-20261115', 'product_policy_version': 1}))
        self.assertFalse(c.enabled({'task_id': 'historic'}))

    def test_blueprint_compiler_does_not_drop_comprehension_bindings(self):
        from tests.test_blueprint import BlueprintTests
        from mechanical_video_next import blueprint
        fixture = BlueprintTests(); fixture.setUp()
        try:
            plan = valid_plan()
            fixture.data.update({k: plan[k] for k in ('product_policy_version', 'product_identity',
                                                      'product_references', 'product_opening')})
            fixture.data['product_opening']['shot_id'] = 'opening'
            fixture.data['shots'][0]['comprehension'] = plan['shots'][0]['comprehension']
            fixture.data['shots'][0]['narration'] = ['press handle']
            fixture.save()
            binding = blueprint.compile_config(fixture.blueprint, fixture.base, fixture.output)
            config = json.loads(fixture.output.read_text())
            self.assertEqual(config['product_identity'], plan['product_identity'])
            self.assertEqual(config['storyboard'][0]['comprehension'], plan['shots'][0]['comprehension'])
            self.assertEqual(binding['shot_requirements'][0]['comprehension'], plan['shots'][0]['comprehension'])
        finally:
            fixture.doCleanups()


@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'ffmpeg required')
class EncodedMediaCounterexamples(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(); cls.path = Path(cls.tmp.name)/'fixture.mp4'
        # Deliberately synthetic grey video/tone. Validates files, not product perception.
        subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'color=c=gray:s=32x32:r=30',
                        '-f', 'lavfi', '-i', 'sine=frequency=440', '-t', '1', '-c:v', 'libx264',
                        '-c:a', 'aac', '-y', str(cls.path)], check=True)
        cls.media = dict(path=str(cls.path), sha256=hashlib.sha256(cls.path.read_bytes()).hexdigest())

    @classmethod
    def tearDownClass(cls): cls.tmp.cleanup()

    def test_real_encoded_media_binding_normal_contract(self):
        p = valid_plan(); report = valid_report(p, self.media)
        self.assertEqual(c.validate_media_qa(p, report)['scope'], 'independent-reviewer-proxy-only')

    def test_pass_without_actual_evidence_and_false_capabilities_rejected(self):
        mutations = [
            lambda r: r.update(media=[]),
            lambda r: r['media'][0].update(sha256='stale'),
            lambda r: r.update(reviewer_thread_id='maker'),
            lambda r: r['viewer_comprehension'][0].update(evidence=''),
            lambda r: r['viewer_comprehension'][0].update(continuous_viewing=False),
            lambda r: r['viewer_comprehension'][0].update(listening=False),
            lambda r: r['viewer_comprehension'][0].update(viewing_method='frames_only'),
            lambda r: r['mechanism_comprehension'][0].update(narration_matches_action=False),
            lambda r: r['product_recognition'][0].update(product_identified=False),
            lambda r: r['viewer_comprehension'][0].update(time_range=[0, .2]),
            lambda r: r['viewer_comprehension'][0]['blind_observation'].update(observation_order=3),
        ]
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                p = valid_plan(); r = valid_report(p, copy.deepcopy(self.media)); mutate(r)
                with self.assertRaises(ValueError): c.validate_media_qa(p, r)

    def test_missing_full_mp4_rejected(self):
        p = valid_plan(); p['shots'][0]['time_range'] = [0, 149]
        with self.assertRaisesRegex(ValueError, 'Incomplete MP4'):
            c.validate_media_qa(p, valid_report(p, self.media))

    def test_unrelated_or_empty_review_receipt_cannot_grant_pass(self):
        for content in ('{}', 'unrelated source text', '{"media_sha256":"another-video"}'):
            with self.subTest(content=content):
                p = valid_plan(); report = valid_report(p, self.media)
                path = Path(self.tmp.name)/'unrelated-review.json'; path.write_text(content)
                report['viewer_comprehension'][0]['actual_media_evidence'] = [dict(
                    path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest())]
                with self.assertRaisesRegex(ValueError, 'receipt'):
                    c.validate_media_qa(p, report)

    def test_arbitrary_nonempty_evidence_string_without_receipt_rejected(self):
        p = valid_plan(); report = valid_report(p, self.media)
        report['viewer_comprehension'][0].pop('actual_media_evidence')
        with self.assertRaisesRegex(ValueError, 'bound review receipt'):
            c.validate_media_qa(p, report)
