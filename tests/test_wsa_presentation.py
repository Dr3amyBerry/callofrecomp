"""Presentation percentiles use actual compositor timestamps, never FPS windows."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools/recomp/diagnostics'))
from capture_wsa_presentation import parse_latency, summarize_presentations


class PresentationTests(unittest.TestCase):
    def test_actual_column_sentinels_and_duplicate_buffers(self):
        period, stamps = parse_latency('13333333\r\r\n1 100 2\r\r\n3 200 4\n0 0 0\n5 9223372036854775807 6\n')
        self.assertEqual(period, 13333333)
        self.assertEqual(stamps, [100, 200])
        result = summarize_presentations([100, 200, 200, 300], 13333333)
        self.assertEqual(result['present_intervals'], 2)

    def test_percentiles_are_individual_presentation_intervals(self):
        times = [0]
        for i in range(100):
            times.append(times[-1] + (100_000_000 if i == 99 else 10_000_000))
        s = summarize_presentations(times, 10_000_000)
        self.assertAlmostEqual(s['mean_present_interval_ms'], 10.9)
        self.assertEqual(s['p95_present_interval_ms'], 10)
        self.assertEqual(s['p99_present_interval_ms'], 10)
        self.assertEqual(s['max_present_interval_ms'], 100)
        self.assertEqual(s['intervals_over_50ms'], 1)
        self.assertAlmostEqual(s['presented_rate_hz'], 1000 / 10.9)

    def test_malformed_or_reset_input_rejected(self):
        for text in ('', '0\n1 2 3', '13333333\nbad', '13333333\n1 200 2\n1 100 2'):
            with self.assertRaises(ValueError):
                parse_latency(text)
        for values in ([], [1], [-1, 2]):
            with self.assertRaises(ValueError):
                summarize_presentations(values, 13333333)


if __name__ == '__main__':
    unittest.main()
