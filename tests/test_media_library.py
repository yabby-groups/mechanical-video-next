import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from mechanical_video_next.reference_library import ingest_media, match_media, search_media, prepare_media_clip, record_media_use, media_uses


class MediaLibraryTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.media = self.root / 'original.mp4'
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i',
                        'color=red:s=64x64:r=24:d=4', '-c:v', 'libx264', str(self.media)], check=True)
        self.proof = self.root / 'license.txt'
        self.proof.write_text('permission')
        self.metadata = {'source_type': 'LICENSED_REUSE', 'origin': 'third_party',
                         'tags': ['gear'], 'mechanism_knowledge': ['rotation'],
                         'source_url': 'https://example.com/gear', 'credit': 'Creator', 'content_verified': True,
                         'sources': ['source'], 'used_shots': [],
                         'segment': {'start_sec': 1, 'end_sec': 3},
                         'quality': {'approved': True},
                         'license': {'status': 'VERIFIED', 'name': 'License', 'holder': 'Creator',
                                     'editing_and_distribution': True, 'commercial_use': True,
                                     'proof': {'path': str(self.proof), 'position': 'paragraph 1',
                                               'sha256': hashlib.sha256(b'permission').hexdigest()},
                                     'usage_scopes': ['film']}}
        self.shot = {'tags': ['gear'], 'mechanism_knowledge': ['rotation'], 'usage_scope': 'film',
                     'min_width': 64, 'min_height': 64, 'min_fps': 24}

    def test_dedup_and_independent_rights(self):
        first = ingest_media(self.metadata, self.media, self.root)
        reference = ingest_media({'tags': ['gear']}, self.media, self.root)
        self.assertEqual(first['sha256'], reference['sha256'])
        self.assertNotEqual(first['record'], reference['record'])
        self.assertEqual(len(list((self.root / 'media/blobs').iterdir())), 1)
        result = match_media(self.shot, self.root)
        self.assertEqual(result['decision'], 'REUSE')
        self.assertTrue(any('reference_only' in a['reasons'] for a in result['attempts']))
        self.assertEqual(len(search_media('gear', self.root)), 2)

    def test_current_proof_blob_and_scope_are_required(self):
        item = ingest_media(self.metadata, self.media, self.root)
        self.proof.write_text('changed')
        result = match_media(self.shot, self.root)
        self.assertEqual(result['decision'], 'GENERATE')
        self.assertIn('license_proof_invalid', result['attempts'][0]['reasons'])
        Path(item['blob']).write_bytes(b'tampered')
        result = match_media({**self.shot, 'usage_scope': 'advertising'}, self.root)
        self.assertIn('media_hash_invalid', result['attempts'][0]['reasons'])
        self.assertIn('usage_scope_not_authorized', result['attempts'][0]['reasons'])

    def test_priority_content_quality_and_repeat(self):
        ingest_media(self.metadata, self.media, self.root)
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i',
                        'color=blue:s=64x64:r=24:d=4', '-c:v', 'libx264', str(self.media)], check=True)
        project = ingest_media({**self.metadata, 'source_type':'OWNED', 'origin': 'project', 'project_id': 'p'}, self.media, self.root)
        result = match_media({**self.shot, 'project_id': 'p'}, self.root)
        self.assertEqual(result['selected']['sha256'], project['sha256'])
        result = match_media({**self.shot, 'project_id': 'p', 'used_hashes': [project['sha256']]}, self.root)
        self.assertIn('already_used', result['attempts'][0]['reasons'])
        result = match_media({**self.shot, 'mechanism_knowledge': ['unrelated'], 'min_width': 4000}, self.root)
        self.assertEqual(result['decision'], 'GENERATE')
        self.assertIn('content_mismatch', result['attempts'][0]['reasons'])
        self.assertIn('insufficient_width', result['attempts'][0]['reasons'])

    def test_bad_segments_rejected(self):
        for segment in ({'start_sec': 3, 'end_sec': 2}, {'start_sec': 0, 'end_sec': float('nan')},
                        {'start_sec': 0, 'end_sec': 5}):
            with self.assertRaises(ValueError):
                ingest_media({**self.metadata, 'segment': segment}, self.media, self.root)

    def test_restrictions_and_unverified_content_rejected(self):
        metadata = {**self.metadata, 'content_verified': False,
                    'license': {**self.metadata['license'], 'usage_restrictions': ['NC']}}
        ingest_media(metadata, self.media, self.root)
        result = match_media(self.shot, self.root)
        self.assertEqual(result['reuse_decision'], 'RESEARCH_REQUIRED')
        self.assertFalse(result['generation_required'])
        self.assertIn('license_restriction', result['attempts'][0]['reasons'])
        self.assertIn('content_or_attribution_unverified', result['attempts'][0]['reasons'])
        self.assertTrue(all(x['status'] == 'NOT_SEARCHED' for x in result['external_search_gaps']))

    def test_duration_type_and_license_name(self):
        entry = ingest_media(self.metadata, self.media, self.root)
        chosen = match_media(self.shot, self.root)
        self.assertEqual(chosen['source_time_range'], [1, 3])
        self.assertEqual(chosen['license']['status'], 'VERIFIED')
        self.assertEqual(chosen['attempts'][0]['priority'], 3)
        rejected = match_media({**self.shot, 'duration_sec': 3, 'accepted_types': ['model']}, self.root)
        self.assertEqual(rejected['reuse_decision'], 'RESEARCH_REQUIRED')
        self.assertIn('segment_too_short', rejected['attempts'][0]['reasons'])
        self.assertIn('media_type_mismatch', rejected['attempts'][0]['reasons'])
        self.assertEqual([x['priority'] for x in rejected['external_search_gaps']], [3, 4, 4, 4, 5])
        lic = {**self.metadata['license'], 'name': 'CC-BY-NC4'}
        other = ingest_media({**self.metadata, 'license': lic}, self.media, self.root)
        result = match_media(self.shot, self.root)
        rejected_record = next(a for a in result['attempts'] if a['record'] == other['record'])
        self.assertIn('license_restriction', rejected_record['reasons'])
        with self.assertRaises(ValueError):
            prepare_media_clip(other['record'], self.root)

    def test_real_video_clip_cache_and_tampering(self):
        entry = ingest_media(self.metadata, self.media, self.root)
        result = prepare_media_clip(entry['record'], self.root, 1, 1.2)
        self.assertFalse(result['cache_hit'])
        self.assertTrue(prepare_media_clip(entry['record'], self.root, 1, 1.2)['cache_hit'])
        Path(result['path']).write_bytes(b'corrupt')
        repaired = prepare_media_clip(entry['record'], self.root, 1, 1.2)
        self.assertFalse(repaired['cache_hit'])
        with self.assertRaises(ValueError):
            prepare_media_clip(entry['record'], self.root, 1, 3.1)
        Path(entry['blob']).write_bytes(b'corrupt')
        with self.assertRaises(ValueError):
            prepare_media_clip(entry['record'], self.root, 1, 1.2)

    def test_segment_selection_and_native_graphic_reuse(self):
        ingest_media(self.metadata, self.media, self.root)
        selected = match_media({**self.shot, 'duration_sec':1}, self.root)
        self.assertEqual(selected['source_time_range'], [1,2])
        duplicate = match_media({**self.shot, 'duration_sec':1,
            'used_intervals':[{'sha256':selected['selected_asset']['sha256'], 'time_range':[1,2]}]}, self.root)
        self.assertEqual(duplicate['reuse_decision'],'RESEARCH_REQUIRED')
        diagram = self.root/'diagram.json'
        diagram.write_text(json.dumps({'type':'diagram', 'title':'Evidence-matched flow', 'items':[
            {'label':'Input','detail':'Rotation'}, {'label':'Output','detail':'Movement'}]}))
        native = ingest_media(self.metadata, diagram, self.root)
        result = match_media({**self.shot,'accepted_types':['graphic']}, self.root)
        self.assertEqual(result['selected_asset']['sha256'], native['sha256'])
        self.assertIsNone(result['source_time_range'])

    def test_actual_usage_history_is_idempotent_and_not_acceptance(self):
        entry = ingest_media(self.metadata, self.media, self.root)
        final = {'path':str(self.media),'sha256':entry['sha256']}
        for _ in range(2):
            record_media_use(entry['record'],'demo','rotation',[1,2],final,['rotation'],self.root)
        rows = media_uses(entry['sha256'],self.root)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['shot_id'],'rotation')
        self.assertEqual(search_media('gear',self.root)[0]['uses'],rows)
        self.assertEqual(rows[0]['acceptance'],'NOT_GRANTED_BY_USAGE_RECORD')
        with self.assertRaisesRegex(ValueError,'outside recorded'):
            record_media_use(entry['record'],'demo','rotation',[0,4],final,['rotation'],self.root)

    def test_cached_external_media_never_outranks_owned_local_work(self):
        ingest_media({**self.metadata,'origin':'project','project_id':'p'},self.media,self.root)
        ingest_media({**self.metadata,'source_type':'GENERATED','origin':'local'},self.media,self.root)
        result = match_media({**self.shot,'project_id':'p'},self.root)
        self.assertEqual(result['source_type'],'GENERATED')
        self.assertEqual(result['selected']['priority'],2)
        self.assertTrue(any(a['priority']==3 and a['metadata']['source_type']=='LICENSED_REUSE'
                            for a in result['attempts']))
