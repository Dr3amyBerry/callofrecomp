#!/usr/bin/env python3
"""Find absolute x86 references to ASCII strings in PE32 binaries.

Useful for legacy binaries that embed absolute VAs in PUSH/MOV operands. The
tool does not pretend every 4-byte match is an instruction-level xref; it emits
candidate references with section/VA metadata for reproducible follow-up.
"""
from __future__ import annotations

import argparse
import json
import re
import struct
from pathlib import Path

from pe_inspect import PEFile


def file_offset_to_rva(pe: PEFile, file_offset: int) -> int | None:
    if file_offset < pe.size_of_headers:
        return file_offset
    for section in pe.sections:
        if section.raw_offset <= file_offset < section.raw_offset + section.raw_size:
            return section.virtual_address + (file_offset - section.raw_offset)
    return None


def collect_strings(pe: PEFile, pattern: re.Pattern[str], min_length: int) -> list[dict]:
    result = []
    for file_offset, value in pe.ascii_strings(min_length):
        if not pattern.search(value):
            continue
        rva = file_offset_to_rva(pe, file_offset)
        if rva is None:
            continue
        result.append(
            {
                "value": value,
                "file_offset": file_offset,
                "rva": rva,
                "va": pe.image_base + rva,
            }
        )
    return result


def candidate_xrefs(pe: PEFile, string_va: int, executable_only: bool = True) -> list[dict]:
    needle = struct.pack("<I", string_va)
    refs = []
    for section in pe.sections:
        if executable_only and not (section.characteristics & 0x20000000):
            continue
        raw = pe.data[section.raw_offset : section.raw_offset + section.raw_size]
        start = 0
        while True:
            index = raw.find(needle, start)
            if index < 0:
                break
            rva = section.virtual_address + index
            refs.append(
                {
                    "section": section.name,
                    "file_offset": section.raw_offset + index,
                    "rva": rva,
                    "va": pe.image_base + rva,
                }
            )
            start = index + 1
    return refs


def analyze(path: Path, regex: str, min_length: int, include_unreferenced: bool) -> dict:
    pe = PEFile(path)
    pattern = re.compile(regex)
    rows = []
    for item in collect_strings(pe, pattern, min_length):
        refs = candidate_xrefs(pe, item["va"])
        if refs or include_unreferenced:
            rows.append({**item, "candidate_xrefs": refs})
    return {
        "binary": path.name,
        "image_base": pe.image_base,
        "regex": regex,
        "strings": rows,
        "referenced_string_count": sum(bool(x["candidate_xrefs"]) for x in rows),
        "candidate_xref_count": sum(len(x["candidate_xrefs"]) for x in rows),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Find candidate absolute x86 references to PE32 ASCII strings"
    )
    parser.add_argument("file", type=Path)
    parser.add_argument("--regex", default=r".+", help="Python regex applied to each ASCII string")
    parser.add_argument("--min-length", type=int, default=4)
    parser.add_argument("--include-unreferenced", action="store_true")
    parser.add_argument("--json", dest="json_path", type=Path)
    args = parser.parse_args()

    report = analyze(args.file, args.regex, args.min_length, args.include_unreferenced)
    for item in report["strings"]:
        refs = ", ".join(f"0x{x['va']:08x}" for x in item["candidate_xrefs"])
        print(f"0x{item['va']:08x} {item['value']!r} -> {refs or '<none>'}")

    if args.json_path:
        args.json_path.parent.mkdir(parents=True, exist_ok=True)
        args.json_path.write_text(
            json.dumps({"schema_version": 1, **report}, indent=2) + "\n",
            encoding="utf-8",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
