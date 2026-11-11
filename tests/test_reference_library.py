"""Local cache, provenance and approval gates; no network or renderer calls."""
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from mechanical_video_next import reference_library as lib
from mechanical_video_next import workflow as w


class ReferenceLibraryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'references'
        self.candidate = {
            'id': '../../unsafe-original-id',
            'url': 'https://www.douyin.com/video/123456?utm_source=test',
            'title': '拉链如何闭合', 'observed_at': '2026-11-11T08:00:00+08:00',
            'followers': None, 'likes': 1200, 'source': 'actual page observation',
            'confidence': 'PARTIAL', 'viewing': {'status': 'VIDEO_NOT_VIEWED'},
            'patterns': ['逐步解释'], 'hypotheses': ['Not observed as full video'],
            'evidence': [], 'unknown': {'audio': None}}

    def ingest(self, candidates=None, **extra):
        return lib.ingest({'candidates': candidates or [self.candidate], **extra},
                          '拉链', ['啮合', 'zipper'], self.root)

    def media(self, name):
        path = Path(self.temp.name) / name
        path.write_bytes(b'fixture for hash validation; not a quality claim')
        return [{'path': str(path), 'sha256': w.filehash(path)}]

    def blueprint(self):
        evidence = self.media('mechanics.png')
        blueprint = {
            'status': 'FROZEN', 'core_question': '拉链如何闭合',
            'original_topic': '拉链', 'knowledge_goals': ['guide and teeth'],
            'duration_seconds': 3, 'pacing': 'one movement', 'voice_requirements': 'Neil',
            'subtitle_requirements': 'matched', 'creative_decisions': ['original'], 'sources': ['fixture'],
            'qa_requirements': [{'requirement_id': 'q1', 'shot_id': 's1', 'expected_observable_effect': 'visible teeth',
                                 'verification_method': 'actual media', 'minimal_repair': 'camera'}],
            'opening_0_3': 'Question and existing mechanical movement',
            'first_motion_seconds': 1, 'disassembly_order': ['slider'],
            'closeups': ['teeth'], 'annotations': ['原理示意'],
            'narration_structure': ['question', 'cause'], 'sound_design': 'temporary narration',
            'causal_ending': 'Teeth engage in the slider',
            'shots': [{'shot_id': 's1', 'time_range': [0, 3], 'knowledge_goal': 'engagement',
                       'asset': 'verified fixture', 'template': 'detail',
                       'feasibility_evidence': evidence}],
            'reference_principles': [{'reference_id': 'observed-1', 'principle': 'show engagement',
                                       'production_requirement': 'show teeth', 'shot_ids': ['s1'],
                                       'expected_observable_effect': 'visible engagement', 'verification_method': 'actual media',
                                       'minimal_repair': 'camera', 'decision_basis': 'observed fixture',
                                       'implementation_cost': {'tier': 'low'},
                                       'evidence': evidence}]}
        qa = {'checks': dict.fromkeys(w.ANIMATIC_CHECKS, 'PASS'),
              'blueprint_sha256': w.digest(blueprint), 'independent_reviewer': True,
              'reviewer_thread_id': 'actual-qa-fixture', 'issues': [],
              'media': self.media('animatic.mp4')}
        return blueprint, qa

    def test_canonical_work_identity_handles_tracking_and_platform_forms(self):
        pairs = [
            ('https://www.youtube.com/watch?v=Ab_12&utm_source=x', 'https://youtu.be/Ab_12?t=4'),
            ('https://www.douyin.com/video/123456', 'https://www.douyin.com/?modal_id=123456'),
            ('https://www.xiaohongshu.com/explore/abc123?xsec_token=x',
             'https://www.xiaohongshu.com/discovery/item/abc123?source=x'),
            ('https://www.bilibili.com/video/BV1abc?spm=track', 'https://m.bilibili.com/video/BV1abc')]
        for a, b in pairs:
            with self.subTest(url=a):
                self.assertEqual(lib.canonical_video_id(a), lib.canonical_video_id(b))
        self.assertNotEqual(lib.canonical_video_id('https://example.org/watch?v=a'),
                            lib.canonical_video_id('https://example.org/watch?v=b'))

    def test_search_urls_and_unresolved_short_links_rejected(self):
        for url in ('file:///tmp/data', 'https://www.douyin.com/search/拉链',
                    'https://v.douyin.com/abc/', 'https://youtube.com/',
                    'https://example.org/', 'https://xhslink.com/abc'):
            with self.subTest(url=url), self.assertRaises(ValueError):
                lib.canonical_video_id(url)

    def test_unviewed_and_unknown_evidence_preserved_without_freshness_claim(self):
        self.ingest()
        result = lib.search('zipper', self.root)
        self.assertFalse(result['network_accessed'])
        self.assertFalse(result['freshness_confirmed'])
        candidate = result['results'][0]['observations'][0]['candidate']
        self.assertEqual(candidate, self.candidate)
        self.assertIsNone(candidate['followers'])
        self.assertEqual(candidate['viewing']['status'], 'VIDEO_NOT_VIEWED')

    def test_repeat_ingest_reuses_immutable_observation(self):
        first = self.ingest()
        path = next((self.root / 'patterns/observations').glob('*/*.json'))
        initial = path.read_bytes()
        second = self.ingest()
        self.assertEqual(first['new_observations'], 1)
        self.assertEqual(second['new_observations'], 0)
        self.assertEqual(path.read_bytes(), initial)
        self.assertEqual(len(list((self.root / 'patterns/observations').glob('*/*.json'))), 1)
        observation = json.loads(path.read_text())
        self.assertEqual(path.stem, w.digest(observation))
        self.assertEqual(observation['captured_at'], self.candidate['observed_at'])

    def test_multiple_observations_deduplicate_reference_but_keep_history(self):
        self.ingest()
        refreshed = dict(self.candidate, observed_at='2026-11-12T08:00:00+08:00',
                         likes=1500, url='https://www.douyin.com/?modal_id=123456')
        self.ingest([refreshed])
        result = lib.search('拉链', self.root)
        self.assertEqual(len(result['results']), 1)
        self.assertEqual(len(result['results'][0]['observations']), 2)
        self.assertEqual({o['candidate']['likes'] for o in result['results'][0]['observations']}, {1200, 1500})

    def test_theme_mechanism_and_pattern_indices_are_links_not_copied_candidates(self):
        self.ingest()
        for query in ('拉链', '啮合', '逐步解释'):
            self.assertEqual(len(lib.search(query, self.root)['results']), 1)
        for category in ('themes', 'mechanisms', 'patterns'):
            index = json.loads(next((self.root / category).glob('*.json')).read_text())
            self.assertIn('observations', index)
            self.assertNotIn('candidate', index)
        self.assertEqual(lib.search('nonexistent mechanism', self.root)['results'], [])

    def test_source_raw_file_hash_and_uncertainty_remain_available(self):
        source = Path(self.temp.name) / 'candidates.json'
        document = {'candidates': [self.candidate], 'status': 'BLOCKED'}
        source.write_text(json.dumps(document, indent=4))
        lib.ingest(document, '拉链', [], self.root, source)
        index = json.loads(next((self.root / 'themes').glob('*.json')).read_text())
        self.assertEqual(index['provenance'][0]['sha256'], w.filehash(source))
        self.assertEqual(index['provenance'][0]['path'], str(source.resolve()))

    def test_bad_capture_or_nonfinite_data_writes_no_library(self):
        for update in ({'observed_at': None}, {'observed_at': '2026-11-11'}, {'likes': float('nan')}):
            with self.subTest(update=update), self.assertRaises(ValueError):
                self.ingest([dict(self.candidate, **update)])
            self.assertFalse(self.root.exists())

    def test_arbitrary_ids_and_labels_never_become_paths(self):
        lib.ingest({'candidates': [self.candidate]}, '../../拉链', ['../../escape'], self.root)
        self.assertFalse((Path(self.temp.name) / 'escape').exists())
        self.assertEqual(len(list((self.root / 'themes').glob('*.json'))), 1)
        self.assertEqual(len(lib.search('escape', self.root)['results']), 1)

    def test_symlink_escape_and_tampering_are_rejected(self):
        self.root.mkdir()
        external = Path(self.temp.name) / 'external'
        external.mkdir()
        (self.root / 'patterns').symlink_to(external, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'escapes library root'):
            self.ingest()
        self.assertEqual(list(external.iterdir()), [])
        (self.root / 'patterns').unlink()
        self.ingest()
        observation = next((self.root / 'patterns/observations').glob('*/*.json'))
        data = json.loads(observation.read_text())
        data['candidate']['likes'] = 999999
        observation.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            lib.search('拉链', self.root)

    def test_only_frozen_blueprint_with_exact_actual_independent_qa_is_verified(self):
        blueprint, qa = self.blueprint()
        output = self.ingest(creative_blueprint=blueprint, blueprint_qa=qa)
        self.assertIsNotNone(output['blueprint'])
        results = lib.search('zipper', self.root)['blueprints']
        self.assertEqual(len(results), 1)
        self.assertTrue(results[0]['evidence_current'])
        Path(qa['media'][0]['path']).write_bytes(b'changed after capture')
        results = lib.search('拉链', self.root)['blueprints']
        self.assertFalse(results[0]['evidence_current'])
        self.assertEqual(results[0]['status'], 'VERIFIED_AT_CAPTURE')

    def test_unverified_blueprints_are_skipped_but_real_candidates_cached(self):
        blueprint, qa = self.blueprint()
        for update in ({'blueprint_sha256': 'wrong'}, {'independent_reviewer': False},
                       {'checks': dict.fromkeys(w.ANIMATIC_CHECKS, 'UNKNOWN')}):
            with self.subTest(update=update):
                result = self.ingest(creative_blueprint=blueprint, blueprint_qa=dict(qa, **update))
                self.assertIsNone(result['blueprint'])
                self.assertTrue(result['blueprint_rejection'])
        result = self.ingest(creative_blueprint=dict(blueprint, status='PROVISIONAL'), blueprint_qa=qa)
        self.assertIsNone(result['blueprint'])
        self.assertEqual(len(lib.search('拉链', self.root)['results']), 1)
        self.assertEqual(list((self.root / 'blueprints').glob('*.json')), [])

    def test_cli_ingest_and_search_run_without_network(self):
        source = Path(self.temp.name) / 'input.json'
        source.write_text(json.dumps({'candidates': [self.candidate]}))
        for args in (['ingest', '--input', str(source), '--topic', '拉链', '--mechanisms', '啮合'],
                     ['search', '--query', 'zipper']):
            output = io.StringIO()
            with patch('sys.argv', ['reference_library', *args, '--root', str(self.root)]), redirect_stdout(output):
                lib.main()
            self.assertFalse(json.loads(output.getvalue())['network_accessed'])


if __name__ == '__main__':
    unittest.main()
