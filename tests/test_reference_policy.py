"""Synthetic light contracts only: no historical task, CAD, or media writes."""
import copy
import unittest
import hashlib
import json
import tempfile
from pathlib import Path
from mechanical_video_next import reference_policy as p


def fixture(strategy='verified-existing'):
    research = {'mechanism_id': 'fixture-two-gear', 'references': [{
        'id': 'manual', 'location': 'fixture://manual', 'source_name': 'Synthetic fixture',
        'author': 'test author', 'type': 'drawing', 'acquired_at': '2026-11-15',
        'viewed_scope': {'status': 'DRAWING_INSPECTED', 'evidence': ['fixture-only review'],
                         'drawing_numbers': ['A1'], 'parts': ['input','output'],
                         'connections': ['mesh'], 'dimensions': ['module=1 fixture']},
        'structure_evidence': ['A1 gear mesh'], 'motion_evidence': ['manual arrows'],
        'license': 'test fixture CC0', 'usable_content': ['synthetic drawing'],
        'mechanism_id': 'fixture-two-gear', 'unknowns': [], 'conflicts': [],
        'unresolved_core_conflict': False}]}
    candidates = []
    for name in p.STRATEGIES:
        candidates.append({'strategy': name, 'id': name, 'qualified': name == strategy,
            'reason': 'synthetic fixture qualification' if name == strategy else 'searched; unavailable',
            'source_ids': ['manual'], 'mechanism_id': research['mechanism_id'],
            'validation_evidence': ['fixture assembly check'], 'legal_use': True,
            'content_match': True, 'source_files': [{'path':__file__,'sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}]})
    asset = {'strategy': strategy, 'selected_candidate_id': strategy, 'candidates': candidates,
             'model':copy.deepcopy(candidates[1]['source_files'][0]),
             'mechanism_id': research['mechanism_id'], 'model_source':'fixture manual', 'substantive_repairs':[]}
    blueprint = {'core_question':'How does input drive output?', 'duration_seconds':120,
        'shots':[{'shot_id':'s1','knowledge_ids':['k1'],'time_range':[0,120]}],
        'evidence_map':[{'knowledge_id':'k1','conclusion':'input gear drives output',
            'source_ids':['manual'], 'reference_locations':[{'source_id':'manual','position':'A1 mesh arrows'}],
            'parts':['input','output'], 'actions':['input rotation','output rotation'],
            'usable_material':['manual redraw'], 'shot_ids':['s1'],
            'verification_method':'compare marked rotation to A1', 'verified':True}],
        'content_timing':{'status':'PASS','basis':'synthetic measured fixture; no real content acceptance',
            'measured_narration_seconds':115, 'chapters':[{'id':'c1','knowledge_ids':['k1'],
                'new_information':'transmission','duration_reason':'fixture timing only'}]}}
    qa = {'reviewer_role':'QA','independent':True,'plan_sha256':p.plan_digest(blueprint,research,asset),
          'content_checks':{key:{'status':'PASS','evidence':['synthetic test check']} for key in p.CONTENT_CHECKS}}
    return blueprint,research,asset,qa


class ReferencePolicyTests(unittest.TestCase):
    def test_route_plan_commands_and_external_inputs_bound(self):
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/'input.json'; source.write_text('{}')
            plan=Path(tmp)/'plan.json'
            plan.write_text(json.dumps({'steps':[{'command':['uv','run','tool'],
                'inputs':[str(source)],'outputs':[]}]}))
            binding={'path':str(plan),'sha256':hashlib.sha256(plan.read_bytes()).hexdigest(),
                     'input_hashes':{str(source.resolve()):hashlib.sha256(source.read_bytes()).hexdigest()}}
            p.validate_route_plan(plan,binding)
            # A later writer cannot exempt an earlier external reader.
            plan.write_text(json.dumps({'steps':[
                {'inputs':[str(source)],'outputs':[]},
                {'inputs':[],'outputs':[str(source)]}]}))
            binding['sha256']=hashlib.sha256(plan.read_bytes()).hexdigest()
            p.validate_route_plan(plan,binding)
            source.write_text('{"changed":true}')
            with self.assertRaisesRegex(ValueError,'external inputs'): p.validate_route_plan(plan,binding)
            plan.write_text('{"steps":[]}')
            with self.assertRaisesRegex(ValueError,'reviewed commands'): p.validate_route_plan(plan,binding)

    def test_internal_generated_input_needs_no_external_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            generated=str(Path(tmp)/'not-yet-generated.json')
            plan=Path(tmp)/'plan.json'
            plan.write_text(json.dumps({'steps':[{'inputs':[],'outputs':[generated]},
                                                 {'inputs':[generated],'outputs':[]}]}))
            p.validate_route_plan(plan,{'path':str(plan),
                'sha256':hashlib.sha256(plan.read_bytes()).hexdigest(),'input_hashes':{}})

    def test_content_qa_blocking_issues_rejected(self):
        for severity in ('blocking','critical','major','error'):
            b,r,a,q=fixture()
            q['issues']=[{'severity':severity,'evidence':'unresolved mechanical error'}]
            with self.assertRaisesRegex(ValueError,'blocking content QA'): p.validate_preproduction(b,r,a,q)

    def test_appearance_and_mismatched_viewing_rejected(self):
        b,r,a,q = fixture()
        r['references'][0]['type']='photo'
        with self.assertRaisesRegex(ValueError,'Appearance-only'): p.validate_research(r)
        r['references'][0]['type']='cad'
        with self.assertRaisesRegex(ValueError,'match reference type'): p.validate_research(r)

    def test_existing_model_must_be_selected_source(self):
        b,r,a,q = fixture()
        a['model']={'path':'invented.glb','sha256':'unbound'}
        with self.assertRaisesRegex(ValueError,'actual asset model'): p.validate_asset(r,a)
    def test_prefers_qualified_existing_model(self):
        b,r,a,q = fixture()
        self.assertEqual(p.validate_preproduction(b,r,a,q)['asset_strategy'],'verified-existing')

    def test_permits_evidence_based_parametric_model(self):
        b,r,a,q = fixture('autonomous-cad')
        self.assertEqual(p.validate_preproduction(b,r,a,q)['knowledge_points'],1)

    def test_insufficient_evidence_rejects_invention(self):
        b,r,a,q = fixture('autonomous-cad')
        r['references'][0]['viewed_scope']['status']='COVER_ONLY'
        with self.assertRaisesRegex(ValueError,'Title, cover'):
            p.validate_plan(b,r,a)
        b,r,a,q = fixture()
        for candidate in a['candidates']: candidate['qualified']=False
        with self.assertRaisesRegex(ValueError,'never invent'):
            p.validate_plan(b,r,a)

    def test_legal_matching_media_has_priority(self):
        b,r,a,q = fixture()
        a['candidates'][0]['qualified']=True
        with self.assertRaisesRegex(ValueError,'prefer qualified legal reuse'):
            p.validate_asset(r,a)
        a.update(strategy='existing-media',selected_candidate_id='existing-media')
        with self.assertRaisesRegex(ValueError,'executable 3D provenance'):
            p.validate_asset(r,a)
        a['candidates'][0]['legal_use']=False
        with self.assertRaisesRegex(ValueError,'permitted use'): p.validate_asset(r,a)

    def test_model_mixing_and_missing_claim_positions_rejected(self):
        b,r,a,q = fixture()
        r['references'][0]['mechanism_id']='different-product'
        with self.assertRaisesRegex(ValueError,'mixed mechanism'): p.validate_plan(b,r,a)
        b,r,a,q = fixture()
        b['evidence_map'][0]['reference_locations'][0]['source_id']='other'
        with self.assertRaisesRegex(ValueError,'bind its source'): p.validate_plan(b,r,a)

    def test_missing_narration_claim_and_padding_rejected(self):
        b,r,a,q = fixture()
        b['shots'][0]['knowledge_ids']=['invented']
        with self.assertRaisesRegex(ValueError,'verified knowledge'): p.validate_plan(b,r,a)
        b,r,a,q = fixture()
        b['content_timing']['chapters'].append(copy.deepcopy(b['content_timing']['chapters'][0]))
        with self.assertRaisesRegex(ValueError,'Repeated'): p.validate_plan(b,r,a)
        b,r,a,q = fixture()
        b['content_timing']['status']='INSUFFICIENT_CONTENT'
        with self.assertRaisesRegex(ValueError,'Content insufficient'): p.validate_plan(b,r,a)

    def test_independent_qa_unknown_and_stale_bindings_block(self):
        b,r,a,q = fixture()
        q['content_checks']['model_matches']['status']='UNKNOWN'
        with self.assertRaisesRegex(ValueError,'FAIL/UNKNOWN'): p.validate_preproduction(b,r,a,q)
        b,r,a,q = fixture()
        a['model_source']='changed version'
        with self.assertRaisesRegex(ValueError,'exact reference'): p.validate_preproduction(b,r,a,q)

    def test_video_requires_actual_time_ranges_and_patent_embodiment(self):
        b,r,a,q = fixture()
        ref=r['references'][0]; ref['type']='video'; ref['viewed_scope']['status']='VIDEO_INSPECTED'
        with self.assertRaisesRegex(ValueError,'time ranges'): p.validate_research(r)
        ref['viewed_scope'].update(time_ranges=[[1,5]],confirmed_actions=['gear rotates'])
        p.validate_research(r)
        ref['type']='patent'; ref['viewed_scope']['status']='DOCUMENT_READ'
        with self.assertRaisesRegex(ValueError,'Patent'): p.validate_research(r)
        ref['viewed_scope'].update(embodiment='Example 2',figure_numbers=['Fig 3'])
        p.validate_research(r)

    def test_report_rejects_invented_measurements_and_unverified_claims(self):
        media=[{'path':'fixture.mp4','sha256':'fixture'}]
        report={'media':media,'primary_references':['manual'],'model_material_sources':['fixture'],
                'teaching_approximations':['module dimensions'], 'duration_added_knowledge':['transmission'],
                'removed_repetition':['duplicate explode'], 'actual_reuse_ratio':None,
                'supported_knowledge_count':1,'unverified_conclusions':[],
                'wrong_structure_rebuilds':None,'human_interventions':None}
        p.validate_final_report(report,media)
        report['actual_reuse_ratio']=.8
        with self.assertRaisesRegex(ValueError,'measured basis'): p.validate_final_report(report,media)
        report['actual_reuse_ratio']=None; report['unverified_conclusions']=['unseen spring']
        with self.assertRaisesRegex(ValueError,'Unverified'): p.validate_final_report(report,media)
