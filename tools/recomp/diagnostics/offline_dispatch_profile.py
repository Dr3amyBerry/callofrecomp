#!/usr/bin/env python3
"""Audit archived Simpleperf samples for one native hot symbol, without ADB.

Verify the recorded Simpleperf Build ID against the supplied *unstripped* ELF
before resolving inlined source lines. Output only aggregates; do not publish
raw proprietary guest PC addresses, ELF samples or device trace timestamps.
This is CPU sampling evidence, NOT game FPS, GPU time, or a dispatch hit rate.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import re
import subprocess
import sys


def parse_elf_build_id(elf_notes: str) -> str:
    matches = re.findall(r"Build ID:\s*([0-9a-fA-F]{40})\b", elf_notes)
    if len(matches) != 1:
        raise ValueError("Expected exactly one 20-byte ELF Build ID")
    return matches[0].lower()


def recorded_build_id(build_ids: dict[str, str], dso: str = "libmain.so") -> str:
    matching = [value.removeprefix("0x").lower() for name, value in build_ids.items()
                if name.replace("\\", "/").split("/")[-1] == dso]
    if len(matching) != 1 or not re.fullmatch(r"[0-9a-f]{40}", matching[0]):
        raise ValueError("Missing or ambiguous recorded native library Build ID")
    return matching[0]


def symbol_range(nm_output: str, symbol: str) -> tuple[int, int]:
    matches = []
    for line in nm_output.splitlines():
        parts = line.split()
        if len(parts) == 4 and parts[3] == symbol and parts[2] in {"T", "t"}:
            begin, size = int(parts[0], 16), int(parts[1], 16)
            if size > 0:
                matches.append((begin, begin + size))
    if len(matches) != 1:
        raise ValueError("Expected one nonempty exact native symbol")
    return matches[0]


def aggregate_annotations(annotated: list[tuple[str, str, int]],
                          process_samples: int) -> dict:
    if process_samples < 1:
        raise ValueError("No process samples")
    by_inline, by_line, by_file = Counter(), Counter(), Counter()
    included = 0
    for fn, source, weight in annotated:
        if weight <= 0:
            raise ValueError("Sample weight must be positive")
        if not fn:
            raise ValueError("Missing symbolizer function")
        basename = source.replace("\\", "/").split("/")[-1]
        if not basename:
            basename = "(unresolved)"
        by_inline[fn] += weight
        by_line[basename] += weight
        by_file[basename.split(":")[0]] += weight
        included += weight
    if included > process_samples:
        raise ValueError("More sampled symbol hits than total process samples")
    def rows(counter):
        return [{"name": name, "samples": n} for name, n in
                sorted(counter.items(), key=lambda x: (-x[1], x[0]))]
    return {
        "symbol_samples": included,
        "process_samples": process_samples,
        "symbol_process_share_pct": round(included * 100 / process_samples, 3),
        "inline_function_counts": rows(by_inline),
        "source_file_counts": rows(by_file),
        "source_line_counts": rows(by_line),
        "interpretation": (
            "Sparse Simpleperf CPU samples annotated through inlined DWARF "
            "source; not a guest dispatcher hit rate, CPU ms/frame or FPS."
        ),
    }


def run_command(command: list[str], input_text: str | None = None) -> str:
    result = subprocess.run(command, input=input_text, capture_output=True,
                            text=True, errors="replace", timeout=120)
    if result.returncode != 0:
        raise RuntimeError(f"Tool failed: {Path(command[0]).name}: "
                           f"{result.stderr[-350:]}")
    return result.stdout


def offline_report(perf: Path, elf: Path, ndk: Path, symbol: str = "guest_run") -> dict:
    if not perf.is_file() or not elf.is_file():
        raise ValueError("Private perf.data and exact unstripped ELF required")
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", symbol):
        raise ValueError("Expected one plain C symbol name")
    tools = sorted((ndk / "toolchains/llvm/prebuilt").glob("*/bin"))
    if len(tools) != 1:
        raise ValueError("Expected one NDK host toolchain directory")
    bin_dir = tools[0]
    names = [("llvm-nm", "llvm-nm"), ("llvm-readelf", "llvm-readelf"),
             ("llvm-addr2line", "llvm-addr2line")]
    def executable(stem):
        matches = list(bin_dir.glob(stem)) + list(bin_dir.glob(stem + ".exe"))
        if len(matches) != 1:
            raise ValueError(f"Missing or ambiguous {stem} in NDK")
        return str(matches[0])
    nm = run_command([executable("llvm-nm"), "-S", str(elf)])
    begin, end = symbol_range(nm, symbol)
    notes = run_command([executable("llvm-readelf"), "-n", str(elf)])
    elf_id = parse_elf_build_id(notes)

    sys.path.insert(0, str(ndk / "simpleperf"))
    from simpleperf_report_lib import ReportLib
    lib = ReportLib()
    lib.SetRecordFile(str(perf))
    perf_id = recorded_build_id(lib.GetAllBuildIds())
    if elf_id != perf_id:
        raise ValueError("Recorded perf.data Build ID differs from supplied ELF")
    n = 0
    elf_hits = 0
    native = Counter()
    while (sample := lib.GetNextSample()) is not None:
        n += 1
        match = lib.GetSymbolOfCurrentSample()
        if match and Path(match.dso_name).name == "libmain.so":
            elf_hits += 1
            address = int(match.vaddr_in_file)
            if begin <= address < end:
                native[address] += 1
    if not native:
        raise ValueError("No CPU samples in requested native symbol")
    ordered = sorted(native)
    source = run_command([executable("llvm-addr2line"), "-f", "-C",
                          "-e", str(elf)],
                         "".join(f"0x{addr:x}\n" for addr in ordered)).splitlines()
    if len(source) != 2 * len(ordered):
        raise RuntimeError("Unexpected llvm-addr2line response")
    annotations = [(source[2*i], source[2*i+1], native[address])
                   for i, address in enumerate(ordered)]
    report = aggregate_annotations(annotations, n)
    report.update({
        "target_symbol": symbol,
        "verified_elf_build_id": elf_id,
        "libmain_samples": elf_hits,
        "unique_native_sample_sites_in_symbol": len(native),
        "warning": (
            "Only CPU user-space sampling from an archived capture. Exact "
            "ELF Build ID is verified, but this does not prove a change "
            "in gameplay performance or recover consecutive dispatch calls."
        )
    })
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--perf", required=True, type=Path)
    p.add_argument("--elf", required=True, type=Path)
    p.add_argument("--ndk", required=True, type=Path)
    p.add_argument("--symbol", default="guest_run")
    p.add_argument("--out", type=Path, help="optional private aggregate JSON output")
    args = p.parse_args()
    if args.out and args.out.exists():
        p.error("Refusing to overwrite an earlier profiler report")
    result = offline_report(args.perf, args.elf, args.ndk, args.symbol)
    report = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(report, encoding="utf-8")
    # Print only the compact diagnostic summary (no private paths).
    print("Archived CPU samples:", result["process_samples"],
          "symbol:", result["target_symbol"],
          "symbol_samples:", result["symbol_samples"],
          "percentage:", result["symbol_process_share_pct"])
    for row in result["inline_function_counts"][:10]:
        print("inline", row["name"], row["samples"])
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
