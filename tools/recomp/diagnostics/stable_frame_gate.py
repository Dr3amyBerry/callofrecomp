#!/usr/bin/env python3
"""Fail-closed, read-only stability gate for physical TECNO/WSA FPS experiments.

Unlike simple median comparisons, rejects sustained within-run slowdowns and
unrepeatable A/B baselines. Preserve even tiny directional gains as *signals*;
never relabel a small A/B/A/B sample as statistically proven or production-safe.
Inputs are frame stats logs from one scene, verified outside this tool.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from statistics import median

REPO = Path(__file__).resolve().parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from tools.recomp.analyze_frame_stats import parse_frames, selected_stats  # noqa: E402

LABELS = ("A1", "B1", "A2", "B2")


class UnstableCaptureError(ValueError):
    pass


def percent_change(new: float, old: float) -> float:
    if old <= 0:
        raise UnstableCaptureError("FPS baseline must be positive")
    return 100.0 * (new / old - 1.0)


def capture_gate(text: str, *, last: int = 40, edge: int = 8,
                 max_edge_drift_pct: float = 5.0,
                 max_half_drift_pct: float = 5.0,
                 max_p10_gap_pct: float = 12.0,
                 min_warmup: int = 10) -> dict:
    if last < 16 or last % 2 or edge < 3 or edge * 2 > last or min_warmup < 0:
        raise ValueError("Invalid stability window or warmup lengths")
    for x in (max_edge_drift_pct, max_half_drift_pct, max_p10_gap_pct):
        if not 0 < x <= 100:
            raise ValueError("Invalid percentage gate")
    all_frames = parse_frames(text)
    if len(all_frames) < last + min_warmup:
        return {"stable": False, "reason_codes": ["insufficient_warmup_or_windows"],
                "available_windows": len(all_frames), "required_windows": last + min_warmup}
    series = all_frames[-last:]
    # Keep ordering: selected_stats sorts FPS and loses temporal information.
    fps = [f["fps"] for f in series]
    if any(f <= 0 for f in fps):
        return {"stable": False, "reason_codes": ["non_positive_fps"],
                "available_windows": len(all_frames)}
    first_edge = median(fps[:edge])
    last_edge = median(fps[-edge:])
    early_half = median(fps[:last // 2])
    late_half = median(fps[last // 2:])
    summary = selected_stats(all_frames, last=last)
    edge_drift = percent_change(last_edge, first_edge)
    half_drift = percent_change(late_half, early_half)
    p10_gap = 100.0 * (1.0 - summary["p10_window_fps"] / summary["median_fps"])
    fails = []
    if abs(edge_drift) > max_edge_drift_pct:
        fails.append("edge_drift")
    if abs(half_drift) > max_half_drift_pct:
        fails.append("half_drift")
    if p10_gap > max_p10_gap_pct:
        fails.append("p10_gap")
    if summary["likely_mixed_loading_or_menu"]:
        fails.append("likely_loading_or_menu")
    return {
        "stable": not fails,
        "reason_codes": fails,
        "available_windows": len(all_frames),
        "selected_windows": last,
        "warmup_windows": len(all_frames) - last,
        "median_fps": summary["median_fps"],
        "median_cpu_ms": summary["median_cpu_ms"],
        "p10_window_fps": summary["p10_window_fps"],
        "edge_first_fps": first_edge,
        "edge_last_fps": last_edge,
        "edge_drift_pct": round(edge_drift, 4),
        "half_early_fps": early_half,
        "half_late_fps": late_half,
        "half_drift_pct": round(half_drift, 4),
        "p10_gap_pct": round(p10_gap, 4),
    }


def analyze_abab(captures: dict[str, str], *, last: int = 40,
                 max_repeat_drift_pct: float = 5.0,
                 **gate_options) -> dict:
    if set(captures) != set(LABELS):
        raise ValueError("Expected exactly A1, B1, A2, B2 log texts")
    if not 0 < max_repeat_drift_pct <= 100:
        raise ValueError("Invalid repeat tolerance")
    stages = {label: capture_gate(captures[label], last=last, **gate_options)
              for label in LABELS}
    result = {
        "status": "inconclusive_unstable_measurement",
        "stage_stability": stages,
        "selected_windows": last,
        "reason": "A/B/A/B medians alone cannot establish causality or significance",
        "caution": "One-second window summaries are not per-frame p10/p99. "
                   "The caller must independently verify APK hashes, equal "
                   "scene/camera/graphics, saves, power, temperature, and CPU/GPU frequency.",
    }
    if not all(row["stable"] for row in stages.values()):
        result["invalid_stages"] = [k for k in LABELS if not stages[k]["stable"]]
        return result

    a1, b1, a2, b2 = (stages[x] for x in LABELS)
    baseline_repeat = percent_change(a2["median_fps"], a1["median_fps"])
    candidate_repeat = percent_change(b2["median_fps"], b1["median_fps"])
    fps_pairs = [percent_change(b["median_fps"], a["median_fps"])
                 for a, b in ((a1, b1), (a2, b2))]
    cpu_pairs = [percent_change(b["median_cpu_ms"], a["median_cpu_ms"])
                 for a, b in ((a1, b1), (a2, b2))]
    stats = {
        "a_mean_of_medians_fps": (a1["median_fps"] + a2["median_fps"]) / 2,
        "b_mean_of_medians_fps": (b1["median_fps"] + b2["median_fps"]) / 2,
        "fps_delta_pair_pct": [round(x, 4) for x in fps_pairs],
        "cpu_delta_pair_pct": [round(x, 4) for x in cpu_pairs],
        "a_repeat_delta_pct": round(baseline_repeat, 4),
        "b_repeat_delta_pct": round(candidate_repeat, 4),
    }
    result["comparisons"] = stats
    if max(abs(baseline_repeat), abs(candidate_repeat)) > max_repeat_drift_pct:
        result["status"] = "inconclusive_repeated_baseline_mismatch"
    elif all(x > 0 for x in fps_pairs) and all(x < 0 for x in cpu_pairs):
        result["status"] = "consistent_positive_signal_unconfirmed"
        result["reason"] = ("Both chronological A/B pairs trend faster in FPS and "
                            "lower in CPU ms; retain opt-in for further independent "
                            "replication, never claim statistical proof from two pairs")
    else:
        result["status"] = "no_consistent_positive_signal"
        result["reason"] = "At least one pair does not show lower CPU and higher FPS"
    return result


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--a1", required=True, type=Path)
    ap.add_argument("--b1", required=True, type=Path)
    ap.add_argument("--a2", required=True, type=Path)
    ap.add_argument("--b2", required=True, type=Path)
    ap.add_argument("--last", type=int, default=40)
    ap.add_argument("--max-edge-drift-pct", type=float, default=5.0)
    ap.add_argument("--max-half-drift-pct", type=float, default=5.0)
    ap.add_argument("--max-p10-gap-pct", type=float, default=12.0)
    ap.add_argument("--max-repeat-drift-pct", type=float, default=5.0)
    ap.add_argument("--out", type=Path, help="optional NEW report JSON; never overwrite")
    args = ap.parse_args(argv)
    try:
        logs = {key: Path(getattr(args, key.lower())).read_text(encoding="utf-8",
                    errors="replace") for key in LABELS}
        report = analyze_abab(logs, last=args.last,
                              max_edge_drift_pct=args.max_edge_drift_pct,
                              max_half_drift_pct=args.max_half_drift_pct,
                              max_p10_gap_pct=args.max_p10_gap_pct,
                              max_repeat_drift_pct=args.max_repeat_drift_pct)
        encoded = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
        if args.out is not None:
            if args.out.suffix.lower() != ".json":
                raise ValueError("--out must have a .json suffix")
            with args.out.open("x", encoding="utf-8") as file:
                file.write(encoded)
        print(encoded, end="")
        return 0
    except (ValueError, OSError) as error:
        ap.exit(2, "STABILITY_GATE_ERROR: " + str(error) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
