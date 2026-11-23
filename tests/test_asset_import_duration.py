"""Asset import must accept a short diagnostic without authorizing its video."""
import json
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import produce


class AssetImportDurationTests(unittest.TestCase):
    def test_direct_script_import_can_prepare_diagnostic_evidence(self):
        code = (
            "import sys; from pathlib import Path; "
            "sys.path.insert(0, sys.argv[1]); import produce; "
            "produce.prepare_shot_evidence(Path(sys.argv[2]))"
        )
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(
                ['uv', 'run', '--project', str(ROOT), 'python', '-I', '-c', code,
                 str(ROOT / 'scripts'), directory],
                cwd=directory, capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_short_storyboard_imports_asset_but_cannot_render_normal_local_video(self):
        cfg = json.loads((ROOT / 'tests/fixtures/production/planetary-01.json').read_text())
        cfg['id'] = 'short-asset-regression'
        cfg['assembly_config'] = 'tests/fixtures/production/assembly.json'
        cfg['storyboard'] = [cfg['storyboard'][0]]
        cfg['storyboard'][0]['seconds'] = 4
        cfg['shots'][cfg['storyboard'][0]['shot']]['seconds'] = 4
        cfg['content_policy_version'] = 1
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / 'config.json'
            config.write_text(json.dumps(cfg))
            with patch.object(sys, 'argv', ['produce', str(config), '--phase', 'asset']), \
                 patch.object(produce, 'asset') as asset, \
                 patch.object(produce, 'Metrics') as metrics, \
                 patch('scripts.common.sample_budget', return_value=0), \
                 patch.object(produce, 'writejson'):
                metrics.return_value.start = 0
                metrics.return_value.peak = 0
                produce.main()
                asset.assert_called_once()
            with patch.object(sys, 'argv', ['produce', str(config), '--phase', 'local']), \
                 patch.object(produce, 'asset') as asset:
                with self.assertRaisesRegex(AssertionError, 'Storyboard duration outside'):
                    produce.main()
                asset.assert_not_called()
