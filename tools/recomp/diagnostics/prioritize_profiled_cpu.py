#!/usr/bin/env python3
"""Rank archived *physical TECNO* CPU targets with exact Simpleperf identity.

Strictly retrospective/offline; no ADB and no generated-game edits. Verify
BOTH raw Simpleperf captures, their exact recorded libmain.so Build IDs and
sample counts against archived summary files and one matching unstripped ELF,
then summarize two recordings and the ORIGINAL CoDSP p-code op mix.

Samples are statistical HOST instruction-PC observations, not guest
instruction executions, exclusive function times, CPU milliseconds per
function, or FPS. Ghidra B ownership of source-line labels is approximate.
Never estimate a speedup by adding overlapping inlined function samples.

Writes an address/aggregate-only report under ignored .local/profiles.
No PE bytes, guest-generated source, native stack traces or original code
are exported to Git.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/"tools/recomp"))
from diagnostics.analyze_cfg_regions import verify_inputs
from diagnostics.offline_dispatch_profile import (
    parse_elf_build_id, recorded_build_id, run_command
)
from diagnostics.benchmark_cfg_region import ndk_clang
from pcode2c import parse
from region_cfg import extract_function

PROFILE_SLOTS=("v1","v2")
PINNED_ELF_BUILD_ID="80dc3884c64e395f87d7975f200d34edccf648fd"
PROFILE_TARGETS={
    0x0041B8F0:"geometry_collision",
    0x004196F0:"geometry_collision",
    0x0047BD40:"state_structures",
    0x004D94C0:"visibility",
    0x004D8280:"visibility",
    0x004D8420:"visibility",
    0x004D6BC0:"visibility",
    0x0042B0A0:"integer_geometry_state",
}
RANGES_X87=(0x1000,0x1200)
ARCH_FLAGS=(0x200,0x202,0x206,0x207,0x20b)
FLOAT_OPS=frozenset((
    "FLOAT2FLOAT","INT2FLOAT","FLOAT2INT","FLOAT_ADD","FLOAT_SUB",
    "FLOAT_MULT","FLOAT_DIV","FLOAT_EQUAL","FLOAT_NOTEQUAL",
    "FLOAT_LESS","FLOAT_LESSEQUAL","FLOAT_NAN","FLOAT_NEG",
    "FLOAT_ABS","FLOAT_SQRT","FLOAT_CEIL","FLOAT_FLOOR",
    "FLOAT_ROUND","ROUND","TRUNC"
))


def profile_counts(analysis: dict) -> dict[int,int]:
    """Extract unique original CoDSP function-B labels only; never chunks."""
    records=analysis["resolved_guest"]["top_body_function_samples"]
    observed={}
    for item in records:
        if item["module"]!="codsp":
            continue
        pc=int(item["entry_va"],16)
        count=item["samples"]
        if pc in observed or type(count) is not int or count < 0:
            raise ValueError("ambiguous/negative original function entry samples")
        observed[pc]=count
    return observed


def compare_profiles(
    left: dict, right: dict,
    targets: dict[int,str] | None=None,
    *, reference_cpu_ms:float=38.895,
    target_cpu_ms:float=1000/60,
) -> dict:
    """Noncausal CPU share/upper-bound triage, not estimated optimization."""
    if not 0<target_cpu_ms<reference_cpu_ms:
        raise ValueError("reference CPU time must exceed target budget")
    targets=PROFILE_TARGETS if targets is None else targets
    if not targets or any(not isinstance(pc,int) or pc<0 for pc in targets):
        raise ValueError("target addresses must be valid original PCs")
    runs=(left,right)
    for analysis in runs:
        if analysis["total_cpu_samples"] <=0 or analysis["libmain_cpu_samples"]<=0:
            raise ValueError("empty profile")
        if analysis["libmain_cpu_samples"]>analysis["total_cpu_samples"]:
            raise ValueError("libmain samples exceed entire CPU profile")
        owned=analysis["resolved_guest"]
        if owned["native_samples_total"]!=analysis["libmain_cpu_samples"]:
            raise ValueError("Guest label population does not match native samples")
        if owned["unique_ghidra_body_samples"]>owned["guest_label_resolved_samples"]:
            raise ValueError("unique labels larger than all guest source labels")
    pc_counts=[profile_counts(analysis) for analysis in runs]
    rows=[]
    for pc,area in targets.items():
        counts=[observed.get(pc,0) for observed in pc_counts]
        # Counting missing target in a truncated top-N as 0 is not sound.
        # Require each chosen function appear in BOTH top-N analyses.
        if any(pc not in observed for observed in pc_counts):
            raise ValueError(f"required target missing from truncated summary: {pc:#x}")
        process_share=[100*c/run["total_cpu_samples"]
                       for c,run in zip(counts,runs)]
        libmain_share=[100*c/run["libmain_cpu_samples"]
                       for c,run in zip(counts,runs)]
        rows.append({
            "guest_original_entry":f"0x{pc:08x}",
            "area_hypothesis":area,
            "native_samples_A1":counts[0],"native_samples_A2":counts[1],
            "process_sample_pct_A1":round(process_share[0],3),
            "process_sample_pct_A2":round(process_share[1],3),
            "libmain_sample_pct_A1":round(libmain_share[0],3),
            "libmain_sample_pct_A2":round(libmain_share[1],3),
            "sample_rate_stability_ratio":round(
                min(process_share)/max(process_share),3) if max(process_share)>0 else 0,
            "priority_by_minimum_confirmed_sample_share_pct":
                round(min(process_share),3),
        })
    rows.sort(key=lambda x:(-x["priority_by_minimum_confirmed_sample_share_pct"],
                            x["guest_original_entry"]))
    group=Counter()
    for row in rows:
        group[row["area_hypothesis"]]+=1
    # These snapshots do NOT have an exclusive per-function time
    # decomposition. Report an observational sample SHARE, not CPU time.
    combined=[]
    for index,run in enumerate(runs):
        observed=pc_counts[index]
        samples=sum(observed[pc] for pc in targets)
        share=samples/run["total_cpu_samples"]
        combined.append({
            "capture":PROFILE_SLOTS[index],
            "sum_of_unique_B_label_samples":samples,
            "percent_of_all_process_samples":round(100*share,3),
            "illustrative_Amdahl_ceiling_if_these_sampled_contributions_were_exclusive":{
                "remaining_cpu_ms_per_frame_at_100pct_elimination":round(
                    reference_cpu_ms*(1-share),3),
                "CPU_only_FPS_ceiling_if_100pct_removed_and_CPU_bound":round(
                    1000/(reference_cpu_ms*(1-share)),2),
            },
        })
    needed=100*(reference_cpu_ms-target_cpu_ms)/reference_cpu_ms
    return {
        "schema":"callofrecomp-phase15-archived-physical-CPU-priority-v1",
        "captures_process_samples":[run["total_cpu_samples"] for run in runs],
        "captures_libmain_samples":[run["libmain_cpu_samples"] for run in runs],
        "reference_cpu_ms_per_frame_from_separate_3D_window":reference_cpu_ms,
        "goal_cpu_ms_per_frame_at_60fps":round(target_cpu_ms,4),
        "overall_required_CPU_ms_reduction_pct_if_CPU_bound":round(needed,3),
        "target_original_functions":len(targets),
        "ranked_original_function_sample_targets":rows,
        "selected_8_function_combined_sample_share":combined,
        "group_function_counts":dict(group),
        "warning":"These are approximate weighted host PC samples attributed via optimized line tables and Ghidra B ranges, NOT exclusive CPU time, call counts or per-frame measurements. Amdahl arithmetic is only a hypothetical ceiling, not expected FPS. Do not compare across different build IDs or treat residual unlabeled samples as zero cost.",
    }


def function_complexity(instructions:list,mapping:dict,pc:int)->dict:
    body,_ranges,_warnings=extract_function(instructions,mapping,pc)
    ops=Counter()
    x87_insns=0
    flags=0
    read_write=Counter()
    potential_alias=0
    for _addr,_width,operations in body:
        this_x87=False
        for mnemonic,out,inputs in operations:
            ops[mnemonic]+=1
            if mnemonic in {"LOAD","STORE"}:read_write[mnemonic]+=1
            for is_output,varnode in [(True,out),*[(False,v) for v in inputs]]:
                if varnode is None:continue
                space,offset,width=varnode
                if space=="m" and mnemonic not in {"BRANCH","CBRANCH","CALL"}:
                    potential_alias+=1
                if space=="r":
                    if offset<RANGES_X87[1] and offset+width>RANGES_X87[0]:
                        this_x87=True
                    if is_output and any(offset<=f<offset+width for f in ARCH_FLAGS):
                        flags+=1
        x87_insns+=this_x87
    return {
        "original_x86_instructions":len(body),
        "pcode_micro_ops":sum(ops.values()),
        "pcode_mem_LOAD_ops":read_write["LOAD"],
        "pcode_mem_STORE_ops":read_write["STORE"],
        "pcode_direct_m_data_references":potential_alias,
        "pcode_x87_touching_original_insns":x87_insns,
        "pcode_FLOAT_operators":sum(v for k,v in ops.items() if k in FLOAT_OPS),
        "pcode_POPCOUNT_ops":ops["POPCOUNT"],
        "pcode_arch_flag_write_microops":flags,
        "pcode_INT_MULT_ops":ops["INT_MULT"],
        "pcode_INT_ADD_ops":ops["INT_ADD"],
        "integer_only_no_x87_body":x87_insns==0,
        "all_results_are_STATIC_opcode_counts":True,
    }


def _real_raw_samples(perf:Path,ndk:Path,expected_id:str)->tuple[int,int,str]:
    sys.path.insert(0,str(ndk/"simpleperf"))
    from simpleperf_report_lib import ReportLib
    engine=ReportLib()
    engine.SetRecordFile(str(perf))
    bid=recorded_build_id(engine.GetAllBuildIds())
    if bid!=expected_id:
        raise ValueError("raw perf Build ID is NOT the pinned unstripped ELF")
    total=host=0
    while engine.GetNextSample() is not None:
        total+=1
        symbol=engine.GetSymbolOfCurrentSample()
        if symbol and Path(symbol.dso_name).name=="libmain.so":
            host+=1
    return total,host,bid


def main(argv=None)->int:
    ap=argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--profiles",type=Path,default=ROOT/".local/profiles")
    ap.add_argument("--out",required=True,type=Path)
    args=ap.parse_args(argv)
    try:
        source=args.profiles.resolve(strict=True)
        if source!=(ROOT/".local/profiles").resolve():
            raise ValueError("only original archived local profile directory allowed")
        out=args.out.resolve()
        if not out.is_relative_to(source) or out==source or out.exists():
            raise ValueError("output must be NEW and inside ignored .local/profiles")
        pcod=ROOT/"recomp_out/codsp.pcode"
        mapping=ROOT/"recomp_out/codsp_function_map_v2.json"
        verify_inputs(pcod,mapping)
        _compiler,_size,_dump=ndk_clang()
        ndk=_compiler.parents[5]
        readelf=_compiler.parent/"llvm-readelf.exe"
        elf=source/"strategy_spawn_cpu_v1_symbols/libmain.so"
        elf_id=parse_elf_build_id(run_command([str(readelf),"-n",str(elf)]))
        if elf_id!=PINNED_ELF_BUILD_ID:
            raise ValueError("installed unstripped ELF not the profiled code build")
        analyses=[]
        capture_fingerprints=[]
        for slot in PROFILE_SLOTS:
            perf=source/f"strategy_spawn_cpu_{slot}.perf.data"
            report=source/f"strategy_spawn_cpu_{slot}_analysis.json"
            summary=json.loads(report.read_text(encoding="utf-8"))
            raw_total,raw_libmain,raw_id=_real_raw_samples(perf,ndk,elf_id)
            if (summary["total_cpu_samples"]!=raw_total or
                    summary["libmain_cpu_samples"]!=raw_libmain):
                raise ValueError("archived JSON sample counts do not match raw Simpleperf")
            analyses.append(summary)
            capture_fingerprints.append({
                "capture":slot,
                "raw_perf_SHA256":hashlib.sha256(perf.read_bytes()).hexdigest(),
                "raw_perf_size":perf.stat().st_size,
                "raw_observed_total_process_samples":raw_total,
                "raw_observed_libmain_samples":raw_libmain,
                "readelf_native_build_ID":raw_id,
            })
        if capture_fingerprints[0]["raw_perf_SHA256"]==capture_fingerprints[1]["raw_perf_SHA256"]:
            raise ValueError("expected TWO distinct archived Simpleperf captures")
        report=compare_profiles(*analyses)
        rows={int(item["guest_original_entry"],16):item
              for item in report["ranked_original_function_sample_targets"]}
        all_insns,_,_=parse(pcod)
        gmap=json.loads(mapping.read_text(encoding="utf-8"))
        for pc in PROFILE_TARGETS:
            rows[pc]["original_pcode_body"]=function_complexity(all_insns,gmap,pc)
        report["raw_Simpleperf_build_ID_proofs"]=capture_fingerprints
        report["exact_verified_native_ELF_build_ID"]=elf_id
        report["unstripped_native_ELF_SHA256"]=hashlib.sha256(elf.read_bytes()).hexdigest()
        report["pinning_guards"]="raw two capture Build IDs, sample totals, distinct raw SHA256, exact unstripped ELF, Ghidra B map/pcode SHA256"
        out.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
        print("PHASE15_ARCHIVED_TECNO_PROFILE_TRIAGE",
              report["captures_process_samples"],
              "targeted",len(rows),
              "min_target_share",
              min(x["percent_of_all_process_samples"] for x in report["selected_8_function_combined_sample_share"]),
              flush=True)
        for row in report["ranked_original_function_sample_targets"]:
            print("PROFILED_CPU",row["guest_original_entry"],
                  row["native_samples_A1"],row["native_samples_A2"],
                  "min_pct",row["priority_by_minimum_confirmed_sample_share_pct"],
                  "x87_insns",row["original_pcode_body"]["pcode_x87_touching_original_insns"],
                  "LOADS",row["original_pcode_body"]["pcode_mem_LOAD_ops"],
                  "STORES",row["original_pcode_body"]["pcode_mem_STORE_ops"],
                  flush=True)
        return 0
    except (ValueError,RuntimeError,ImportError,OSError) as e:
        print("PHASE15_ARCHIVED_PROFILE_REJECTED",e,file=sys.stderr)
        return 2


if __name__=="__main__":
    raise SystemExit(main())
