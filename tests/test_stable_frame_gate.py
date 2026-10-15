"""Stability-gated A/B/A/B: preserve tiny signals, reject time-varying FPS."""
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import sys
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.recomp.diagnostics.stable_frame_gate import (
    capture_gate, analyze_abab, percent_change,
)


def make_log(*, fps=22.0, cpu=43.6, final_drop=0.0, count=53):
    lines = []
    for i in range(count):
        if i >= count - 40:
            part = (i - (count - 40)) / 39
            f = fps - final_drop * part
        else:
            f = fps
        # Slight deterministic measurement jitter without a long-term slope.
        f += 0.1 if i % 2 == 0 else -0.1
        c = cpu + (fps - f) * 2.1
        lines.append(f"frame stats: fps={f:.3f} ms avg={1000/f:.3f} "
                     f"min=40.0 max=60.0 cpu={c:.3f} swap=2.2 pace=0.0")
    return "\n".join(lines) + "\n"


class StableFrameGateTests(unittest.TestCase):
    def test_stable_run_preserved(self):
        r = capture_gate(make_log())
        self.assertTrue(r["stable"])
        self.assertEqual(r["selected_windows"], 40)
        self.assertEqual(r["warmup_windows"], 13)
        self.assertLess(abs(r["edge_drift_pct"]), 1.0)

    def test_sustained_fps_drop_fails_even_when_no_loading(self):
        r = capture_gate(make_log(final_drop=6.4))
        self.assertFalse(r["stable"])
        self.assertIn("edge_drift", r["reason_codes"])
        self.assertIn("half_drift", r["reason_codes"])
        self.assertNotIn("likely_loading_or_menu", r["reason_codes"])

    def test_insufficient_log_is_not_a_valid_baseline(self):
        r = capture_gate(make_log(count=48))
        self.assertFalse(r["stable"])
        self.assertEqual(r["reason_codes"], ["insufficient_warmup_or_windows"])

    def test_unchanged_baseline_not_rejected(self):
        r = capture_gate(make_log(fps=16.0, cpu=60.0))
        self.assertTrue(r["stable"])  # Low FPS can still be stable; no magic FPS floor.

    def test_negative_or_zero_fps_not_accepted(self):
        log = make_log().replace("fps=22.100", "fps=0.000")
        r = capture_gate(log)
        self.assertFalse(r["stable"])
        self.assertIn("non_positive_fps", r["reason_codes"])

    def test_user_supplied_gate_params_checked(self):
        for opts in ({"last": 1}, {"last": 39}, {"edge": 21},
                     {"max_half_drift_pct": 0}, {"max_p10_gap_pct": 101},
                     {"min_warmup": -1}):
            with self.subTest(opts=opts):
                with self.assertRaises(ValueError):
                    capture_gate(make_log(), **opts)

    def test_abab_rejects_large_baseline_drift_and_fake_13percent(self):
        seq = {
            "A1": make_log(final_drop=6.4),
            "B1": make_log(fps=22.0, cpu=43.67),
            "A2": make_log(fps=21.75, cpu=44.11),
            "B2": make_log(fps=22.25, cpu=43.16),
        }
        r = analyze_abab(seq)
        self.assertEqual(r["status"], "inconclusive_unstable_measurement")
        self.assertEqual(r["invalid_stages"], ["A1"])
        self.assertNotIn("comparisons", r)

    def test_abab_slight_consistent_gain_is_preserved(self):
        # Two very small but consistent pairwise FPS/CPU advantages.
        logs = {
            "A1": make_log(fps=22.05, cpu=43.60),
            "B1": make_log(fps=22.10, cpu=43.41),
            "A2": make_log(fps=21.85, cpu=43.95),
            "B2": make_log(fps=22.05, cpu=43.56),
        }
        r = analyze_abab(logs)
        self.assertEqual(r["status"], "consistent_positive_signal_unconfirmed")
        self.assertTrue(all(v > 0 for v in r["comparisons"]["fps_delta_pair_pct"]))
        self.assertTrue(all(v < 0 for v in r["comparisons"]["cpu_delta_pair_pct"]))
        self.assertIn("never claim statistical proof", r["reason"])

    def test_abab_rejects_directionally_mixed_gain(self):
        logs = {"A1": make_log(fps=22.0, cpu=43.6),
                "B1": make_log(fps=22.2, cpu=43.5),
                "A2": make_log(fps=22.0, cpu=43.6),
                "B2": make_log(fps=21.8, cpu=43.8)}
        r = analyze_abab(logs)
        self.assertEqual(r["status"], "no_consistent_positive_signal")

    def test_abab_rejects_large_between_session_drift(self):
        logs = {"A1": make_log(fps=22.0), "B1": make_log(fps=22.2),
                "A2": make_log(fps=18.0), "B2": make_log(fps=18.2)}
        r = analyze_abab(logs)
        self.assertEqual(r["status"], "inconclusive_repeated_baseline_mismatch")

    def test_invalid_labels_rejected(self):
        with self.assertRaisesRegex(ValueError, "exactly A1"):
            analyze_abab({"A1": make_log()})

    def test_cli_creates_new_report_and_wont_overwrite(self):
        with TemporaryDirectory() as temp:
            path = Path(temp)
            args = []
            for stage in ("a1", "b1", "a2", "b2"):
                f = path / (stage + ".log")
                f.write_text(make_log(), encoding="utf-8")
                args.extend(["--" + stage, str(f)])
            args.extend(["--out", str(path / "report.json")])
            tool = ROOT / "tools/recomp/diagnostics/stable_frame_gate.py"
            result = subprocess.run([sys.executable, str(tool), *args],
                                    capture_output=True, text=True, timeout=18)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads((path / "report.json").read_text())["status"],
                             "no_consistent_positive_signal")
            second = subprocess.run([sys.executable, str(tool), *args],
                                    capture_output=True, text=True, timeout=18)
            self.assertEqual(second.returncode, 2)
            self.assertIn("File exists", second.stderr)


    def test_stable_but_wrong_scene_baseline_is_rejected(self):
        r = capture_gate(make_log(fps=16.85, cpu=56.0),
                         reference_fps=21.675,
                         max_reference_deviation_pct=7.0)
        self.assertFalse(r["stable"])
        self.assertEqual(r["reason_codes"], ["reference_mismatch"])
        self.assertLess(r["reference_delta_pct"], -20)

    def test_matching_external_reference_is_accepted(self):
        r = capture_gate(make_log(fps=21.70, cpu=44.25),
                         reference_fps=21.675,
                         max_reference_deviation_pct=7.0)
        self.assertTrue(r["stable"])
        self.assertAlmostEqual(r["reference_delta_pct"], 0.1153, places=3)

    def test_reference_guard_only_applies_to_a_not_b(self):
        logs = {
            "A1": make_log(fps=16.85, cpu=55.0),
            "B1": make_log(fps=26.0, cpu=36.0),
            "A2": make_log(fps=21.70, cpu=44.25),
            "B2": make_log(fps=26.3, cpu=35.5),
        }
        r = analyze_abab(logs, expected_baseline_fps=21.675,
                         max_baseline_deviation_pct=7.0)
        self.assertEqual(r["status"], "inconclusive_unstable_measurement")
        self.assertEqual(r["invalid_stages"], ["A1"])
        self.assertNotIn("reference_mismatch", r["stage_stability"]["B1"]["reason_codes"])
        self.assertTrue(r["stage_stability"]["B1"]["stable"])

    def test_external_reference_parameters_are_validated(self):
        with self.assertRaises(ValueError):
            capture_gate(make_log(),reference_fps=0)
        with self.assertRaises(ValueError):
            capture_gate(make_log(),reference_fps=22,max_reference_deviation_pct=0)


if __name__ == "__main__":
    unittest.main()
