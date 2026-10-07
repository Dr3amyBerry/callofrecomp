#!/usr/bin/env python3
"""Fingerprint observed Call of Duty 1.5 SP searchpath insertion behavior.

Verifies the original routine by SHA-256, avoiding redistributing code bytes.
The meaning of the field at node+0x0C is not yet established.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path

ROUTINE_RVA = 0x248B0
ROUTINE_BYTES = 55
ROUTINE_SHA256 = "51a41202f498c49d4e8c7d001c8ac647d531882c324f220c57fc7bb6ebe07683"
BASELINE_SHA256 = "c755c7da411c87039ade462a2299402c3c4ca5c4fc4f1ae5cea6e25b05c69f47"


def file_offset_for_rva(data: bytes, rva: int) -> int:
    if len(data) < 64 or data[:2] != b"MZ":
        raise ValueError("Not an MZ/PE file")
    pe_offset = struct.unpack_from("<I", data, 0x3C)[0]
    if pe_offset + 24 > len(data) or data[pe_offset:pe_offset + 4] != b"PE\0\0":
        raise ValueError("Invalid PE header")
    sections = struct.unpack_from("<H", data, pe_offset + 6)[0]
    optional_size = struct.unpack_from("<H", data, pe_offset + 20)[0]
    table = pe_offset + 24 + optional_size
    for i in range(sections):
        at = table + i * 40
        if at + 40 > len(data):
            raise ValueError("Truncated section table")
        _, vsize, vaddr, raw_size, raw_offset = struct.unpack_from("<8sIIII", data, at)
        if vaddr <= rva < vaddr + raw_size:
            offset = raw_offset + rva - vaddr
            if offset + ROUTINE_BYTES > raw_offset + raw_size or offset + ROUTINE_BYTES > len(data):
                raise ValueError("Routine extends beyond section")
            return offset
    raise ValueError("Routine RVA not mapped")


def probe(path: Path, require_baseline: bool = True) -> dict:
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if require_baseline and digest != BASELINE_SHA256:
        raise ValueError("CoDSP.exe baseline SHA-256 mismatch")
    offset = file_offset_for_rva(data, ROUTINE_RVA)
    routine_digest = hashlib.sha256(data[offset:offset + ROUTINE_BYTES]).hexdigest()
    if routine_digest != ROUTINE_SHA256:
        raise ValueError("Searchpath insertion routine fingerprint mismatch")
    return {
        "schema_version": 1,
        "binary": path.name,
        "file_sha256": digest,
        "routine_rva": ROUTINE_RVA,
        "routine_bytes": ROUTINE_BYTES,
        "routine_sha256": routine_digest,
        "searchpath_head_va": "0x013F9E3C",
        "link_offset": 0,
        "class_field_offset": 12,
        "branches": [
            {"condition": "new.class_field == 0 OR list empty", "action": "prepend"},
            {"condition": "new.class_field != 0 AND list not empty", "action": "after head and consecutive class_field==0 successors"},
        ],
        "confidence": "observed machine code fingerprint; field semantics not identified",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("exe", type=Path)
    parser.add_argument("--allow-unpinned-file", action="store_true",
                        help="only require the 55-byte routine fingerprint")
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    try:
        report = probe(args.exe, not args.allow_unpinned_file)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    result = json.dumps(report, indent=2) + "\n"
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(result, encoding="utf-8")
    print(result, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
