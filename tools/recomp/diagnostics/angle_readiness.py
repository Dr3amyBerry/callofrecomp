#!/usr/bin/env python3
"""Read-only audit of a pinned ANGLE source checkout and Android/WSA driver selection.

No settings.put, installs, APK changes, system driver changes, network downloads,
graphics context creation, or FPS measurements are performed.
"""
from __future__ import annotations
import argparse
import json
import shutil
import subprocess
from pathlib import Path

DOC_MARKERS = (
    "Android builds currently require Linux",
    "target_os = \"android\"",
    "autoninja -C out/Android angle_apks",
    "angle_enable_vulkan = true",
    "angle_debug_package",
    "angle_gl_driver_selection_pkgs",
    "angle_gl_driver_selection_values",
)
ANGLE_REQUIRED_PATHS = (
    "DEPS",
    "README.md",
    "doc/DevSetupAndroid.md",
    "doc/DevSetup.md",
    "extensions/EGL_ANGLE_platform_angle_vulkan.txt",
    "src/libANGLE/renderer/vulkan/DisplayVk.cpp",
)

def run(args: list[str], timeout: int = 22) -> tuple[int, str]:
    try:
        result = subprocess.run(
            args, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, errors="replace", timeout=timeout, check=False)
        return result.returncode, result.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return -1, ""

def parse_package_path(code: int, output: str) -> bool:
    return code == 0 and any(line.startswith("package:")
                             for line in output.splitlines())

def parse_settings(output: str) -> str | None:
    val = output.strip()
    return None if val in ("", "null") else val

def classify(source_ok: bool, android_sdk: int | None, app_debuggable: bool,
             java_activity: bool, angle_apk_present: bool,
             selected_packages: str | None, selected_values: str | None,
             debug_package: str | None) -> dict:
    pkgs = (selected_packages or "").split(",")
    drivers = (selected_values or "").split(",")
    selected = "unspecified"
    if len(pkgs) == len(drivers):
        for pkg, driver in zip(pkgs, drivers):
            if pkg == "org.callofrecomp":
                selected = driver
                break
    supports_platform = android_sdk is not None and android_sdk >= 29
    can_try = (source_ok and supports_platform and app_debuggable and
               java_activity and angle_apk_present and
               debug_package == "org.chromium.angle")
    selected_angle = can_try and selected == "angle"
    reasons = []
    if not source_ok:
        reasons.append("ANGLE source tree missing expected files or docs")
    if not supports_platform:
        reasons.append("Android API must be at least 29 for documented package driver selection")
    if not app_debuggable:
        reasons.append("App is not debuggable; debug ANGLE selection needs root instead")
    if not java_activity:
        reasons.append("No Java-launched Android activity confirmed")
    if not angle_apk_present:
        reasons.append("Official AngleLibraries.apk is not installed")
    if debug_package != "org.chromium.angle":
        reasons.append("angle_debug_package not configured (left unchanged)")
    if selected != "angle":
        reasons.append("org.callofrecomp not opted into ANGLE (left unchanged)")
    return {
        "architecture_candidate": supports_platform and app_debuggable and java_activity,
        "debug_angle_package_present": angle_apk_present,
        "app_selection": selected,
        "settings_point_to_angle": selected_angle,
        "could_test_once_angle_is_built_and_installed": bool(
            source_ok and supports_platform and app_debuggable and java_activity),
        "blockers_for_current_test": reasons,
        "vulkan_angle_execution_verified": False,
        "gameplay_fps_measured": False,
    }

def audit(source: Path, project: Path, adb: str, serial: str) -> dict:
    source = source.resolve()
    missing = [f for f in ANGLE_REQUIRED_PATHS if not (source / f).is_file()]
    docs = ((source / "doc/DevSetupAndroid.md").read_text(
        encoding="utf-8", errors="replace")
        if not missing else "")
    doc_checks = {fragment: fragment in docs for fragment in DOC_MARKERS}
    source_ok = not missing and all(doc_checks.values())
    c, head = run(["git", "-C", str(source), "rev-parse", "HEAD"])
    if c != 0 or len(head) != 40:
        raise ValueError("Not a valid ANGLE Git checkout")
    c, tree = run(["git", "-C", str(source), "show", "-s", "--format=%T", "HEAD"])
    if c != 0 or len(tree) != 40:
        raise ValueError("Cannot verify source tree identity")
    c, fsck = run(["git", "-C", str(source), "fsck", "--no-reflogs"], 50)
    if c != 0:
        raise ValueError("Git object integrity verification failed")
    c, dirty = run(["git", "-C", str(source), "status", "--porcelain=v1"])
    if c != 0:
        raise ValueError("Git source status unavailable")
    host = {tool:shutil.which(tool) is not None for tool in ("gn", "gclient", "autoninja", "ninja")}
    # WSL executable can exist without a Linux distro; no automatic installation.
    wc, distro = run(["wsl", "--list", "--quiet"], 12)
    host["wsl_linux_distribution"] = wc == 0 and bool(distro)
    def adb_read(*args: str) -> tuple[int, str]:
        return run([adb, "-s", serial, "shell", *args], 25)
    _, sdk_raw = adb_read("getprop", "ro.build.version.sdk")
    _, arch = adb_read("getprop", "ro.product.cpu.abi")
    sdk = int(sdk_raw) if sdk_raw.isdigit() else None
    pc, ptext = adb_read("pm", "path", "org.chromium.angle")
    ac, atxt = adb_read("pm", "path", "org.chromium.angle.agi")
    _, dumpsys = adb_read("dumpsys", "package", "org.callofrecomp")
    _, chooser = adb_read("settings", "get", "global", "angle_debug_package")
    _, apps = adb_read("settings", "get", "global", "angle_gl_driver_selection_pkgs")
    _, values = adb_read("settings", "get", "global", "angle_gl_driver_selection_values")
    _, all_angle = adb_read("settings", "get", "global", "angle_gl_driver_all_angle")
    manifest = project / "android/AndroidManifest.xml"
    activity = project / "android/java/org/callofrecomp/GameActivity.java"
    java_activity = (manifest.is_file() and activity.is_file() and
                     '.GameActivity' in manifest.read_text(encoding='utf-8') and
                     'extends SDLActivity' in activity.read_text(encoding='utf-8'))
    # Installed package is debuggable if Android's package flags say so.
    is_debuggable = "DEBUGGABLE" in dumpsys
    state = classify(source_ok, sdk, is_debuggable, java_activity,
                     parse_package_path(pc, ptext),
                     parse_settings(apps), parse_settings(values), parse_settings(chooser))
    return {
        "source": {
            "repository": "https://chromium.googlesource.com/angle/angle.git",
            "commit": head, "git_tree": tree, "git_fsck_passed": True,
            "clean": dirty == "", "missing_expected_files": missing,
            "documentation_checks": doc_checks,
            "source_complete_with_dependencies": False,
            "dependencies_need_gclient_sync": True,
        },
        "host_build": {
            "available_tools": host,
            "android_build_ready": (
                host["wsl_linux_distribution"] and host["gn"] and
                host["gclient"] and host["autoninja"]),
            "official_android_build_requires_linux": True,
        },
        "android": {
            "serial":serial, "api": sdk, "abi":arch,
            "app_debuggable":is_debuggable,
            "java_launched_sdl_activity_confirmed":java_activity,
            "angle_package_installed":parse_package_path(pc, ptext),
            "angle_agi_package_installed":parse_package_path(ac, atxt),
            "settings": {
                "angle_debug_package":parse_settings(chooser),
                "angle_gl_driver_selection_pkgs":parse_settings(apps),
                "angle_gl_driver_selection_values":parse_settings(values),
                "angle_gl_driver_all_angle":parse_settings(all_angle),
            },
        },
        "decision":state,
        "caveat":"This audit does not install, enable or execute ANGLE or compare FPS.",
    }

def main()->int:
    p=argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--project", type=Path, default=Path("."))
    p.add_argument("--adb", default="adb")
    p.add_argument("--serial", default="127.0.0.1:58526")
    p.add_argument("--json-out", type=Path)
    args=p.parse_args()
    output=audit(args.source,args.project,args.adb,args.serial)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True,exist_ok=True)
        args.json_out.write_text(json.dumps(output,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(output,indent=2))
    return 0
if __name__=="__main__":
    raise SystemExit(main())
