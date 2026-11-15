import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from mechanical_video_next import workflow as w


class HDWorkprintTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'source.json'
        self.config = self.root / 'hd.json'
        self.request = self.root / 'request.json'
        source = {'render': {'width': 1920, 'height': 1080, 'fps': 30,
                             'preview_native': False}, 'shots': {'s': {'angle': 1}}}
        self.source.write_text(json.dumps(source))
        hd = copy.deepcopy(source)
        hd['render']['preview_native'] = True
        self.config.write_text(json.dumps(hd))
        self.authorization = {
            'kind': 'explicit-user-native-hd-candidate', 'user_request': '制作高清版本',
            'formal_acceptance': False, 'config_sha256': w.filehash(self.config),
            'baseline_config': {'path': str(self.source), 'sha256': w.filehash(self.source)},
            'baseline_animatic_qa_sha256': 'qa', 'baseline_media_sha256': 'media'}
        self.data = {'handoffs': {'animatic-qa': {'sha256': 'qa'}}}
        self.qa = {'checks': {'encoding': 'PASS', 'listening': 'UNKNOWN'},
                   'media': [{'path': 'clip', 'sha256': 'media'}], 'issues': []}
        self.asset = {'qualified': True, 'independent_meshes': True, 'missing_required_parts': []}

    def check(self):
        self.request.write_text(json.dumps(self.authorization))
        self.data['hd_workprint_authorization'] = {
            'path': str(self.request), 'sha256': w.filehash(self.request)}
        with patch.object(w, 'load', return_value=self.data), \
                patch.object(w, 'artifact', return_value=self.qa), \
                patch.object(w, 'check_media'), \
                patch.object(w, 'check_asset', return_value=self.asset), \
                patch.object(w, 'event') as event:
            w.require_hd_workprint_request(self.root, self.config)
            return event.call_args.kwargs

    def test_unknown_stays_unaccepted(self):
        self.assertFalse(self.check()['formal_acceptance'])
        self.assertEqual(self.qa['checks']['listening'], 'UNKNOWN')

    def test_fail_not_allowed(self):
        self.qa['checks']['encoding'] = 'FAIL'
        with self.assertRaisesRegex(ValueError, 'failed'):
            self.check()

    def test_changed_motion_even_with_new_authorization_hash_rejected(self):
        hd = json.loads(self.config.read_text())
        hd['shots']['s']['angle'] = 2
        self.config.write_text(json.dumps(hd))
        self.authorization['config_sha256'] = w.filehash(self.config)
        with self.assertRaisesRegex(ValueError, 'only enable native'):
            self.check()

    def test_stale_baseline_qa_rejected(self):
        self.data['handoffs']['animatic-qa']['sha256'] = 'new-qa'
        with self.assertRaisesRegex(ValueError, 'QA changed'):
            self.check()

    def test_other_media_rejected(self):
        self.authorization['baseline_media_sha256'] = 'other'
        with self.assertRaisesRegex(ValueError, 'exact reviewed'):
            self.check()

    def test_major_issue_rejected(self):
        self.qa['issues'] = [{'severity': 'major'}]
        with self.assertRaisesRegex(ValueError, 'major defects'):
            self.check()

    def test_evidenced_floor_only_correction(self):
        source = json.loads(self.source.read_text())
        source['shots']['s']['studio_lighting'] = {'floor_gap': -.0028}
        self.source.write_text(json.dumps(source))
        hd = copy.deepcopy(source)
        hd['render']['preview_native'] = True
        hd['shots']['s']['studio_lighting']['floor_gap'] = -.0032
        self.config.write_text(json.dumps(hd))
        evidence = self.root / 'bounds.json'
        evidence.write_text('{"method":"native evaluated mesh bounds"}')
        self.authorization.update(config_sha256=w.filehash(self.config),
            baseline_config={'path': str(self.source), 'sha256': w.filehash(self.source)},
            derived_floor_corrections=[{'shot_id': 's', 'from': -.0028, 'to': -.0032,
                'evidence': {'path': str(evidence), 'sha256': w.filehash(evidence)}}])
        self.assertFalse(self.check()['formal_acceptance'])
        evidence.write_text('changed')
        with self.assertRaisesRegex(ValueError, 'hashed evidence'):
            self.check()
