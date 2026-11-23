import copy
import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image
from pypdf import PdfWriter

from mechanical_video_next import comprehension, reference_policy, source_policy, workflow
from scripts.common import filehash


class ProductionSourceTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.task = workflow.create_task('Test cabinet latch', root=self.root,
                                         visual_policy_version=2, media_policy_version=1)
        self.policy = workflow.load(self.task)

    def binding(self, path):
        return dict(path=str(path), sha256=filehash(path))

    def pdf(self, filename, title):
        path = self.root / filename
        writer = PdfWriter()
        writer.add_blank_page(width=200, height=200)
        writer.add_metadata({'/Title': title})
        writer.write(path)
        return self.binding(path)

    def test_new_task_rejects_typed_and_relabelled_sources_with_older_policy_fields(self):
        self.assertEqual(self.policy[source_policy.FIELD], source_policy.NO_PATENT_POLICY_VERSION)
        for source in (
            {'type': 'patent', 'location': 'fixture://sample'},
            {'type': 'document', 'location': 'https://patents.google.com/patent/US7900978B2/en'},
            {'type': 'drawing', 'document_id': 'CN 204764965 U'},
            {'type': 'cad', 'evidence_files': [self.pdf('unlabelled.bin', 'United States Patent')]},
        ):
            with self.subTest(source=source):
                payload = {'references': [source], 'production_contract_version': 1}
                with self.assertRaisesRegex(ValueError, 'PATENT_SOURCE_FORBIDDEN'):
                    workflow.put_handoff(self.task, 'Producer', 'research', payload)
        with self.assertRaisesRegex(ValueError, 'Unsupported no-patent'):
            workflow.put_handoff(self.task, 'Producer', 'research', {source_policy.FIELD: 0})
        self.assertFalse(self.policy['handoffs'])

    def test_cad_assembly_and_blueprint_follow_linked_sources(self):
        provenance = self.root / 'provenance.json'
        provenance.write_text(json.dumps({'source_files': [{'document_id': 'US7900978B2'}]}))
        asset = {'model_provenance': self.binding(provenance)}
        with self.assertRaisesRegex(ValueError, 'PATENT_SOURCE_FORBIDDEN'):
            reference_policy.validate_asset({}, asset, policy=self.policy)
        with self.assertRaisesRegex(ValueError, 'PATENT_SOURCE_FORBIDDEN'):
            workflow.put_handoff(self.task, 'CAD', 'cad-model', asset)
        with self.assertRaisesRegex(ValueError, 'PATENT_SOURCE_FORBIDDEN'):
            workflow.validate_production_sources(self.task, {'assembly_config': str(provenance)}, policy=self.policy)
        with self.assertRaisesRegex(ValueError, 'PATENT_SOURCE_FORBIDDEN'):
            workflow.put_handoff(self.task, 'Producer', 'creative-blueprint',
                                 {'production_config': self.binding(provenance)})

    def test_archived_policy_keeps_pinned_source_and_bytes(self):
        historical = {'type': 'patent', 'location': 'https://patents.google.com/patent/US7900978B2/en'}
        path = self.root / 'historical.json'
        path.write_text(json.dumps(historical))
        before = filehash(path)
        source_policy.validate_sources(historical, policy={})
        self.assertEqual(filehash(path), before)
        source_policy.validate_sources({'feedback': '旧版本采用 US7900978B2 专利作为资料。'}, policy=self.policy)

    def test_current_exterior_needs_model_matched_evidence(self):
        path = self.root / 'cabinet.jpg'
        Image.new('RGB', (12, 12)).save(path)
        product = dict.fromkeys(comprehension.PRODUCT_FIELDS, 'fixture')
        observation = dict(observed_product='fixture', identified_parts=['plate'],
                           assembly_positions='plate surrounds catch', unknowns=[],
                           figure_or_region='front', exterior_visible=True)
        ref = dict(reference_id='photo', product_id='fixture', mechanism_id='fixture',
                   type='photo', location=str(path), evidence_files=[self.binding(path)],
                   relationship_status='CONFIRMED', relationship_evidence='Label and part match',
                   depicts_real_product=True, supported_claims=['front plate'], observations=observation)
        research = dict(product_identity=product, product_references=[ref], mechanism_id='fixture')
        self.assertEqual(set(comprehension.validate_product_research(research, policy=self.policy)), {'photo'})
        for candidate in [dict(observation, exterior_visible=False), dict(observation, status='UNKNOWN')]:
            ref['observations'] = candidate
            with self.assertRaisesRegex(ValueError, 'PRODUCT_APPEARANCE_UNKNOWN'):
                comprehension.validate_product_research(research, policy=self.policy)
        ref.update(type='manual', observations=observation)
        self.assertTrue(comprehension.validate_product_research(research, policy=self.policy))
        ref.update(type='video', observations=dict(
            observation, viewed_ranges=[[1, 4]], key_timecodes=[2], confirmed_actions=['press'],
            viewing_method='continuous_video'))
        self.assertTrue(comprehension.validate_product_research(research, policy=self.policy))

    def test_unviewed_mechanism_source_is_unknown(self):
        row = dict.fromkeys(('location', 'source_name', 'author', 'acquired_at',
                             'structure_evidence', 'motion_evidence', 'license', 'usable_content'), 'fixture')
        row.update(id='manual', mechanism_id='fixture', type='manual', unknowns=[], conflicts=[],
                   viewed_scope={'status': 'UNKNOWN', 'evidence': 'unavailable'})
        with self.assertRaisesRegex(ValueError, 'mechanical facts UNKNOWN'):
            reference_policy.validate_research({'mechanism_id': 'fixture', 'references': [row]},
                                               policy=self.policy)

    def test_two_topics_share_native_reveal_and_reject_trimmed_or_caption_only_edit(self):
        for anchor, part in [('rear housing', 'side cover'), ('hinge support', 'top cover')]:
            with self.subTest(part=part):
                shot = dict(seconds=2, template='exploded_view', science={'disassembly': {
                    'operation': 'cycle', 'anchor': anchor, 'parts': {part: [0, 0, 1]},
                    'reveal_targets': {'contact': [0, 0, 0]}}})
                config = dict(shots={'one': shot}, storyboard=[dict(id='one', shot='one', seconds=2)])
                comprehension.validate_native_reveal(config)
                cut = copy.deepcopy(config)
                cut['storyboard'][0]['seconds'] = .5
                with self.assertRaisesRegex(ValueError, 'PRODUCT_DISASSEMBLY_MISSING'):
                    comprehension.validate_native_reveal(cut)
                shot.update(template='motion_trace', science={}, graphic={'text': 'Shell removed'})
                with self.assertRaisesRegex(ValueError, 'PRODUCT_DISASSEMBLY_MISSING'):
                    comprehension.validate_native_reveal(config)
