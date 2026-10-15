#!/usr/bin/env python3
"""Compare generated native ARM64 functions offline, without accessing a device.

This is an *instruction-size and opcode histogram* audit, not a profiler.
It does NOT prove equivalent machine code when counts match, nor FPS gains.
Supply archived symbolized .so and freshly compiled .o/.so from the same
module revision. Never include game binary or proprietary source in output.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import re
import subprocess

SYMBOL = re.compile(r"^([0-9a-fA-F]+)\s+([0-9a-fA-F]+)\s+[Tt]\s+(\w+)$")
MNEMONIC = re.compile(r"^\s*[0-9a-fA-F]+:\s+([A-Za-z][\w.]*)\b")
DEFAULT_SYMBOLS = (
    "codsp_chunk_83_spaces",
    "codsp_chunk_84_spaces",
    "codsp_chunk_88_spaces",
)


def symbol_sizes(nm_output: str, only: set[str] | None = None) -> dict[str, int]:
    symbols: dict[str, int] = {}
    for line in nm_output.splitlines():
        match = SYMBOL.fullmatch(line.strip())
        if not match:
            continue
        size = int(match.group(2), 16)
        name = match.group(3)
        if only is not None and name not in only:
            continue
        if name in symbols:
            raise ValueError("Duplicate native symbol in nm output")
        if size:
            symbols[name] = size
    return symbols


def mnemonic_histogram(disassembly: str) -> Counter[str]:
    counts: Counter[str] = Counter()
    for line in disassembly.splitlines():
        match = MNEMONIC.match(line)
        if match:
            counts[match.group(1)] += 1
    return counts


def comparison(before_size: int, after_size: int,
               before_ops: Counter[str], after_ops: Counter[str]) -> dict:
    if min(before_size, after_size) <= 0 or not before_ops or not after_ops:
        raise ValueError("No symbol or instruction data")
    a, b = sum(before_ops.values()), sum(after_ops.values())
    # On AArch64 all instructions in these chunk bodies are fixed 4 bytes.
    if before_size != a * 4 or after_size != b * 4:
        raise ValueError("Unexpected instruction count / symbol size for AArch64")
    changes = [
        {"opcode": opcode, "delta": after_ops[opcode] - before_ops[opcode]}
        for opcode in sorted(before_ops.keys() | after_ops.keys())
        if after_ops[opcode] != before_ops[opcode]
    ]
    return {
        "before_bytes": before_size,
        "after_bytes": after_size,
        "delta_bytes": after_size - before_size,
        "before_instructions": a,
        "after_instructions": b,
        "delta_instructions": b-a,
        "opcode_changes": changes,
    }


def run(exe: Path, arguments: list[str]) -> str:
    proc = subprocess.run([str(exe), *arguments], text=True,
                          capture_output=True, timeout=180)
    if proc.returncode:
        raise RuntimeError(f"{exe.name} failed: {proc.stderr[-300:]}")
    return proc.stdout


def compare_files(llvm_nm: Path, llvm_objdump: Path,
                  before: Path, after: Path,
                  names: tuple[str, ...]) -> dict:
    if not before.is_file() or not after.is_file():
        raise FileNotFoundError("Two native symbolized files are required")
    requested = set(names)
    before_symbols = symbol_sizes(run(llvm_nm, ["-S", str(before)]), requested)
    after_symbols = symbol_sizes(run(llvm_nm, ["-S", str(after)]), requested)
    rows = {}
    for name in names:
        if name not in before_symbols or name not in after_symbols:
            raise ValueError("Symbol not present in BOTH inputs: " + name)
        a = mnemonic_histogram(run(llvm_objdump,
            ["--no-show-raw-insn", "--disassemble-symbols=" + name,
             str(before)]))
        b = mnemonic_histogram(run(llvm_objdump,
            ["--no-show-raw-insn", "--disassemble-symbols=" + name,
             str(after)]))
        rows[name] = comparison(before_symbols[name], after_symbols[name],
                                a, b)
    return {
        "comparison_type": "static AArch64 symbol size + opcode frequency",
        "inspected_symbols": rows,
        "overall_delta_bytes": sum(row["delta_bytes"] for row in rows.values()),
        "overall_delta_instructions":
            sum(row["delta_instructions"] for row in rows.values()),
        "warning": (
            "Matching opcode histograms do not establish byte-identical "
            "machine code, cycle cost or gameplay FPS."
        ),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--before", required=True, type=Path,
                    help="symbolized original ARM64 ELF (.so or .o)")
    ap.add_argument("--after", required=True, type=Path,
                    help="symbolized candidate ARM64 ELF (.so or .o)")
    ap.add_argument("--llvm-bin", required=True, type=Path,
                    help="NDK LLVM host bin folder (with llvm-nm / llvm-objdump)")
    ap.add_argument("--symbols", default=",".join(DEFAULT_SYMBOLS),
                    help="comma-separated exact native symbols to inspect")
    ap.add_argument("--output", type=Path,
                    help="optional JSON report; private directory recommended")
    args = ap.parse_args()
    names = tuple(name.strip() for name in args.symbols.split(","))
    if not names or any(not re.fullmatch(r"[a-zA-Z_][a-zA-Z_0-9]*", x)
                        for x in names) or len(set(names)) != len(names):
        ap.error("Expected unique C-style exact symbol names")
    def executable(stem: str) -> Path:
        variants = [args.llvm_bin / stem, args.llvm_bin / (stem + ".exe")]
        found = [v for v in variants if v.is_file()]
        if len(found) != 1:
            raise FileNotFoundError("Need exactly one NDK LLVM executable: "+stem)
        return found[0]
    data = compare_files(executable("llvm-nm"),
                         executable("llvm-objdump"),
                         args.before, args.after, names)
    payload = json.dumps(data, indent=2) + "\n"
    if args.output:
        if args.output.exists():
            raise ValueError("Refuse to overwrite prior audit report")
        args.output.write_text(payload, encoding="utf-8")
    print(payload)


if __name__ == "__main__":
    main()
