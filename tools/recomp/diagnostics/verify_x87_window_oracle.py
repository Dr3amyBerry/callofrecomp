#!/usr/bin/env python3
"""Bounded x87 guest-output oracle, Unicorn x86 vs real private pcode2c lowering.

Checks one 5-instruction x87 window's observed float32 memory result, PC,
general registers and input memory. It does NOT claim binary80/FSW equivalence.
Commercial PE, p-code and translated C/DLL stay strictly under ignored local
directories. Not an ARM64 fast path and does not modify the installed game.
"""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
from pathlib import Path
import random
import struct
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
sys.path.insert(0,str(HERE.parent))
from audit_hot_function import scan_pcode
from pcode2c import Gen,temporary_layout
from verify_x86_prefix_oracle import (
    OracleError, require_private_path, require_ignored_output,
    require_original_fingerprints, compile_lowering, MEM_BYTES, REG_BYTES
)

START=0x0041B960
STOP=0x0041B973
EXPECTED_INSNS=[
    (0x41b960,6,"fld"),
    (0x41b966,2,"fsub"),
    (0x41b968,4,"fmul"),
    (0x41b96c,3,"fsub"),
    (0x41b96f,4,"fstp"),
]
RAM_INPUTS=(0x350000,0x360000,0x320024,0x35010c)
RAM_OUTPUT=0x320010
REG_OFFSETS={"EAX":0,"ECX":4,"EDX":8,"EBX":12,"ESP":16,"EBP":20,"ESI":24,"EDI":28}


def validate_x87_instruction_layout(insns: list[dict]) -> None:
    if [(i["pc"],i["size"]) for i in insns]!=[
        (pc,size) for pc,size,_ in EXPECTED_INSNS
    ]:
        raise OracleError("Unexpected x87 window p-code instruction bounds")
    if any(not i["ops"] for i in insns):
        raise OracleError("Missing x87 window p-code instruction operations")


def read_verified_bytes(pe_path: Path, insns: list[dict]) -> bytes:
    import pefile
    from capstone import Cs,CS_ARCH_X86,CS_MODE_32
    validate_x87_instruction_layout(insns)
    pe=pefile.PE(str(pe_path),fast_load=True)
    if pe.OPTIONAL_HEADER.ImageBase!=0x400000:
        raise OracleError("Unsupported original PE base")
    code=pe.get_data(START-0x400000,STOP-START)
    if len(code)!=STOP-START:
        raise OracleError("Truncated original x87 instruction bytes")
    decoded=list(Cs(CS_ARCH_X86,CS_MODE_32).disasm(code,START))
    if [(i.address,i.size,i.mnemonic) for i in decoded]!=EXPECTED_INSNS:
        raise OracleError("Original x86 bytes differ from approved x87 window")
    return code


def generate_x87_lowering(insns: list[dict]) -> str:
    validate_x87_instruction_layout(insns)
    generator=Gen({})
    result=[
        "/* PRIVATE GENERATED FROM USER-SUPPLIED CoDSP p-code. DO NOT COMMIT. */",
        '#include "recomp_rt.h"',
        "uint8_t *MEM;",
        "uint8_t R[0x2000];",
        "uint8_t U[0x400000];",
        "uint32_t PC;",
        "int recomp_miss;",
        "__declspec(dllexport) uint32_t prefix_result_pc(void) {return PC;}",
        "__declspec(dllexport) void execute_prefix(uint8_t *regs,uint8_t *memory) {",
        "MEM=memory;",
        "memcpy(R,regs,sizeof(R));",
    ]
    for i in insns:
        generator.temp_offsets=temporary_layout(i["ops"])
        if generator.temp_offsets is None:
            raise OracleError("Unproven unique temporary input")
        result.append(f"{{ uint8_t T[{max(1,len(generator.temp_offsets))}];")
        for mn,out,args in i["ops"]:
            if mn in {"BRANCH","CBRANCH","RETURN","BRANCHIND","CALL","CALLIND"}:
                raise OracleError("Control transfer in x87 linear window")
            generated=generator.op(
                mn,out,args,lambda _: (_ for _ in ()).throw(
                    OracleError("Unexpected jump")),None)
            if "unsupported(" in generated or "goto " in generated:
                raise OracleError("Unsupported x87 p-code in this bounded oracle")
            result.append(generated)
        result.append("}")
    if generator.unsupported:
        raise OracleError("Unsupported operations generated")
    result.extend([f"PC=0x{STOP:x}u;","memcpy(regs,R,sizeof(R));","}"])
    return "\n".join(result)+"\n"


def case_input_bits(case: int) -> tuple[int,int,int,int]:
    if case<16:
        exact=(0.0,1.0,-1.0,0.5,-0.5,2.0,-2.0,8.0,-8.0,
               3.5,-3.5,1.0e-10,-1.0e-10,1.0e10,-1.0e10,-0.0)
        return tuple(struct.unpack("<I",struct.pack("<f",
                     exact[(case+i)%len(exact)]))[0] for i in range(4))
    rng=random.Random(0x41b960+case*719)
    def one() -> int:
        # Finite single-precision values; intentionally exclude NaN, Inf,
        # denormals and non-default x87 control modes from a PASS claim.
        exponent=rng.randrange(115,141)
        return (rng.randrange(2)<<31)|(exponent<<23)|rng.getrandbits(23)
    return one(),one(),one(),one()


def compare_one_case(code: bytes,library,case: int) -> None:
    from unicorn import Uc,UC_ARCH_X86,UC_MODE_32
    from unicorn.x86_const import (
        UC_X86_REG_EAX,UC_X86_REG_EBX,UC_X86_REG_ECX,UC_X86_REG_EDX,
        UC_X86_REG_ESP,UC_X86_REG_EBP,UC_X86_REG_ESI,UC_X86_REG_EDI,
        UC_X86_REG_EIP,UC_X86_REG_FPCW
    )
    ids=dict(zip(REG_OFFSETS,[
        UC_X86_REG_EAX,UC_X86_REG_ECX,UC_X86_REG_EDX,UC_X86_REG_EBX,
        UC_X86_REG_ESP,UC_X86_REG_EBP,UC_X86_REG_ESI,UC_X86_REG_EDI
    ]))
    rng=random.Random(0x41B960 ^ (case*0x9e3779b1))
    uc=Uc(UC_ARCH_X86,UC_MODE_32)
    uc.mem_map(0x1000,MEM_BYTES-0x1000)
    uc.mem_write(START,code)
    uc.reg_write(UC_X86_REG_FPCW,0x37f)
    uc.reg_write(UC_X86_REG_EIP,START)
    regs=ctypes.create_string_buffer(REG_BYTES)
    ram=ctypes.create_string_buffer(MEM_BYTES)
    input_registers={}
    for name,off in REG_OFFSETS.items():
        val={"ECX":0x350000,"EBP":0x35010c,"ESI":0x360000,"ESP":0x320000}.get(
            name,rng.getrandbits(32))
        input_registers[name]=val
        uc.reg_write(ids[name],val)
        ctypes.memmove(ctypes.addressof(regs)+off,val.to_bytes(4,"little"),4)

    # Randomize a surrounding stack span, not only the destination, to
    # detect unintended stores outside the final float32 output.
    region_addr=0x31ffe0
    region=bytearray(rng.randbytes(0x100))
    regions={region_addr:region}
    bits=case_input_bits(case)
    # In this subblock all four scalar inputs are non-aliased mapped bytes.
    for address,raw in zip(RAM_INPUTS,bits):
        data=raw.to_bytes(4,"little")
        if region_addr<=address<region_addr+len(region):
            offset=address-region_addr
            region[offset:offset+4]=data
        else:
            regions[address]=bytearray(data)
    for address,blob in regions.items():
        uc.mem_write(address,bytes(blob))
        ctypes.memmove(ctypes.addressof(ram)+address,bytes(blob),len(blob))

    try:
        uc.emu_start(START,STOP,timeout=500000,count=len(EXPECTED_INSNS))
    except Exception as ex:
        raise OracleError(f"Unicorn x87 trap in case {case}: {ex}") from ex
    library.execute_prefix(ctypes.cast(regs,ctypes.c_void_p),
                           ctypes.cast(ram,ctypes.c_void_p))
    if (uc.reg_read(UC_X86_REG_EIP)!=STOP or
        library.prefix_result_pc()!=STOP):
        raise OracleError(f"PC mismatch in x87 case {case}")
    for name,offset in REG_OFFSETS.items():
        actual=int.from_bytes(regs.raw[offset:offset+4],"little")
        expected=uc.reg_read(ids[name])&0xffffffff
        if actual!=expected:
            raise OracleError(f"General-purpose register mismatch in case {case}")
    for address,original in regions.items():
        expected=bytes(uc.mem_read(address,len(original)))
        observed=ctypes.string_at(ctypes.addressof(ram)+address,len(original))
        if expected!=observed:
            raise OracleError(f"x87 memory output mismatch in case {case}")


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--pe",required=True,type=Path)
    parser.add_argument("--pcode",required=True,type=Path)
    parser.add_argument("--compiler",required=True,type=Path)
    parser.add_argument("--output",required=True,type=Path)
    parser.add_argument("--cases",type=int,default=256)
    args=parser.parse_args()
    if not 1<=args.cases<=4096:
        parser.error("cases must be between 1 and 4096")
    try:
        for dep in ("unicorn","capstone","pefile"):
            __import__(dep)
        root=Path.cwd()
        require_private_path(args.pe,root/".local/private")
        require_private_path(args.pcode,root/"recomp_out")
        require_ignored_output(args.output,root)
        pe_hash=hashlib.sha256(args.pe.read_bytes()).hexdigest()
        pcode_hash=hashlib.sha256(args.pcode.read_bytes()).hexdigest()
        require_original_fingerprints(pe_hash,pcode_hash)
        if not args.compiler.is_file():
            raise OracleError("Missing LLVM-MinGW host compiler")
        insns=scan_pcode(args.pcode,[(START,STOP-1)])
        code=read_verified_bytes(args.pe,insns)
        translated=generate_x87_lowering(insns)
        args.output.mkdir(parents=True,exist_ok=False)
        src=args.output/"translated_private_x87.c"
        dll=args.output/"translated_private_x87.dll"
        src.write_text(translated,encoding="utf8")
        compile_lowering(src,dll,args.compiler,root/"tools/recomp")
        library=ctypes.CDLL(str(dll.resolve()))
        library.execute_prefix.argtypes=(ctypes.c_void_p,ctypes.c_void_p)
        library.execute_prefix.restype=None
        library.prefix_result_pc.argtypes=()
        library.prefix_result_pc.restype=ctypes.c_uint32
        for case in range(args.cases):
            compare_one_case(code,library,case)
        report={
            "window_exclusive":[hex(START),hex(STOP)],
            "original_x86_instructions":len(insns),
            "cases":args.cases,
            "float32_output_bitwise_matches":args.cases,
            "source_pe_sha256":pe_hash,
            "source_pcode_sha256":pcode_hash,
            "verified":["unmodified GPRs","output float32 bytes and nearby stack",
                        "no changes to four input scalars","guest EIP and translated PC"],
            "excluded":["x87 binary80 internal registers/stack",
                        "x87 status/control word and exceptions",
                        "AF/flags, NaN/Inf/denormal tests",
                        "full function, general aliasing, ARM64 speed, TECNO FPS"],
            "status":"passed",
            "game_runtime_patched":False
        }
        (args.output/"summary.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf8")
        print(json.dumps(report,indent=2))
        return 0
    except (OSError,ValueError,OracleError,ImportError) as ex:
        print("x87 ORACLE FAILED:",str(ex),file=sys.stderr)
        return 2


if __name__=="__main__":
    raise SystemExit(main())
