"""Phase14B: two-path independent x86/translated-C state oracle for CoDSP.

Extends the audited 20-instruction prefix into the first seven x86 instructions
of the taken branch at 0x41bce0. Both paths terminate BEFORE any x87 instruction.
The actual x86 bytes are executed in Unicorn; the other side is translated
using pcode2c.Gen. No user game bytes, private C, or DLL may enter Git.
"""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
from pathlib import Path
import random
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent))

from audit_hot_function import scan_pcode
from pcode2c import Gen, temporary_layout
from verify_x86_prefix_oracle import (
    OracleError, START, STOP, BRANCH_TARGET, REG_OFFSETS, FLAG_BITS,
    REG_BYTES, MEM_BYTES, require_original_fingerprints,
    require_private_path, require_ignored_output, decode_and_validate,
    generate_lowering, compile_lowering, trial_inputs
)

TAKEN_END = 0x0041BCF5
TAKEN_EXPECTED = (
    (0x0041BCE0,4,"lea"),
    (0x0041BCE4,2,"xor"),
    (0x0041BCE6,2,"sub"),
    (0x0041BCE8,4,"mov"),
    (0x0041BCEC,4,"mov"),
    (0x0041BCF0,2,"mov"),
    (0x0041BCF2,3,"lea"),
)
CONTROL = frozenset({"BRANCH","CBRANCH","CALL","RETURN","BRANCHIND","CALLIND"})
ARCH_OBSERVED = (frozenset(byte for off in REG_OFFSETS.values()
                             for byte in range(off, off + 4))
                 | frozenset(offset for _name, (_bit, offset) in FLAG_BITS.items()))


def verify_taken_layout(pe_path: Path, insns: list[dict]) -> bytes:
    """Pin each PE instruction size, start and mnemonic independently."""
    from capstone import Cs, CS_ARCH_X86, CS_MODE_32
    import pefile
    expected=[(pc,sz,mn) for pc,sz,mn in TAKEN_EXPECTED]
    if [(ins["pc"],ins["size"]) for ins in insns] != [
            (pc,sz) for pc,sz,_ in expected]:
        raise OracleError("Taken branch is not the verified seven-instruction window")
    if any(not ins["ops"] for ins in insns):
        raise OracleError("Missing p-code in branch continuation")
    original=pefile.PE(str(pe_path),fast_load=True)
    if original.OPTIONAL_HEADER.ImageBase != 0x400000:
        raise OracleError("Wrong original CoDSP PE base")
    data=original.get_data(BRANCH_TARGET-0x400000,TAKEN_END-BRANCH_TARGET)
    if len(data)!=TAKEN_END-BRANCH_TARGET:
        raise OracleError("Truncated taken branch bytes")
    decoder=Cs(CS_ARCH_X86,CS_MODE_32)
    decoded=list(decoder.disasm(data,BRANCH_TARGET))
    if [(ins.address,ins.size,ins.mnemonic) for ins in decoded]!=expected:
        raise OracleError("Capstone differs from verified x86 branch layout")
    return data


def generate_two_path_lowering(prefix: list[dict], taken: list[dict]) -> str:
    """Derive both arms from real pcode2c.Gen, preserving original prefix."""
    # Existing bounded generator emits PC=TAKEN_START; goto oracle_exit.
    base=generate_lowering(prefix)
    branch=f"PC=0x{BRANCH_TARGET:x}u; goto oracle_exit;"
    if base.count(branch)!=1 or base.count("oracle_exit:")!=1:
        raise OracleError("Original prefix translation no longer has exact expected branch")
    branch_statements=[]
    gen=Gen({})
    for original in taken:
        gen.temp_offsets=temporary_layout(original["ops"])
        if gen.temp_offsets is None:
            raise OracleError("Uninitialized local p-code temporary")
        branch_statements.append(" {")
        branch_statements.append(f" uint8_t T[{max(1,len(gen.temp_offsets))}];")
        for mnemonic,out,args in original["ops"]:
            if mnemonic in CONTROL or mnemonic=="CALLOTHER":
                raise OracleError("Unexpected control/opaque operation in taken branch")
            def forbidden(_):
                raise OracleError("Unexpected nested branch in continuation")
            statement=gen.op(mnemonic,out,args,forbidden,None)
            if "unsupported(" in statement or "goto " in statement:
                raise OracleError("Unverifiable translation in taken branch")
            branch_statements.append(" "+statement)
        branch_statements.append(" }")
    if gen.unsupported:
        raise OracleError("Unsupported p-code in taken continuation")
    branch_code="\n".join(branch_statements)
    marker="oracle_exit:"
    base=base.replace(branch,"goto oracle_taken;",1)
    body=f"goto oracle_exit;\noracle_taken:\n{branch_code}\nPC=0x{TAKEN_END:x}u;\n{marker}"
    return base.replace(marker,body,1)


def compare_case(prefix_code: bytes, taken_code: bytes, library, case: int) -> bool:
    """Check both arms against actual x86 without leaving verified windows."""
    from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
    from unicorn.x86_const import (
        UC_X86_REG_EIP, UC_X86_REG_EFLAGS, UC_X86_REG_EAX, UC_X86_REG_ECX,
        UC_X86_REG_EDX, UC_X86_REG_EBX, UC_X86_REG_ESP, UC_X86_REG_EBP,
        UC_X86_REG_ESI, UC_X86_REG_EDI
    )
    regs_x86=dict(zip(REG_OFFSETS,(
        UC_X86_REG_EAX,UC_X86_REG_ECX,UC_X86_REG_EDX,UC_X86_REG_EBX,
        UC_X86_REG_ESP,UC_X86_REG_EBP,UC_X86_REG_ESI,UC_X86_REG_EDI
    )))
    initial, eflags, memory=trial_inputs(case)
    unicorn=Uc(UC_ARCH_X86,UC_MODE_32)
    unicorn.mem_map(0x1000,MEM_BYTES-0x1000)
    unicorn.mem_write(START,prefix_code)
    unicorn.mem_write(BRANCH_TARGET,taken_code)
    unicorn.reg_write(UC_X86_REG_EIP,START)
    unicorn.reg_write(UC_X86_REG_EFLAGS,eflags)
    rng=random.Random(0x14b002 ^ (case*0x9e3779b1))
    arch=ctypes.create_string_buffer(REG_BYTES)
    expected_initial=bytearray(rng.randbytes(REG_BYTES))
    ctypes.memmove(ctypes.addressof(arch),bytes(expected_initial),REG_BYTES)
    guest=ctypes.create_string_buffer(MEM_BYTES)
    for name,offset in REG_OFFSETS.items():
        value=initial[name]
        unicorn.reg_write(regs_x86[name],value)
        data=value.to_bytes(4,"little")
        ctypes.memmove(ctypes.addressof(arch)+offset,data,4)
        expected_initial[offset:offset+4]=data
    for name,(bit,offset) in FLAG_BITS.items():
        b=(eflags>>bit)&1
        arch[offset]=bytes((b,))
        expected_initial[offset]=b
    for address,data in memory:
        unicorn.mem_write(address,data)
        ctypes.memmove(ctypes.addressof(guest)+address,data,len(data))
    allowed={START,STOP,TAKEN_END}
    # Approved address set includes every independently audited x86 boundary.
    # We must not execute memory after the exit markers.
    from capstone import Cs,CS_ARCH_X86,CS_MODE_32
    dis=Cs(CS_ARCH_X86,CS_MODE_32)
    allowed.update(ins.address for ins in dis.disasm(prefix_code,START))
    allowed.update(pc for pc,_size,_mn in TAKEN_EXPECTED)
    allowed.add(TAKEN_END)
    visited=[]
    bad=[]
    def hook(uc,address,size,_user):
        visited.append(address)
        if address not in allowed:
            bad.append(address)
            uc.emu_stop()
        elif address in (STOP,TAKEN_END):
            uc.emu_stop()
    unicorn.hook_add(UC_HOOK_CODE,hook)
    try:
        unicorn.emu_start(START,0,timeout=500000,count=40)
    except Exception as ex:
        raise OracleError(f"x86 trap in case {case}: {ex}") from ex
    expected_pc=TAKEN_END if case%2==0 else STOP
    if bad or not visited or visited[-1]!=expected_pc or unicorn.reg_read(UC_X86_REG_EIP)!=expected_pc:
        raise OracleError(f"x86 left audited paths in case {case} (no PC/code leak)")
    library.execute_prefix(ctypes.cast(arch,ctypes.c_void_p),
                           ctypes.cast(guest,ctypes.c_void_p))
    if library.prefix_result_pc()!=expected_pc:
        raise OracleError(f"translated PC differs in case {case}")
    for name,reg in regs_x86.items():
        actual=int.from_bytes(arch.raw[REG_OFFSETS[name]:REG_OFFSETS[name]+4],"little")
        if actual!=unicorn.reg_read(reg)&0xffffffff:
            raise OracleError(f"general-purpose register mismatch in case {case}: {name}")
    for name,(bit,offset) in FLAG_BITS.items():
        if arch.raw[offset]!=(unicorn.reg_read(UC_X86_REG_EFLAGS)>>bit)&1:
            raise OracleError(f"flag mismatch in case {case}: {name}")
    for address,data in memory:
        oracle=bytes(unicorn.mem_read(address,len(data)))
        observed=ctypes.string_at(ctypes.addressof(guest)+address,len(data))
        if oracle!=observed:
            raise OracleError(f"memory mismatch in bounded region in case {case}")
    # The translator may materialize supported register flags only. Verify
    # that adjacent byte padding and all unrelated architectural slots remain
    # unchanged, not just that the observed outputs matched.
    for i,(before,after) in enumerate(zip(expected_initial,arch.raw)):
        if i not in ARCH_OBSERVED and before!=after:
            raise OracleError(f"unobserved architectural byte changed in case {case}")
    return expected_pc==TAKEN_END


def main(argv: list[str] | None=None) -> int:
    parser=argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--pe",required=True,type=Path)
    parser.add_argument("--pcode",required=True,type=Path)
    parser.add_argument("--compiler",required=True,type=Path)
    parser.add_argument("--output",required=True,type=Path)
    parser.add_argument("--cases",type=int,default=512)
    args=parser.parse_args(argv)
    if not 2<=args.cases<=4096:
        parser.error("Need 2 to 4096 even/odd cases")
    try:
        for dep in ("unicorn","capstone","pefile"):
            __import__(dep)
        root=Path.cwd()
        require_private_path(args.pe,root/".local/private")
        require_private_path(args.pcode,root/"recomp_out")
        require_ignored_output(args.output,root)
        require_original_fingerprints(hashlib.sha256(args.pe.read_bytes()).hexdigest(),
                                      hashlib.sha256(args.pcode.read_bytes()).hexdigest())
        if not args.compiler.is_file():
            raise OracleError("Missing LLVM-MinGW compiler")
        head=scan_pcode(args.pcode,[(START,STOP-1)])
        branch=scan_pcode(args.pcode,[(BRANCH_TARGET,TAKEN_END-1)])
        code_head, count=decode_and_validate(args.pe,head)
        code_branch=verify_taken_layout(args.pe,branch)
        translated=generate_two_path_lowering(head,branch)
        args.output.mkdir(parents=True,exist_ok=False)
        src=args.output/"translated_private_branch.c"
        dll=args.output/"translated_private_branch.dll"
        src.write_text(translated,encoding="utf-8")
        compile_lowering(src,dll,args.compiler,root/"tools/recomp")
        lib=ctypes.CDLL(str(dll.resolve()))
        lib.execute_prefix.argtypes=(ctypes.c_void_p,ctypes.c_void_p)
        lib.execute_prefix.restype=None
        lib.prefix_result_pc.argtypes=()
        lib.prefix_result_pc.restype=ctypes.c_uint32
        taken_count=0
        for case in range(args.cases):
            taken_count+=int(compare_case(code_head,code_branch,lib,case))
        if not 0<taken_count<args.cases:
            raise OracleError("Not both control paths exercised")
        report={
            "schema":"phase14b-two-path-independent-x86-v1",
            "oracle":"Unicorn x86 32-bit original private CoDSP PE",
            "translator":"project pcode2c.Gen translated host DLL",
            "source_sha256":hashlib.sha256(args.pe.read_bytes()).hexdigest(),
            "pcode_sha256":hashlib.sha256(args.pcode.read_bytes()).hexdigest(),
            "original_x86_instructions_per_path":{
                "not_taken":count,"taken":count+len(TAKEN_EXPECTED)},
            "paths_terminated_exclusive":{
                "not_taken":f"0x{STOP:x}","taken":f"0x{TAKEN_END:x}"},
            "cases":args.cases,"taken":taken_count,"not_taken":args.cases-taken_count,
            "checked":["8 x86 GPRs","CF PF ZF SF OF","original branch PC",
                       "3 mapped RAM regions and stack bytes",
                       "R 0x2000 untouched bytes excluding supported GPRs/flags"],
            "not_checked":["AF (not emitted by this translator)",
                           "x87 because tested paths end BEFORE first x87 instruction",
                           "full game function/other control branches",
                           "arbitrary memory alias and unmapped guest RAM",
                           "CPU/frame performance on TECNO"],
            "status":"passed","engine_unchanged":True,
        }
        (args.output/"summary.json").write_text(
            json.dumps(report,indent=2)+"\n",encoding="utf-8")
        print(json.dumps(report,indent=2),flush=True)
        return 0
    except (OSError,ValueError,OracleError) as error:
        print("PHASE14B_BOUND_ORACLE_FAILED",str(error),file=sys.stderr)
        return 2


if __name__=="__main__":
    raise SystemExit(main())
