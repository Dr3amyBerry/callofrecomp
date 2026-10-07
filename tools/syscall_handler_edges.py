#!/usr/bin/env python3
"""Inventory direct CALL/JMP edges inside numbered engine syscall handlers.

Uses the jump tables recovered by engine_vm_probe and binutils objdump for
instruction boundaries. This produces evidence, *not* guessed syscall names.
The boundaries are provisional: each handler is scanned from its dispatch
target up to the next distinct dispatch target (or the configured byte cap).
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from bisect import bisect_right
from pathlib import Path

from engine_vm_probe import PEFile, PEFormatError, recover_syscall_dispatch

BRANCH_RE = re.compile(
    r"^\s*(?P<va>[0-9a-fA-F]+):\s+"
    r"(?:[0-9a-fA-F]{2}\s+)+"
    r"(?P<op>call|jmp)\s+(?P<target>0x[0-9a-fA-F]+)\b"
)


def decoded_direct_edges(exe: Path, start: int, stop: int, objdump: str) -> list[dict]:
    """Disassemble the bounded region and return *direct* branch targets."""
    if stop <= start:
        return []
    result = subprocess.run(
        [
            objdump, "-D", "-M", "intel",
            f"--start-address=0x{start:x}",
            f"--stop-address=0x{stop:x}",
            str(exe),
        ],
        check=True, capture_output=True, text=True,
    )
    edges: list[dict] = []
    for line in result.stdout.splitlines():
        match = BRANCH_RE.match(line)
        if match:
            src = int(match.group("va"), 16)
            if start <= src < stop:
                edges.append({
                    "source_va": src,
                    "kind": match.group("op"),
                    "target_va": int(match.group("target"), 16),
                })
    return edges


def analyze(
    exe: Path,
    callback_va: int,
    start_id: int,
    end_id: int,
    max_handler_bytes: int = 192,
    objdump: str = "objdump",
) -> dict:
    if start_id < 0 or end_id < start_id or max_handler_bytes < 1:
        raise ValueError("invalid syscall range or max-handler-bytes")
    pe = PEFile(exe)
    table = recover_syscall_dispatch(pe, callback_va)
    if end_id > table["max_id"]:
        raise ValueError(f"end-id {end_id} exceeds dispatcher max {table['max_id']}")
    entries = table["entries"]
    distinct_targets = sorted({entry["target_va"] for entry in entries})
    cache: dict[int, dict] = {}
    for item in entries[start_id:end_id + 1]:
        va = item["target_va"]
        if va not in cache:
            pos = bisect_right(distinct_targets, va)
            next_target = (
                distinct_targets[pos] if pos < len(distinct_targets)
                else va + max_handler_bytes
            )
            end = min(next_target, va + max_handler_bytes)
            # Validate that both ends are file-backed; never decode unbacked data.
            pe.va_to_offset(va)
            pe.va_to_offset(end - 1)
            cache[va] = {
                "entry_va": va,
                "entry_rva": va - pe.image_base,
                "scan_end_va": end,
                "scan_bytes": end - va,
                "direct_edges": decoded_direct_edges(exe, va, end, objdump),
            }
    return {
        "schema_version": 1,
        "binary": exe.name,
        "dispatcher_callback_va": callback_va,
        "id_range": [start_id, end_id],
        "max_handler_bytes": max_handler_bytes,
        "evidence": "objdump decoded direct branches; handler boundaries are provisional",
        "handlers": [
            {"id": item["id"], **cache[item["target_va"]]}
            for item in entries[start_id:end_id + 1]
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Inventory bounded direct edges from engine syscall handlers")
    parser.add_argument("exe", type=Path)
    parser.add_argument("--callback-va", required=True, type=lambda v: int(v, 0))
    parser.add_argument("--start-id", required=True, type=int)
    parser.add_argument("--end-id", required=True, type=int)
    parser.add_argument("--max-handler-bytes", type=int, default=192)
    parser.add_argument("--objdump", default="objdump")
    parser.add_argument("--json", dest="json_path", type=Path)
    args = parser.parse_args()
    try:
        report = analyze(
            args.exe, args.callback_va, args.start_id, args.end_id,
            args.max_handler_bytes, args.objdump,
        )
    except (OSError, PEFormatError, ValueError, subprocess.CalledProcessError) as exc:
        parser.error(str(exc))
    for item in report["handlers"]:
        outgoing = ", ".join(
            f"{edge['kind']} 0x{edge['target_va']:08x}"
            for edge in item["direct_edges"]
        ) or "(no direct branch found)"
        print(f"{item['id']:3}: handler 0x{item['entry_va']:08x} -> {outgoing}")
    if args.json_path:
        args.json_path.parent.mkdir(parents=True, exist_ok=True)
        args.json_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
