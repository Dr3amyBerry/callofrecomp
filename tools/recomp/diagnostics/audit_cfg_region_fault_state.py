#!/usr/bin/env python3
"""Original x86 page-fault boundary vs cached CFG R state (fail-closed).

Unicorn unmaps a real 4-KiB guest page prior to execution. The *same nth*
guest memory access is trapped in a PRIVATE instrumented host CFG helper
using setjmp/longjmp BEFORE its memory access. Captures global R at the trap.
Only supports CoDSP.exe original 1.5 and geometrical 29-instruction block.

Unlike normal-exit correctness, a mid-region guest memory fault makes local
cached x86 registers visible only if committed to R. This diagnoses whether
the opt-in fast path is eligible for production fault/SEH semantics. It does
NOT install a signal handler or patch the real game.
"""
from __future__ import annotations
import argparse,ctypes,hashlib,json,random,shutil,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/"tools/recomp"))
from diagnostics.verify_x86_prefix_oracle import (
    OracleError,require_private_path,require_ignored_output,
    require_original_fingerprints,FLAG_BITS,REG_OFFSETS)
from diagnostics.verify_geometry_region_original_x86 import (
    START,EXIT,COUNT,FULL_RAM,REG_SIZE,ALIASES,prepare_case,pe_code_and_edges)
from diagnostics.benchmark_cfg_region import run
from pcode2c import parse
from cfg_region_lab import select_block,generate_runtime_region_c
from diagnostics.analyze_cfg_regions import verify_inputs
from unicorn import Uc,UC_ARCH_X86,UC_MODE_32,UC_HOOK_CODE,UC_HOOK_MEM_READ,UC_HOOK_MEM_WRITE
from unicorn import UC_HOOK_MEM_READ_UNMAPPED,UC_HOOK_MEM_WRITE_UNMAPPED,UcError
import unicorn.x86_const as X

ARCH_IDS={
    "EAX":X.UC_X86_REG_EAX,"ECX":X.UC_X86_REG_ECX,
    "EDX":X.UC_X86_REG_EDX,"EBX":X.UC_X86_REG_EBX,
    "ESP":X.UC_X86_REG_ESP,"EBP":X.UC_X86_REG_EBP,
    "ESI":X.UC_X86_REG_ESI,"EDI":X.UC_X86_REG_EDI,
}
PAGE=0x1000

def emulator(before:bytearray,initial_flags:int,initial_regs:dict,
             *,unmapped_page:int|None=None):
    uc=Uc(UC_ARCH_X86,UC_MODE_32)
    uc.mem_map(0x1000,FULL_RAM-0x1000)
    uc.mem_write(0x1000,bytes(memoryview(before)[0x1000:]))
    for name,value in initial_regs.items():uc.reg_write(ARCH_IDS[name],value)
    uc.reg_write(X.UC_X86_REG_EFLAGS,initial_flags)
    uc.reg_write(X.UC_X86_REG_EIP,START)
    if unmapped_page is not None:
        uc.mem_unmap(unmapped_page,PAGE)
    return uc

def trace_all(before,flags,regs,original_boundaries):
    uc=emulator(before,flags,regs)
    observed=[]
    visited=[]
    def code(cpu,pc,length,_):
        visited.append(pc)
        if pc==EXIT:cpu.emu_stop()
        elif pc not in original_boundaries:
            raise OracleError("Unicorn wandered beyond 29 verified instructions")
    def memory(cpu,kind,address,size,_value,_):
        observed.append({"pc":cpu.reg_read(X.UC_X86_REG_EIP),
                         "kind":"read" if kind==16 else "write",
                         "address":address,"size":size})
    uc.hook_add(UC_HOOK_CODE,code)
    uc.hook_add(UC_HOOK_MEM_READ|UC_HOOK_MEM_WRITE,memory)
    uc.emu_start(START,0,count=COUNT+3,timeout=500000)
    if visited!=sorted(original_boundaries)+[EXIT]:
        raise OracleError("Trace of geometry original deviated from known CFG")
    return observed

def case_fault(before,flags,regs,page:int):
    uc=emulator(before,flags,regs,unmapped_page=page)
    missed=[]
    visited=[]
    def code(cpu,pc,_size,_):visited.append(pc)
    def missing(_cpu,kind,address,size,_value,_):
        missed.append((kind,address,size))
        return False
    uc.hook_add(UC_HOOK_CODE,code)
    uc.hook_add(UC_HOOK_MEM_READ_UNMAPPED|UC_HOOK_MEM_WRITE_UNMAPPED,missing)
    try:
        uc.emu_start(START,0,count=COUNT+3,timeout=500000)
    except UcError:
        if not missed:raise OracleError("Unicorn raised error before memory fault hook")
    else:
        raise OracleError("Expected original unmapped page did not fault")
    if not missed or (missed[0][1]//PAGE)*PAGE!=page:
        raise OracleError("Unicorn original faulted on a different guest page")
    observed_gpr={name:uc.reg_read(reg)&0xffffffff for name,reg in ARCH_IDS.items()}
    return {"fault_pc":uc.reg_read(X.UC_X86_REG_EIP),
            "fault_address":missed[0][1],
            "gpr":observed_gpr,
            "eflags":uc.reg_read(X.UC_X86_REG_EFLAGS),
            "instructions_reached":len(visited)}

def case_fault_at_instruction(before,flags,regs,page:int,at_pc:int):
    """Unmap a 4KiB guest page on entry to the precise original x86 insn.

    Unlike unmapping before function entry, this also tests later uses of
    pages already read or written by PREVIOUS COMPLETED instructions. The
    memory page is copied at fault time and restored for an exact final RAM
    differential. Missing/unmapped is a real Unicorn guest page failure.
    """
    uc=emulator(before,flags,regs)
    missed=[]
    visited=[]
    page_image=[]
    def code(cpu,pc,_length,_):
        visited.append(pc)
        if pc==at_pc:
            page_image.append(bytes(cpu.mem_read(page,PAGE)))
            cpu.mem_unmap(page,PAGE)
        if pc==EXIT:
            cpu.emu_stop()
    def missing(_cpu,kind,address,size,_value,_):
        missed.append((kind,address,size))
        return False
    uc.hook_add(UC_HOOK_CODE,code)
    uc.hook_add(UC_HOOK_MEM_READ_UNMAPPED|UC_HOOK_MEM_WRITE_UNMAPPED,missing)
    try:
        uc.emu_start(START,0,count=COUNT+3,timeout=500000)
    except UcError as exc:
        if not missed:raise OracleError(
            "Unicorn failed before target memory exception") from exc
    else:
        raise OracleError("Expected at-instruction unmapped page never faulted")
    if (len(page_image)!=1 or not missed or
        uc.reg_read(X.UC_X86_REG_EIP)!=at_pc or
        (missed[0][1]//PAGE)*PAGE!=page):
        raise OracleError("Original x86 at-instruction fault boundary mismatch")
    original_regs={name:uc.reg_read(reg)&0xffffffff
                   for name,reg in ARCH_IDS.items()}
    original_flags=uc.reg_read(X.UC_X86_REG_EFLAGS)
    uc.mem_map(page,PAGE)
    uc.mem_write(page,page_image[0])
    return {
        "fault_pc":at_pc,"fault_address":missed[0][1],
        "gpr":original_regs,"eflags":original_flags,
        "ram":bytes(uc.mem_read(0x1000,FULL_RAM-0x1000)),
        "visited_instructions":len(visited),
    }


def complete_expected_R(initial:bytes,guest:dict)->bytes:
    """Architectural bytes other than eight GPR + five modelled flags stay."""
    expected=bytearray(initial)
    for name,off in REG_OFFSETS.items():
        expected[off:off+4]=guest["gpr"][name].to_bytes(4,"little")
    for name,(bit,off) in FLAG_BITS.items():
        expected[off]=(guest["eflags"]>>bit)&1
    return bytes(expected)


INSTRUMENTED_DECL=r"""
#include "recomp_rt.h"
#include <setjmp.h>
uint8_t *MEM;
uint8_t R[0x2000];
uint8_t U[0x400000];
uint32_t PC;
int recomp_miss;
static jmp_buf fault_escape;
static uint32_t hit_index;
static uint32_t access_counter;
static uint32_t fault_address;
static uint32_t trapped;
static uint32_t logged_access[128];
static uint8_t *checked_addr(uint32_t address) {
  ++access_counter;
  if (access_counter<=128) logged_access[access_counter-1]=address;
  if (access_counter==hit_index) {
    trapped=1;
    fault_address=address;
    longjmp(fault_escape,1);
  }
  return MEM+address;
}
#undef G
#define G(a) checked_addr((uint32_t)(a))
"""

INSTRUMENTED_WRAPPER=r"""
#if defined(_WIN32)
#define API __declspec(dllexport)
#else
#define API __attribute__((visibility("default")))
#endif
API void run_fault_probe(uint8_t *state, uint8_t *memory, uint32_t target) {
 MEM=memory;
 memcpy(R,state,0x2000);
 PC=0x0041c017u;
 trapped=0;
 fault_address=0;
 access_counter=0;
 hit_index=target;
 if (setjmp(fault_escape)==0)
   codsp_cfg14_geom_41c017();
 memcpy(state,R,0x2000);
}
API uint32_t probe_fault_address(void){return fault_address;}
API uint32_t probe_visited_count(void){return access_counter;}
API uint32_t probe_guest_pc(void){return PC;}
API uint32_t probe_trapped(void){return trapped;}
API uint32_t probe_access_address(uint32_t index) {
 return index<access_counter && index<128 ? logged_access[index] : 0xffffffffu;
}
"""

def instrument_helper(private_src:Path, output:Path):
    code=private_src.read_text(encoding="utf-8")
    marker='#include "recomp_rt.h"\n'
    if code.count(marker)!=1:
        raise OracleError("private helper source includes changed; refuse instrument")
    derived=INSTRUMENTED_DECL+code.replace(marker,"",1)+INSTRUMENTED_WRAPPER
    if "uint8_t R[0x2000]" not in INSTRUMENTED_DECL:
        raise OracleError("missing instrumented register mapping")
    source=output/"private_fault_instrumented.c"
    dll=output/"private_fault_instrumented.dll"
    source.write_text(derived,encoding="utf-8")
    compiler=shutil.which("clang")
    if not compiler:raise OracleError("host clang missing")
    run([compiler,"-O1","-ffp-contract=off","-std=c11","-shared",
         "-I",str(ROOT/"tools/recomp"),str(source),"-o",str(dll)])
    lib=ctypes.CDLL(str(dll.resolve()))
    lib.run_fault_probe.argtypes=(ctypes.c_void_p,ctypes.c_void_p,ctypes.c_uint32)
    lib.run_fault_probe.restype=None
    for name in ("probe_fault_address","probe_visited_count",
                 "probe_guest_pc","probe_trapped"):
        getattr(lib,name).restype=ctypes.c_uint32
    lib.probe_access_address.argtypes=(ctypes.c_uint32,)
    lib.probe_access_address.restype=ctypes.c_uint32
    return lib

def run_faults(case:int,private_code:bytes,lib,original_boundaries:set,
               *,all_memory_ops:bool=False):
    before,state,flags,regs=prepare_case(case,private_code)
    timeline=trace_all(before,flags,regs,original_boundaries)
    # Legacy mode audits the first use of each page. Expanded mode
    # unmaps on entry to EACH original x86 memory instruction, including
    # revisits to stack pages after earlier committed STOREs.
    first={}
    for i,access in enumerate(timeline,1):
        first.setdefault((access["address"]//PAGE)*PAGE,(i,access))
    chosen=( [(i,(access["address"]//PAGE)*PAGE,access)
             for i,access in enumerate(timeline,1)]
            if all_memory_ops else
            [(index,page,access) for page,(index,access) in first.items()])
    chosen=[(i,page,item) for i,page,item in chosen
            if page!=(START&~0xfff)]
    if all_memory_ops:
        from collections import Counter
        pcs=Counter(item["pc"] for _i,_page,item in chosen)
        if any(n!=1 for n in pcs.values()):
            raise OracleError("multiple memory accesses inside a single x86 instruction; "
                              "safe-at-instruction unmap cannot distinguish them")
    tested=[]
    for access_number,page,item in chosen:
        guest=(case_fault_at_instruction(before,flags,regs,page,item["pc"])
               if all_memory_ops else case_fault(before,flags,regs,page))
        state_c=ctypes.create_string_buffer(state,REG_SIZE)
        mem_c=ctypes.create_string_buffer(bytes(before),FULL_RAM)
        lib.run_fault_probe(state_c,mem_c,access_number)
        if lib.probe_trapped()!=1 or lib.probe_visited_count()!=access_number:
            raise OracleError("instrumented helper failed to trap at guest memory index")
        if guest["fault_address"]!=lib.probe_fault_address():
            raise OracleError("instrumented memory address differs from original x86 fault")
        if guest["fault_pc"]!=item["pc"]:
            raise OracleError("Unicorn unexpected fault PC in guest memory timeline")
        divergent=[]
        for name,offset in REG_OFFSETS.items():
            if int.from_bytes(state_c.raw[offset:offset+4],"little")!=guest["gpr"][name]:
                divergent.append(name)
        for name,(bit,off) in FLAG_BITS.items():
            if state_c.raw[off]!=((guest["eflags"]>>bit)&1):
                divergent.append(name)
        if lib.probe_guest_pc()!=guest["fault_pc"]:
            divergent.append("PC")
        ram_match=True
        full_R_match=True
        access_order_match=True
        if all_memory_ops:
            access_order_match=all(
                lib.probe_access_address(i)==timeline[i]["address"]
                for i in range(access_number))
            if not access_order_match:divergent.append("guest_memory_access_order")
            # Compare all bytes written before the fault: restarting the
            # failing x86 instruction must NOT replay earlier STOREs.
            ram_match=mem_c.raw[0x1000:]==guest["ram"]
            full_R_match=state_c.raw==complete_expected_R(state,guest)
            if not full_R_match:divergent.append("full_R")
            if not ram_match:divergent.append("committed_RAM")
        tested.append({
            "case":case,"memory_access":access_number,
            "fault_pc":f"0x{guest['fault_pc']:08x}",
            "fault_page":f"0x{page:08x}",
            "guest_memory_address_same":True,
            "guest_memory_prefix_order_matched":access_order_match if all_memory_ops else None,
            "full_R_matched":full_R_match if all_memory_ops else None,
            "earlier_guest_STORES_preserved":ram_match if all_memory_ops else None,
            "dirty_fields_on_fault":divergent,
            "safely_maintains_arch_state":not divergent,
        })
        print("ORIGINAL_X86_PAGE_FAULT",case,"access",access_number,
              "pc",f"0x{guest['fault_pc']:08x}",
              "dirty_arch",divergent,flush=True)
    return tested

def strict_fault_safety_gate(rows:list[dict])->bool:
    # A 100% normal-exit PASS is not evidence of exception correctness.
    # Require actual original guest page-fault cases and fail closed if
    # ANY modeled architectural field/guest-PC mismatch occurs.
    return bool(rows) and all(
        row.get("guest_memory_address_same") is True and
        row.get("safely_maintains_arch_state") is True and
        row.get("dirty_fields_on_fault")==[]
        for row in rows
    )


def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pe",required=True,type=Path)
    ap.add_argument("--out",required=True,type=Path)
    ap.add_argument("--cases",type=int,default=2)
    ap.add_argument("--all-memory-ops",action="store_true",
                    help="unmap page at EVERY original memory instruction "
                         "and compare full R plus earlier committed guest RAM")
    ap.add_argument("--candidate",choices=("legacy","checkpoint"),
                    default="legacy",
                    help="use ignored standalone recompiled helper with guest-memory checkpoints")
    ap.add_argument("--require-safe",action="store_true",
                    help="return exit 4 when any original x86 fault-state differs")
    args=ap.parse_args(argv)
    if not 1<=args.cases<=5:ap.error("--cases must be [1,5]")
    try:
        require_private_path(args.pe,ROOT/".local/private")
        pcode=ROOT/"recomp_out/codsp.pcode"
        mapfile=ROOT/"recomp_out/codsp_function_map_v2.json"
        pehash=hashlib.sha256(args.pe.read_bytes()).hexdigest()
        pcodehash=hashlib.sha256(pcode.read_bytes()).hexdigest()
        require_original_fingerprints(pehash,pcodehash)
        verify_inputs(pcode,mapfile)
        require_ignored_output(args.out,ROOT)
        insns,_,_=parse(pcode)
        body_map=json.loads(mapfile.read_text(encoding="utf-8"))
        block=select_block(insns,body_map,0x0041B8F0,START)
        original=pe_code_and_edges(args.pe,block)
        source=ROOT/"recomp_out/codsp_cfg14_geom_41c017.c"
        if not source.is_file():raise OracleError("private original-derived helper missing")
        args.out.mkdir(parents=True,exist_ok=False)
        if args.candidate=="checkpoint":
            derived,_selected=generate_runtime_region_c(
                block,cache_count=5,fault_policy="checkpoint")
            source=args.out/"private_checkpoint_helper_source.c"
            source.write_text(derived,encoding="utf-8")
        instrument=instrument_helper(source,args.out)
        rows=[]
        for case in range(args.cases):
            rows.extend(run_faults(
                case,original,instrument,
                {pc for pc,_n,_ops in block.instructions},
                all_memory_ops=args.all_memory_ops))
        failures=[x for x in rows if not x["safely_maintains_arch_state"]]
        report={
            "schema":"phase14c-x86-page-fault-architectural-state-audit-v1",
            "pe_sha256":pehash,"pcode_sha256":pcodehash,
            "cases":args.cases,"fault_locations":len(rows),
            "unsafe_fault_locations":len(failures),
            "strict_fault_safety_gate":"PASS" if strict_fault_safety_gate(rows) else "FAIL",
            "source_private_helper_sha256":hashlib.sha256(source.read_bytes()).hexdigest(),
            "region":"0x0041c017",
            "candidate":args.candidate,
            "all_original_memory_instructions_tested":args.all_memory_ops,
            "full_R_and_RAM_at_fault_compared":args.all_memory_ops,
            "checkpoint_policy_is_offline_only":True,
            "unsafe_for_exception_sensitive_guest_code":bool(failures),
            "default_and_production_fastpath_recommended":False,
            "original_reference":"Unicorn x86 UC_ERR_*_UNMAPPED real 4KiB page",
            "comparator":"PRIVATE instrumented cached-C G() forced longjmp before nth guest memory access",
            "risk":"local R cache not flushed before fault and guest PC lags original faulting PC",
            "rows":rows,
            "limitations":["not a real Android OS SEH/signal recovery",
                           "uses exact 24 MiB simulated memory and a finite set of fault pages",
                           "does not prove all 4 GiB guest addresses",
                           "not a dynamic frame-rate benchmark"],
        }
        (args.out/"summary.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
        print("CFG14_FAULT_BOUNDARY_AUDIT",len(rows),
              "unsafe",len(failures),flush=True)
        if args.require_safe and not strict_fault_safety_gate(rows):
            print("CFG14_FAULT_SAFETY_GATE_REJECTED",len(failures),file=sys.stderr)
            return 4
        return 0 if rows else 2
    except (OracleError,OSError,ValueError,RuntimeError) as e:
        print("CFG14_FAULT_AUDIT_FAILED",e,file=sys.stderr)
        return 2

if __name__=="__main__":
    raise SystemExit(main())
