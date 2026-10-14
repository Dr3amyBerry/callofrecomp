#!/usr/bin/env python3
"""Offline comparison of CallofRecomp's opt-in Android frame stats logs.

Only compare the same game scene, graphics profile, device, APK build,
thermal state, and similarly warmed windows. This tool cannot validate
those conditions and does not measure individual-frame percentiles.
No device access, game assets, network calls or runtime changes.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
from statistics import median

FRAME_STATS = re.compile(
    r"\bframe stats: fps=(\d+(?:\.\d+)?) ms avg=(\d+(?:\.\d+)?)"
    r" min=(\d+(?:\.\d+)?) max=(\d+(?:\.\d+)?)"
    r" cpu=(\d+(?:\.\d+)?) swap=(\d+(?:\.\d+)?) pace=(\d+(?:\.\d+)?)"
)
FIELDS = ("fps", "avg_ms", "window_min_ms", "window_max_ms",
          "cpu_ms", "swap_ms", "pace_ms")


def parse_frames(text: str) -> list[dict[str, float]]:
    return [dict(zip(FIELDS, map(float, match.groups())))
            for match in FRAME_STATS.finditer(text)]


def selected_stats(frames: list[dict[str, float]], *, last: int = 40,
                   skip_first: int = 0) -> dict:
    if last < 1 or skip_first < 0:
        raise ValueError("last must be positive and skip_first nonnegative")
    clean = frames[skip_first:]
    if len(clean) < last:
        raise ValueError(f"requested {last} windows after skipping {skip_first}; "
                         f"only {len(clean)} available")
    rows = clean[-last:]
    fps = sorted(row["fps"] for row in rows)
    # Lower-bound nearest-rank percentile of one-second FPS summaries.
    p10 = fps[max(0, (last + 9) // 10 - 1)]
    report = {
        "count": last,
        "median_fps": median(fps),
        "p10_window_fps": p10,
        "min_window_fps": fps[0],
        "max_window_fps": fps[-1],
        "median_cpu_ms": median(row["cpu_ms"] for row in rows),
        "median_swap_ms": median(row["swap_ms"] for row in rows),
        "median_pace_ms": median(row["pace_ms"] for row in rows),
    }
    report["likely_mixed_loading_or_menu"] = (
        fps[0] < 10 or (fps[-1] >= 40 and fps[0] < 30))
    return report


def compare(base: dict, candidate: dict) -> dict:
    if base["count"] != candidate["count"]:
        raise ValueError("different number of summary windows")
    base_fps = base["median_fps"]
    delta = (candidate["median_fps"] - base_fps)
    return {
        "median_fps_delta": delta,
        "median_fps_delta_pct": (100 * delta / base_fps) if base_fps else None,
        "median_cpu_ms_delta": (candidate["median_cpu_ms"] - base["median_cpu_ms"]),
        "warning": (
            "These are one-second summary-window medians, NOT per-frame "
            "percentiles or proof of a speedup. Compare matching scene/view, "
            "build, device, power/thermal, and warmup. Profiling changes "
            "overhead; repeat A/B/A if delta is small."),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--baseline", required=True, type=Path)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--last", type=int, default=40)
    parser.add_argument("--skip-first", type=int, default=0)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    summary = {
        "baseline": selected_stats(
            parse_frames(args.baseline.read_text(encoding="utf-8", errors="replace")),
            last=args.last, skip_first=args.skip_first),
        "candidate": selected_stats(
            parse_frames(args.candidate.read_text(encoding="utf-8", errors="replace")),
            last=args.last, skip_first=args.skip_first),
    }
    summary["comparison"] = compare(summary["baseline"], summary["candidate"])
    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        for key in ("baseline", "candidate"):
            stats = summary[key]
            print(f"{key}: {stats['count']} summary windows, "
                  f"FPS median={stats['median_fps']:.2f} "
                  f"p10_window={stats['p10_window_fps']:.2f}, "
                  f"CPU median={stats['median_cpu_ms']:.2f}ms, "
                  f"swap median={stats['median_swap_ms']:.2f}ms, "
                  f"mixed_loading_or_menu={stats['likely_mixed_loading_or_menu']}")
        delta = summary["comparison"]
        print(f"delta: {delta['median_fps_delta']:+.2f} FPS "
              f"({delta['median_fps_delta_pct']:+.2f}%)" if
              delta["median_fps_delta_pct"] is not None else
              f"delta: {delta['median_fps_delta']:+.2f} FPS (baseline FPS is zero)")
        print(delta["warning"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
