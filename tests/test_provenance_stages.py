"""Cache reuse must not turn a cheap scene audit into final render proof."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from mechanical_video_next import provenance as p


class ProvenanceStagesTests(unittest.TestCase):
    def test_stage_cache_and_dependency_invalidation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            media = root/'test.mp4'
            media.write_bytes(b'unit fixture, never a real render')
            source = root/'source.json'
            source.write_text('{}')
            doc = dict(media=p.binding(media),shots=[dict(model_assets=[p.binding(source)],
                                                        product_references=[p.binding(source)])])
            proof = root/'proof.json'
            proof.write_text(json.dumps(doc))
            with patch.object(p,'ROOT',root), patch.object(p,'filehash', wraps=p.filehash) as sha, \
                 patch.object(p,'blender_version_output',return_value='tool-version'), \
                 patch.object(p.subprocess,'check_output',return_value='tool-version'), \
                 patch.object(p,'_validate',return_value={'status':'scene-only'}) as audit:
                # The audit implementation itself participates in cache identity.
                real_sha = sha._mock_wraps
                sha.side_effect = lambda path: 'implementation' if str(path).endswith('provenance_audit.py') else real_sha(path)
                p.validate(proof,stage='preview')
                self.assertTrue(p.validate(proof,stage='preview')['cache_hit'])
                self.assertEqual(audit.call_count,1)
                p.validate(proof,stage='final')
                self.assertEqual(audit.call_count,2)
                self.assertTrue(audit.call_args.kwargs['replay'])
                source.write_text('{"changed":true}')
                with self.assertRaisesRegex(ValueError,'stale'):
                    p.validate(proof,stage='preview')
                self.assertEqual(audit.call_count,2)

    def test_non_3d_segments_are_rejected_even_with_authorization(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp)/'fixture'
            source.write_bytes(b'fixture')
            ref = p.binding(source)
            for segment in [dict(media_kind='layered'),
                            dict(media_kind='live-action-broll',authorization=ref,source='licensed product clip'),
                            dict(media_kind='live-action-broll',authorization=ref,source='licensed product clip',
                                 mechanical_claim='hidden gear geometry')]:
                build = dict(narration=ref,subtitles=ref,segments=[segment])
                with self.assertRaises(ValueError):
                    p.compose(build,Path(tmp)/'out.mp4')
