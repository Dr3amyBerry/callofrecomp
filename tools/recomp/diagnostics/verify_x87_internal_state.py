#!/usr/bin/env python3
"""Independent x87 *intermediate* binary80 audit for CoDSP geometry.

Capstone-verified ORIGINAL user-supplied PE bytes run in Unicorn x86.
Unmodified pcode2c.Gen lowers the matching private Ghidra instructions into
isolated host DLLs, one per instruction checkpoint.

Compare numeric binary80 ST0 while x87 TOP is live; compare observed RAM,
GPR, exact guest PC. Native FPCW/FPSW/FPTAG are RECORDED but cannot be
equated to the project's R array without a proven semantic mapping.
Unknown or divergent binary80 intermediates fail the fidelity gate:
this tool NEVER patches the Android app or enables a fast path.

All proprietary source bytes, DLLs and detailed input cases must stay under
ignored .local/profiles. JSON includes only audit counts and hashes.
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
sys.path.insert(0,str(HERE))
sys.path.insert(0,str(HERE.parent))
from audit_hot_function import scan_pcode
from pcode2c import Gen,temporary_layout
from verify_x86_prefix_oracle import (
    OracleError, require_private_path, require_ignored_output,
    require_original_fingerprints, compile_lowering, REG_BYTES, MEM_BYTES
)
from verify_x87_window_oracle import (
    START,STOP,EXPECTED_INSNS,REG_OFFSETS,RAM_INPUTS,case_input_bits,
    read_verified_bytes
)

CHECKPOINTS=tuple(pc+size for pc,size,_name in EXPECTED_INSNS)
X87_ST0_OFFSET=0x1100
X87_ST0_SIZE=10
CONTROL_WORD=0x037f
MEMORY_WATCH=(0x31ffe0,0x100)


def verify_unicorn_fp_slot_encoding() -> int:
    # Synthetic x86 fld/fstp m80; this independently checks Unicorn FPn's
    # Python tuple representation against the x86's own m80 serialization.
    import struct
    from unicorn import Uc, UC_ARCH_X86, UC_MODE_32
    import unicorn.x86_const as X
    code=bytes.fromhex("d90500200000db3d00210000")
    input_bits=(0x3f800000,0xbf800000,0x3fc00000,0x00000000,
                0x80000000,0x00000001,0x7f7fffff,0x00800000,
                0x7f800000,0xff800000,0x7fc00001)
    for bits in input_bits:
        uc=Uc(UC_ARCH_X86,UC_MODE_32)
        uc.mem_map(0x1000,0x2000)
        uc.mem_write(0x1000,code)
        uc.mem_write(0x2000,struct.pack("<I",bits))
        uc.reg_write(X.UC_X86_REG_FPCW,CONTROL_WORD)
        uc.emu_start(0x1000,0x1006,count=1)
        top=(uc.reg_read(X.UC_X86_REG_FPSW)>>11)&7
        fields=uc.reg_read(getattr(X,"UC_X86_REG_FP"+str(top)))
        encoded=fp80_bytes(*fields)
        uc.emu_start(0x1006,0x100c,count=1)
        serialized=bytes(uc.mem_read(0x2100,X87_ST0_SIZE))
        if encoded!=serialized:
            raise OracleError("Unicorn physical FP slot disagrees with x86 FSTP m80")
    return len(input_bits)



def fp80_bytes(mantissa: int, signed_exp: int) -> bytes:
    """Convert Unicorn UC_X86_REG_FP<n> physical 80-bit slot to Intel bytes."""
    if not (0<=mantissa<(1<<64) and 0<=signed_exp<(1<<16)):
        raise OracleError("Malformed Unicorn x87 80-bit physical slot")
    return mantissa.to_bytes(8,"little")+signed_exp.to_bytes(2,"little")


def build_checkpoint_lowering(insns: list[dict], checkpoint: int) -> str:
    """Generate a real staged private C oracle from the current translator."""
    selected=[]
    for ins in insns:
        selected.append(ins)
        if ins["pc"]+ins["size"]==checkpoint:
            break
    if not selected or selected[-1]["pc"]+selected[-1]["size"]!=checkpoint:
        raise OracleError("Checkpoint is not an audited instruction boundary")
    if [(ins["pc"],ins["size"]) for ins in selected] != [
            (pc,size) for pc,size,_ in EXPECTED_INSNS[:len(selected)]]:
        raise OracleError("P-code no longer matches pinned x87 window")
    lines=[
        "/* PRIVATE TRANSLATION FROM LOCALLY OWNED CODSP PCODE: NEVER COMMIT. */",
        '#include "recomp_rt.h"',
        "uint8_t *MEM;",
        "uint8_t R[0x2000];",
        "uint8_t U[0x400000];",
        "uint32_t PC;",
        "int recomp_miss;",
        "__declspec(dllexport) uint32_t oracle_pc(void) { return PC; }",
        "__declspec(dllexport) void execute_prefix(uint8_t *regs, uint8_t *memory) {",
        "MEM=memory;",
        "memcpy(R,regs,sizeof(R));",
    ]
    gen=Gen({})
    for ins in selected:
        if not ins["ops"]:
            raise OracleError("Missing p-code operation in x87 window")
        gen.temp_offsets=temporary_layout(ins["ops"])
        if gen.temp_offsets is None:
            raise OracleError("Unproven p-code unique local temporary")
        lines.append(f" {{ uint8_t T[{max(1,len(gen.temp_offsets))}];")
        for mnemonic,out,args in ins["ops"]:
            if mnemonic in {"BRANCH","CBRANCH","BRANCHIND",
                            "CALL","CALLIND","RETURN","CALLOTHER"}:
                raise OracleError("Unexpected control or opaque op in x87 window")
            def no_jump(_value):
                raise OracleError("Unexpected x87 checkpoint branch")
            statement=gen.op(mnemonic,out,args,no_jump,None)
            if "unsupported(" in statement or "goto " in statement:
                raise OracleError("Non-equivalent p-code operation in x87 stage")
            lines.append(" "+statement)
        lines.append(" }")
    if gen.unsupported:
        raise OracleError("Unsupported p-code operation in x87 stage")
    lines.extend([
        f"PC=0x{checkpoint:x}u;",
        "memcpy(regs,R,sizeof(R));",
        "}",
    ])
    return "\n".join(lines)+"\n"


def seed_case(uc, host_regs, host_mem, case: int) -> list[tuple[int, bytes]]:
    """Same non-aliased deterministic float32 inputs as prior x87 output oracle."""
    from unicorn.x86_const import (
        UC_X86_REG_EAX,UC_X86_REG_ECX,UC_X86_REG_EDX,UC_X86_REG_EBX,
        UC_X86_REG_ESP,UC_X86_REG_EBP,UC_X86_REG_ESI,UC_X86_REG_EDI,
        UC_X86_REG_FPCW
    )
    ids=dict(zip(REG_OFFSETS,[
        UC_X86_REG_EAX,UC_X86_REG_ECX,UC_X86_REG_EDX,UC_X86_REG_EBX,
        UC_X86_REG_ESP,UC_X86_REG_EBP,UC_X86_REG_ESI,UC_X86_REG_EDI
    ]))
    rng=random.Random(0x41B960 ^ (case*0x9e3779b1))
    uc.reg_write(UC_X86_REG_FPCW,CONTROL_WORD)
    ctypes.memset(ctypes.addressof(host_regs),0,REG_BYTES)
    ctypes.memset(ctypes.addressof(host_mem),0,MEM_BYTES)
    for name,off in REG_OFFSETS.items():
        value={"ECX":0x350000,"EBP":0x35010c,
               "ESI":0x360000,"ESP":0x320000}.get(name,rng.getrandbits(32))
        uc.reg_write(ids[name],value)
        ctypes.memmove(ctypes.addressof(host_regs)+off,value.to_bytes(4,"little"),4)
    region_addr,length=MEMORY_WATCH
    stack=bytearray(rng.randbytes(length))
    memory={region_addr:stack}
    for address,bits in zip(RAM_INPUTS,case_input_bits(case)):
        content=bits.to_bytes(4,"little")
        if region_addr<=address<region_addr+length:
            offset=address-region_addr
            stack[offset:offset+4]=content
        else:
            memory[address]=bytearray(content)
    for address,data in memory.items():
        uc.mem_write(address,bytes(data))
        ctypes.memmove(ctypes.addressof(host_mem)+address,bytes(data),len(data))
    return [(address,bytes(data)) for address,data in memory.items()]


def audit_case(raw_code: bytes, checkpoint: int, library, case: int) -> dict:
    from unicorn import Uc,UC_ARCH_X86,UC_MODE_32
    import unicorn.x86_const as R

    uc=Uc(UC_ARCH_X86,UC_MODE_32)
    uc.mem_map(0x1000,MEM_BYTES-0x1000)
    uc.mem_write(START,raw_code)
    uc.reg_write(R.UC_X86_REG_EIP,START)
    regs=ctypes.create_string_buffer(REG_BYTES)
    mem=ctypes.create_string_buffer(MEM_BYTES)
    regions=seed_case(uc,regs,mem,case)
    count=CHECKPOINTS.index(checkpoint)+1
    try:
        uc.emu_start(START,checkpoint,timeout=500000,count=count)
    except Exception as e:
        raise OracleError(f"Unicorn x87 trap at checkpoint in case {case}: {e}") from e
    if uc.reg_read(R.UC_X86_REG_EIP)!=checkpoint:
        raise OracleError("Unicorn did not reach expected original checkpoint")
    if uc.reg_read(R.UC_X86_REG_FPCW)!=CONTROL_WORD:
        raise OracleError("Unicorn changed original x87 control word")
    library.execute_prefix(ctypes.cast(regs,ctypes.c_void_p),
                           ctypes.cast(mem,ctypes.c_void_p))
    if library.oracle_pc()!=checkpoint:
        raise OracleError("Translated p-code didn't reach checkpoint")
    reg_ids=(
        R.UC_X86_REG_EAX,R.UC_X86_REG_ECX,R.UC_X86_REG_EDX,
        R.UC_X86_REG_EBX,R.UC_X86_REG_ESP,R.UC_X86_REG_EBP,
        R.UC_X86_REG_ESI,R.UC_X86_REG_EDI,
    )
    gpr_ok=all(int.from_bytes(regs.raw[off:off+4],"little")==
               (uc.reg_read(register)&0xffffffff)
               for off,register in zip(REG_OFFSETS.values(),reg_ids))
    memory_ok=all(bytes(uc.mem_read(addr,len(initial)))==
                  ctypes.string_at(ctypes.addressof(mem)+addr,len(initial))
                  for addr,initial in regions)
    sw=uc.reg_read(R.UC_X86_REG_FPSW)
    top=(sw>>11)&7
    tag=uc.reg_read(R.UC_X86_REG_FPTAG)
    # UC_X86_REG_FPn: physical stack slot, tuple of significand and sign/exp.
    # None of these FPU metadata words has a proven exact R-array counterpart.
    x87_live=count < len(CHECKPOINTS)
    match=None
    mismatch_shape={}
    if x87_live:
        value=uc.reg_read(getattr(R,f"UC_X86_REG_FP{top}"))
        if not isinstance(value,tuple) or len(value)!=2:
            raise OracleError("Unicorn FP<n> did not expose physical binary80")
        expected=fp80_bytes(*value)
        actual=regs.raw[X87_ST0_OFFSET:X87_ST0_OFFSET+X87_ST0_SIZE]
        match=expected==actual
        if not match:
            original_sig=int.from_bytes(expected[:8],"little")
            translated_sig=int.from_bytes(actual[:8],"little")
            mismatch_shape={
                "signexp_match": expected[8:] == actual[8:],
                "upper53_significand_match": original_sig>>11==translated_sig>>11,
                "original_low11_nonzero": bool(original_sig&0x7ff),
                "translated_low11_zero": not bool(translated_sig&0x7ff),
            }
    return {
        "gpr_match":gpr_ok,
        "memory_match":memory_ok,
        "binary80_st0_live":x87_live,
        "binary80_st0_match":match,
        "binary80_mismatch_shape":mismatch_shape,
        "unicorn_status_word":sw,
        "unicorn_tag_word":tag,
    }


def make_report(insns: list[dict], original_code: bytes, checkpoint: int,
                library, cases: int) -> dict:
    """Aggregate without storing user game numeric inputs, bytes or FP payloads."""
    counts={"gpr_match":0,"memory_match":0,
            "binary80_match":0,"binary80_differ":0,"binary80_not_live":0,
            "unicorn_status_nonzero":0,"mismatch_signexp_match":0,
            "mismatch_upper53_significand_match":0,
            "mismatch_original_low11_nonzero":0,
            "mismatch_translated_low11_zero":0}
    for case in range(cases):
        row=audit_case(original_code,checkpoint,library,case)
        counts["gpr_match"]+=bool(row["gpr_match"])
        counts["memory_match"]+=bool(row["memory_match"])
        counts["binary80_match"]+=row["binary80_st0_match"] is True
        counts["binary80_differ"]+=row["binary80_st0_match"] is False
        counts["binary80_not_live"]+=not row["binary80_st0_live"]
        counts["unicorn_status_nonzero"]+=bool(row["unicorn_status_word"])
        for key,value in row["binary80_mismatch_shape"].items():
            counts["mismatch_"+key]+=bool(value)
    return {
        "end_pc_exclusive":f"0x{checkpoint:08x}",
        "original_instructions":CHECKPOINTS.index(checkpoint)+1,
        "cases":cases,"counts":counts,
        "checks":("Unicorn original x87 physical TOP ST0 binary80 when live; "
                  "GPR, PC, watched RAM"),
        "status":"binary80_equal_in_tested_cases" if counts["binary80_differ"]==0
                and counts["gpr_match"]==cases and counts["memory_match"]==cases
                else "mismatch_or_incomplete",
        "warning":("FPCW/FPSW/FPTAG recorded on original x86 ONLY, "
                   "no original-to-translator state equivalence claimed"),
    }


def st0_fidelity_gate(checkpoints: list[dict], cases: int) -> bool:
    # This is ONLY the live ST0 binary80 GPR/RAM checkpoint gate, not
    # equivalence of all x87 control/status/tag words or exceptions.
    if cases<=0 or not checkpoints:
        return False
    live_found=False
    for entry in checkpoints:
        counts=entry["counts"]
        if counts["gpr_match"]!=cases or counts["memory_match"]!=cases:
            return False
        if counts["binary80_differ"]>0:
            return False
        live=cases-counts["binary80_not_live"]
        if live:
            live_found=True
            if counts["binary80_match"]!=live:
                return False
    return live_found


def main(argv: list[str] | None=None) -> int:
    ap=argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pe",required=True,type=Path)
    ap.add_argument("--pcode",required=True,type=Path)
    ap.add_argument("--compiler",required=True,type=Path)
    ap.add_argument("--output",required=True,type=Path)
    ap.add_argument("--cases",type=int,default=128)
    ap.add_argument("--require-bitwise-st0",action="store_true",
                    help="fail closed when any live binary80 ST0 differs")
    args=ap.parse_args(argv)
    if not 1<=args.cases<=4096:
        ap.error("--cases outside safe [1,4096]")
    try:
        for module in ("unicorn","capstone","pefile"):
            __import__(module)
        root=Path.cwd()
        require_private_path(args.pe,root/".local/private")
        require_private_path(args.pcode,root/"recomp_out")
        require_ignored_output(args.output,root)
        require_original_fingerprints(
            hashlib.sha256(args.pe.read_bytes()).hexdigest(),
            hashlib.sha256(args.pcode.read_bytes()).hexdigest())
        if not args.compiler.is_file():
            raise OracleError("Verified local LLVM-MinGW compiler missing")
        selftest=verify_unicorn_fp_slot_encoding()
        print("FPU_PHYSICAL_SLOT_SELFTEST",selftest,"synthetic FSTP m80 cases",flush=True)
        insns=scan_pcode(args.pcode,[(START,STOP-1)])
        raw_code=read_verified_bytes(args.pe,insns)
        args.output.mkdir(parents=True,exist_ok=False)
        checkpoints=[]
        for checkpoint in CHECKPOINTS:
            source=build_checkpoint_lowering(insns,checkpoint)
            suffix=f"{checkpoint:08x}"
            source_path=args.output/f"translated_private_{suffix}.c"
            dll_path=args.output/f"translated_private_{suffix}.dll"
            source_path.write_text(source,encoding="utf-8")
            compile_lowering(source_path,dll_path,args.compiler,root/"tools/recomp")
            lib=ctypes.CDLL(str(dll_path.resolve()))
            lib.execute_prefix.argtypes=(ctypes.c_void_p,ctypes.c_void_p)
            lib.execute_prefix.restype=None
            lib.oracle_pc.argtypes=()
            lib.oracle_pc.restype=ctypes.c_uint32
            report=make_report(insns,raw_code,checkpoint,lib,args.cases)
            checkpoints.append(report)
            print("ORACLE_BINARY80",report["end_pc_exclusive"],
                  "tests",args.cases,
                  "binary80_matches",report["counts"]["binary80_match"],
                  "binary80_differences",report["counts"]["binary80_differ"],
                  "GPR_matches",report["counts"]["gpr_match"],
                  "RAM_matches",report["counts"]["memory_match"],
                  flush=True)
        result={
            "schema":"callofrecomp-original-x87-binary80-intermediate-v1",
            "window":[f"0x{START:08x}",f"0x{STOP:08x}"],
            "identity":{"pe_sha256":hashlib.sha256(args.pe.read_bytes()).hexdigest(),
                        "pcode_sha256":hashlib.sha256(args.pcode.read_bytes()).hexdigest()},
            "control_word_original":f"0x{CONTROL_WORD:04x}",
            "case_count_per_checkpoint":args.cases,
            "unicorn_fp_slot_selftest_passed":selftest,
            "checkpoints":checkpoints,
            "binary80_all_live_checkpoints_equal":all(x["counts"]["binary80_differ"]==0 for x in checkpoints),
            "live_ST0_binary80_fidelity_gate":("PASS" if st0_fidelity_gate(checkpoints,args.cases) else "FAIL"),
            "full_fpu_state_equivalent":False,
            "engine_modified":False,
            "limitations":[
                "FPCW/FPSW/FPTAG have no independently proven pcode R mapping",
                "Only ST0 binary80 when live; not all x87 physical stack registers",
                "Original x87 default precision, no alternate rounding/exceptions",
                "Non-aliased selected input memory, not full game function",
                "No Android ARM64 or TECNO frames profiled",
            ]
        }
        (args.output/"summary.json").write_text(
            json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8")
        print("AUDIT_SUMMARY",args.output/"summary.json",flush=True)
        if args.require_bitwise_st0 and not st0_fidelity_gate(checkpoints,args.cases):
            print("ST0_BINARY80_GATE_FAILED: original and translated numerical states differ",
                  file=sys.stderr)
            return 4
        return 0 if all(c["counts"]["gpr_match"]==args.cases and
                        c["counts"]["memory_match"]==args.cases
                        for c in checkpoints) else 3
    except (OSError,ValueError,OracleError,ImportError) as e:
        print("AUDIT_FAILED",str(e),file=sys.stderr)
        return 2


if __name__=="__main__":
    raise SystemExit(main())
