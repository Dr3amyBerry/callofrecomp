"""Phase14C: offline ORIGINAL-CFG-region host A/B + AArch64 compilation trial.

Hashes pin user's local CoDSP originals. All source/object/DLL outputs remain
under new ignored .local/profiles subdirectory. NO Android app or repo binaries
are modified. Guest memory for A/B is a 64KiB address-folded lab model shared
by A and B; it is NOT a whole-game x86 state oracle.
"""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
from pathlib import Path
import random
import re
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/"tools/recomp"))
from pcode2c import parse
from cfg_region_lab import select_block,generate_region_c,cache_candidates
from diagnostics.analyze_cfg_regions import verify_inputs

R_BYTES=0x2000
MEM_BYTES=65536
CASE_MEMORY=0x14c92
REGION_PCODE="recomp_out/codsp.pcode"
REGION_MAP="recomp_out/codsp_function_map_v2.json"


def run(command: list[str], timeout:int=180) -> str:
    p=subprocess.run(command,timeout=timeout,capture_output=True,text=True)
    if p.returncode:
        raise RuntimeError(f"Failed command {command[:4]}: {p.stderr[-1500:]}")
    return p.stdout


def ndk_clang() -> tuple[Path,Path,Path]:
    candidates=sorted((Path.home()/"AppData/Local/Android/Sdk/ndk").glob(
        "*/toolchains/llvm/prebuilt/windows-x86_64/bin/clang.exe"),
        reverse=True)
    for compiler in candidates:
        binpath=compiler.parent
        size=binpath/"llvm-size.exe"
        objdump=binpath/"llvm-objdump.exe"
        if size.is_file() and objdump.is_file():
            return compiler,size,objdump
    raise RuntimeError("Android NDK Clang/llvm-size/llvm-objdump not installed")


def compile_host(source:Path, dll:Path) -> None:
    compiler=shutil.which("clang")
    if not compiler:raise RuntimeError("Host LLVM-MinGW clang unavailable")
    run([compiler,"-shared","-O1","-ffp-contract=off","-std=c11",
         "-I",str(ROOT/"tools/recomp"),str(source),"-o",str(dll)],timeout=180)


def compile_arm(source:Path, obj:Path, compiler:Path,
                opt:str="-O1") -> None:
    run([str(compiler),"--target=aarch64-linux-android26","-c","-fPIC",
         opt,"-ffp-contract=off","-std=c11",
         "-I",str(ROOT/"tools/recomp"),str(source),"-o",str(obj)],timeout=300)


def arm_stats(obj:Path, size:Path, dump:Path) -> dict:
    table=run([str(size),"-A",str(obj)])
    sections=re.search(r"^\s*\.text\s+(\d+)\s+",table,re.M)
    if not sections:raise RuntimeError("No ARM64 .text in candidate object")
    dis=run([str(dump),"-d",str(obj)])
    counts={"loads":0,"stores":0,"calls":0,"spills_not_measured":True}
    # LLVM-objdump presents one mnemonical instruction per text line.
    for line in dis.splitlines():
        m=re.search(r"^\s*[0-9a-f]+:\s+(?:[0-9a-f]{2}\s+){4}([a-z][a-z0-9_.]+)",line)
        if not m:
            m=re.search(r"^\s*[0-9a-f]+:\s+[0-9a-f]{8}\s+([a-z][a-z0-9_.]+)",line)
        if not m:continue
        op=m.group(1)
        if op.startswith(("ldr","ldp","ldur","ldrs","ldar","ldxr")):
            counts["loads"]+=2 if op.startswith("ldp") else 1
        elif op.startswith(("str","stp","stur","stlr","stxr")):
            counts["stores"]+=2 if op.startswith("stp") else 1
        if op in {"bl","blr"}:counts["calls"]+=1
    counts["text_bytes"]=int(sections.group(1))
    return counts


def open_library(file:Path):
    lib=ctypes.CDLL(str(file.resolve()))
    lib.execute_region.argtypes=(ctypes.c_void_p,ctypes.c_void_p,ctypes.c_uint32)
    lib.execute_region.restype=None
    lib.result_pc.argtypes=()
    lib.result_pc.restype=ctypes.c_uint32
    return lib


def differential(a,b,pcs:tuple[int,...],seeds:int,
                 *, fast_start_pc:int|None=None)->dict:
    count=0
    fast_cases=0
    delegated_cases=0
    exits=set()
    seed=CASE_MEMORY
    for pc in pcs:
        for index in range(seeds):
            rng=random.Random(seed ^ (pc*0x9e3779b1) ^ index)
            initial_reg=rng.randbytes(R_BYTES)
            initial_mem=rng.randbytes(MEM_BYTES)
            state_a=ctypes.create_string_buffer(initial_reg,R_BYTES)
            state_b=ctypes.create_string_buffer(initial_reg,R_BYTES)
            memory_a=ctypes.create_string_buffer(initial_mem,MEM_BYTES)
            memory_b=ctypes.create_string_buffer(initial_mem,MEM_BYTES)
            a.execute_region(state_a,memory_a,pc)
            end_a=a.result_pc()
            # Dedicated fast entry: every other original instruction PC goes
            # through unchanged A (simulated dispatcher delegation), not the
            # start-only lowering which intentionally does not handle it.
            delegate=fast_start_pc is not None and pc!=fast_start_pc
            if delegate:
                a.execute_region(state_b,memory_b,pc)
                end_b=a.result_pc()
                delegated_cases+=1
            else:
                b.execute_region(state_b,memory_b,pc)
                end_b=b.result_pc()
                fast_cases+=1

            if end_a!=end_b or state_a.raw!=state_b.raw or memory_a.raw!=memory_b.raw:
                raise RuntimeError(f"A/B R/RAM/PC mismatch at original PC 0x{pc:x}, seed {index}")
            exits.add(end_a)
            count+=1
    return {
        "cases":count, "every_pc_was_an_independent_entry":True,
        "state_compared":["R full 8192 bytes","simulated MEM full 65536 bytes","guest PC"],
        "unique_exit_pc_count":len(exits),
        "fast_entry_cases":fast_cases,
        "delegated_original_baseline_cases":delegated_cases,
        "fallback_is_host_simulation_not_android_integration":True,
        "all_equal":True,
        "original_x86_oracle":False,
    }


def main(argv:list[str]|None=None)->int:
    cli=argparse.ArgumentParser(description=__doc__.splitlines()[0])
    cli.add_argument("--entry",type=lambda x:int(x,0),required=True)
    cli.add_argument("--block",type=lambda x:int(x,0),required=True)
    cli.add_argument("--cache-count",type=int,action="append",
                     help="compare this number of disjoint cached regs; repeatable")
    cli.add_argument("--seeds",type=int,default=24)
    cli.add_argument("--entry-policy",choices=("all_entries","start_only"),
                     default="all_entries")
    cli.add_argument("--output",type=Path,required=True)
    args=cli.parse_args(argv)
    if not 1<=args.seeds<=256:
        cli.error("seeds per PC must be [1,256]")
    counts=sorted(set(args.cache_count or (2,4,6)))
    if any(not 1<=n<=12 for n in counts):
        cli.error("cache counts must be 1..12")
    out=args.output.resolve()
    private=(ROOT/".local/profiles").resolve()
    if not out.is_relative_to(private) or out==private or out.exists():
        cli.error("output must be a NEW folder under ignored .local/profiles")
    pcode=ROOT/REGION_PCODE
    mapping=ROOT/REGION_MAP
    p_hash,m_hash=verify_inputs(pcode,mapping)
    insns,_userops,_funcs=parse(pcode)
    body_map=json.loads(mapping.read_text(encoding="utf-8"))
    region=select_block(insns,body_map,args.entry,args.block)
    all_pcs=tuple(pc for pc,_sz,_ops in region.instructions)
    available=cache_candidates(region)
    print("CFG_REGION",f"0x{args.block:08x}","instructions",len(all_pcs),
          "disjoint_register_candidates",len(available),
          "selected_trials",counts,flush=True)
    out.mkdir(parents=True,exist_ok=False)
    ndk,size,dump=ndk_clang()
    specs=[]
    for count in [0]+counts:
        source,selected=generate_region_c(region,cache_count=count,
                                              entry_policy=args.entry_policy)
        folder=out/f"cache_{count}"
        folder.mkdir()
        src=folder/"private_region.c"
        dll=folder/"private_region.dll"
        obj=folder/"private_region_aarch64.o"
        src.write_text(source,encoding="utf-8")
        compile_host(src,dll)
        compile_arm(src,obj,ndk)
        stats=arm_stats(obj,size,dump)
        specs.append((count,selected,stats,open_library(dll)))
        print("ARM64_REGION",count,"cached_fields",len(selected),
              "text_bytes",stats["text_bytes"],
              "loads",stats["loads"],"stores",stats["stores"],
              "calls",stats["calls"],flush=True)
    base=specs[0]
    trials=[]
    for count,selected,stats,lib in specs[1:]:
        validated=differential(base[3],lib,all_pcs,args.seeds,
                               fast_start_pc=region.start
                               if args.entry_policy=="start_only" else None)
        compared={
            "requested_cache_count":count,
            "selected_cache_fields":len(selected),
            "cached_register_offsets_and_sizes":[[hex(v[1]),v[2]] for v in selected],
            "A_B_host_equivalence":validated,
            "A_ARM64":base[2],
            "B_ARM64":stats,
            "delta_static_text_bytes":stats["text_bytes"]-base[2]["text_bytes"],
            "delta_static_loads":stats["loads"]-base[2]["loads"],
            "delta_static_stores":stats["stores"]-base[2]["stores"],
            "chosen_for_production":False,
        }
        trials.append(compared)
        print("DIFF",count,"cases",validated["cases"],
              "ALL_R_RAM_PC_EQUAL",validated["all_equal"],
              "text_delta",compared["delta_static_text_bytes"],
              "load_delta",compared["delta_static_loads"],
              "store_delta",compared["delta_static_stores"],flush=True)
    report={
        "schema":"phase14c-original-cfg-offline-ab-v1",
        "pcode_sha256":p_hash,"ghidra_body_map_sha256":m_hash,
        "function":f"0x{args.entry:08x}",
        "block":f"0x{args.block:08x}",
        "block_instruction_count":len(all_pcs),
        "entry_policy":args.entry_policy,
        "entry_tested_at_every_original_x86_pc":args.entry_policy=="all_entries",
        "dispatch_fallback_required_if_start_only":args.entry_policy=="start_only",
        "guest_RAM_model":"64KiB folded simulated address map: not original 4GiB guest RAM",
        "compiler":"Android NDK aarch64-linux-android26 -O1 -ffp-contract=off",
        "strict_semantic_limits":["No FP/x87 or CALLOTHER","No CALL/RETURN/BRANCHIND",
            "No full original x86/Unicorn oracle for this block",
            "No dynamic ARM64 execution measurements, no FPS",
            "No proof of realistic guest memory aliasing under full 4GiB map"],
        "trials":trials,
        "android_or_runtime_modified":False,
    }
    (out/"summary.json").write_text(json.dumps(report,indent=2,sort_keys=True)+"\n",
                                    encoding="utf-8")
    print("REGION_A_B_REPORT",out/"summary.json",flush=True)
    return 0


if __name__=="__main__":
    raise SystemExit(main())
