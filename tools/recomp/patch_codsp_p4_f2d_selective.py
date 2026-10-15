#!/usr/bin/env python3
"""Version-pinned CoDSP 1.5 p4 selective x87 normal-to-double experiment.

The generated game source is private, under recomp_out/, and is NEVER part of
this repository. Rewrites only f2d(rd(...),10) at guest labels within four
hot original function bodies. Every other f2d stays on the old exact path.
--restore is byte-identical to the original; unknown sources fail closed.
"""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import re
from codsp_p4_profiled_pcs import PROFILED_GUEST_PCS

ORIGINAL_SHA256 = "ee9156183cc0410bf0641592f93d3d0efa4febc906cc014969ddb30d95a196d3"
PCODE_SHA256 = "36f9093b386e03b4bcdc489cff2a708f7c0b8012e9a0fa78a7001bd3f125da1e"
# SHA of the deterministic private generated-C patch, not game asset bytes.
PATCHED_SHA256 = "b9a667ba9f467be99d94e3ca6ce6464b8a3e1ddfaf04c1ff17715beeb70fe284"
# Half-open original Ghidra function-body intervals. In particular, 0x47bd6c
# to 0x47bd70 is not owned by the sampled body and must remain untouched.
HOT_RANGES = (
    (0x00475D80, 0x00475EBD),  # 114 archived CPU samples
    (0x00476070, 0x004760FB),  # 85
    (0x004766E0, 0x00476DE2),  # 105
    (0x0047BD40, 0x0047BD6C),  # 213 (two recovered body intervals)
    (0x0047BD70, 0x0047C419),
)
INCLUDE = '#include "recomp_rt.h"'
# The header exposes the existing inline checked helper under
# CODRECOMP_X87_NORMAL_F2D; disabling its *global* f2d macro lets every
# unselected instruction call the original implementation.
HEADER_GUARD = (
    '#if defined(CODRECOMP_X87_NORMAL_F2D_P4_SELECTIVE)\n'
    '#undef f2d\n'
    '#else\n'
    '#error "Patched CoDSP p4 requires CODRECOMP_X87_NORMAL_F2D_P4_SELECTIVE"\n'
    '#endif\n'
)
LABEL = re.compile(r"(?m)^L_([0-9a-fA-F]+):[ \t]*(?:\r?\n)")
SLOW_CALL = re.compile(r"(?<![A-Za-z_0-9])f2d\(rd\([^()\r\n]*\),10\)")
FAST_CALL = re.compile(r"(?<![A-Za-z_0-9])codsp_x87_normal_f2d\(rd\([^()\r\n]*\),10\)")
EXPECTED_REPLACEMENTS = 520  # original CoDSP 1.5, five exact body intervals
PROFILED_PATCHED_SHA256 = "9b3d27670850fcdad26b7318374e7614102650e5d03825c4b28843e6be444b90"
PROFILED_EXPECTED_REPLACEMENTS = 277  # 124 profiled PCs, two historical captures
PROFILED_HEADER_GUARD = HEADER_GUARD.replace(
    "CODRECOMP_X87_NORMAL_F2D_P4_SELECTIVE",
    "CODRECOMP_X87_NORMAL_F2D_P4_PROFILED",
)



def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def is_hot(pc: int) -> bool:
    return any(start <= pc < end for start, end in HOT_RANGES)


def convert_blocks(source: str, to_fast: bool, *, profiled: bool = False) -> tuple[str, int, int]:
    """Pure PC-local conversion; never substitutes generated guest control flow."""
    matches = list(LABEL.finditer(source))
    if not matches:
        raise ValueError("No original guest labels found")
    chunks = [source[:matches[0].start()]]
    seen = set()
    modified_labels = 0
    count = 0
    old, new = (SLOW_CALL, "codsp_x87_normal_f2d") if to_fast else (FAST_CALL, "f2d")
    for i, match in enumerate(matches):
        pc = int(match.group(1), 16)
        if pc in seen:
            raise ValueError(f"Duplicate guest instruction label: {pc:08x}")
        seen.add(pc)
        end = matches[i+1].start() if i+1 < len(matches) else len(source)
        block = source[match.end():end]
        if (pc in PROFILED_GUEST_PCS if profiled else is_hot(pc)):
            changed, n = old.subn(lambda m: m.group(0).replace(
                "f2d(" if to_fast else "codsp_x87_normal_f2d(", new+"(", 1), block)
            if n:
                modified_labels += 1
                count += n
            block = changed
        chunks.extend((match.group(0), block))
    return "".join(chunks), count, modified_labels


def inject_guard(text: str, to_fast: bool, *, profiled: bool = False) -> str:
    line_end = "\r\n" if "\r\n" in text[:400] else "\n"
    header = (PROFILED_HEADER_GUARD if profiled else HEADER_GUARD).replace("\n", line_end)
    anchor = INCLUDE + line_end
    if to_fast:
        if text.count(anchor) != 1 or header in text:
            raise ValueError("Unknown generated include layout or duplicate patch guard")
        return text.replace(anchor, anchor + header, 1)
    if text.count(anchor + header) != 1:
        raise ValueError("Missing exact selective p4 patch guard")
    return text.replace(anchor + header, anchor, 1)


def patch_text(text: str, to_fast: bool, *, profiled: bool = False) -> tuple[str, int, int]:
    # Rewriting label-local f2d does not touch .text/.rodata or branch labels.
    modified, count, labels = convert_blocks(text, to_fast, profiled=profiled)
    modified = inject_guard(modified, to_fast, profiled=profiled)
    return modified, count, labels


def mutate(source: Path, pcode: Path, *, apply: bool, analyze: bool = False,
           profiled: bool = False) -> None:
    if not source.is_file() or not pcode.is_file():
        raise ValueError("CoDSP p4 generated source and p-code are required")
    if digest(pcode.read_bytes()) != PCODE_SHA256:
        raise ValueError("Unrecognized CoDSP 1.5 p-code; refusing private source rewrite")
    raw = source.read_bytes()
    sha = digest(raw)
    target_sha = PROFILED_PATCHED_SHA256 if profiled else PATCHED_SHA256
    expected_count = PROFILED_EXPECTED_REPLACEMENTS if profiled else EXPECTED_REPLACEMENTS
    required_sha = ORIGINAL_SHA256 if apply else target_sha
    already_sha = target_sha if apply else ORIGINAL_SHA256
    if sha == already_sha and not analyze:
        print("Selective p4: already in requested state, SHA-256", sha)
        return
    if sha != required_sha:
        raise ValueError("Unrecognized p4 generated source SHA-256: " + sha)
    text = raw.decode("utf-8")
    modified, n, n_labels = patch_text(text, apply, profiled=profiled)
    out = modified.encode("utf-8")
    output_sha = digest(out)
    if apply:
        if not n or (n != expected_count and not analyze):
            raise ValueError(f"Unexpected selective conversion count: {n}")
        if not analyze and output_sha != target_sha:
            raise ValueError("Changed selective patch layout; no write performed")
    elif output_sha != ORIGINAL_SHA256:
        raise ValueError("Selective restore failed to reproduce original generated source")
    if analyze:
        print("proposed_sha256", output_sha, "replacements", n,
              "guest_labels", n_labels, "bytes_delta", len(out)-len(raw))
        return
    # Source is private and generated: atomically change only this exact file.
    temp = source.with_name(source.name + ".selective.tmp")
    if temp.exists():
        raise ValueError("Refusing to overwrite existing private temporary file")
    try:
        temp.write_bytes(out)
        if digest(temp.read_bytes()) != output_sha:
            raise RuntimeError("Temporary source checksum mismatch")
        os.replace(temp, source)
    finally:
        if temp.exists():
            temp.unlink()
    print("Selective p4", "profiled" if profiled else "body-wide",
          "applied" if apply else "restored",
          "SHA-256", output_sha, "conversion_sites", n, "labels", n_labels)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("source", type=Path)
    ap.add_argument("pcode", type=Path)
    opts = ap.add_mutually_exclusive_group(required=True)
    opts.add_argument("--apply", action="store_true")
    opts.add_argument("--restore", action="store_true")
    opts.add_argument("--analyze", action="store_true",
                      help="offline dry-run of the original-to-candidate rewrite")
    ap.add_argument("--profiled", action="store_true",
                    help="use the fixed two-session 2+-sample hot-PC set; OFF unless requested")
    args = ap.parse_args()
    mutate(args.source, args.pcode, apply=args.apply or args.analyze,
           analyze=args.analyze, profiled=args.profiled)


if __name__ == "__main__":
    main()
