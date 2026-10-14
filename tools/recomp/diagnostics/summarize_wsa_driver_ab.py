#!/usr/bin/env python3
"""Validate WSA Camp Toccoa GL4ES(A1)/ANGLE(B)/GL4ES(A2) measurement provenance.

A single B run is exploratory; NEVER label it a TECNO ARM64 FPS improvement.
All raw gameplay logs and screenshots remain in the private ignored .local area.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path


class InvalidTrial(ValueError):
    pass


def validate(run: dict, role: str) -> None:
    if run.get("device") != "127.0.0.1:58526" or run.get("profile") != "Equilibrado":
        raise InvalidTrial(f"{role}: not comparable WSA/profile")
    if run.get("scene") != "Camp Toccoa training, static spawn":
        raise InvalidTrial(f"{role}: not the fixed Camp Toccoa scene")
    if run.get("uncapped_diagnostic") is not False:
        raise InvalidTrial(f"{role}: the host FPS cap differed")
    stats = run.get("stats", {})
    if (stats.get("count", 0) < 20 or
        run.get("analyzed_last_windows") != stats.get("count") or
        run.get("frame_summary_windows", 0) < stats["count"] or
        stats.get("likely_mixed_loading_or_menu") is not False or
        stats.get("median_fps", 0) <= 0 or
        stats.get("median_cpu_ms", 0) < 5):
        raise InvalidTrial(f"{role}: missing or mixed gameplay frame windows")
    if role.startswith("A"):
        if role == "A1" and "backend" not in run:
            # Old capture tool; this path is NOT evidence of ANGLE selection.
            if "GL4ES gameplay baseline" not in run.get("stage", ""):
                raise InvalidTrial("A1: unverifiable legacy GL4ES stage")
        else:
            if run.get("backend") != "gl4es":
                raise InvalidTrial(f"{role}: must use GL4ES")
            if not all(
                run.get(k, {}).get("driver_settings_clear") is True
                for k in ("backend_before", "backend_after")
            ):
                raise InvalidTrial(f"{role}: GL4ES selection not verified")
    elif role == "B":
        if run.get("backend") != "angle":
            raise InvalidTrial("B: not labeled ANGLE")
        for stage in ("backend_before", "backend_after"):
            check = run.get(stage, {})
            evidence = check.get("log_evidence", {})
            if (check.get("backend") != "angle" or
                check.get("vulkan_verified") is not True or
                evidence.get("angle_vulkan_execution_verified") is not True or
                evidence.get("game_pid_checked") != run.get("pid")):
                raise InvalidTrial("B: Vulkan not proven in same game PID before and after")
    else:
        raise InvalidTrial("Unknown role")


def summarize(a1: dict, b: dict, a2: dict) -> dict:
    for role, row in (("A1", a1), ("B", b), ("A2", a2)):
        validate(row, role)
    def m(d, key):
        return round(float(d["stats"][key]), 3)
    a_median_mean = (m(a1,"median_fps") + m(a2,"median_fps")) / 2
    a_cpu_mean = (m(a1,"median_cpu_ms") + m(a2,"median_cpu_ms")) / 2
    b_median = m(b,"median_fps")
    return {
        "experiment": "single exploratory A1 GL4ES / B ANGLE Vulkan / A2 GL4ES",
        "hardware": "WSA Android x86_64 / AMD Radeon; NOT TECNO ARM64",
        "target": "Camp Toccoa training static spawn; Equilibrado; 60-FPS host cap",
        "runs": {role: {"fps_median":m(d,"median_fps"),
                        "fps_p10_one_second_windows":m(d,"p10_window_fps"),
                        "cpu_ms_median":m(d,"median_cpu_ms"),
                        "windows":d["stats"]["count"]}
                 for role, d in (("A1",a1),("B",b),("A2",a2))},
        "comparison": {
            "a_control_fps_median_mean":round(a_median_mean,3),
            "b_vs_mean_a_fps_delta":round(b_median-a_median_mean,3),
            "b_vs_mean_a_fps_percent":round(
                (b_median/a_median_mean-1)*100,3),
            "b_median_between_a_controls":min(
                m(a1,"median_fps"),m(a2,"median_fps")) <= b_median <= max(
                m(a1,"median_fps"),m(a2,"median_fps")),
            "b_p10_lower_than_both_controls":m(b,"p10_window_fps") < min(
                m(a1,"p10_window_fps"),m(a2,"p10_window_fps")),
            "b_vs_mean_a_cpu_ms_delta":round(m(b,"median_cpu_ms")-a_cpu_mean,3)
        },
        "decision": "Do not replace GL4ES. No reproducible FPS improvement demonstrated.",
        "limits": [
            "One ANGLE B capture only: cannot infer statistical significance.",
            "p10 is of ~1-second frame-average windows, not individual frames.",
            "Static scene on WSA AMD, not the TECNO CK6n ARM64 Mali.",
            "Similar screenshots do not prove all shaders/gameplay equivalent.",
            "Valid strategy attempts on the actual TECNO remain 0/5."
        ]
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--a1",type=Path,required=True)
    ap.add_argument("--b",type=Path,required=True)
    ap.add_argument("--a2",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    args=ap.parse_args()
    if args.out.exists():
        ap.error("refusing overwrite")
    try:
        runs = [json.loads(p.read_text("utf-8")) for p in (args.a1,args.b,args.a2)]
        data = summarize(*runs)
    except (OSError,ValueError,KeyError,TypeError) as ex:
        ap.error(str(ex))
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(data,ensure_ascii=True,indent=2))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
