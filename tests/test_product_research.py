import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from mechanical_video_next import product_assembly, product_research, reference_library, workflow
from scripts.common import filehash


class ProductResearchTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.library = self.root / 'references'

    def test_fresh_task_retries_bounded_public_queries_and_keeps_hits_unverified(self):
        task = workflow.create_task('rice cooker', root=self.root,
                                    visual_policy_version=2, media_policy_version=1)
        action = workflow.continuation(task, persist=False)['next_action']
        self.assertEqual(action['kind'], 'EXECUTABLE_COMMAND')
        self.assertIn('mechanical_video_next.product_research', action['command'])
        plan = json.loads(Path(action['product_search_plan']).read_text())
        self.assertFalse(plan['cached'])
        self.assertEqual({row['language'] for row in plan['queries']}, {'en', 'ja', 'zh'})
        source = ('https://example.com/rice-cooker', 'Rice cooker disassembly')
        unrelated = ('https://example.com/spam', 'Unrelated pizza')
        patent = ('https://patents.google.com/patent/US7900978B2/en', 'Rice cooker')

        def lookup(query):
            if query['category'] == 'ifixit':
                raise OSError('temporary outage')
            return [unrelated, patent, source]

        with patch.object(product_research, 'search', side_effect=lookup) as browser:
            # Inject public results into the explicit discovery function.
            result = product_research.discover(plan, lookup=browser)
        self.assertGreater(len(result['attempts']), 1)
        self.assertEqual(result['status'], 'INSPECTION_REQUIRED')
        self.assertEqual([(row['url'], row['status']) for row in result['leads']], [(source[0], 'UNKNOWN')])

    def test_reuses_valid_inspection_and_keeps_models_separate(self):
        source = self.root / 'repair.txt'
        source.write_text('Test fixture records the installed hinge.')
        evidence = [dict(path=str(source), sha256=filehash(source), position='Figure 1')]
        row = dict(url='https://example.com/repair?utm_source=track', title='Rice cooker model A',
                   model='A-100', category='repair', status='INSPECTED', license='REFERENCE_ONLY',
                   scope='Rice cooker installation', coverage=['parts', 'assembly'], evidence=evidence)
        record = reference_library.ingest_product_source(row, self.library)
        plan = reference_library.product_search_plan('rice cooker', 'How does it move?', root=self.library,
                                                      seeds=['https://example.com/repair'])
        self.assertEqual(plan['seeds'], [])
        self.assertEqual(plan['cached'][0]['canonical_id'], record['canonical_id'])
        second = dict(record, model='B-200', coverage=['exterior', 'motion'])
        report = reference_library.product_implementations([record, second], pinned_model='A-100')
        self.assertEqual(report[0]['missing'], ['exterior', 'motion'])
        source.write_text('Changed')
        self.assertFalse(reference_library.find_product_sources('rice cooker', self.library))

    def test_compiles_installed_removal_order_and_restores_parts(self):
        graph = {'parts': {name: {'object': name} for name in ('housing', 'cover', 'pin', 'gear')},
                 'connections': {'uncover': {'removal': {'parts': ['cover'], 'path': [[0, 0, 1]]}},
                                 'pin': {'removal': {'parts': ['pin'], 'path': [[0, 1, 0], [1, 1, 0]],
                                                     'after': ['uncover']}}}}
        plan = product_assembly.reveal_plan(graph, {'connections': ['pin'], 'anchor': 'housing',
                                                   'targets': {'gear': [0, 0, 0]}})
        self.assertEqual(plan['groups'], [['cover'], ['pin']])
        clock = product_assembly.path_clock(plan)
        for keys in clock.values():
            self.assertEqual((keys[0], keys[-1]), ((0, [0, 0, 0]), (1, [0, 0, 0])))
        self.assertLess(clock['cover'][2][0], clock['pin'][2][0])
