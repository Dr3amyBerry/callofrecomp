#!/usr/bin/env python3
"""Explicit, temporary ANGLE-for-one-app WSA experiment with best-effort rollback.

DEFAULT IS READ-ONLY. Requires --execute, a signed APK verified by Android
Build Tools, and an independently supplied SHA-256 to make any changes.
This is an EGL-driver identity smoke test, not a gameplay FPS benchmark.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

from verify_angle_apk import inspect

GAME = "org.callofrecomp"
ANGLE = "org.chromium.angle"
SERIAL = "127.0.0.1:58526"
SETTINGS = (
    "angle_debug_package",
    "angle_gl_driver_selection_pkgs",
    "angle_gl_driver_selection_values",
    "angle_gl_driver_all_angle",
)


class TrialError(RuntimeError):
    pass


def adb(serial: str, *arguments: str, timeout: int = 25,
        allow_missing: bool = False) -> str:
    proc = subprocess.run(
        ["adb", "-s", serial, *arguments],
        capture_output=True, text=True, errors="replace",
        timeout=timeout, check=False,
    )
    if proc.returncode == 1 and allow_missing and not proc.stderr.strip() and not proc.stdout.strip():
        return ""
    if proc.returncode != 0:
        raise TrialError(f"adb exit {proc.returncode}: {' '.join(arguments)}; "
                         f"{proc.stderr.strip()[:400]}")
    return proc.stdout.strip()


def setting_value(serial: str, key: str) -> str | None:
    value = adb(serial, "shell", "settings", "get", "global", key)
    return None if value in ("", "null") else value


def snapshot(serial: str) -> dict:
    android_api = adb(serial, "shell", "getprop", "ro.build.version.sdk")
    abi = adb(serial, "shell", "getprop", "ro.product.cpu.abi")
    device = adb(serial, "shell", "getprop", "ro.product.device")
    package = adb(serial, "shell", "pm", "path", GAME)
    flags = adb(serial, "shell", "dumpsys", "package", GAME)
    installed_angle = adb(serial, "shell", "pm", "path", ANGLE, allow_missing=True)
    running_game = adb(serial, "shell", "pidof", GAME, allow_missing=True)
    return {
        "api": int(android_api) if android_api.isdigit() else None,
        "abi": abi,
        "device": device,
        "game_installed": "package:" in package,
        "game_debuggable": "DEBUGGABLE" in flags,
        "angle_installed": "package:" in installed_angle,
        "game_running": bool(running_game),
        "settings": {key: setting_value(serial, key) for key in SETTINGS},
    }


def safe_for_trial(before: dict) -> list[str]:
    issues = []
    if before["api"] is None or before["api"] < 29:
        issues.append("Android API 29+ required")
    if before["abi"] != "x86_64" or before["device"] != "windows_x86_64":
        issues.append("Expected WSA x86_64, never a physical phone")
    if not before["game_installed"] or not before["game_debuggable"]:
        issues.append("CallofRecomp debuggable build not installed")
    if before["angle_installed"]:
        issues.append("ANGLE already installed: refuse to replace an existing package")
    if before["game_running"]:
        issues.append("Game is running: refuse to interrupt a session")
    if any(value is not None for value in before["settings"].values()):
        issues.append("ANGLE settings already configured: refuse to modify custom preferences")
    return issues


def restore(serial: str, before: dict, installed: bool, launched: bool) -> list[str]:
    errors = []
    # Rollback is attempted even after partial configuration or launch failure.
    if launched:
        try:
            adb(serial, "shell", "am", "force-stop", GAME)
        except (OSError, subprocess.TimeoutExpired, TrialError) as ex:
            errors.append(f"stop_game: {ex}")
    for key, original in before["settings"].items():
        try:
            if original is None:
                adb(serial, "shell", "settings", "delete", "global", key)
            else:
                adb(serial, "shell", "settings", "put", "global", key, original)
            if setting_value(serial, key) != original:
                errors.append(f"restore_setting_mismatch: {key}")
        except (OSError, subprocess.TimeoutExpired, TrialError) as ex:
            errors.append(f"restore_setting_error: {key}: {ex}")
    if installed:
        try:
            adb(serial, "uninstall", ANGLE, timeout=70)
            if "package:" in adb(serial, "shell", "pm", "path", ANGLE, allow_missing=True):
                errors.append("ANGLE package still installed after uninstall")
        except (OSError, subprocess.TimeoutExpired, TrialError) as ex:
            errors.append(f"uninstall_error: {ex}")
    return errors


def logcat_verdict(log: str) -> dict:
    # Logcat alone is corroborating evidence, not proof of comparable gameplay.
    return {
        "android_angle_package_selected": bool(
            re.search(r"GraphicsEnvironment.*ANGLE package enabled:\s*org\.chromium\.angle", log)),
        "angle_vulkan_renderer_reported": bool(
            re.search(r"ANGLE\s*:.*Renderer\s*\(Vulkan\b", log, re.I)),
        "gameplay_fps_measured": False,
    }


def run_trial(serial: str, apk: Path, sha256: str, aapt: str, apksigner: str,
              seconds: int) -> dict:
    before = snapshot(serial)
    blockers = safe_for_trial(before)
    if blockers:
        raise TrialError("Unsafe for test: " + "; ".join(blockers))
    verification = inspect(apk, aapt, apksigner, sha256)
    if not verification["ready_for_isolated_trial"]:
        raise TrialError("APK verification did not pass: " + str(verification["checks"]))
    started = False
    installed = False
    install_attempted = False
    trial_error: Exception | None = None
    report = {"verification_sha256": verification["sha256"],
              "baseline_settings": before["settings"], "trial_started": False}
    try:
        install_attempted = True
        adb(serial, "install", "-r", "-d", "--force-queryable", str(apk), timeout=120)
        installed = True
        if "package:" not in adb(serial, "shell", "pm", "path", ANGLE):
            raise TrialError("Android did not register ANGLE package")
        adb(serial, "shell", "settings", "put", "global", "angle_debug_package", ANGLE)
        adb(serial, "shell", "settings", "put", "global", "angle_gl_driver_selection_pkgs", GAME)
        adb(serial, "shell", "settings", "put", "global", "angle_gl_driver_selection_values", "angle")
        t0 = time.time()
        started = True
        adb(serial, "shell", "am", "start", "-n", GAME + "/.LauncherActivity")
        report["trial_started"] = True
        time.sleep(seconds)
        # The most recent 1000 entries may contain unrelated ANGLE log messages:
        # report as diagnostic only, not incontrovertible renderer provenance.
        log = adb(serial, "logcat", "-d", "-t", "1000", timeout=40)
        report.update(logcat_verdict(log))
        report["log_tail_ANGLE"] = [line[:500] for line in log.splitlines()
                                    if "ANGLE" in line or "GraphicsEnvironment" in line][-30:]
        report["host_start_time_epoch"] = t0
        report["gameplay_fps_measured"] = False
    except (OSError, TrialError, subprocess.TimeoutExpired, ValueError) as ex:
        trial_error = ex
    finally:
        # An interrupted installation may have left the package installed.
        if install_attempted and not installed:
            try:
                installed = "package:" in adb(
                    serial, "shell", "pm", "path", ANGLE, allow_missing=True
                )
            except (OSError, subprocess.TimeoutExpired, TrialError):
                # Conservatively attempt cleanup when the package status is unknown.
                installed = True
        report["rollback_errors"] = restore(serial, before, installed, started)
    report["configuration_restored"] = not report["rollback_errors"]
    if trial_error is not None:
        raise TrialError("ANGLE trial failed: " + str(trial_error) +
                         "; rollback: " + str(report["rollback_errors"]))
    if report["rollback_errors"]:
        raise TrialError("ANGLE trial rollback is incomplete: " +
                         str(report["rollback_errors"]))
    return report


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--serial", default=SERIAL)
    p.add_argument("--execute", action="store_true", help="Install and temporarily opt into ANGLE")
    p.add_argument("--apk", type=Path)
    p.add_argument("--expected-sha256")
    p.add_argument("--aapt", default=shutil.which("aapt"))
    p.add_argument("--apksigner", default=shutil.which("apksigner"))
    p.add_argument("--seconds", type=int, default=30)
    p.add_argument("--json-out", type=Path)
    args = p.parse_args()
    if args.seconds < 10 or args.seconds > 180:
        p.error("--seconds must be between 10 and 180")
    if args.serial != SERIAL:
        p.error(f"Only the audited WSA target {SERIAL} is supported")
    if args.execute and (not args.apk or not args.aapt or not args.apksigner or
                         not args.expected_sha256 or
                         not re.fullmatch(r"[a-fA-F0-9]{64}", args.expected_sha256)):
        p.error("--execute requires --apk, --aapt, --apksigner and --expected-sha256")
    try:
        if args.execute:
            result = run_trial(args.serial, args.apk, args.expected_sha256,
                               args.aapt, args.apksigner, args.seconds)
            exit_code = 0 if result["configuration_restored"] else 3
        else:
            before = snapshot(args.serial)
            result = {"mode": "read_only", "wsa": before,
                      "blockers": safe_for_trial(before),
                      "apk_verified": False, "angle_executed": False,
                      "gameplay_fps_measured": False}
            exit_code = 0
    except (OSError, TrialError, subprocess.TimeoutExpired, ValueError, RuntimeError) as ex:
        result = {"error": str(ex), "trial_success": False,
                  "gameplay_fps_measured": False}
        exit_code = 2
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
