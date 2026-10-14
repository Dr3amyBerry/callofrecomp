#!/usr/bin/env python3
"""Audit one original CoDSP hot function without emitting proprietary p-code.

Uses Ghidra v2 disjoint body intervals and sample->guest-PC evidence.
No recompilation, binary patching, Android device access or runtime changes.
Output contains only counts, ranges and anonymized p-code operation categories.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path


class AuditError(ValueError):
    pass


def number(value: int | str) -> int:
    return int(value, 0) if isinstance(value, str) else int(value)


def function_metadata(data: dict, entry: int) -> tuple[list[tuple[int,int]], int, int]:
    functions = [f for f in data.get("functions", [])
                 if number(f["entry_va"]) == entry]
    if len(functions) != 1:
        raise AuditError("Expected exactly one function with this entry")
    fn = functions[0]
    if not fn.get("entry_in_translation"):
        raise AuditError("Entry is not covered by the generated translator")
    ranges = sorted((number(r["start_va"]), number(r["end_va_inclusive"]))
                    for r in data.get("ghidra_body_ranges", [])
                    if number(r["entry_va"]) == entry)
    if not ranges or any(lo > hi for lo, hi in ranges):
        raise AuditError("Missing or malformed Ghidra body intervals")
    if any(x[1] >= y[0] for x, y in zip(ranges, ranges[1:])):
        raise AuditError("Ghidra body intervals overlap")
    chunks = [c for c in data.get("chunks", [])
              if any(number(f["entry_va"]) == entry for f in
                     c.get("body_function_instruction_counts", []))]
    if not chunks:
        raise AuditError("Function has no generated chunks")
    if any(c.get("body_ambiguous_instructions", 0) for c in chunks):
        raise AuditError("Ambiguous body ownership: reject transformations")
    attributed = sum(next(f["instruction_count"] for f in
                          c["body_function_instruction_counts"]
                          if number(f["entry_va"]) == entry) for c in chunks)
    expected = fn.get("body_uniquely_owned_instruction_count")
    if expected is None or attributed != expected:
        raise AuditError("Function count contradicts chunk coverage")
    return ranges, attributed, len(chunks)


def varnode(text: str) -> tuple[str, int, int] | None:
    if text == "-":
        return None
    fields = text.split(":")
    if len(fields) != 3 or fields[0] not in {"r", "u", "c", "m"}:
        raise AuditError("Unexpected p-code varnode syntax")
    offset, size = int(fields[1], 16), int(fields[2])
    if size <= 0 or size > 32:
        raise AuditError("Unsupported varnode width")
    return fields[0], offset, size


def scan_pcode(path: Path, ranges: list[tuple[int,int]]) -> list[dict]:
    if not path.is_file():
        raise AuditError("Missing private p-code source")
    instructions = []
    active = False
    current = None
    interval = 0
    with path.open("r", encoding="utf-8") as stream:
        for line in stream:
            parts = line.split()
            if not parts:
                continue
            tag = parts[0]
            if tag == "I":
                if len(parts) != 3:
                    raise AuditError("Invalid p-code instruction line")
                address, length = int(parts[1]), int(parts[2])
                if length <= 0:
                    raise AuditError("Invalid x86 instruction length")
                while interval < len(ranges) and address > ranges[interval][1]:
                    interval += 1
                active = (interval < len(ranges) and
                          ranges[interval][0] <= address <= ranges[interval][1])
                if active:
                    if address + length - 1 > ranges[interval][1]:
                        raise AuditError("Instruction crosses Ghidra body interval")
                    current = {"pc": address, "size": length, "ops": []}
                    if instructions and address <= instructions[-1]["pc"]:
                        raise AuditError("Out-of-order or duplicate guest PC")
                    instructions.append(current)
            elif tag == "P" and active:
                if len(parts) < 3 or current is None:
                    raise AuditError("P-code operation outside an instruction")
                current["ops"].append((parts[1], varnode(parts[2]),
                                        [varnode(v) for v in parts[3:]]))
    if not instructions or any(not v["ops"] for v in instructions):
        raise AuditError("Body missing or contains empty instructions")
    return instructions


def op_metrics(op: tuple) -> Counter:
    mnemonic, out, inputs = op
    tags = Counter()
    tags["pcode_ops"] += 1
    if any(v is not None and v[0] == "r" for v in inputs):
        tags["reg_reads"] += 1
    if out is not None and out[0] == "r":
        tags["reg_writes"] += 1
    if mnemonic == "LOAD":
        tags["guest_loads"] += 1
    if mnemonic == "STORE":
        tags["guest_stores"] += 1
    if mnemonic in ("CALL","CALLIND","CALLOTHER","RETURN"):
        tags["calls_returns_userops"] += 1
    if mnemonic in ("BRANCH","CALL","CBRANCH","BRANCHIND","CALLIND","RETURN"):
        tags["control_transfers"] += 1
    if mnemonic in ("BRANCHIND","CALLIND","RETURN"):
        tags["indirect_exits"] += 1
    if mnemonic == "CBRANCH":
        tags["conditional_branches"] += 1
    if mnemonic.startswith("FLOAT") or mnemonic in ("ROUND","INT2FLOAT","TRUNC"):
        tags["floating_ops"] += 1
    if mnemonic not in ("LOAD","STORE") and any(
            v is not None and v[0] == "m" for v in ([out]+inputs)):
        tags["direct_guest_memory"] += 1
    return tags


def _windows(instructions: list[dict], weights: Counter, width: int) -> list[dict]:
    windows = []
    for i in range(0, max(len(instructions)-width+1, 0), width):
        items = instructions[i:i+width]
        if any(items[k]["pc"] + items[k]["size"] != items[k+1]["pc"]
               for k in range(len(items)-1)):
            continue
        flags = Counter()
        for insn in items:
            for op in insn["ops"]:
                flags.update(op_metrics(op))
        windows.append({
            "start_pc": hex(items[0]["pc"]),
            "end_pc": hex(items[-1]["pc"]),
            "samples_in_top_sites": sum(weights[ins["pc"]] for ins in items),
            "guest_instructions": len(items),
            "operation_categories": dict(flags),
            "has_memory_write": flags["guest_stores"] != 0 or
                                flags["direct_guest_memory"] != 0,
            "has_call_or_indirect_exit": flags["calls_returns_userops"] != 0,
            "safe_for_register_hoist": False,
        })
    return sorted(windows, key=lambda d:(-d["samples_in_top_sites"],
                                        number(d["start_pc"])))[:12]


def audit(map_data: dict, instructions: list[dict], sample_data: dict,
          entry: int) -> dict:
    ranges, expected, chunks = function_metadata(map_data,entry)
    if len(instructions) != expected:
        raise AuditError(f"Expected {expected} body instructions, found {len(instructions)}")
    covered = {i["pc"] for i in instructions}
    weights = Counter()
    seen_native_pcs = set()
    for record in sample_data.get("top", []):
        n = number(record["native_pc"])
        if n in seen_native_pcs:
            raise AuditError("Repeated sampled native PC")
        seen_native_pcs.add(n)
        pc = number(record["guest_pc"])
        if pc in covered:
            weights[pc] += int(record["weight"])
    flags=Counter()
    mnemonics=Counter()
    arch_read=Counter()
    arch_write=Counter()
    for ins in instructions:
        for op in ins["ops"]:
            mn,out,inputs=op
            flags.update(op_metrics(op))
            mnemonics[mn] += 1
            for x in inputs:
                if x is not None and x[0] == "r":
                    arch_read[f"0x{x[1]:x}:{x[2]}"] += 1
            if out is not None and out[0] == "r":
                arch_write[f"0x{out[1]:x}:{out[2]}"] += 1
    multi_entry_chunks = []
    for c in map_data["chunks"]:
        if any(number(f["entry_va"])==entry for f in
               c.get("body_function_instruction_counts",[])):
            multi_entry_chunks.append({
                "chunk_index": c["index"],
                "multiple_entries": len(c.get("function_entries_in_chunk", [])) > 1,
                "entry_count": len(c.get("function_entries_in_chunk", [])),
                "body_ambiguity": c.get("body_ambiguous_instructions",0)
            })
    return {
        "entry":hex(entry),
        "ranges_inclusive":[[hex(a),hex(b)] for a,b in ranges],
        "original_instructions":len(instructions),
        "generated_chunks_touching_body":chunks,
        "chunk_entry_risks":multi_entry_chunks,
        "operation_categories":dict(flags),
        "most_common_pcode_mnemonics":mnemonics.most_common(12),
        "most_accessed_arch_registers":{
            "read":arch_read.most_common(10),"written":arch_write.most_common(10)},
        "samples_in_top_native_sites_only":sum(weights.values()),
        "top_native_sites_input_count":len(sample_data.get("top", [])),
        "total_original_profile_samples":sample_data.get("samples"),
        "hot_evidence_windows_8_contiguous":_windows(instructions,weights,8),
        "decision":"Audit only; NO safe register-cache patch proven. Retain current game binary.",
        "caveat":"Top 100 native sample sites are truncated selection, not complete dynamic frequency. Shared chunks, indirect exits, memory aliasing and observable flags require proof before hoisting."
    }


def main()->int:
    ap=argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pcode",required=True,type=Path)
    ap.add_argument("--map",required=True,type=Path)
    ap.add_argument("--sample-sites",required=True,type=Path)
    ap.add_argument("--entry",default="0x41b8f0")
    ap.add_argument("--out",required=True,type=Path)
    args=ap.parse_args()
    if args.out.exists():
        ap.error("Refuse overwrite")
    map_data=json.loads(args.map.read_text("utf8"))
    sample_data=json.loads(args.sample_sites.read_text("utf8"))
    entry=number(args.entry)
    ranges,_,_=function_metadata(map_data,entry)
    insns=scan_pcode(args.pcode,ranges)
    result=audit(map_data,insns,sample_data,entry)
    # Do not put raw guest instructions, sampled native PCs or copyrighted
    # game code in this output. Private input paths are not serialized.
    result["pcode_sha256"]=hashlib.sha256(args.pcode.read_bytes()).hexdigest()
    result["map_sha256"]=hashlib.sha256(args.map.read_bytes()).hexdigest()
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,indent=2)+"\n",encoding="utf8")
    print(json.dumps(result,indent=2))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
