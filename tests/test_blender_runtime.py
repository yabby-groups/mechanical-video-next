import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from mechanical_video_next import blender_runtime as runtime


class BlenderRuntimeTests(unittest.TestCase):
    def test_signal_and_graphics_evidence_are_independent(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(runtime, 'ROOT', Path(folder)), \
                patch.object(runtime, '_native_crash_reports', return_value=[]), \
                patch.dict(os.environ, {'BLENDER': sys.executable, 'PYTHONPATH': '/foreign/python',
                                        'DYLD_LIBRARY_PATH': '/foreign/libs', 'MVN_TEST_KEEP': 'yes'}):
            for message, category in (
                ('Could not initialize Metal: no default Metal device available.', 'GRAPHICS_INIT_ERROR'),
                ('Failure with no diagnostic', 'UNKNOWN_CRASH'),
            ):
                code = ('import os, signal, sys; '
                        'assert "PYTHONPATH" not in os.environ and "DYLD_LIBRARY_PATH" not in os.environ; '
                        'assert os.environ["MVN_TEST_KEEP"] == "yes"; '
                        f'print({message!r}, file=sys.stderr, flush=True); os.kill(os.getpid(), signal.SIGABRT)')
                result = runtime.run_blender(['-c', code], directory=Path(folder)/category, allow_failure=True)
                self.assertEqual(result['returncode'], -signal.SIGABRT)
                self.assertTrue(result['process_crash'])
                self.assertTrue(result['process_reaped'])
                self.assertEqual(result['classification'], category)
                self.assertIn(message, Path(result['stderr']).read_text())

    def test_timeout_reaps_a_process_that_ignores_term(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(runtime, 'ROOT', Path(folder)), \
                patch.dict(os.environ, {'BLENDER': sys.executable}):
            code = 'import signal, time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(60)'
            result = runtime.run_blender(['-c', code], directory=Path(folder)/'timeout',
                                         timeout=0.5, allow_failure=True)
            self.assertEqual(result['status'], 'TIMEOUT')
            self.assertEqual(result['classification'], 'RESOURCE_ERROR')
            self.assertEqual(result['returncode'], -signal.SIGKILL)
            self.assertTrue(result['process_reaped'])
            self.assertFalse(result['process_crash'])
            with self.assertRaises(ChildProcessError):
                os.waitpid(result['pid'], os.WNOHANG)

    def test_group_permission_error_still_reaps_blender_pid(self):
        from unittest.mock import Mock

        process = Mock(pid=123)
        process.wait.side_effect = [subprocess.TimeoutExpired('Blender', 2), -signal.SIGKILL]
        with patch.object(os, 'killpg', side_effect=PermissionError('group restricted')):
            errors = runtime.stop_process_group(process)
        self.assertEqual([call.args[0] for call in process.send_signal.call_args_list],
                         [signal.SIGTERM, signal.SIGKILL])
        self.assertEqual(len(errors), 2)
