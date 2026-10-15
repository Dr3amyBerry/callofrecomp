#!/usr/bin/env python3
"""Capture unique WSA SurfaceFlinger presentations; not GPU or simulation time."""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import shlex
import statistics
import subprocess
import time

PACKAGE = 'org.callofrecomp'


def parse_latency(text: str) -> tuple[int, list[int]]:
    # Windows adb shell can emit CRCRLF; ignore transport-only blank lines.
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines or not lines[0].isdigit() or int(lines[0]) <= 0:
        raise ValueError('Missing positive compositor refresh period')
    values = []
    for line in lines[1:]:
        fields = line.split()
        if len(fields) != 3 or any(not f.isdigit() for f in fields):
            raise ValueError('Malformed SurfaceFlinger timestamp row')
        actual = int(fields[1])
        if actual in (0, 2**63 - 1):
            continue
        if values and actual < values[-1]:
            raise ValueError('Presentation timestamps reset or moved backwards')
        values.append(actual)
    return int(lines[0]), values


def summarize_presentations(timestamps: list[int], period_ns: int) -> dict:
    if period_ns <= 0 or any(type(x) is not int or x < 0 for x in timestamps):
        raise ValueError('Invalid presentation timestamp or period')
    values = sorted(set(timestamps))
    if len(values) < 2:
        raise ValueError('At least two distinct presentations required')
    intervals = [(b - a) / 1e6 for a, b in zip(values, values[1:])]
    ordered = sorted(intervals)
    def percentile(p):
        return ordered[max(0, math.ceil(p * len(ordered)) - 1)]
    return {
        'present_intervals': len(intervals),
        'display_refresh_hz': 1e9 / period_ns,
        'observed_duration_s': (values[-1] - values[0]) / 1e9,
        'presented_rate_hz': 1e9 * len(intervals) / (values[-1] - values[0]),
        'mean_present_interval_ms': statistics.mean(intervals),
        'median_present_interval_ms': statistics.median(intervals),
        'p95_present_interval_ms': percentile(.95),
        'p99_present_interval_ms': percentile(.99),
        'max_present_interval_ms': max(intervals),
        'intervals_over_50ms': sum(x > 50 for x in intervals),
        'intervals_over_100ms': sum(x > 100 for x in intervals),
    }


def capture(serial: str, seconds: int, out: Path) -> dict:
    allowed = (Path.cwd() / '.local/profiles').resolve()
    if out.resolve() == allowed or not out.resolve().is_relative_to(allowed):
        raise ValueError('Raw profiling output must remain under ignored .local/profiles')
    destinations = [out.with_suffix(x) for x in ('.json', '.timestamps.json', '.log')]
    if any(x.exists() for x in destinations):
        raise ValueError('Refusing to overwrite a capture')
    def adb(*args):
        return subprocess.run(['adb', '-s', serial, *args], capture_output=True,
                              check=True, timeout=15).stdout.decode('utf-8', 'replace')
    if adb('shell', 'getprop ro.product.device').strip() != 'windows_x86_64':
        raise ValueError('Select the actual WSA x86_64 device explicitly')
    pid = adb('shell', 'pidof ' + PACKAGE).strip()
    if not pid:
        raise ValueError('Game is not running')
    layers = [x for x in adb('shell', 'dumpsys SurfaceFlinger --list').splitlines()
              if 'SurfaceView[' + PACKAGE + '/' in x and '(BLAST)' in x]
    if len(layers) != 1:
        raise ValueError('Expected exactly one actual game BLAST SurfaceView')
    layer = layers[0]
    def latency():
        return parse_latency(adb('shell', 'dumpsys SurfaceFlinger --latency ' + shlex.quote(layer)))
    def game_log():
        return adb('exec-out', 'run-as', PACKAGE, 'cat', 'files/profile/codrecomp.log')
    before = game_log()
    period, initial = latency()
    if not initial:
        raise ValueError('No presentations yet; load gameplay before capture')
    anchor = initial[-1]
    observed = {anchor}
    last_seen = anchor
    gaps = 0
    started = time.monotonic()
    while time.monotonic() - started < seconds:
        time.sleep(.5)
        current_period, stamps = latency()
        if current_period != period:
            raise ValueError('Display refresh changed during capture')
        if stamps:
            if stamps[-1] < last_seen:
                raise ValueError('Compositor timestamp buffer reset')
            if stamps[0] > last_seen:
                gaps += 1
            observed.update(x for x in stamps if x > anchor)
            last_seen = stamps[-1]
    if adb('shell', 'pidof ' + PACKAGE).strip() != pid:
        raise ValueError('Game process changed')
    after = game_log()
    if not after.startswith(before):
        raise ValueError('Game log rotated during capture')
    # The frame summaries are collected concurrently; do not invent per-frame CPU.
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from analyze_frame_stats import parse_frames, selected_stats
    fresh = after[len(before):]
    windows = parse_frames(fresh)
    if len(windows) < 10:
        raise ValueError('Insufficient fresh engine summaries; enable frame_stats')
    stats = selected_stats(windows, last=len(windows))
    if stats['likely_mixed_loading_or_menu'] or stats['median_cpu_ms'] < 5:
        raise ValueError('Likely loading/menu instead of stable gameplay')
    result = {
        'kind': 'actual compositor presentation intervals and simultaneous engine windows',
        'device': serial, 'pid': pid, 'layer': layer,
        'host_capture_seconds': time.monotonic() - started,
        'presentation': summarize_presentations(list(observed), period),
        'engine_window_stats': stats, 'buffer_gaps': gaps,
        'complete_timestamp_coverage': gaps == 0,
        'log_sha256': hashlib.sha256(fresh.encode()).hexdigest(),
        'limitations': ['presentation is not GPU execution or simulation rate',
                       'unique presentation timestamps do not prove unique image content',
                       'CPU and engine FPS percentiles remain per-window statistics',
                       'scene and quality must be fixed externally for A/B'],
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    destinations[0].write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    destinations[1].write_text(json.dumps(sorted(observed)), encoding='utf-8')
    destinations[2].write_text(fresh, encoding='utf-8')
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--serial', required=True)
    ap.add_argument('--seconds', type=int, default=45)
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    if not 15 <= args.seconds <= 3600:
        ap.error('--seconds must be 15..3600')
    result = capture(args.serial, args.seconds, args.out)
    print(json.dumps({k: result[k] for k in ('presentation', 'engine_window_stats',
                                          'complete_timestamp_coverage')}, indent=2))


if __name__ == '__main__':
    main()
