import copy
from contextlib import nullcontext
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('acceptance', ROOT / 'scripts/acceptance.py')
a = importlib.util.module_from_spec(spec)
spec.loader.exec_module(a)


class AcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.first = json.loads((ROOT / 'config/planetary-01.json').read_text())
        self.second = json.loads((ROOT / 'config/planetary-02.json').read_text())

    def test_mutation_boundaries(self):
        for number in (3, 4, 5):
            cfg = a.configuration(number, self.first, self.second)
            original = copy.deepcopy(self.first)
            cfg.pop('id'); original.pop('id')
            if number == 3:
                self.assertEqual(cfg['storyboard'][0]['subtitles'], original['storyboard'][0]['subtitles'])
                original['storyboard'][0]['narration'] = cfg['storyboard'][0]['narration']
            elif number == 4:
                original['storyboard'][0]['subtitles'] = cfg['storyboard'][0]['subtitles']
            else:
                original['shots']['explode']['distance'] = 1.9
            self.assertEqual(cfg, original)

    def test_failed_command_stops_following_scenarios(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(a, 'budget'), \
                patch.object(a.w, 'lock', return_value=nullcontext()), \
                patch.object(a, 'invoke', return_value={'returncode': 1}) as invoke:
            report = a.run_scenarios([1, 2], True, Path(tmp))
            self.assertEqual(report['stopped_on_failure'], 1)
            self.assertEqual(len(report['scenarios']), 1)
            invoke.assert_called_once()

    def test_rejection_is_real_gate_and_does_not_render(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(a.subprocess, 'run') as process:
            result = a.reject_unqualified(Path(tmp))
            self.assertEqual(result['status'], 'SAFE_REJECTION_VERIFIED')
            self.assertFalse(result['media_generated'])
            process.assert_not_called()

    def test_dry_run_does_not_claim_quality_or_metrics(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(a, 'invoke') as invoke:
            report = a.run_scenarios(list(range(1, 8)), False, Path(tmp))
            self.assertEqual(len(report['scenarios']), 7)
            self.assertTrue(all(r['status'] == 'PENDING' for r in report['scenarios']))
            self.assertIsNone(report['tokens'])
            invoke.assert_not_called()


if __name__ == '__main__':
    unittest.main()
