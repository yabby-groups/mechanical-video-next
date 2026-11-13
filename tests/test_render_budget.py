"""Resource regressions: retained media must not force a larger work limit."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from produce import bounded_chunk_frames


class RenderBudgetTests(unittest.TestCase):
    def test_nearly_full_work_uses_smaller_batch_at_same_resolution(self):
        used = 2 * 1024**3 - 25 * 1024**2
        frames = bounded_chunk_frames(16, 215, 960, 540, used)
        self.assertGreaterEqual(frames, 1)
        self.assertLess(frames, 16)
        self.assertLessEqual(used + frames * 960 * 540 * 3 * 1.12 + 8 * 1024**2,
                             2 * 1024**3)

    def test_spare_space_preserves_requested_batch_and_short_last_shot(self):
        self.assertEqual(bounded_chunk_frames(16, 215, 960, 540, 0), 16)
        self.assertEqual(bounded_chunk_frames(16, 5, 960, 540, 0), 5)

    def test_no_single_frame_capacity_fails_closed(self):
        with self.assertRaises(RuntimeError):
            bounded_chunk_frames(16, 215, 960, 540, 2 * 1024**3 - 9 * 1024**2)
