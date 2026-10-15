#!/usr/bin/env python3
"""Read-only ADB battery/thermal/CPU-clock telemetry for reproducible FPS tests.

Never sets CPU governors or power settings. Polls bounded duration and writes
a new per-run JSON, never overwriting. CPU clocks and HAL temperatures may be
unavailable on some devices; missing fields stay null rather than invented.
One sample records the local UTC timestamp, not perfect alignment with FPS logs.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

SERIAL = re.compile(r"^[A-Za-z0-9._:-]{3,120}$")
CPU_IDS = (0, 4, 6, 7)


def adb_read(serial: str, *args: str, timeout: int = 12) -> str | None:
    if not SERIAL.fullmatch(serial):
        raise ValueError("Provide exact authorized ADB serial")
    try:
        r = subprocess.run(["adb", "-s", serial, "shell", *args],
                           capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def parse_battery(text: str | None) -> dict:
    result = {"battery_temperature_c": None, "battery_level_pct": None,
              "usb_powered": None}
    if not text:
        return result
    m = re.search(r"(?m)^\s*temperature:\s*(\d+)\s*$", text)
    if m:
        result["battery_temperature_c"] = int(m.group(1)) / 10.0
    m = re.search(r"(?m)^\s*level:\s*(\d+)\s*$", text)
    if m:
        result["battery_level_pct"] = int(m.group(1))
    m = re.search(r"(?m)^\s*USB powered:\s*(true|false)\s*$", text)
    if m:
        result["usb_powered"] = m.group(1) == "true"
    return result


def parse_thermal(text: str | None) -> dict:
    result = {"thermal_status": None, "hal_cpu_temp_c": None,
              "hal_gpu_temp_c": None, "hal_skin_temp_c": None}
    if not text:
        return result
    match = re.search(r"Thermal Status:\s*(\d+)", text)
    if match:
        result["thermal_status"] = int(match.group(1))
    # Use CURRENT HAL values (not stale cached values) when available.
    current = text.split("Current temperatures from HAL:", 1)
    if len(current) < 2:
        return result
    current = current[1].split("Current cooling devices from HAL:", 1)[0]
    for kind, key in ((0, "hal_cpu_temp_c"), (1, "hal_gpu_temp_c"),
                      (3, "hal_skin_temp_c")):
        for line in current.splitlines():
            match = re.search(
                r"Temperature\{mValue=(-?\d+(?:\.\d+)?),\s*mType="+str(kind)+r",", line)
            if match:
                result[key] = float(match.group(1))
                break
    return result


def snapshot(serial: str, cpu_ids: tuple[int, ...] = CPU_IDS) -> dict:
    if not cpu_ids or len(cpu_ids) > 16 or any(n < 0 or n > 63 for n in cpu_ids):
        raise ValueError("Invalid CPU core selection")
    row = {
        "utc": datetime.now(timezone.utc).isoformat(),
        "cpu_freq_khz": {},
        "freq_readable_cores": 0,
    }
    row.update(parse_battery(adb_read(serial, "dumpsys", "battery")))
    row.update(parse_thermal(adb_read(serial, "dumpsys", "thermalservice")))
    for cpu in cpu_ids:
        value = adb_read(serial, "cat",
                         f"/sys/devices/system/cpu/cpu{cpu}/cpufreq/scaling_cur_freq")
        khz = int(value) if value and value.isdecimal() else None
        row["cpu_freq_khz"][str(cpu)] = khz
        if khz is not None:
            row["freq_readable_cores"] += 1
    return row


def collect(serial: str, *, duration_sec: float = 90.0,
            interval_sec: float = 5.0,
            stop: threading.Event | None = None) -> dict:
    if not (2 <= duration_sec <= 1800 and 1 <= interval_sec <= 60):
        raise ValueError("Duration must be 2..1800sec; interval 1..60sec")
    records = []
    start = time.monotonic()
    while time.monotonic() - start < duration_sec:
        if stop is not None and stop.is_set():
            break
        row = snapshot(serial)
        row["elapsed_sec"] = round(time.monotonic() - start, 3)
        records.append(row)
        remaining = duration_sec - (time.monotonic() - start)
        if remaining <= 0:
            break
        wait = min(interval_sec, remaining)
        if stop is not None:
            if stop.wait(wait):
                break
        else:
            time.sleep(wait)
    return {
        "schema": 1, "serial": serial,
        "duration_elapsed_sec": round(time.monotonic() - start, 3),
        "requested_interval_sec": interval_sec,
        "samples": records,
        "read_only": True,
        "warning": "ADB polling has overhead; frequency samples are instantaneous, "
                   "not per-frame clock traces and not evidence of GPU time.",
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--serial", required=True)
    p.add_argument("--seconds", type=float, default=75.0)
    p.add_argument("--interval", type=float, default=5.0)
    p.add_argument("--out", required=True, type=Path)
    args = p.parse_args(argv)
    if not SERIAL.fullmatch(args.serial):
        p.error("Invalid ADB serial")
    if args.out.suffix.lower() != ".json":
        p.error("--out must be a .json file")
    try:
        result = collect(args.serial, duration_sec=args.seconds,
                         interval_sec=args.interval)
        with args.out.open("x", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
            f.write("\n")
        print(json.dumps({"samples": len(result["samples"]),
                          "elapsed": result["duration_elapsed_sec"],
                          "output": str(args.out)}))
        return 0
    except (ValueError, OSError) as ex:
        p.exit(2, "ADB_PERF_ENV_ERROR: " + str(ex) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
