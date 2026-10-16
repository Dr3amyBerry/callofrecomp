#!/usr/bin/env python3
"""Reversible CoDSP 1.5 ARM64 visibility FLD32 optimization at ten sampled PCs.

Only the single original 32->80 conversion expression is substituted.
Original guest LOAD/PC/store ordering, labels and line endings are preserved.
Hard gates on the original generated-source and private p-code SHA. OFF by default.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
from pathlib import Path
import re
import sys

from patch_codsp_x87_fld32 import OLD_RE, SOURCE_HEADER, PCODE_SHA256

SOURCE_SHA256 = "7532b4222eb40b37c5e8bb5491babe3250756f263f5cc2e9b73f2fba7501bdca"
PC_SITES = (
    0x004d82d4, 0x004d82db, 0x004d82f1, 0x004d845b, 0x004d8471,
    0x004d94f4, 0x004d94fb, 0x004d9505, 0x004d950a, 0x004d9511,
)
MARKER = "CODSP_X87_FLD32_VIS"
NEW_RE = re.compile(
    r"codsp_x87_fld32_normal\((rd\(T\+\d+,4\))\) /\* " + MARKER + r" \*/"
)
ORIGINAL_INSTRUCTION = re.compile(r"L_[0-9a-f]+:")


def verify_original_pcode(path: Path) -> None:
    """No source edit unless every audited PC has exactly one 4->10 p-code op."""
    if sha256(path.read_bytes()).hexdigest() != PCODE_SHA256:
        raise ValueError("Unknown CoDSP 1.5 p-code hash")
    # Parsing a large private p-code file is only needed before applying.
    from pcode2c import parse

    instructions, _, _ = parse(path)
    by_pc = {pc: ops for pc, _, ops in instructions if pc in PC_SITES}
    if len(by_pc) != len(PC_SITES):
        raise ValueError("Missing exact original visibility PC")
    for pc in PC_SITES:
        ops = by_pc[pc]
        converters = [(o, inputs) for mn, o, inputs in ops if mn == "FLOAT2FLOAT"]
        if not (
            len(converters) == 1
            and converters[0][0] is not None
            and converters[0][0][2] == 10
            and len(converters[0][1]) == 1
            and converters[0][1][0] is not None
            and converters[0][1][0][0] == "u"
            and converters[0][1][0][2] == 4
            and any(mn == "LOAD" for mn, _, _ in ops)
        ):
            raise ValueError(f"Unexpected conversion or guest memory at {pc:08x}")


def transform(source: bytes, *, apply: bool) -> bytes:
    if not (source.startswith((SOURCE_HEADER + "\n").encode())
            or source.startswith((SOURCE_HEADER + "\r\n").encode())):
        raise ValueError("Unknown generated CoDSP source header")
    if (source.count(b"\r\n") not in (0, source.count(b"\n"))
            or source.count(b"\r") != source.count(b"\r\n")):
        raise ValueError("Mixed generated-C line endings")
    lines = source.decode("utf8").splitlines(keepends=True)
    labels = {}
    for i, line in enumerate(lines):
        tag = line.strip()
        if ORIGINAL_INSTRUCTION.fullmatch(tag):
            if tag in labels:
                raise ValueError("Duplicate original instruction label")
            labels[tag] = i
    changed = list(lines)
    for pc in PC_SITES:
        idx = labels.get(f"L_{pc:x}:")
        if idx is None:
            raise ValueError(f"Missing original instruction {pc:08x}")
        end = next((i for i in range(idx + 1, len(lines))
                    if ORIGINAL_INSTRUCTION.fullmatch(lines[i].strip())), len(lines))
        region = lines[idx + 1:end]
        pc_write = f" wr(guest_regs+0x10ac,4,(u128)0x{pc:x}ULL);"
        if sum(line.rstrip("\r\n") == pc_write for line in region) != 1:
            raise ValueError(f"Missing expected guest PC write at {pc:08x}")
        pattern = OLD_RE if apply else NEW_RE
        hits = [i for i in range(idx + 1, end) if pattern.search(lines[i])]
        if len(hits) != 1 or len(pattern.findall(lines[hits[0]])) != 1:
            raise ValueError(f"Expected exactly one conversion at {pc:08x}")
        i = hits[0]
        if apply:
            changed[i] = OLD_RE.sub(
                lambda m: f"codsp_x87_fld32_normal({m[1]}) /* {MARKER} */",
                lines[i], count=1,
            )
        else:
            changed[i] = NEW_RE.sub(
                lambda m: f"d2f((f2d({m[1]},4)),10)", lines[i], count=1,
            )
    output = "".join(changed).encode("utf8")
    if output.count(MARKER.encode()) != (len(PC_SITES) if apply else 0):
        raise ValueError("Incomplete patch or extra markers")
    if len(source.splitlines()) != len(output.splitlines()):
        raise ValueError("Source-to-guest line-number mapping changed")
    return output


def transform_file(source: bytes, *, apply: bool) -> bytes:
    markers = source.count(MARKER.encode())
    if apply:
        if sha256(source).hexdigest() != SOURCE_SHA256 or markers:
            raise ValueError("Unrecognized/partially patched CoDSP p8")
    elif markers == 0:
        # Other experimental source patches are not ours to restore.
        return source
    elif markers != len(PC_SITES):
        raise ValueError("Mixed or partial visibility FLD32 markers")
    result = transform(source, apply=apply)
    if not apply and sha256(result).hexdigest() != SOURCE_SHA256:
        raise ValueError("Cannot restore original CoDSP p8 byte-for-byte")
    return result


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("source", type=Path)
    ap.add_argument("pcode", type=Path)
    flags = ap.add_mutually_exclusive_group(required=True)
    flags.add_argument("--apply", action="store_true")
    flags.add_argument("--restore", action="store_true")
    args = ap.parse_args(argv)
    if args.source.name != "codsp_recomp_p8.c":
        ap.error("Visibility FLD32 requires CoDSP p8 source")
    if sha256(args.pcode.read_bytes()).hexdigest() != PCODE_SHA256:
        ap.error("Unknown CoDSP 1.5 p-code hash")
    before = args.source.read_bytes()
    if args.apply:
        verify_original_pcode(args.pcode)
    after = transform_file(before, apply=args.apply)
    if before != after:
        stage = args.source.with_name(args.source.name + ".visfld32.tmp")
        if stage.exists():
            raise ValueError("Staging path already exists")
        try:
            stage.write_bytes(after)
            if stage.read_bytes() != after:
                raise IOError("Staged bytes mismatched")
            stage.replace(args.source)
        finally:
            if stage.exists():
                stage.unlink()
    print("ARM64_VIS_FLD32", "apply" if args.apply else "restore",
          "pcs", len(PC_SITES), "changed", before != after,
          "sha256", sha256(after).hexdigest())


if __name__ == "__main__":
    main()
