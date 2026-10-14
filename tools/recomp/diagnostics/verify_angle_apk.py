#!/usr/bin/env python3
"""Offline integrity/identity gate for an ANGLE Android x86_64 debug-driver APK.

This command NEVER installs packages, starts the game or changes Android settings.
It proves basic APK structure, ABI, package identity and signature verification,
not Google authorship, Vulkan execution or game performance.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import struct
import subprocess
import zipfile
from pathlib import Path

ANGLE_PACKAGE = "org.chromium.angle"
WSA_ABI = "x86_64"
X86_64_EM = 62


def elf_x86_64_header(data: bytes) -> bool:
    return (len(data) >= 20 and data[:4] == b"\x7fELF"
            and data[4] == 2 and data[5] == 1
            and struct.unpack_from("<H", data, 18)[0] == X86_64_EM)


def inspect_archive(apk: Path) -> dict:
    """Read only the APK ZIP index, required native ELF headers and SHA-256."""
    digest = hashlib.sha256()
    with apk.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(block)
    with zipfile.ZipFile(apk) as z:
        entries = z.namelist()
        native = [name for name in entries
                  if name.startswith("lib/") and name.endswith(".so")]
        target = [name for name in native if name.startswith(f"lib/{WSA_ABI}/")]
        egl = [name for name in target if "libegl" in Path(name).name.lower()]
        gles = [name for name in target if "libglesv2" in Path(name).name.lower()]
        checked = egl + gles
        valid_elf_headers = bool(egl and gles) and all(
            elf_x86_64_header(z.open(name).read(20)) for name in checked)
        return {
            "sha256": digest.hexdigest(),
            "size_bytes": apk.stat().st_size,
            "zip_manifest_present": "AndroidManifest.xml" in entries,
            "native_abis": sorted(set(name.split("/")[1] for name in native)),
            "egl_x86_64": egl,
            "glesv2_x86_64": gles,
            "native_elf_headers_valid_x86_64": valid_elf_headers,
        }


def parse_aapt_badging(text: str) -> str | None:
    match = re.search(r"(?m)^package:\s+name='([^']+)'", text)
    return match.group(1) if match else None


def parse_apksigner_result(returncode: int, text: str) -> bool:
    # apksigner exits nonzero for invalid signatures; reject silent/empty output.
    return (returncode == 0 and
            "Verifies" in text and
            re.search(r"(?im)^Verified using v[1234] scheme.*:\s*true\s*$", text) is not None)


def verify_with_android_tools(apk: Path, aapt: str, apksigner: str) -> dict:
    results: dict = {"package_name": None, "apk_signature_verified": False}
    try:
        metadata = subprocess.run(
            [aapt, "dump", "badging", str(apk)],
            check=False, capture_output=True, text=True, timeout=25)
        if metadata.returncode == 0:
            results["package_name"] = parse_aapt_badging(metadata.stdout)
        verified = subprocess.run(
            [apksigner, "verify", "--verbose", str(apk)],
            check=False, capture_output=True, text=True, timeout=40)
        results["apk_signature_verified"] = parse_apksigner_result(
            verified.returncode, verified.stdout)
    except (OSError, subprocess.TimeoutExpired):
        pass
    return results


def inspect(apk: Path, aapt: str | None, apksigner: str | None,
            expected_sha256: str | None = None) -> dict:
    data = inspect_archive(apk)
    data["hash_matches_supplied_reference"] = (
        None if expected_sha256 is None else
        data["sha256"] == expected_sha256.lower())
    data.update(verify_with_android_tools(apk, aapt, apksigner)
                if aapt and apksigner else {
                    "package_name": None, "apk_signature_verified": False})
    checks = {
        "zip_manifest": data["zip_manifest_present"],
        "wsa_egl_gles2_elf_headers": data["native_elf_headers_valid_x86_64"],
        "package_is_org_chromium_angle": data["package_name"] == ANGLE_PACKAGE,
        "android_signature_valid": data["apk_signature_verified"],
        "expected_digest_if_provided": data["hash_matches_supplied_reference"] is not False,
    }
    data["checks"] = checks
    data["ready_for_isolated_trial"] = all(checks.values())
    data["angle_vulkan_executed"] = False
    data["gameplay_performance_measured"] = False
    data["caveat"] = "Signature validity is NOT proof of Google signing or trustworthy build provenance."
    return data


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("apk", type=Path)
    p.add_argument("--aapt", default=shutil.which("aapt"))
    p.add_argument("--apksigner", default=shutil.which("apksigner"))
    p.add_argument("--expected-sha256", type=str)
    p.add_argument("--json-out", type=Path)
    args = p.parse_args()
    if args.expected_sha256 and not re.fullmatch("[a-fA-F0-9]{64}", args.expected_sha256):
        p.error("--expected-sha256 requires 64 hexadecimal characters")
    try:
        output = inspect(args.apk, args.aapt, args.apksigner, args.expected_sha256)
    except (OSError, zipfile.BadZipFile, ValueError, RuntimeError) as ex:
        print(json.dumps({"ready_for_isolated_trial": False, "error": str(ex)}))
        return 2
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(output, indent=2))
    return 0 if output["ready_for_isolated_trial"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
