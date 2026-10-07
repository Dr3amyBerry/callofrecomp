#!/usr/bin/env python3
"""Run the reproducible static-analysis baseline for the verified CoD 1.5 SP build.

This is the preferred entry point for routine analysis. It verifies the original
binary fingerprints first, then invokes the lower-level PE/VM probes and writes
machine-readable reports under analysis/local/ (ignored by Git).
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from engine_vm_probe import analyze as analyze_engine_vm
from pe_inspect import PEFile
from vm_abi_probe import analyze as analyze_module_vm


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROFILE = PROJECT_ROOT / "analysis" / "baselines" / "cod1_sp_pc_1_5.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def parse_hex_mapping(values: dict[str, str]) -> dict[str, int]:
    return {name: int(value, 0) for name, value in values.items()}


def verify_binary(path: Path, expected: dict) -> dict:
    if not path.is_file():
        raise FileNotFoundError(f"required original binary is missing: {path}")

    size = path.stat().st_size
    digest = sha256_file(path)
    expected_size = int(expected["size_bytes"])
    expected_digest = expected["sha256"].lower()

    if size != expected_size:
        raise ValueError(
            f"{path.name}: size mismatch: got {size}, expected {expected_size}"
        )
    if digest.lower() != expected_digest:
        raise ValueError(
            f"{path.name}: SHA-256 mismatch:\n"
            f"  got      {digest}\n"
            f"  expected {expected_digest}"
        )

    return {
        "name": path.name,
        "path": str(path),
        "size_bytes": size,
        "sha256": digest,
        "verified": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify and analyze the known Call of Duty 1.5 SP baseline"
    )
    parser.add_argument(
        "--originals",
        type=Path,
        default=PROJECT_ROOT / "originals",
        help="directory containing CoDSP.exe and the three SP DLLs",
    )
    parser.add_argument(
        "--profile",
        type=Path,
        default=DEFAULT_PROFILE,
        help="verified build profile JSON",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=PROJECT_ROOT / "analysis" / "local",
        help="generated report directory",
    )
    args = parser.parse_args()

    profile = json.loads(args.profile.read_text(encoding="utf-8"))
    binary_specs = profile["binaries"]

    required = ["CoDSP.exe", "gamex86.dll", "cgamex86.dll", "uix86.dll"]
    verified = {}
    for name in required:
        verified[name] = verify_binary(args.originals / name, binary_specs[name])
        print(f"verified {name}: {verified[name]['sha256']}")

    args.out.mkdir(parents=True, exist_ok=True)

    pe_reports = [
        PEFile(args.originals / name).report()
        for name in required
    ]
    (args.out / "pe_report.json").write_text(
        json.dumps({"schema_version": 1, "binaries": pe_reports}, indent=2) + "\n",
        encoding="utf-8",
    )

    module_reports = [
        analyze_module_vm(args.originals / name)
        for name in ("gamex86.dll", "cgamex86.dll", "uix86.dll")
    ]
    (args.out / "vm_abi.json").write_text(
        json.dumps({"schema_version": 1, "modules": module_reports}, indent=2) + "\n",
        encoding="utf-8",
    )

    engine_vm = profile["engine_vm"]
    engine_report = analyze_engine_vm(
        args.originals / "CoDSP.exe",
        int(engine_vm["vm_call_va"], 0),
        parse_hex_mapping(engine_vm["handle_slots"]),
        parse_hex_mapping(engine_vm["syscall_callbacks"]),
    )
    (args.out / "engine_vm.json").write_text(
        json.dumps({"schema_version": 1, **engine_report}, indent=2) + "\n",
        encoding="utf-8",
    )

    summary = {
        "schema_version": 1,
        "profile_id": profile["id"],
        "version": profile["version"],
        "verified_inputs": verified,
        "reports": {
            "pe": "pe_report.json",
            "module_vm": "vm_abi.json",
            "engine_vm": "engine_vm.json",
        },
    }
    (args.out / "baseline_report.json").write_text(
        json.dumps(summary, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"analysis complete: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
