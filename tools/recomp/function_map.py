#!/usr/bin/env python3
"""Map original Ghidra function-entry markers onto unchanged pcode2c chunks.

This is a *diagnostic* map, not a control-flow recovery or CPU profiler.
Function entries do not imply contiguous function bodies: jumps, shared code,
discontiguous Ghidra bodies and gaps can all invalidate range ownership.
Keep per-game sidecars under ignored recomp_out/, never in the public repo.
"""
from __future__ import annotations

import argparse
from bisect import bisect_left
import json
from pathlib import Path


DEFAULT_CHUNK_SIZE = 1500  # Matches pcode2c.CHUNK; caller passes that constant.


def _decimal_or_hex(value: str) -> int:
    return int(value, 16 if value.lower().startswith("0x") else 10)


def scan_pcode_headers(path: Path) -> tuple[list[tuple[int, int]], list[int]]:
    """Read only I/F records. No proprietary p-code operations are materialized."""
    instructions, entries = [], []
    with path.open(encoding="utf-8") as source:
        for number, line in enumerate(source, 1):
            if not line or line[0] not in ("I", "F") or line[1:2] != " ":
                continue
            parts = line.split()
            needed = 3 if parts[0] == "I" else 2
            if len(parts) != needed:
                raise ValueError(f"{path}:{number}: malformed {parts[0]} record")
            try:
                address = _decimal_or_hex(parts[1])
                if parts[0] == "I":
                    instructions.append((address, _decimal_or_hex(parts[2])))
                else:
                    entries.append(address)
            except ValueError as exc:
                raise ValueError(f"{path}:{number}: invalid address/length") from exc
    return instructions, entries


def build_function_map(
    instructions: list[tuple[int, int]],
    function_entries: list[int],
    module: str,
    *,
    parts: int = 1,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
) -> dict:
    """Reproduce generator chunk/part indices without modifying generated code.

    The exact function ENTRY is matched to an I address. The preceding entry
    is only context and must NOT be treated as an owner of all subsequent PCs.
    """
    if not module or parts < 1 or chunk_size < 1:
        raise ValueError("module must be named and parts/chunk_size must be positive")
    insns = sorted(instructions)
    if any(a < 0 or a >= 2**32 or size <= 0 or a + size > 2**32
           for a, size in insns):
        raise ValueError("instruction addresses and sizes must fit guest 32-bit space")
    addresses = [a for a, _ in insns]
    if len(set(addresses)) != len(addresses):
        raise ValueError("duplicate instruction addresses make chunk positions ambiguous")
    entries = sorted(set(function_entries))
    if any(a < 0 or a >= 2**32 for a in entries):
        raise ValueError("function entry address outside guest 32-bit space")
    count = (len(insns) + chunk_size - 1) // chunk_size
    functions, matched = [], []
    assigned = [[] for _ in range(count)]
    for entry in entries:
        position = bisect_left(addresses, entry)
        exists = position < len(addresses) and addresses[position] == entry
        ci = position // chunk_size if exists else None
        functions.append({
            "entry_va": f"0x{entry:08x}",
            "entry_chunk_index": ci,
            "entry_in_translation": exists,
        })
        if exists:
            matched.append(entry)
            assigned[ci].append(entry)
    chunks = []
    for i in range(count):
        chunk = insns[i * chunk_size:(i + 1) * chunk_size]
        start, end = chunk[0][0], chunk[-1][0] + chunk[-1][1]
        previous = bisect_left(matched, start) - 1
        chunks.append({
            "index": i,
            "generated_part": i * parts // count,
            "start_va": f"0x{start:08x}",
            "end_va_exclusive": f"0x{end:08x}",
            "instruction_count": len(chunk),
            "function_entries_in_chunk": [f"0x{va:08x}" for va in assigned[i]],
            "preceding_entry_context": (f"0x{matched[previous]:08x}"
                                        if previous >= 0 else None),
        })
    return {
        "schema_version": 1,
        "module": module,
        "chunk_instruction_limit": chunk_size,
        "generated_part_count": parts,
        "instruction_count": len(insns),
        "chunk_count": count,
        "exported_function_entry_count": len(entries),
        "matched_function_entry_count": len(matched),
        "unmatched_function_entry_count": len(entries) - len(matched),
        "chunks_with_multiple_function_entries": sum(
            len(chunk["function_entries_in_chunk"]) > 1 for chunk in chunks),
        "warning": ("Markers identify function ENTRIES only; chunk intervals can "
                    "contain gaps, interleaved or discontiguous functions. "
                    "Never assign measured chunk time to any listed function."),
        "functions": functions,
        "chunks": chunks,
    }


def write_function_map(path: Path, mapping: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(mapping, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("pcode", type=Path, help="private Ghidra ExportPcode.java output")
    ap.add_argument("--module", help="PE module label; defaults to p-code file stem")
    ap.add_argument("--parts", type=int, default=1, help="match generated --parts")
    ap.add_argument("--out", required=True, type=Path, help="ignored JSON sidecar path")
    args = ap.parse_args()
    if args.out.resolve() == args.pcode.resolve():
        ap.error('--out must not overwrite the original p-code input')
    insns, functions = scan_pcode_headers(args.pcode)
    mapping = build_function_map(insns, functions, args.module or args.pcode.stem,
                                 parts=args.parts)
    write_function_map(args.out, mapping)
    print("module={module} instructions={instruction_count} chunks={chunk_count} "
          "function_entries={matched_function_entry_count} "
          "unmatched={unmatched_function_entry_count} multi_entry_chunks="
          "{chunks_with_multiple_function_entries}".format(**mapping))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
