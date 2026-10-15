"""Phase14C-D: independent original x86 proof for 29-instruction geometry CFG block.

Uses exact guest virtual addresses, no 64KiB fold. Unicorn executes original
CoDSP 1.5 PE bytes and checks every original x86 PC/control edge. Both the
baseline p-code lowering and the cached five-register fast path must match:
- EAX/ECX/EDX/EBX/ESP/EBP/ESI/EDI and five modeled EFLAGS,
- full guest R[0x2000] outside those locations unchanged,
- ALL mapped guest RAM bytes, with tracked read/write alias footprints,
- final guest PC 0x00523CD9 (before the shared epilogue).
A 24 MiB deterministic, sparse-populated original guest address space is used.
This is not full arbitrary 4GiB game-state equivalence. No engine changes.

Generated C, private PE data, DLLs and detailed traces never leave ignored
.local/profiles. Public test fixtures must be synthetic only.
"""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
from pathlib import Path
import random
import shutil
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/"tools/recomp"))
from cfg_region_lab import select_block,generate_region_c,cache_candidates
from pcode2c import parse
from diagnostics.analyze_cfg_regions import verify_inputs
from diagnostics.verify_cfg_against_x86 import (
    EXPECTED_PE_SHA256, decode_pe_instructions
)
from diagnostics.verify_x86_prefix_oracle import (
    FLAG_BITS,REG_OFFSETS,OracleError,require_private_path,
    require_original_fingerprints,require_ignored_output
)
from diagnostics.benchmark_cfg_region import compile_host,open_library

FUNC=0x0041B8F0
START=0x0041C017
EXIT=0x00523CD9
COUNT=29
FULL_RAM=0x1800000 # 24 MiB; covers absolute 0x014BD6AC
REG_SIZE=0x2000
STACK=0x320000
OBJECT=0x340000
SOURCE=0x350000
OUT=0x360000
TABLE=0x370000
ORIGINAL_GLOBAL=0x014BD6AC
CF_MASK=sum(1<<bit for bit,_offset in FLAG_BITS.values())
CASES_LIMIT=256
ALIASES={
    0:"normal: disjoint objects and stack",
    1:"ECX+D4 aliases EBX pointer storage",
    2:"ECX+E0 aliases EBX pointer storage",
    3:"ECX+E0 aliases indexed global table cell",
    4:"ECX+D4 aliases stack+0x58 consumed after POP",
}

def pe_code_and_edges(pe_path:Path, region)->bytes:
    import pefile
    from capstone import Cs,CS_ARCH_X86,CS_MODE_32
    pe=pefile.PE(str(pe_path),fast_load=True)
    if pe.OPTIONAL_HEADER.ImageBase!=0x400000:
        raise OracleError("unexpected source PE base")
    pairs=[(pc,n) for pc,n,_ops in region.instructions]
    if len(pairs)!=COUNT or pairs[0][0]!=START:
        raise OracleError("expected original geometry 29-instruction CFG block")
    for (pc,n),(other,_m) in zip(pairs,pairs[1:]):
        if pc+n!=other:
            raise OracleError("original x86 block not contiguous")
    end=pairs[-1][0]+pairs[-1][1]
    code=pe.get_data(START-0x400000,end-START)
    if len(code)!=end-START:
        raise OracleError("truncated source executable block")
    original=list(Cs(CS_ARCH_X86,CS_MODE_32).disasm(code,START))
    if [(x.address,x.size) for x in original]!=pairs:
        raise OracleError("Capstone disagrees with original guest instruction boundaries")
    if original[-1].mnemonic!="jmp" or int(original[-1].op_str,0)!=EXIT:
        raise OracleError("geometry block does not exit to known shared epilogue")
    if any(x.mnemonic.startswith(("f","call","ret","j")) for x in original[:-1]):
        raise OracleError("unapproved FP or guest control in independent original block")
    independent=decode_pe_instructions(pe_path,list(region.instructions))
    if len(independent)!=COUNT or independent[-1].target!=EXIT:
        raise OracleError("independent x86 original control verification failed")
    return code


def prepare_case(case:int,code:bytes)->tuple[bytearray,bytes,int,dict]:
    rng=random.Random(0x14cdee ^ (case*0x9e3779b1))
    scenario=case%len(ALIASES)
    data=bytearray(FULL_RAM)
    data[START:START+len(code)]=code
    def w4(address,value):
        if not 0x1000<=address<=FULL_RAM-4:
            raise OracleError("test generator guest pointer escaped 24MiB mapping")
        data[address:address+4]=(value&0xffffffff).to_bytes(4,"little")
    # Keep deterministic randomized well-defined RAM in each used page.
    for address,length in ((STACK-0x100,0x400),(OBJECT-0x200,0x400),
                           (SOURCE-0x100,0x400),(OUT-0x200,0x600),
                           (TABLE-0x100,0x1000)):
        data[address:address+length]=rng.randbytes(length)
    stack_values={0x14:rng.getrandbits(32),0x58:rng.getrandbits(32),
                  0x5c:rng.getrandbits(32)}
    for offset,value in stack_values.items():w4(STACK+offset,value)
    pointer=SOURCE
    w4(OBJECT,pointer)
    index=case%4
    w4(OBJECT+4,index)
    for off in range(0,0x80,4):
        w4(SOURCE+off,rng.getrandbits(32))
    # Alias case 1 overwrites [EBX] with [EAX]. Make it another mapped
    # source pointer, so later dereferences remain inside the oracle map.
    if scenario==1:
        w4(SOURCE,SOURCE+0x100)
        # The next STORE aliases [EBX+4] (table index). Keep that
        # *mutated* index inside the verified table to exercise true
        # write->read alias rather than a synthetic unmapped fault.
        w4(SOURCE+0x104,case%4)
        w4(SOURCE+0x108,rng.getrandbits(32))
    w4(ORIGINAL_GLOBAL,TABLE)
    # Dedicated indexed original read 72*index+0x40.
    for n in range(4):w4(TABLE+72*n+0x40,rng.getrandbits(32))
    if scenario==0: ecx=OUT
    elif scenario==1:ecx=OBJECT-0xd4
    elif scenario==2:ecx=OBJECT-0xe0
    elif scenario==3:ecx=TABLE+72*index+0x40-0xe0
    else:ecx=STACK+0x58-0xd4
    regs={
        "EAX":rng.getrandbits(32),"ECX":ecx,
        "EDX":rng.getrandbits(32),"EBX":OBJECT,
        "ESP":STACK,"EBP":rng.getrandbits(32),
        "ESI":rng.getrandbits(32),"EDI":rng.getrandbits(32),
    }
    flags=0x2|rng.getrandbits(12)&CF_MASK
    original_R=bytearray(rng.randbytes(REG_SIZE))
    for name,offset in REG_OFFSETS.items():
        original_R[offset:offset+4]=regs[name].to_bytes(4,"little")
    for name,(bit,offset) in FLAG_BITS.items():
        original_R[offset]=(flags>>bit)&1
    return data,bytes(original_R),flags,regs


def compare_state(case:int, pe_code:bytes, libs:dict,
                  pe_boundaries:set[int]) -> dict:
    from unicorn import Uc,UC_ARCH_X86,UC_MODE_32,UC_HOOK_CODE,UC_HOOK_MEM_READ,UC_HOOK_MEM_WRITE
    from unicorn.x86_const import (
        UC_X86_REG_EAX,UC_X86_REG_ECX,UC_X86_REG_EDX,UC_X86_REG_EBX,
        UC_X86_REG_ESP,UC_X86_REG_EBP,UC_X86_REG_ESI,UC_X86_REG_EDI,
        UC_X86_REG_EIP,UC_X86_REG_EFLAGS,
    )
    registers=dict(zip(REG_OFFSETS,(
        UC_X86_REG_EAX,UC_X86_REG_ECX,UC_X86_REG_EDX,UC_X86_REG_EBX,
        UC_X86_REG_ESP,UC_X86_REG_EBP,UC_X86_REG_ESI,UC_X86_REG_EDI,
    )))
    before,initial_R,eflags,seed_regs=prepare_case(case,pe_code)
    uc=Uc(UC_ARCH_X86,UC_MODE_32)
    uc.mem_map(0x1000,FULL_RAM-0x1000)
    uc.mem_write(0x1000,bytes(memoryview(before)[0x1000:]))
    uc.reg_write(UC_X86_REG_EIP,START)
    uc.reg_write(UC_X86_REG_EFLAGS,eflags)
    for name,reg in registers.items():uc.reg_write(reg,seed_regs[name])
    read_bytes=set()
    write_bytes=set()
    accesses=[]
    visited=[]
    bad=[]
    def on_code(machine,pc,_length,_user):
        visited.append(pc)
        if pc==EXIT:
            machine.emu_stop()
        elif pc not in pe_boundaries:
            bad.append(pc)
            machine.emu_stop()
    def on_read(_machine,_access,address,size,_value,_user):
        if not (0x1000<=address and address+size<=FULL_RAM):
            bad.append(address)
        for i in range(address,address+size):read_bytes.add(i)
        accesses.append(("r",address,size))
    def on_write(_machine,_access,address,size,_value,_user):
        for i in range(address,address+size):write_bytes.add(i)
        accesses.append(("w",address,size))
    uc.hook_add(UC_HOOK_CODE,on_code)
    uc.hook_add(UC_HOOK_MEM_READ,on_read)
    uc.hook_add(UC_HOOK_MEM_WRITE,on_write)
    try:
        uc.emu_start(START,0,count=COUNT+3,timeout=500000)
    except Exception as error:
        raise OracleError(f"original x86 execution trapped in case {case}: {error}") from error
    if bad or visited!=list(sorted(pe_boundaries))+[EXIT] or uc.reg_read(UC_X86_REG_EIP)!=EXIT:
        # list(sorted()) only correct for this proven straight-line CFG block.
        raise OracleError(f"Unicorn left verified linear geometry CFG in case {case}")
    expected_regs={name:uc.reg_read(reg)&0xffffffff for name,reg in registers.items()}
    final_eflags=uc.reg_read(UC_X86_REG_EFLAGS)
    final_ram=bytes(uc.mem_read(0x1000,FULL_RAM-0x1000))
    report={}
    for label,lib in libs.items():
        state=ctypes.create_string_buffer(initial_R,REG_SIZE)
        memory=ctypes.create_string_buffer(bytes(before),FULL_RAM)
        lib.execute_region(state,memory,START)
        if lib.result_pc()!=EXIT:
            raise OracleError(f"{label} guest PC mismatch case {case}: {lib.result_pc():08x}")
        for name,offset in REG_OFFSETS.items():
            value=int.from_bytes(state.raw[offset:offset+4],"little")
            if value!=expected_regs[name]:
                raise OracleError(f"{label} {name} mismatch case {case}")
        for name,(bit,offset) in FLAG_BITS.items():
            if state.raw[offset]!=((final_eflags>>bit)&1):
                raise OracleError(f"{label} {name} EFLAGS mismatch case {case}")
        expected_state=bytearray(initial_R)
        for name,offset in REG_OFFSETS.items():
            expected_state[offset:offset+4]=expected_regs[name].to_bytes(4,"little")
        for name,(bit,offset) in FLAG_BITS.items():
            expected_state[offset]=(final_eflags>>bit)&1
        if state.raw!=bytes(expected_state):
            raise OracleError(f"{label} wrote unexpected R architectural bytes in case {case}")
        after=memory.raw
        if after[0x1000:]!=final_ram:
            raise OracleError(f"{label} RAM exact-address mismatch in case {case}")
        report[label]=True
    # A true alias requires at least one write to address later read;
    # this counts execution order, not merely overlapping address ranges.
    seen_writes=set()
    aliased=False
    for kind,address,size in accesses:
        for off in range(address,address+size):
            if kind=="r" and off in seen_writes:aliased=True
            if kind=="w":seen_writes.add(off)
    return {
        "case":case,"scenario":case%len(ALIASES),
        "matched_versions":sorted(report),
        "reads":len(read_bytes),"writes":len(write_bytes),
        "read_after_write_alias":aliased,
        "mapped_memory_bytes":FULL_RAM,
        "final_pc":f"0x{EXIT:08x}",
    }


def main(argv:list[str]|None=None) -> int:
    cli=argparse.ArgumentParser(description=__doc__.splitlines()[0])
    cli.add_argument("--pe",type=Path,required=True)
    cli.add_argument("--pcode",type=Path,default=ROOT/"recomp_out/codsp.pcode")
    cli.add_argument("--map",type=Path,default=ROOT/"recomp_out/codsp_function_map_v2.json")
    cli.add_argument("--out",type=Path,required=True)
    cli.add_argument("--cases",type=int,default=40)
    args=cli.parse_args(argv)
    if not 5<=args.cases<=CASES_LIMIT:
        cli.error("case count outside [5,256]")
    try:
        require_private_path(args.pe,ROOT/".local/private")
        require_original_fingerprints(hashlib.sha256(args.pe.read_bytes()).hexdigest(),
                                      hashlib.sha256(args.pcode.read_bytes()).hexdigest())
        a,b=verify_inputs(args.pcode,args.map)
        require_ignored_output(args.out,ROOT)
        mapping=json.loads(args.map.read_text(encoding="utf-8"))
        insns,_userops,_funcs=parse(args.pcode)
        region=select_block(insns,mapping,FUNC,START)
        private_code=pe_code_and_edges(args.pe,region)
        boundaries={pc for pc,_n,_ops in region.instructions}
        # Explicitly keep x87 and the epilogue out of this small fast path.
        args.out.mkdir(parents=True,exist_ok=False)
        libraries={}
        for cache in (0,5):
            code,selected=generate_region_c(region,cache_count=cache,
                                            entry_policy="start_only",
                                            memory_model="exact")
            folder=args.out/f"cache_{cache}"
            folder.mkdir()
            source=folder/"private_region_exact.c"
            binary=folder/"private_region_exact.dll"
            source.write_text(code,encoding="utf-8")
            compile_host(source,binary)
            libraries[f"pcode_cache_{cache}"]=open_library(binary)
        checked=[]
        for case in range(args.cases):
            result=compare_state(case,private_code,libraries,boundaries)
            checked.append(result)
            if (case+1)%10==0:
                print("ORIGINAL_X86_REGION_CHECKED",case+1,flush=True)
        grouped={str(i):[x for x in checked if x["scenario"]==i] for i in ALIASES}
        result={
            "schema":"phase14c-real-original-x86-exact-RAM-oracle-v1",
            "source_sha256":hashlib.sha256(args.pe.read_bytes()).hexdigest(),
            "pcode_sha256":a,"map_sha256":b,
            "original_start_pc":f"0x{START:08x}",
            "original_exit_pc":f"0x{EXIT:08x}",
            "original_x86_instructions":COUNT,
            "memory_model":"EXACT guest 32-bit addresses, 24 MiB mapped; no modulo",
            "cases":args.cases,
            "tested_scenarios":{str(scenario):{
                "description":ALIASES[int(scenario)],
                "cases":len(rows),
                "read_after_write_alias_cases":sum(bool(x["read_after_write_alias"]) for x in rows),
                "guest_pc_and_GPR_and_5_EFLAGS_and_full_R_and_full_RAM_matched":True}
                for scenario,rows in grouped.items()},
            "x86_reference":"Unicorn executing CoDSP.exe ORIGINAL bytes, disassembly verified by Capstone",
            "variants":["original_project_pcode2c_uncached","project_pcode2c_cached_5_R_fields"],
            "all_passed":True,
            "checkpoints_not_proven":[
                "arbitrary guest memory outside mapped 24MiB",
                "other guest PCs and x87 precision/control/tag state",
                "AF and unsupported flags",
                "asynchronous interrupts and guest exceptions",
                "real-world load frequencies and CPU/frame reduction",
                "epilogue body: this oracle stops immediately upon jump to 0x00523CD9"],
            "engine_modified":False,
        }
        (args.out/"summary.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
        for key,data in result["tested_scenarios"].items():
            print("ORIGINAL_X86_ALIAS_CASES",key,data["cases"],
                  "actual_read_after_write",data["read_after_write_alias_cases"],flush=True)
        print("PHASE14C_ORIGINAL_X86_PASS",args.cases,flush=True)
        return 0
    except (OSError,ValueError,OracleError,RuntimeError) as exc:
        print("PHASE14C_ORIGINAL_X86_FAILED",exc,file=sys.stderr,flush=True)
        return 2

if __name__=="__main__":
    raise SystemExit(main())
