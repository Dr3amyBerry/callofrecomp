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
from collections import defaultdict
import json
from pathlib import Path


DEFAULT_CHUNK_SIZE = 1500  # Matches pcode2c.CHUNK; caller passes that constant.


def _decimal_or_hex(value: str) -> int:
    return int(value, 16 if value.lower().startswith("0x") else 10)


def scan_pcode_provenance(
    path: Path,
) -> tuple[list[tuple[int, int]], list[int], list[tuple[int, int, int]]]:
    """Read only I/F/B records, never proprietary raw p-code operation bodies.

    B records describe inclusive Ghidra function body address ranges. Older
    Ghidra exports have no B records; they remain fully supported.
    """
    instructions, entries, bodies = [], [], []
    with path.open(encoding="utf-8") as source:
        for number, line in enumerate(source, 1):
            if not line or line[0] not in ("I", "F", "B") or line[1:2] != " ":
                continue
            parts = line.split()
            needed = {"I": 3, "F": 2, "B": 4}[parts[0]]
            if len(parts) != needed:
                raise ValueError(f"{path}:{number}: malformed {parts[0]} record")
            try:
                numbers = tuple(_decimal_or_hex(part) for part in parts[1:])
                if parts[0] == "I":
                    instructions.append(numbers)
                elif parts[0] == "F":
                    entries.append(numbers[0])
                else:
                    bodies.append(numbers)
            except ValueError as exc:
                raise ValueError(f"{path}:{number}: invalid address/length") from exc
    return instructions, entries, bodies


def scan_pcode_headers(path: Path) -> tuple[list[tuple[int, int]], list[int]]:
    """Backwards-compatible I/F-only interface for earlier diagnostics."""
    instructions, entries, _ = scan_pcode_provenance(path)
    return instructions, entries


def build_function_map(
    instructions: list[tuple[int, int]],
    function_entries: list[int],
    module: str,
    *,
    parts: int = 1,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    function_bodies: list[tuple[int, int, int]] | None = None,
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
    result = {
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

    if function_bodies:
        for chunk in chunks:
            chunk["body_unmapped_instructions"] = 0
            chunk["body_ambiguous_instructions"] = 0
            chunk["_owners"] = defaultdict(int)
        # Body ranges are Ghidra's membership model, *not* a proven dynamic
        # call stack. Multiple functions may claim an instruction, and branch
        # targets may enter in the middle of a body without visiting its F.
        body_ranges = sorted(set(function_bodies))
        known_entries = set(entries)
        for entry, lo, hi in body_ranges:
            if (entry not in known_entries or lo < 0 or lo >= 2**32
                    or hi < lo or hi >= 2**32):
                raise ValueError("invalid B record: entry unknown or body out of range")
        events = []
        for entry, lo, hi in body_ranges:
            events.append((lo, entry, 1))
            events.append((hi + 1, entry, -1))
        events.sort()
        active = defaultdict(int)
        cursor = 0
        per_entry_count = defaultdict(int)
        uniquely_owned = ambiguous = unmapped = 0
        for i, (address, size) in enumerate(insns):
            while cursor < len(events) and events[cursor][0] <= address:
                _, entry, delta = events[cursor]
                active[entry] += delta
                if active[entry] == 0:
                    del active[entry]
                cursor += 1
            chunk = chunks[i // chunk_size]
            # Reject instructions crossing a body boundary, even when the
            # instruction's starting address is inside a known body.
            crosses_boundary = (cursor < len(events)
                                and events[cursor][0] < address + size)
            if crosses_boundary or not active:
                unmapped += 1
                chunk["body_unmapped_instructions"] += 1
            elif len(active) != 1:
                ambiguous += 1
                chunk["body_ambiguous_instructions"] += 1
            else:
                owner = next(iter(active))
                uniquely_owned += 1
                per_entry_count[owner] += 1
                chunk["_owners"][owner] += 1
        for chunk in chunks:
            owners = chunk.pop("_owners")
            chunk["body_function_instruction_counts"] = [
                {"entry_va": f"0x{entry:08x}", "instruction_count": count}
                for entry, count in sorted(owners.items())]
        for function in functions:
            function["body_uniquely_owned_instruction_count"] = per_entry_count[
                int(function["entry_va"], 16)]
        result.update({
            "schema_version": 2,
            "ghidra_body_range_count": len(body_ranges),
            "ghidra_body_ranges": [
                {"entry_va": f"0x{entry:08x}", "start_va": f"0x{lo:08x}",
                 "end_va_inclusive": f"0x{hi:08x}"}
                for entry, lo, hi in body_ranges],
            "body_uniquely_owned_instruction_count": uniquely_owned,
            "body_ambiguous_instruction_count": ambiguous,
            "body_unmapped_instruction_count": unmapped,
            "warning": ("Ghidra B ranges describe static function body membership, "
                        "including discontiguous ranges. They cannot establish runtime "
                        "function calls, exclusive CPU or complete control flow. "
                        "Never apportion chunk CPU samples among these owners."),
        })
    return result


def write_function_map(path: Path, mapping: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(mapping, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("pcode", type=Path, help="private Ghidra ExportPcode.java output")
    ap.add_argument("--module", help="PE module label; defaults to p-code file stem")
    ap.add_argument("--parts", type=int, default=1, help="match generated --parts")
    ap.add_argument("--body-records", type=Path,
                    help="optional separate Ghidra F/B-only export from the same binary")
    ap.add_argument("--out", required=True, type=Path, help="ignored JSON sidecar path")
    args = ap.parse_args()
    protected = {args.pcode.resolve()}
    if args.body_records:
        protected.add(args.body_records.resolve())
    if args.out.resolve() in protected:
        ap.error('--out must not overwrite an original p-code or body input')
    insns, functions, bodies = scan_pcode_provenance(args.pcode)
    if args.body_records:
        separate_instructions, separate_functions, separate_bodies = (
            scan_pcode_provenance(args.body_records))
        if separate_instructions:
            ap.error('--body-records must contain only F/B, never I/P')
        if not separate_bodies:
            ap.error('--body-records must contain Ghidra B body intervals')
        # Ghidra analysis may have changed since the original p-code was
        # exported; fail closed rather than silently associating stale ranges.
        if set(separate_functions) != set(functions):
            ap.error('--body-records F entries do not match the original p-code')
        if bodies and sorted(set(bodies)) != sorted(set(separate_bodies)):
            ap.error('--body-records contradict inline B records')
        bodies = separate_bodies
    mapping = build_function_map(insns, functions, args.module or args.pcode.stem,
                                 parts=args.parts, function_bodies=bodies)
    write_function_map(args.out, mapping)
    print("module={module} instructions={instruction_count} chunks={chunk_count} "
          "function_entries={matched_function_entry_count} "
          "unmatched={unmatched_function_entry_count} multi_entry_chunks="
          "{chunks_with_multiple_function_entries}".format(**mapping))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
