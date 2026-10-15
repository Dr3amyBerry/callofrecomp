#!/usr/bin/env python3
"""Phase14F original-CFG superregion offline A/B + independent x86 oracle.

Selects a complete, forward-only multi-basic-block original CoDSP 1.5
subgraph with NO GUEST DATA MEMORY, CALLOTHER, CALL, RETURN or x87.
Verifies original x86 Capstone instruction boundaries/branches then uses
Unicorn ORIGINAL bytes to crosscheck all five modeled EFLAGS, eight GPR,
entire 8192-byte R and exact guest exit PC. The host-generated p-code A
and register-cached B are compared independently against original x86.

This is not an APK, FPS benchmark, proof about unknown side entries,
native signal recovery, or whole-game correctness. All derived C and DLLs
are generated only into a new ignored .local/profiles folder.
"""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
from pathlib import Path
import random
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/"tools/recomp"))

from cfg_superregion import discover_superregions,description
from cfg_region_lab import generate_region_c
from pcode2c import parse
from diagnostics.analyze_cfg_regions import verify_inputs
from diagnostics.verify_cfg_against_x86 import (
    check_edges, decode_pe_instructions, EXPECTED_PE_SHA256
)
from diagnostics.verify_x86_prefix_oracle import (
    REG_OFFSETS, FLAG_BITS, OracleError,require_private_path,require_ignored_output
)
from diagnostics.benchmark_cfg_region import (
    compile_arm, compile_host, open_library, ndk_clang,arm_stats
)

R_BYTES=0x2000


def validate_original_x86(pe: Path, region) -> dict[int, bytes]:
    import pefile
    from capstone import Cs,CS_ARCH_X86,CS_MODE_32
    from capstone.x86_const import X86_OP_MEM
    decoded=decode_pe_instructions(pe,list(region.instructions))
    structural=check_edges(list(region.instructions),decoded)
    if structural["mismatch_count"] or not structural["all_edges_agree_where_decoded"]:
        raise OracleError("Independent original Capstone CFG edges disagree with p-code")
    source=pefile.PE(str(pe),fast_load=True)
    cs=Cs(CS_ARCH_X86,CS_MODE_32)
    cs.detail=True
    payload={}
    for pc,size,ops in region.instructions:
        buf=source.get_data(pc-0x400000,size)
        original=list(cs.disasm(buf,pc,count=1))
        if len(original)!=1 or original[0].size!=size:
            raise OracleError(f"Original x86 instruction boundary mismatch 0x{pc:08x}")
        # LEA uses a memory-looking address mode but does not read data;
        # reject too rather than silently accepting a mistaken side effect.
        if any(operand.type==X86_OP_MEM for operand in original[0].operands):
            raise OracleError(f"x86 original has memory operand at 0x{pc:08x}")
        payload[pc]=buf
    return payload


def update_conditional_coverage(
    visited: list[int],
    conditionals: dict[int, int],
    observed: dict[int, dict[str, int]],
) -> None:
    """Track only actual x86 branch outcomes, never infer unexecuted paths."""
    for before,after in zip(visited,visited[1:]):
        if before not in conditionals:
            continue
        branch="fallthrough" if after==before+conditionals[before] else "taken"
        observed[before][branch]+=1


def oracle_cases(region,payload,libs:dict,counts:int)->dict:
    from unicorn import Uc,UC_ARCH_X86,UC_MODE_32,UC_HOOK_CODE
    from unicorn import UC_HOOK_MEM_READ,UC_HOOK_MEM_WRITE
    import unicorn.x86_const as X
    regs={
        "EAX":X.UC_X86_REG_EAX,"ECX":X.UC_X86_REG_ECX,
        "EDX":X.UC_X86_REG_EDX,"EBX":X.UC_X86_REG_EBX,
        "ESP":X.UC_X86_REG_ESP,"EBP":X.UC_X86_REG_EBP,
        "ESI":X.UC_X86_REG_ESI,"EDI":X.UC_X86_REG_EDI,
    }
    pcs=set(payload)
    uc=Uc(UC_ARCH_X86,UC_MODE_32)
    targets=[t for _source,t in region.exits if t is not None]
    largest=max([0x400000,*pcs,*targets])
    # Bound memory map to original code/data near the source function.
    if largest>=0x01000000:raise OracleError("far dynamic exit exceeds bounded oracle range")
    length=((largest+0x2000-0x400000+0xfff)//0x1000)*0x1000
    uc.mem_map(0x400000,length)
    for pc,data in payload.items():uc.mem_write(pc,data)
    for target in targets:
        if target not in pcs:
            uc.mem_write(target,b"\x90")
    visited=[]
    outside=[]
    illegal=[]
    def code_hook(cpu,pc,_n,_):
        visited.append(pc)
        if pc not in pcs:
            outside.append(pc)
            cpu.emu_stop()
    def memory_hook(cpu,kind,addr,size,_value,_):
        illegal.append((addr,size))
        cpu.emu_stop()
    uc.hook_add(UC_HOOK_CODE,code_hook)
    uc.hook_add(UC_HOOK_MEM_READ|UC_HOOK_MEM_WRITE,memory_hook)
    flags_mask=sum(1<<bit for bit,_slot in FLAG_BITS.values())
    exits={}
    path_signatures=set()
    conditionals={pc:size for pc,size,ops in region.region.instructions
                  if any(mn=="CBRANCH" for mn,_out,_args in ops)}
    outcomes={pc:{"taken":0,"fallthrough":0} for pc in conditionals}
    for case in range(counts):
        rng=random.Random(0x14F5001 ^ (region.region.start*0x9e3779b1) ^ case)
        raw=bytearray(rng.randbytes(R_BYTES))
        for name,offset in REG_OFFSETS.items():
            raw[offset:offset+4]=rng.getrandbits(32).to_bytes(4,"little")
        # All omitted architectural flags are zero, TF=0 (no #DB).
        initial_flags=(rng.getrandbits(32)&flags_mask)|2
        for _name,(bit,off) in FLAG_BITS.items():
            raw[off]=(initial_flags>>bit)&1
        initial=bytes(raw)
        for name,off in REG_OFFSETS.items():
            uc.reg_write(regs[name],int.from_bytes(initial[off:off+4],"little"))
        uc.reg_write(X.UC_X86_REG_EFLAGS,initial_flags)
        uc.reg_write(X.UC_X86_REG_EIP,region.region.start)
        visited.clear();outside.clear();illegal.clear()
        try:
            uc.emu_start(region.region.start,0,count=128,timeout=400000)
        except Exception as exc:
            raise OracleError(f"Unicorn original faulted at case {case}: {exc}") from exc
        if illegal or len(outside)!=1 or not visited:
            raise OracleError("x86 original performed guest RAM access or did not exit bounded CFG")
        actual_exit=outside[0]
        if actual_exit not in {target for _source,target in region.exits}:
            raise OracleError(f"x86 original unexpected CFG exit PC 0x{actual_exit:08x}")
        expected=bytearray(initial)
        for name,off in REG_OFFSETS.items():
            expected[off:off+4]=(uc.reg_read(regs[name])&0xffffffff).to_bytes(4,"little")
        finale=uc.reg_read(X.UC_X86_REG_EFLAGS)
        for _name,(bit,off) in FLAG_BITS.items():
            expected[off]=(finale>>bit)&1
        for label,lib in libs.items():
            rb=ctypes.create_string_buffer(initial,R_BYTES)
            mem=ctypes.create_string_buffer(65536)
            lib.execute_region(rb,mem,region.region.start)
            resultpc=lib.result_pc()
            if resultpc!=actual_exit or rb.raw!=expected:
                offsets=[hex(i) for i,(a,b) in enumerate(zip(rb.raw,expected)) if a!=b]
                raise OracleError(
                    f"original x86 vs {label} mismatch case={case} "
                    f"PC={hex(resultpc)} expected={hex(actual_exit)} "
                    f"first_R_byte_diffs={offsets[:12]}")
        path_signatures.add(tuple(pc for pc in visited if pc in pcs))
        update_conditional_coverage(visited,conditionals,outcomes)
        exits[f"0x{actual_exit:08x}"]=exits.get(f"0x{actual_exit:08x}",0)+1
    return {
        "independent_original_x86_cases":counts,
        "original_x86_paths_reached":len(path_signatures),
        "guest_exit_distribution":exits,
        "original_x86_conditional_outcome_coverage":{
            f"0x{pc:08x}":observed for pc,observed in outcomes.items()},
        "all_original_conditional_outcomes_exercised":all(
            pair["taken"]>0 and pair["fallthrough"]>0
            for pair in outcomes.values()),
        "8_GPR_5_modeled_EFLAGS_all_8192_R_bytes_and_PC_matched":True,
        "guest_memory_accesses_from_x86":0,
        "not_checked":"full guest EFLAGS AF/DF, x87, asynchronous signals or runtime",
    }


def main(argv=None)->int:
    ap=argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--entry",type=lambda x:int(x,0),required=True)
    ap.add_argument("--start",type=lambda x:int(x,0),required=True)
    ap.add_argument("--pe",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    ap.add_argument("--cases",type=int,default=96)
    ap.add_argument("--max-blocks",type=int,default=12)
    ap.add_argument("--max-insns",type=int,default=48)
    args=ap.parse_args(argv)
    if not 8<=args.cases<=512:ap.error("--cases must be 8..512")
    try:
        require_private_path(args.pe,ROOT/".local/private")
        require_ignored_output(args.out,ROOT)
        if hashlib.sha256(args.pe.read_bytes()).hexdigest()!=EXPECTED_PE_SHA256:
            raise OracleError("CoDSP original PE fingerprint mismatch")
        pcode=ROOT/"recomp_out/codsp.pcode"
        mapfile=ROOT/"recomp_out/codsp_function_map_v2.json"
        p_sha,m_sha=verify_inputs(pcode,mapfile)
        insns,_,_=parse(pcode)
        mapping=json.loads(mapfile.read_text(encoding="utf-8"))
        found=discover_superregions(
            insns,mapping,args.entry,
            maximum_blocks=args.max_blocks,
            maximum_instructions=args.max_insns)
        matches=[item for item in found if item.region.start==args.start]
        if len(matches)!=1:
            raise OracleError("no unique verified eligible original memory-free superregion")
        region=matches[0]
        original_payload=validate_original_x86(args.pe,region.region)
        args.out.mkdir(parents=True,exist_ok=False)
        ndk,size,dump=ndk_clang()
        libs={}
        objects={}
        for cache in (0,3,5):
            src,selected=generate_region_c(
                region.region,cache_count=cache,entry_policy="start_only",
                memory_model="exact",fault_policy="legacy")
            folder=args.out/f"cache_{cache}"
            folder.mkdir()
            source=folder/"private_original_cfg.c"
            source.write_text(src,encoding="utf-8")
            dll=folder/"private_original_cfg.dll"
            compile_host(source,dll)
            libs[str(cache)]=open_library(dll)
            objects[str(cache)]={}
            for opt in ("-O1","-O2"):
                obj=folder/f"original_cfg_arm64_{opt[1:]}.o"
                compile_arm(source,obj,ndk,opt=opt)
                objects[str(cache)][opt]=arm_stats(obj,size,dump)
            objects[str(cache)]["cached_fields"]=[
                [f"0x{x[1]:x}",x[2]] for x in selected
            ]
            print("ARM64_MULTI_BLOCK",cache,objects[str(cache)],flush=True)
        oracle=oracle_cases(region,original_payload,libs,args.cases)
        report={
            "schema":"phase14f-verified-original-superregion-ab-x86-v1",
            "pe_sha256":EXPECTED_PE_SHA256,"pcode_sha256":p_sha,
            "map_sha256":m_sha,"superregion":description(region),
            "oracle":oracle,"ndk_static":objects,
            "original_runtime_dispatcher_fallback_intact":True,
            "android_apk_or_runtime_modified":False,
            "production_eligible":False,
            "fps_benchmarked":False,
        }
        (args.out/"summary.json").write_text(
            json.dumps(report,indent=2)+"\n",encoding="utf-8")
        print("PHASE14F_ORIGINAL_X86_SUPERREGION_PASS",
              args.cases,description(region),flush=True)
        return 0
    except (OracleError,ValueError,OSError,RuntimeError,ImportError) as exc:
        print("PHASE14F_SUPERREGION_FAILED",exc,file=sys.stderr,flush=True)
        return 2

if __name__=="__main__":
    raise SystemExit(main())
