#!/usr/bin/env python3
"""Attribute archived TECNO *native PC samples* to original p-code instruction labels.

Use the exact installed native ELF Build ID and archived generated source
line positions. Fail closed if the first 12 guest-PC aggregates disagree
with the independently archived attribution, to reject stale generated
source or symbol mismatches. Emit only aggregate operator PRESENCE
categories; neither one sample nor one source line measures how much time
its individual p-code micro-ops take.

This is not a CPU profiling run, does not touch ADB, and must never
export unstripped ELF, original p-code, private C, raw perf.data or
an optimized gameplay binary to the public repository.
"""
from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
import json
import hashlib
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/"tools/recomp"))
from diagnostics.analyze_cfg_regions import verify_inputs
from diagnostics.benchmark_cfg_region import ndk_clang
from diagnostics.offline_dispatch_profile import (
    recorded_build_id,parse_elf_build_id,run_command
)
from diagnostics.prioritize_profiled_cpu import PINNED_ELF_BUILD_ID,PROFILE_TARGETS
from pcode2c import parse
from resolve_guest_samples import symbolize_native_pcs,resolve_native_samples


def opcode_presence(operations:list)->tuple[str,...]:
    categories=set()
    for mnemonic,out,inputs in operations:
        if mnemonic.startswith("FLOAT") or mnemonic in ("ROUND","TRUNC","INT2FLOAT"):
            categories.add("float_pcode")
        if mnemonic=="POPCOUNT":categories.add("parity_pcode")
        if mnemonic=="LOAD" or mnemonic=="STORE":
            categories.add("guest_mem_pcode")
        if any(v and v[0]=="m" for v in ([out] if out else [])+list(inputs)) and mnemonic not in ("BRANCH","CBRANCH","CALL"):
            categories.add("guest_mem_pcode")
        for v in ([out] if out else [])+list(inputs):
            if v and v[0]=="r" and v[1]<0x1200 and v[1]+v[2]>0x1000:
                categories.add("x87_state_pcode")
        if out and out[0]=="r" and any(out[1]<=p<out[1]+out[2]
                                        for p in (0x200,0x202,0x206,0x207,0x20b)):
            categories.add("flags_written_pcode")
        if mnemonic in ("INT_MULT","INT_DIV","INT_SDIV","INT_REM","INT_SREM"):
            categories.add("integer_math_pcode")
    return tuple(sorted(categories))


def categorize_guest_label_samples(
    rows:list[dict], indexed:dict[int,list], selections:set[int]|None=None
)->dict:
    selections=selections if selections is not None else set(indexed)
    total=owned=0
    group=Counter()
    exclusive=Counter()
    top=[]
    missed=[]
    for row in rows:
        if row["module"]!="codsp":
            continue
        samples=row["samples"]
        pc=int(row["guest_pc"],16)
        if type(samples) is not int or samples<=0:
            raise ValueError("negative/invalid resolved native sample count")
        total+=samples
        if pc not in selections:
            continue
        ops=indexed.get(pc)
        if ops is None:
            missed.append(f"0x{pc:08x}")
            continue
        owned+=samples
        markers=opcode_presence(ops)
        for item in markers:group[item]+=samples
        bucket=("x87-associated" if "x87_state_pcode" in markers
                else "memory-associated" if "guest_mem_pcode" in markers
                else "integer-other")
        exclusive[bucket]+=samples
        top.append({"guest_pc":f"0x{pc:08x}",
                    "native_samples":samples,
                    "pcode_categories":list(markers)})
    if missed:
        raise ValueError("Sampled guest-PC labels outside exact original p-code")
    top.sort(key=lambda row:(-row["native_samples"],row["guest_pc"]))
    if sum(exclusive.values())!=owned:
        raise AssertionError("exclusive sample buckets do not partition owned labels")
    return {
        "all_codsp_guest_PC_resolved_samples":total,
        "selected_original_function_guest_PC_samples":owned,
        "exclusive_instruction_annotation_buckets":dict(exclusive),
        "overlapping_pcode_presence_sample_counts":dict(group),
        "top_sampled_original_instruction_labels":top[:20],
        "warning":"Samples are HOST execution PCs attributed through source-line labels; a label with FLOAT, POPCOUNT or LOAD does not prove that micro-op consumed the samples. Categories overlap and are not CPU time.",
    }


def main(argv=None)->int:
    ap=argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--slot",choices=("v1","v2"),required=True)
    ap.add_argument("--out",type=Path,required=True)
    args=ap.parse_args(argv)
    try:
        root=(ROOT/".local/profiles").resolve()
        out=args.out.resolve()
        if not out.is_relative_to(root) or out==root or out.exists() or out.suffix!=".json":
            raise ValueError("new ignored JSON path required")
        pcode=ROOT/"recomp_out/codsp.pcode"
        code_map=ROOT/"recomp_out/codsp_function_map_v2.json"
        verify_inputs(pcode,code_map)
        cc,_,_=ndk_clang()
        ndk=cc.parents[5]
        elf=root/"strategy_spawn_cpu_v1_symbols/libmain.so"
        elf_id=parse_elf_build_id(
            run_command([str(cc.parent/"llvm-readelf.exe"),"-n",str(elf)]))
        if elf_id!=PINNED_ELF_BUILD_ID:
            raise ValueError("native ELF Build ID unexpected")
        sys.path.insert(0,str(ndk/"simpleperf"))
        from simpleperf_report_lib import ReportLib
        perf=root/f"strategy_spawn_cpu_{args.slot}.perf.data"
        archive=json.loads(
            (root/f"strategy_spawn_cpu_{args.slot}_analysis.json").read_text(encoding="utf-8"))
        lib=ReportLib()
        lib.SetRecordFile(str(perf))
        if recorded_build_id(lib.GetAllBuildIds())!=elf_id:
            raise ValueError("native ELF Build ID mismatch in raw Simpleperf")
        native=Counter()
        total=0
        while lib.GetNextSample() is not None:
            total+=1
            symbol=lib.GetSymbolOfCurrentSample()
            if symbol and Path(symbol.dso_name).name=="libmain.so":
                native[int(symbol.vaddr_in_file)]+=1
        if (total!=archive["total_cpu_samples"] or
            sum(native.values())!=archive["libmain_cpu_samples"]):
            raise ValueError("raw samples diverge from archived count")
        generated=sorted((ROOT/"recomp_out").glob("*_recomp*.c"))
        maps=[json.loads((ROOT/"recomp_out"/f"{mod}_function_map_v2.json").read_text(encoding="utf-8"))
              for mod in ("codsp","cgamex86","gamex86","uix86")]
        if not generated or len(maps)!=4:
            raise ValueError("original native-source and Ghidra maps missing")
        rows=symbolize_native_pcs(
            sorted(native.items()),elf,cc.parent/"llvm-addr2line.exe")
        result=resolve_native_samples(rows,generated,maps,top=100000)
        prior=archive["resolved_guest"]
        # Compare every previously published top pair; source line table
        # drift must NOT masquerade as a new operator hotspot.
        for key in ("guest_label_resolved_samples","unique_ghidra_body_samples",
                    "unresolved_source_samples","unowned_ghidra_body_samples"):
            if result[key]!=prior[key]:
                raise ValueError(f"native-source attribution drift in {key}")
        for kind in ("top_guest_instruction_labels","top_body_function_samples"):
            earlier=prior[kind]
            if result[kind][:len(earlier)]!=earlier:
                raise ValueError(f"historical attribution top rows changed for {kind}")
        instructions,_,_=parse(pcode)
        by_pc={pc:ops for pc,_sz,ops in instructions}
        bodies=json.loads(code_map.read_text(encoding="utf-8"))
        from region_cfg import extract_function
        targets=set()
        for entry in PROFILE_TARGETS:
            owned,_b,_issues=extract_function(instructions,bodies,entry)
            targets.update(pc for pc,_n,_ops in owned)
        by_label=categorize_guest_label_samples(
            result["top_guest_instruction_labels"],by_pc,targets)
        output={
            "schema":"phase15-archived-TECNO-native-PC-operator-presence-v1",
            "slot":args.slot,"exact_unstripped_ELF_build_ID":elf_id,
            "raw_simpleperf_sha256":hashlib.sha256(perf.read_bytes()).hexdigest(),
            "raw_samples":total,"raw_libmain_samples":sum(native.values()),
            "source_label_attribution_fingerprint_matches_archive":True,
            "selected_targets":sorted(f"0x{x:08x}" for x in PROFILE_TARGETS),
            "classification":by_label,
            "not_a_cpu_time_breakdown":True,
            "not_a_millisecond_or_FPS_speedup_claim":True,
        }
        out.write_text(json.dumps(output,indent=2)+"\n",encoding="utf-8")
        print("PHASE15_NATIVE_TO_GUEST_PCODE_CLASSIFICATION_PASS",args.slot,
              "observations",by_label["selected_original_function_guest_PC_samples"],
              "categories",by_label["exclusive_instruction_annotation_buckets"],
              flush=True)
        return 0
    except (ValueError,OSError,RuntimeError,ImportError) as error:
        print("PHASE15_NATIVE_GUEST_CLASSIFICATION_REJECTED",
              error,file=sys.stderr,flush=True)
        return 2


if __name__=="__main__":
    raise SystemExit(main())
