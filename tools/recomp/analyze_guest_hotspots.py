#!/usr/bin/env python3
"""Annotate existing guest CPU chunk samples with Ghidra function-entry metadata.

This does not profile functions. An x86 function may cross multiple chunks,
a chunk may contain many functions, and the recorded start/end is a dispatch
slot rather than the current instruction. NEVER assign its sampled CPU time
to any individual function in the candidate list.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

RE_CHUNK = re.compile(
    r"\bcpu sample: chunk ([0-9a-fA-F]{8})-([0-9a-fA-F]{8}) "
    r"time_us=(\d+) calls=(\d+)\b"
)


def annotate(text: str, mappings: list[dict], top: int = 20) -> dict:
    if top < 1:
        raise ValueError("top must be positive")
    index: dict[tuple[str, str], list[tuple[str, dict]]] = {}
    for doc in mappings:
        if (not isinstance(doc, dict) or doc.get("schema_version") not in (1, 2)
                or not isinstance(doc.get("chunks"), list)):
            raise ValueError("unsupported or incomplete function map schema")
        for chunk in doc["chunks"]:
            key = (chunk["start_va"].lower(), chunk["end_va_exclusive"].lower())
            index.setdefault(key, []).append((doc["module"], chunk))
    aggregates: dict[tuple[str, str], dict] = {}
    records = 0
    for line in text.splitlines():
        match = RE_CHUNK.search(line)
        if not match:
            continue
        start, end = ("0x" + match[1].lower(), "0x" + match[2].lower())
        records += 1
        row = aggregates.setdefault((start, end), {
            "start_va": start, "end_va_exclusive": end,
            "sampled_time_us": 0, "sampled_calls": 0, "sample_records": 0,
        })
        row["sampled_time_us"] += int(match[3])
        row["sampled_calls"] += int(match[4])
        row["sample_records"] += 1
    ordered = sorted(aggregates.values(),
                     key=lambda x: (-x["sampled_time_us"], x["start_va"], x["end_va_exclusive"]))
    for row in ordered:
        key = (row["start_va"], row["end_va_exclusive"])
        found = index.get(key, [])
        row["matches"] = [{
            "module": module,
            "chunk_index": chunk["index"],
            "generated_part": chunk["generated_part"],
            "function_entries_in_chunk": chunk["function_entries_in_chunk"],
            "preceding_entry_context": chunk["preceding_entry_context"],
            "body_function_instruction_counts": chunk.get("body_function_instruction_counts"),
            "body_ambiguous_instructions": chunk.get("body_ambiguous_instructions"),
            "body_unmapped_instructions": chunk.get("body_unmapped_instructions"),
        } for module, chunk in found]
        row["exact_chunk_match"] = len(found) == 1
        row["function_cpu_attribution"] = "NOT_AVAILABLE"
    return {
        "sample_records": records,
        "sampled_chunk_count": len(ordered),
        "chunk_rows_without_unique_map": sum(
            not row["exact_chunk_match"] for row in ordered),
        "warning": ("Only elapsed CPU time of sampled CHUNK dispatches is recorded; "
                    "this may have sampling overhead and cannot be divided "
                    "between candidate functions or compared to full frame CPU."),
        "hot_chunks": ordered[:top],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("log", type=Path, help="private engine log with cpu sample: chunk records")
    ap.add_argument("--map", action="append", dest="maps", required=True,
                    type=Path, help="private JSON function map (repeat for each module)")
    ap.add_argument("--top", type=int, default=20)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    result = annotate(args.log.read_text(encoding="utf-8", errors="replace"),
                      [json.loads(path.read_text(encoding="utf-8")) for path in args.maps],
                      top=args.top)
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"sample_records={result['sample_records']} "
              f"hot_chunks={result['sampled_chunk_count']} "
              f"unmatched_or_ambiguous={result['chunk_rows_without_unique_map']}")
        for row in result["hot_chunks"]:
            labels = [
                f"{m['module']}:chunk{m['chunk_index']}"
                f"({len(m['function_entries_in_chunk'])} entries)"
                for m in row["matches"]]
            print(f"{row['start_va']}..{row['end_va_exclusive']} "
                  f"sampled_us={row['sampled_time_us']} "
                  f"calls={row['sampled_calls']} "
                  f"matches={','.join(labels) or 'NO_EXACT_MAP'}")
        print("WARNING: chunk timing is NOT per-function CPU attribution.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
