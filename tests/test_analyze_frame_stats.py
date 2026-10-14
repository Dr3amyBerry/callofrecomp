"""Offline real-frame-log analyzer never confuses loading with stable gameplay."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools/recomp"))
from analyze_frame_stats import compare, parse_frames, selected_stats


class FrameStatTest(unittest.TestCase):
    def test_parse_and_summary_window_not_individual_frame_percentile(self):
        example = (
            "frame stats: fps=1.0 ms avg=1000.0 min=9.0 max=9999.0 "
            "cpu=984.0 swap=1.0 pace=0.0\n"
            "unrelated output\n"
            + "".join(
                f"frame stats: fps={10+i}.0 ms avg=40.00 min=1.0 max=123.0 "
                f"cpu={30+i}.0 swap=2.0 pace=0.0\r\n" for i in range(10)
            )
        )
        frames = parse_frames(example)
        self.assertEqual(len(frames), 11)
        summary = selected_stats(frames, last=10, skip_first=1)
        self.assertEqual(summary["median_fps"], 14.5)
        self.assertEqual(summary["p10_window_fps"], 10)
        self.assertEqual(summary["median_cpu_ms"], 34.5)
        self.assertEqual(summary["median_swap_ms"], 2)
        self.assertFalse(summary["likely_mixed_loading_or_menu"])
        contaminated = selected_stats(frames, last=11)
        self.assertTrue(contaminated["likely_mixed_loading_or_menu"])

    def test_compare_clearly_describes_uncertainty(self):
        frames = parse_frames("frame stats: fps=20.0 ms avg=50.00 "
                              "min=40 max=80 cpu=47 swap=2.0 pace=0.0\n")
        base = selected_stats(frames, last=1)
        faster = dict(base, median_fps=22.0, median_cpu_ms=45.0)
        result = compare(base, faster)
        self.assertEqual(result["median_fps_delta"], 2)
        self.assertAlmostEqual(result["median_fps_delta_pct"], 10)
        self.assertEqual(result["median_cpu_ms_delta"], -2)
        self.assertIn("NOT per-frame", result["warning"])

    def test_invalid_window_requests_rejected(self):
        frames = parse_frames("frame stats: fps=20 ms avg=50 "
                              "min=40 max=60 cpu=48 swap=1 pace=0\n")
        for last, skip in ((0, 0), (2, 0), (1, -1), (1, 1)):
            with self.subTest(last=last, skip=skip):
                with self.assertRaises(ValueError):
                    selected_stats(frames, last=last, skip_first=skip)
        with self.assertRaises(ValueError):
            compare({"count": 1}, {"count": 2})


if __name__ == "__main__":
    unittest.main()
