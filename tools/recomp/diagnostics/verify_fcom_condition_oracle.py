#!/usr/bin/env python3
"""Observe only x87 FCOMP condition flags using real PE bytes and Unicorn x86.

Compares C0/C1/C2/C3 against opt-in codsp_fcom.h candidate (NOT the whole
80-bit stack, FPSW status/control, or engine performance). No modifications to
Android, the original executable, or the generated game source are made.
"""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
from pathlib import Path
import random
import subprocess
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from verify_x86_prefix_oracle import (
    OracleError,require_private_path,require_ignored_output,
    require_original_fingerprints,MEM_BYTES
)

FLD_PC=0x41b960
FCOMP_PC=0x41b986
FCOMP_END=0x41b98c
COND_MASK=0x4700
FIXED_CASES=(
    (0x00000000,0x00000000),
    (0x3f800000,0x40000000),
    (0x40000000,0x3f800000),
    (0x3f800000,0x3f800000),
    (0xbf800000,0x3f800000),
    (0x7f800000,0x7f800000),
    (0xff800000,0x7f800000),
    (0x7fc12345,0x3f800000),
    (0x3f800000,0x7fc12345),
    (0x7f800001,0x3f800000),
    (0x3f800000,0x7f800001),
    (0x00000001,0x80000001),
    (0x80000000,0x00000000),
)


def operand_pairs(random_count: int) -> list[tuple[int,int]]:
    if random_count<0 or random_count>10000:
        raise OracleError("Invalid random case count")
    rng=random.Random(0x41b986)
    pairs=list(FIXED_CASES)
    for _ in range(random_count):
        def finite() -> int:
            return (rng.randrange(2)<<31)|(rng.randrange(1,255)<<23)|rng.getrandbits(23)
        pairs.append((finite(),finite()))
    return pairs


def validate_decoded_fcomp(fld,compare) -> None:
    if [(i.address,i.size,i.mnemonic) for i in fld]!=[(FLD_PC,6,"fld")]:
        raise OracleError("Unexpected x87 FLD bytes/source instruction")
    if [(i.address,i.size,i.mnemonic) for i in compare]!=[
        (FCOMP_PC,6,"fcomp")
    ]:
        raise OracleError("Unexpected original FCOMP instruction")


def source_wrapper() -> str:
    return """/* Local diagnostic only. No original game source or executable bytes. */
#define CODRECOMP_X87_FCOM_FASTPATH 1
#include "codsp_fcom.h"
__declspec(dllexport) uint16_t eval_fcom(uint32_t lhs, uint32_t rhs) {
    uint8_t R[0x1180]={0};
    uint8_t M[4]={0};
    wr(R+0x1100,10,d2f(f2d((u128)lhs,4),10));
    wr(M,4,rhs);
    codsp_fcom_pop_float32(R,M,0x41b986u,0);
    return (uint16_t)rd(R+0x10a2,2);
}
"""


def compare_pairs(fld_code: bytes, fcomp_code: bytes, lib,
                  pairs: list[tuple[int,int]]) -> dict:
    from unicorn import Uc,UC_ARCH_X86,UC_MODE_32
    from unicorn.x86_const import (
        UC_X86_REG_EBP,UC_X86_REG_EIP,UC_X86_REG_FPCW,
        UC_X86_REG_FPSW,UC_X86_REG_EFLAGS
    )
    matched=0
    unmatched=0
    native_invalid_op=0
    exceptions=0
    for lhs,rhs in pairs:
        u=Uc(UC_ARCH_X86,UC_MODE_32)
        u.mem_map(0x1000,MEM_BYTES-0x1000)
        u.mem_write(FLD_PC,fld_code)
        u.mem_write(FCOMP_PC,fcomp_code)
        u.mem_write(0x350000,lhs.to_bytes(4,"little"))
        u.mem_write(0x55b584,rhs.to_bytes(4,"little"))
        u.reg_write(UC_X86_REG_EBP,0x35010c)
        u.reg_write(UC_X86_REG_EFLAGS,2)
        u.reg_write(UC_X86_REG_FPCW,0x037f)
        try:
            # Initialize ST0 using actual x86 FLD, then execute the original
            # compare+pop without executing any intervening game instructions.
            u.emu_start(FLD_PC,0,count=1)
            u.emu_start(FCOMP_PC,0,count=1)
        except Exception as ex:
            raise OracleError(f"Unicorn FCOMP cannot execute: {ex}") from ex
        if u.reg_read(UC_X86_REG_EIP)!=FCOMP_END:
            raise OracleError("Original x86 compare did not reach expected PC")
        status=int(u.reg_read(UC_X86_REG_FPSW))
        actual=status&COND_MASK
        candidate=int(lib.eval_fcom(lhs,rhs))&COND_MASK
        native_invalid_op+=int(bool(status&1))
        if actual==candidate:
            matched+=1
        else:
            unmatched+=1
    return {
        "cases":len(pairs),
        "condition_flags_match":matched,
        "condition_flags_mismatch":unmatched,
        "native_status_IE_set_cases":native_invalid_op,
        "condition_mask":hex(COND_MASK),
        "status":"matched_observed_C_bits" if not unmatched else "condition_bit_mismatch",
        "important_limit":"Only C0/C1/C2/C3, not all x87 FSW, exception behavior, TOP or 80-bit stack"
    }


def main() -> int:
    p=argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--pe",required=True,type=Path)
    p.add_argument("--pcode",required=True,type=Path)
    p.add_argument("--compiler",required=True,type=Path)
    p.add_argument("--output",required=True,type=Path)
    p.add_argument("--random-cases",type=int,default=250)
    args=p.parse_args()
    try:
        import pefile
        from capstone import Cs,CS_ARCH_X86,CS_MODE_32
        root=Path.cwd()
        require_private_path(args.pe,root/".local/private")
        require_private_path(args.pcode,root/"recomp_out")
        require_ignored_output(args.output,root)
        require_original_fingerprints(
            hashlib.sha256(args.pe.read_bytes()).hexdigest(),
            hashlib.sha256(args.pcode.read_bytes()).hexdigest())
        if not args.compiler.is_file():
            raise OracleError("Missing LLVM-MinGW compiler")
        hdr=(root/"tools/recomp/runtime/codsp_fcom.h").read_text("utf8")
        if "#define CODSP_FCOM_GUARD(regs,mem,pc,addr) 0" not in hdr:
            raise OracleError("Default FCOM path is no longer OFF: stop the investigation")
        pe=pefile.PE(str(args.pe),fast_load=True)
        if pe.OPTIONAL_HEADER.ImageBase!=0x400000:
            raise OracleError("Unsupported original PE base")
        fld=pe.get_data(FLD_PC-0x400000,6)
        fcomp=pe.get_data(FCOMP_PC-0x400000,6)
        if len(fld)!=6 or len(fcomp)!=6:
            raise OracleError("Truncated FCOMP reference instructions")
        disasm=Cs(CS_ARCH_X86,CS_MODE_32)
        validate_decoded_fcomp(list(disasm.disasm(fld,FLD_PC)),
                               list(disasm.disasm(fcomp,FCOMP_PC)))
        pairs=operand_pairs(args.random_cases)
        args.output.mkdir(parents=True,exist_ok=False)
        c=args.output/"fcom_condition_oracle.c"
        dll=args.output/"fcom_condition_oracle.dll"
        c.write_text(source_wrapper(),encoding="utf8")
        command=[str(args.compiler),"-shared","-O1","-std=c11",
                 "-I"+str(root/"tools/recomp"),
                 "-I"+str(root/"tools/recomp/runtime"),
                 str(c),"-o",str(dll)]
        built=subprocess.run(command,text=True,capture_output=True,timeout=100)
        if built.returncode:
            raise OracleError("Could not compile FCOM candidate: "+built.stderr[:500])
        lib=ctypes.CDLL(str(dll.resolve()))
        lib.eval_fcom.argtypes=(ctypes.c_uint32,ctypes.c_uint32)
        lib.eval_fcom.restype=ctypes.c_uint16
        result=compare_pairs(fld,fcomp,lib,pairs)
        result["original_source_pinned"]=True
        result["candidate"]="codsp_fcom.h experimental fast path ON only inside local host DLL"
        result["android_fast_path_changed"]=False
        (args.output/"summary.json").write_text(
            json.dumps(result,indent=2)+"\n",encoding="utf8")
        print(json.dumps(result,indent=2))
        return 0 if result["condition_flags_mismatch"]==0 else 1
    except (OSError,OracleError,ValueError,ImportError,subprocess.TimeoutExpired) as ex:
        print("FCOM ORACLE ERROR:",str(ex),file=sys.stderr)
        return 2


if __name__=="__main__":
    raise SystemExit(main())
