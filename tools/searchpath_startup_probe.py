#!/usr/bin/env python3
"""Fingerprint and summarize one CoD 1.5 SP searchpath startup scan.

Reports original observed argument-word patterns and loop bounds. It does not
assign package priority or localization semantics without supporting evidence.
Original binary bytes are neither displayed nor committed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path

from searchpath_order_probe import BASELINE_SHA256, file_offset_for_rva

SCAN_RVA = 0x250E0
SCAN_SIZE = 40
SCAN_SHA256 = "4bab47e5b8163d26f05c3f0d73239b64b8569d16585fbfc2be0d86db7bf5cb4b"
SCAN_VA = 0x4250E0
EXPECTED_HELPER = 0x424E10


def decode_scan(data: bytes, address: int = SCAN_VA) -> dict:
    if len(data) != SCAN_SIZE:
        raise ValueError("startup scan region has an unexpected length")
    # Narrow, high-confidence observations, not a general disassembler:
    # a first call with two zero-valued pushed arguments, then a second
    # call with selector 1 and loop register starting at the embedded bound.
    if not (data[1] == 0x6A and data[2] == 0 and
            data[3] == 0x6A and data[4] == 0 and
            data[8] == 0xE8 and
            data[16] == 0xBE and
            data[21] == 0x56 and data[22] == 0x6A and data[23] == 1 and
            data[27] == 0xE8 and data[35] == 0x4E and
            data[36] == 0x79 and data[38] == 0x5E and data[39] == 0xC3):
        raise ValueError("startup scan control-flow shape is not recognized")
    first_target = address + 8 + 5 + struct.unpack_from("<i", data, 9)[0]
    indexed_target = address + 27 + 5 + struct.unpack_from("<i", data, 28)[0]
    if first_target != EXPECTED_HELPER or indexed_target != EXPECTED_HELPER:
        raise ValueError("startup scan helper call target mismatch")
    maximum = struct.unpack_from("<I", data, 17)[0]
    if maximum > 1000:
        raise ValueError("implausible startup scan loop bound")
    return {
        "first_call": {
            "va": address + 8,
            "target_va": first_target,
            "observed_immediate_arguments": [0, 0],
        },
        "indexed_calls": {
            "call_va": address + 27,
            "target_va": indexed_target,
            "observed_selector": 1,
            "index_first": maximum,
            "index_last": 0,
            "index_count": maximum + 1,
            "loop_direction": "descending",
        },
        "interpretation": "A helper call followed by a descending indexed scan; the helper's full package/locale semantics remain unverified.",
    }


def analyze(path: Path, require_baseline: bool = True) -> dict:
    binary = path.read_bytes()
    file_digest = hashlib.sha256(binary).hexdigest()
    if require_baseline and file_digest != BASELINE_SHA256:
        raise ValueError("original CoD 1.5 SP executable SHA-256 mismatch")
    offset = file_offset_for_rva(binary, SCAN_RVA)
    sample = binary[offset:offset + SCAN_SIZE]
    digest = hashlib.sha256(sample).hexdigest()
    if digest != SCAN_SHA256:
        raise ValueError("startup searchpath scan routine SHA-256 mismatch")
    return {
        "schema_version": 1,
        "file_name": path.name,
        "binary_sha256": file_digest,
        "scan_va": SCAN_VA,
        "scan_bytes": SCAN_SIZE,
        "scan_sha256": digest,
        **decode_scan(sample),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("exe", type=Path)
    parser.add_argument("--allow-unpinned-file", action="store_true")
    parser.add_argument("--json", dest="json_path", type=Path)
    args = parser.parse_args()
    try:
        report = analyze(args.exe, not args.allow_unpinned_file)
    except (OSError, ValueError, struct.error) as exc:
        parser.error(str(exc))
    output = json.dumps(report, indent=2) + "\n"
    if args.json_path:
        args.json_path.parent.mkdir(parents=True, exist_ok=True)
        args.json_path.write_text(output, encoding="utf-8")
    print(output, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
