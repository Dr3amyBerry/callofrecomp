#!/usr/bin/env python3
"""Phase14E: resume independent original CoDSP x86 after EACH cached CFG fault.

Offline recovery proof: original source bytes are executed with Unicorn x86
from the guest PC and architectural state captured from a faulted checkpoint
helper. Verify NO repeat of previously executed guest STOREs, full final RAM
and modeled GPR/EFLAGS equivalence to uninterrupted original x86 execution.

This is NOT OS signal/SEH recovery in an Android APK. All derived source,
DLL, PE data and traces remain ignored under .local/profiles.
"""
from __future__ import annotations
import argparse,ctypes,hashlib,json,sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/"tools/recomp"))
from cfg_region_lab import select_block,generate_runtime_region_c,generate_region_c
from pcode2c import parse
from diagnostics.analyze_cfg_regions import verify_inputs
from diagnostics.verify_x86_prefix_oracle import (
    OracleError,require_original_fingerprints,require_ignored_output,
    require_private_path,REG_OFFSETS,FLAG_BITS)
from diagnostics.verify_geometry_region_original_x86 import (
    FULL_RAM,REG_SIZE,COUNT,START,EXIT,prepare_case,pe_code_and_edges)
from diagnostics.audit_cfg_region_fault_state import (
    emulator,trace_all,case_fault_at_instruction,complete_expected_R,
    instrument_helper,ARCH_IDS,PAGE)
from diagnostics.benchmark_cfg_region import compile_host,open_library
from unicorn import UC_HOOK_CODE,UC_HOOK_MEM_READ,UC_HOOK_MEM_WRITE
import unicorn.x86_const as X


def unicorn_to_shared_end(mem:bytes,regs:dict,eflags:int,start:int,
                          known_guest_pcs:set[int])->dict:
    """Run original CoDSP bytes; never execute past the shared epilogue entry."""
    uc=emulator(bytearray(mem),eflags,regs)
    uc.reg_write(X.UC_X86_REG_EIP,start)
    events=[]
    visited=[]
    def code(cpu,pc,_size,_):
        visited.append(pc)
        if pc==EXIT:cpu.emu_stop()
        elif pc not in known_guest_pcs:
            raise OracleError("resumed original entered unverified code")
    def memory(cpu,typ,address,size,value,_):
        events.append((cpu.reg_read(X.UC_X86_REG_EIP),
                       "read" if typ==16 else "write",address,size))
    uc.hook_add(UC_HOOK_CODE,code)
    uc.hook_add(UC_HOOK_MEM_READ|UC_HOOK_MEM_WRITE,memory)
    uc.emu_start(start,0,count=COUNT+3,timeout=500000)
    if uc.reg_read(X.UC_X86_REG_EIP)!=EXIT:
        raise OracleError("resumed original PC did not reach shared epilogue")
    return {
        "ram":bytes(uc.mem_read(0x1000,FULL_RAM-0x1000)),
        "gpr":{name:uc.reg_read(reg)&0xffffffff
               for name,reg in ARCH_IDS.items()},
        "eflags":uc.reg_read(X.UC_X86_REG_EFLAGS),
        "visited":visited,"events":events,
    }


def eflags_from_checkpoint(state:bytes)->int:
    # Reconstruct only the five flags materialized by the production
    # p-code. Other guest flags, including AF, are outside this proof.
    return 2 | sum((state[offset]&1)<<bit
                   for _name,(bit,offset) in FLAG_BITS.items())


def registers_from_checkpoint(state:bytes)->dict:
    return {name:int.from_bytes(state[offset:offset+4],"little")
            for name,offset in REG_OFFSETS.items()}


def verify_recovery(case:int,code:bytes,library,original_pcs:set[int],
                    original_translator):
    before,initial_R,seed_flags,seed_gprs=prepare_case(case,code)
    baseline=unicorn_to_shared_end(
        bytes(before),seed_gprs,seed_flags,START,original_pcs)
    events=baseline["events"]
    if len(events)!=24:
        raise OracleError("original guest memory trace changed from pinned 24 accesses")
    if len(set(pc for pc,_kind,_a,_s in events))!=len(events):
        raise OracleError("original memory event PC repeated; require micro-PC fallback")
    observations=[]
    for access_index,event in enumerate(events,1):
        at_pc,kind,address,size=event
        page=(address//PAGE)*PAGE
        original_fault=case_fault_at_instruction(
            before,seed_flags,seed_gprs,page,at_pc)
        mutable_R=ctypes.create_string_buffer(initial_R,REG_SIZE)
        mutable_MEM=ctypes.create_string_buffer(bytes(before),FULL_RAM)
        library.run_fault_probe(mutable_R,mutable_MEM,access_index)
        if library.probe_trapped()!=1:
            raise OracleError(f"host C failed to stop at access {access_index}")
        if library.probe_guest_pc()!=at_pc:
            raise OracleError(f"guest PC mismatch at fault {access_index}")
        if library.probe_fault_address()!=address:
            raise OracleError(f"memory operand address mismatch at fault {access_index}")
        prefix_addresses=tuple(library.probe_access_address(k)
                               for k in range(access_index))
        if prefix_addresses!=tuple(e[2] for e in events[:access_index]):
            raise OracleError("cached C memory access prefix differs from original x86")
        if mutable_R.raw!=complete_expected_R(initial_R,original_fault):
            raise OracleError(f"full 8192-byte guest R differs at fault {access_index}")
        if mutable_MEM.raw[0x1000:]!=original_fault["ram"]:
            raise OracleError(f"earlier committed guest memory differs at fault {access_index}")
        checkpoint_regs=registers_from_checkpoint(mutable_R.raw)
        checkpoint_flags=eflags_from_checkpoint(mutable_R.raw)
        resumed=unicorn_to_shared_end(
            mutable_MEM.raw,checkpoint_regs,checkpoint_flags,
            at_pc,original_pcs)
        if resumed["gpr"]!=baseline["gpr"]:
            raise OracleError(f"resumed GPR mismatch at access {access_index}")
        for _name,(bit,off) in FLAG_BITS.items():
            if (resumed["eflags"]>>bit)&1 != (baseline["eflags"]>>bit)&1:
                raise OracleError(f"resumed {_name} differs at access {access_index}")
        if resumed["ram"]!=baseline["ram"]:
            raise OracleError(f"resumed RAM differs at access {access_index}")
        # Also resume from the faulting PC using the actual original
        # uncached pcode2c.Gen A translator (not just original Unicorn
        # x86). The ordinary dispatcher can enter this guest PC directly;
        # never restart the accelerated block leader.
        normal_R=ctypes.create_string_buffer(mutable_R.raw,REG_SIZE)
        normal_RAM=ctypes.create_string_buffer(mutable_MEM.raw,FULL_RAM)
        original_translator.execute_region(normal_R,normal_RAM,at_pc)
        if original_translator.result_pc()!=EXIT:
            raise OracleError("uncached original translator did not exit at shared epilogue")
        if normal_RAM.raw[0x1000:]!=baseline["ram"]:
            raise OracleError("uncached translator replayed/omitted a guest memory write")
        if normal_R.raw!=complete_expected_R(initial_R,baseline):
            raise OracleError("uncached original translator architecture differs from original x86")
        # Only the suffix executes on restart. Together with the cached
        # helper's verified prefix, this guarantees not replaying earlier
        # STOREs and preserves exact guest READ/WRITE event order.
        combined=events[:access_index-1]+resumed["events"]
        if combined!=events:
            raise OracleError(f"memory sequence includes replay or omission at {access_index}")
        stored_before=sum(e[1]=="write" for e in events[:access_index-1])
        stored_after=sum(e[1]=="write" for e in resumed["events"])
        all_stores=sum(e[1]=="write" for e in events)
        if stored_before+stored_after!=all_stores:
            raise OracleError("STORE count differs between resumed and original")
        observations.append({
            "case":case,"access_index":access_index,
            "fault_pc":f"0x{at_pc:08x}",
            "failed_access_type":kind,
            "RAM_and_R_exact_at_fault":True,
            "resumed_GPR_5_EFLAGS_RAM_PC_identical":True,
            "original_pcode2c_all_entries_translator_fallback_exact":True,
            "memory_access_order_and_guest_STORE_counts_identical":True,
            "original_guest_store_count":all_stores,
        })
        if access_index%8==0:
            print("ORIGINAL_X86_RESUME_CHECKED",case,access_index,
                  "guest_STORES",all_stores,flush=True)
    return observations


def main(argv=None)->int:
    ap=argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pe",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    ap.add_argument("--cases",type=int,default=2)
    args=ap.parse_args(argv)
    if not 1<=args.cases<=8:ap.error("1..8 original memory alias seeds")
    try:
        require_private_path(args.pe,ROOT/".local/private")
        pcode=ROOT/"recomp_out/codsp.pcode"
        mapping=ROOT/"recomp_out/codsp_function_map_v2.json"
        sha_pe=hashlib.sha256(args.pe.read_bytes()).hexdigest()
        sha_pcode=hashlib.sha256(pcode.read_bytes()).hexdigest()
        require_original_fingerprints(sha_pe,sha_pcode)
        _p,_m=verify_inputs(pcode,mapping)
        require_ignored_output(args.out,ROOT)
        original_insns,_,_=parse(pcode)
        region=select_block(
            original_insns,json.loads(mapping.read_text(encoding="utf-8")),
            0x0041B8F0,START)
        code=pe_code_and_edges(args.pe,region)
        known={pc for pc,_sz,_ops in region.instructions}
        args.out.mkdir(parents=True,exist_ok=False)
        source=args.out/"private_checkpoint_helper.c"
        candidate,selected=generate_runtime_region_c(
            region,cache_count=5,fault_policy="checkpoint")
        source.write_text(candidate,encoding="utf-8")
        library=instrument_helper(source,args.out)
        # Original, uncached guest translation A accepts EVERY original
        # instruction PC. The checkpoint must delegate here on faults,
        # not reenter the cached leader and replay prior guest STOREs.
        fallback_source=args.out/"private_original_all_entries.c"
        fallback_dll=args.out/"private_original_all_entries.dll"
        old_c,_=generate_region_c(
            region,cache_count=0,entry_policy="all_entries",
            memory_model="exact",fault_policy="legacy")
        fallback_source.write_text(old_c,encoding="utf-8")
        compile_host(fallback_source,fallback_dll)
        original_translator=open_library(fallback_dll)
        rows=[]
        for case in range(args.cases):
            rows.extend(verify_recovery(
                case,code,library,known,original_translator))
        report={
            "schema":"phase14d-original-x86-resume-after-cfg-fault-v1",
            "original_pe_sha256":sha_pe,"original_pcode_sha256":sha_pcode,
            "candidate_c_sha256":hashlib.sha256(source.read_bytes()).hexdigest(),
            "guest_block_start":f"0x{START:08x}",
            "original_shared_epilogue_entry":f"0x{EXIT:08x}",
            "memory_model":"exact 24MiB guest map",
            "cases":args.cases,
            "unique_guest_mem_ops_per_case":24,
            "verified_resume_fault_boundaries":len(rows),
            "all_identical_to_independent_original":True,
            "all_prior_guest_STORES_applied_exactly_once":True,
            "all_uncached_original_translator_fallback_states_equivalent":True,
            "modeled_flags":["CF","PF","ZF","SF","OF"],
            "critical_limitations":[
                "not actual Android signal/SEH delivery or deoptimizer",
                "not 4GiB guest memory nor arbitrary page permissions",
                "guest EFLAGS AF, x87 and hidden guest state not validated",
                "original x86 resumed in Unicorn from checkpoint, "
                "not from actual Android dispatcher",
                "guest exception recovery must be implemented before unblocking APK",
            ],
            "samples":rows,
        }
        (args.out/"summary.json").write_text(
            json.dumps(report,indent=2)+"\n",encoding="utf-8")
        print("PHASE14D_GUEST_FAULT_RESUME_PASS",
              len(rows),"checkpoint_restarts_verified",flush=True)
        return 0
    except (OracleError,ValueError,OSError,RuntimeError) as exc:
        print("PHASE14D_GUEST_FAULT_RESUME_FAILED",
              str(exc),file=sys.stderr,flush=True)
        return 2

if __name__=="__main__":
    raise SystemExit(main())
