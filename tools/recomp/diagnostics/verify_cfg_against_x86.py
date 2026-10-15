"""Independent x86 instruction/edge verifier for phase14 CFG recovery.

This validator uses REAL CoDSP.exe bytes decoded by Capstone, not the Ghidra
p-code semantics for its x86-side observations. It independently checks
instruction boundaries and explicit call/jump destinations where known.
It is NOT an oracle for state transitions, x87 or memory side effects.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/recomp"))
from pcode2c import parse  # noqa: E402
from region_cfg import extract_function, micro_exits  # noqa: E402
from diagnostics.analyze_cfg_regions import (
    HOT_FUNCTIONS, PCODE_SHA256, MAP_SHA256, sha256_file,
)  # noqa: E402

EXPECTED_PE_SHA256 = "c755c7da411c87039ade462a2299402c3c4ca5c4fc4f1ae5cea6e25b05c69f47"


@dataclass(frozen=True)
class X86Instruction:
    pc: int
    size: int
    control: str
    target: int | None = None


def check_edges(instructions: list, decoded: list[X86Instruction]) -> dict:
    """Pure structural crosscheck. Never guesses over missing p-code bytes."""
    by_pc = {x.pc: x for x in decoded}
    if len(by_pc) != len(decoded):
        raise ValueError("duplicate independently decoded x86 PC")
    counts = Counter()
    mismatches = []
    for pc, length, ops in instructions:
        ins = by_pc.get(pc)
        if ins is None:
            counts["missing_x86_decode"] += 1
            mismatches.append((pc, "missing_x86_decode"))
            continue
        if ins.size != length:
            counts["instruction_length_mismatch"] += 1
            mismatches.append((pc, "instruction_length_mismatch"))
            continue
        counts["boundaries_matching"] += 1
        if not ops:
            counts["unverifiable_missing_pcode"] += 1
            continue
        exits, issues = micro_exits(ops, pc + length)
        pairs = {(e.kind, e.target) for e in exits}
        expected = {
            "conditional": ("conditional_taken", ins.target),
            "direct_jump": ("direct_jump", ins.target),
            "direct_call": ("direct_call", ins.target),
            "indirect_jump": ("dynamic_branchind", None),
            "indirect_call": ("dynamic_callind", None),
            "return": ("dynamic_return", None),
        }
        if ins.control in expected:
            counts["x86_control_instructions"] += 1
            expected_exit = expected[ins.control]
            if expected_exit not in pairs:
                counts["control_target_mismatch"] += 1
                mismatches.append((pc, "control_target_mismatch"))
            else:
                counts["control_targets_matching"] += 1
        elif ins.control == "normal":
            if any(e.kind in {"direct_jump", "direct_call", "conditional_taken",
                              "dynamic_branchind", "dynamic_callind", "dynamic_return"}
                   for e in exits):
                counts["unexpected_pcode_control"] += 1
                mismatches.append((pc, "unexpected_pcode_control"))
            else:
                counts["ordinary_instructions_matching"] += 1
        else:
            counts["x86_control_unclassified"] += 1
            mismatches.append((pc, "x86_control_unclassified"))
        counts["pcode_micro_warnings"] += len(issues)
    if len(instructions) != len(decoded):
        counts["decoded_count_mismatch"] = abs(len(instructions) - len(decoded))
    return {
        "instructions": len(instructions),
        "counts": dict(sorted(counts.items())),
        "mismatch_count": len(mismatches),
        "mismatch_samples": [
            {"pc": f"0x{pc:08x}", "reason": reason}
            for pc, reason in mismatches[:40]
        ],
        "unverified_pcode_insns": counts["unverifiable_missing_pcode"],
        "all_edges_agree_where_decoded": len(mismatches) == 0,
        "not_validating": [
            "actual x86 register/memory/flags or x87 equivalence",
            "indirect dynamic targets",
            "nested call-return behavior",
            "thread or asynchronous guest events",
        ],
    }


def decode_pe_instructions(pe_file: Path, body: list) -> list[X86Instruction]:
    """Capstone disassembles original PE bytes one address at a time."""
    import pefile
    from capstone import Cs, CS_ARCH_X86, CS_MODE_32
    from capstone import CS_GRP_JUMP, CS_GRP_CALL, CS_GRP_RET
    from capstone.x86_const import X86_OP_IMM

    pe = pefile.PE(str(pe_file), fast_load=True)
    if pe.OPTIONAL_HEADER.ImageBase != 0x400000:
        raise ValueError("Unexpected CoDSP x86 image base")
    md = Cs(CS_ARCH_X86, CS_MODE_32)
    md.detail = True
    out = []
    for pc, length, _ops in body:
        code = pe.get_data(pc - 0x400000, length)
        decoded = list(md.disasm(code, pc, count=1)) if len(code) == length else []
        if len(decoded) != 1:
            # An independent decoder failure must be counted explicitly.
            continue
        ins = decoded[0]
        group = (
            "return" if ins.group(CS_GRP_RET) else
            "call" if ins.group(CS_GRP_CALL) else
            "jump" if ins.group(CS_GRP_JUMP) else "normal"
        )
        immediate = (
            bool(ins.operands) and ins.operands[0].type == X86_OP_IMM
        )
        target = int(ins.operands[0].imm) & 0xffffffff if immediate else None
        if group == "call":
            control = "direct_call" if immediate else "indirect_call"
        elif group == "jump":
            if immediate:
                control = "direct_jump" if ins.mnemonic.startswith("jmp") else "conditional"
            else:
                control = "indirect_jump"
        else:
            control = group
        out.append(X86Instruction(pc, ins.size, control, target))
    return out


def _verify_paths(pe: Path, pcode: Path, body_map: Path, out: Path) -> None:
    expected = {
        pe: ROOT / ".local/private",
        pcode: ROOT / "recomp_out",
        body_map: ROOT / "recomp_out",
    }
    for file, parent in expected.items():
        if not file.resolve(strict=True).is_relative_to(parent.resolve(strict=True)):
            raise ValueError("Original PE and Ghidra inputs must be in private local paths")
    root = (ROOT / ".local/profiles").resolve()
    output = out.resolve()
    if not output.is_relative_to(root) or output == root or output.exists():
        raise ValueError("Output must be a NEW report inside .local/profiles")
    if pe.name.lower() != "codsp.exe" or pcode.name != "codsp.pcode" or body_map.name != "codsp_function_map_v2.json":
        raise ValueError("Unexpected original 1.5 PE/pcode/map filename")
    if sha256_file(pe) != EXPECTED_PE_SHA256:
        raise ValueError("Original CoDSP.exe PE SHA-256 mismatch")
    if sha256_file(pcode) != PCODE_SHA256 or sha256_file(body_map) != MAP_SHA256:
        raise ValueError("Ghidra p-code/map SHA-256 mismatch")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pe", type=Path, required=True)
    ap.add_argument("--pcode", type=Path, default=ROOT / "recomp_out/codsp.pcode")
    ap.add_argument("--map", type=Path, default=ROOT / "recomp_out/codsp_function_map_v2.json")
    ap.add_argument("--entry", action="append", type=lambda x: int(x, 0))
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)
    try:
        _verify_paths(args.pe, args.pcode, args.map, args.out)
        insns, _, _ = parse(args.pcode)
        mapping = json.loads(args.map.read_text(encoding="utf-8"))
        entries = tuple(args.entry) if args.entry else HOT_FUNCTIONS
        result = {}
        for entry in entries:
            body, ranges, _ = extract_function(insns, mapping, entry)
            records = decode_pe_instructions(args.pe, body)
            check = check_edges(body, records)
            check["body_ranges"] = [[f"0x{a:08x}", f"0x{b:08x}"] for a, b in ranges]
            result[f"0x{entry:08x}"] = check
            print("X86_CFG", f"0x{entry:08x}", "boundaries",
                  check["counts"].get("boundaries_matching", 0),
                  "edges", check["counts"].get("control_targets_matching", 0),
                  "mismatches", check["mismatch_count"],
                  "missing_pcode", check["unverified_pcode_insns"], flush=True)
        report = {
            "schema": "callofrecomp-phase14-independent-x86-edges-v1",
            "source_sha256": {
                "pe": EXPECTED_PE_SHA256, "pcode": PCODE_SHA256,
                "ghidra_v2_map": MAP_SHA256,
            },
            "semantics": "capstone_original_PE_vs_pcode_CFG_structural_only",
            "functions": result,
        }
        args.out.parent.mkdir(exist_ok=True, parents=True)
        with args.out.open("x", encoding="utf-8", newline="\n") as sink:
            json.dump(report, sink, indent=2, sort_keys=True)
            sink.write("\n")
        print("PHASE14_INDEPENDENT_X86_REPORT", args.out, flush=True)
        return 0
    except (ValueError, OSError, ImportError) as error:
        ap.error(str(error))


if __name__ == "__main__":
    raise SystemExit(main())
