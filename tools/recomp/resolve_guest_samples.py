#!/usr/bin/env python3
"""Resolve sampled native C source lines to original x86 instruction labels.

Input is a TSV of source_file, 1-based source_line, native_sample_count.
Use *unstripped* local Android libmain.so and llvm-addr2line/simpleperf to
produce those source lines. No guest bytecode or original PE assets are read.

This is only line-table attribution: compiler inlining, scheduling and
optimization can associate a native PC with a different source line than
the actually executing guest instruction. Ghidra B ranges are analysis
metadata, not proof of true function ownership or precise CPU time.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import csv
import json
from pathlib import Path
import re
import subprocess

INSTRUCTION_LABEL = re.compile(r"^\s*L_([0-9a-fA-F]+):\s*$")
FUNCTION_BEGIN = re.compile(
    r"^\s*(?:static\s+)?void\s+\w+_chunk_\d+(?:_spaces)?\s*\(")
SOURCE_MODULE = re.compile(r"^([a-z0-9]+)_recomp(?:_p\d+)?\.c$", re.I)


def resolve_source_lines(path: Path, requested: set[int]) -> dict[int, int | None]:
    """Find the last genuine guest instruction label within the same C chunk.

    Relative p-code L_<addr>_<index> labels are *not* new instructions.
    The dyn dispatcher, wrappers and generated metadata have no guest owner.
    """
    if any(line <= 0 for line in requested):
        raise ValueError("source lines must be positive")
    result = {}
    if not requested:
        return result
    max_line = max(requested)
    pc = None
    with path.open(encoding="utf-8", errors="replace") as stream:
        for number, source in enumerate(stream, 1):
            if number > max_line:
                break
            if (FUNCTION_BEGIN.match(source) or source.startswith("dyn:")
                    or source.startswith("#undef GR")
                    or source.startswith("}")):
                pc = None
            matched = INSTRUCTION_LABEL.match(source)
            if matched:
                pc = int(matched.group(1), 16)
            if number in requested:
                result[number] = pc
    for number in requested:
        result.setdefault(number, None)
    return result


def parse_resolved_samples(tsv: Path) -> list[tuple[str, int, int]]:
    """Read explicitly tab-separated, pre-symbolized native sample counts."""
    rows = []
    with tsv.open(encoding="utf-8-sig", newline="") as stream:
        for number, values in enumerate(csv.reader(stream, delimiter="\t"), 1):
            if not values or (len(values) == 1 and not values[0].strip()):
                continue
            if number == 1 and values == ["source_file", "source_line", "samples"]:
                continue
            if len(values) != 3:
                raise ValueError(f"{tsv}:{number}: expected three TSV columns")
            source, raw_line, raw_weight = values
            if not source or not raw_line.isdecimal() or not raw_weight.isdecimal():
                raise ValueError(f"{tsv}:{number}: invalid source/line/count")
            line, weight = int(raw_line), int(raw_weight)
            if line <= 0 or weight <= 0:
                raise ValueError(f"{tsv}:{number}: source line and samples must be positive")
            rows.append((source.replace("\\", "/").split("/")[-1], line, weight))
    return rows


def parse_native_pcs(tsv: Path) -> list[tuple[int, int]]:
    """Read sampled ELF-relative virtual addresses; NEVER raw Android process PCs.

    ASLR load bias / mmap file offsets must already be resolved using the
    recording's DSO mapping. Treating a raw process PC as ELF-relative would
    silently symbolize the wrong function.
    """
    rows = []
    with tsv.open(encoding="utf-8-sig", newline="") as stream:
        for number, values in enumerate(csv.reader(stream, delimiter="\t"), 1):
            if not values or (len(values) == 1 and not values[0].strip()):
                continue
            if number == 1 and values == ["elf_pc", "samples"]:
                continue
            if (len(values) != 2 or not re.fullmatch(r"0x[0-9a-fA-F]+", values[0])
                    or not values[1].isdecimal()):
                raise ValueError(f"{tsv}:{number}: expected ELF virtual 0xADDR TAB samples")
            pc, weight = int(values[0], 16), int(values[1])
            if pc >= 2**64 or weight <= 0:
                raise ValueError(f"{tsv}:{number}: invalid ELF PC or sample count")
            rows.append((pc, weight))
    return rows


def symbolize_native_pcs(
    rows: list[tuple[int, int]], elf: Path, addr2line: Path,
) -> list[tuple[str, int, int]]:
    """Resolve ELF PCs including inlined helper frames with llvm-addr2line.

    Optimization often attributes a hot instruction to memcpy/rd/scarry
    defined in recomp_rt.h or NDK headers. Use -a -f -i and select the
    *outermost* positive-line generated-C frame, never the helper's line.
    If the generated parent has line 0, remain unresolved rather than guess.
    """
    if not elf.is_file() or not addr2line.is_file():
        raise ValueError("unstripped libmain.so and llvm-addr2line must exist")
    unique_pcs = sorted({pc for pc, _ in rows})
    mapped = {}
    for start in range(0, len(unique_pcs), 256):
        batch = unique_pcs[start:start + 256]
        done = subprocess.run(
            [str(addr2line), "-a", "-f", "-i", "-e", str(elf),
             *[f"0x{pc:x}" for pc in batch]],
            capture_output=True, text=True, check=True)
        groups = []
        current = None
        for line in done.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            if re.fullmatch(r"0x[0-9a-fA-F]+", line):
                if current is not None:
                    groups.append(current)
                current = (int(line, 16), [])
            elif current is None:
                raise ValueError("llvm-addr2line output missing -a address markers")
            else:
                current[1].append(line)
        if current is not None:
            groups.append(current)
        if len(groups) != len(batch) or [p for p, _ in groups] != batch:
            raise ValueError("llvm-addr2line output addresses mismatch requested ELF PCs")
        for pc, frames in groups:
            if len(frames) % 2:
                raise ValueError("llvm-addr2line returned incomplete inline frames")
            candidate = None
            for line in frames[1::2]:
                match = re.fullmatch(r"(.+?):(\d+)(?::\d+)?", line)
                if not match:
                    continue
                filename = match.group(1).replace("\\", "/").split("/")[-1]
                lineno = int(match.group(2))
                if SOURCE_MODULE.fullmatch(filename) and lineno > 0:
                    # An inlined helper can list multiple callsite frames.
                    # The final generated-code frame is the guest caller.
                    candidate = (filename, lineno)
            mapped[pc] = candidate or ("(unresolved)", 1)
    return [(mapped[pc][0], mapped[pc][1], weight) for pc, weight in rows]


def _owners_from_bodies(module: str, pcs: set[int], document: dict) -> dict[int, tuple[int, ...]]:
    if document.get("schema_version") != 2:
        return {pc: () for pc in pcs}
    events = []
    for body in document.get("ghidra_body_ranges", []):
        entry = int(body["entry_va"], 16)
        start = int(body["start_va"], 16)
        end = int(body["end_va_inclusive"], 16)
        if start > end or end >= 2**32:
            raise ValueError(f"invalid Ghidra body interval in {module}")
        events.append((start, entry, 1))
        events.append((end + 1, entry, -1))
    events.sort()
    active = defaultdict(int)
    index = 0
    owned = {}
    for pc in sorted(pcs):
        while index < len(events) and events[index][0] <= pc:
            _, entry, change = events[index]
            active[entry] += change
            if active[entry] == 0:
                del active[entry]
            index += 1
        owned[pc] = tuple(sorted(active))
    return owned


def resolve_native_samples(
    rows: list[tuple[str, int, int]], generated: list[Path], maps: list[dict],
    *, top: int = 20,
) -> dict:
    if top < 1:
        raise ValueError("top must be positive")
    by_source = {}
    for file in generated:
        key = file.name.lower()
        if key in by_source:
            raise ValueError(f"duplicate generated source basename: {key}")
        by_source[key] = file
    by_module = {}
    for document in maps:
        module = document.get("module", "").split(".", 1)[0].lower()
        if document.get("schema_version") not in (1, 2) or not module or module in by_module:
            raise ValueError("invalid or duplicate module provenance map")
        by_module[module] = document

    requested = defaultdict(set)
    for filename, line, _ in rows:
        requested[filename.lower()].add(line)
    line_guest_pc = {}
    for filename, lines in requested.items():
        if filename in by_source:
            line_guest_pc[filename] = resolve_source_lines(by_source[filename], lines)
        else:
            line_guest_pc[filename] = {line: None for line in lines}

    sample_pcs = defaultdict(set)
    observations = []
    for filename, line, count in rows:
        filename = filename.lower()
        guest_pc = line_guest_pc[filename][line]
        pattern = SOURCE_MODULE.fullmatch(filename)
        module = pattern.group(1).lower() if pattern else None
        if guest_pc is not None and module:
            sample_pcs[module].add(guest_pc)
        observations.append((module, guest_pc, count))
    owners = {
        module: _owners_from_bodies(module, pcs, by_module.get(module, {}))
        for module, pcs in sample_pcs.items()
    }

    function_hits = defaultdict(int)
    guest_pc_hits = defaultdict(int)
    total = resolved = unique = ambiguous = unowned = 0
    for module, pc, weight in observations:
        total += weight
        if module is None or pc is None:
            continue
        resolved += weight
        guest_pc_hits[(module, pc)] += weight
        matched = owners.get(module, {}).get(pc, ())
        if len(matched) == 1:
            function_hits[(module, matched[0])] += weight
            unique += weight
        elif len(matched) > 1:
            ambiguous += weight
        else:
            unowned += weight
    top_functions = sorted(function_hits.items(), key=lambda x: (-x[1], x[0]))
    top_pcs = sorted(guest_pc_hits.items(), key=lambda x: (-x[1], x[0]))
    return {
        "native_samples_total": total,
        "guest_label_resolved_samples": resolved,
        "unresolved_source_samples": total - resolved,
        "unique_ghidra_body_samples": unique,
        "ambiguous_ghidra_body_samples": ambiguous,
        "unowned_ghidra_body_samples": unowned,
        "functions_with_unique_samples": len(function_hits),
        "warning": ("These are weighted native profiler samples attributed through "
                    "optimized C line tables and Ghidra static B ranges. "
                    "They are approximate sampling evidence, NOT per-function "
                    "exclusive CPU time or proof of correct runtime ownership. "
                    "Never compare profiled and unprofiled FPS without A/B."),
        "top_body_function_samples": [
            {"module": module, "entry_va": f"0x{entry:08x}", "samples": weight}
            for (module, entry), weight in top_functions[:top]],
        "top_guest_instruction_labels": [
            {"module": module, "guest_pc": f"0x{pc:08x}", "samples": weight}
            for (module, pc), weight in top_pcs[:top]],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    samples = ap.add_mutually_exclusive_group(required=True)
    samples.add_argument("--samples", type=Path,
                         help="already-symbolized TSV: source_file TAB source_line TAB samples")
    samples.add_argument("--native-pcs", type=Path,
                         help="TSV with pre-normalized ELF-relative 0xPC TAB samples")
    ap.add_argument("--elf", type=Path,
                    help="required with --native-pcs: unstripped libmain.so")
    ap.add_argument("--addr2line", type=Path,
                    help="required with --native-pcs: NDK llvm-addr2line executable")
    ap.add_argument("--generated", action="append", required=True, type=Path,
                    help="private generated *_recomp_pN.c (repeat for each part)")
    ap.add_argument("--map", action="append", type=Path, default=[],
                    help="private function_map v2 JSON with Ghidra B body ranges")
    ap.add_argument("--top", type=int, default=20)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    if args.native_pcs:
        if not args.elf or not args.addr2line:
            ap.error("--native-pcs requires --elf and --addr2line")
        rows = symbolize_native_pcs(parse_native_pcs(args.native_pcs),
                                     args.elf, args.addr2line)
    else:
        if args.elf or args.addr2line:
            ap.error("--elf and --addr2line are only valid with --native-pcs")
        rows = parse_resolved_samples(args.samples)
    maps = [json.loads(file.read_text(encoding="utf-8")) for file in args.map]
    report = resolve_native_samples(rows, args.generated, maps, top=args.top)
    if args.json:
        print(json.dumps(report, sort_keys=True, indent=2))
    else:
        print(f"native_samples={report['native_samples_total']} "
              f"guest_label_resolved={report['guest_label_resolved_samples']} "
              f"unique_body={report['unique_ghidra_body_samples']} "
              f"ambiguous_body={report['ambiguous_ghidra_body_samples']} "
              f"no_body={report['unowned_ghidra_body_samples']}")
        for f in report["top_body_function_samples"]:
            print(f"candidate {f['module']} entry={f['entry_va']} samples={f['samples']}")
        print("WARNING: source-line attribution is approximate; no exclusive CPU-time claim.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
