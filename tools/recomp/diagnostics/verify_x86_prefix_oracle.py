#!/usr/bin/env python3
"""Independent x86 differential oracle for one linear CoDSP hot-function prefix.

Only private, user-provided CoDSP.exe / Ghidra p-code may be used for live runs.
The generated translation C/DLL, emulator inputs and trace belong in ignored
.local/profiles. No proprietary bytes/translated statements are written to Git.
Does NOT alter the Android app, build configuration, source p-code or saves.

Unicorn x86 executes actual PE instruction bytes; the other side executes
a host-compiled lowering from the project's current pcode2c.Gen.
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
sys.path.insert(0,str(HERE.parent))
from audit_hot_function import scan_pcode
from pcode2c import Gen,temporary_layout

# Verified, version-specific hashes. An unknown game executable or p-code
# export must not accidentally receive a PASS from this narrow oracle.
EXPECTED_PE_SHA256="c755c7da411c87039ade462a2299402c3c4ca5c4fc4f1ae5cea6e25b05c69f47"
EXPECTED_PCODE_SHA256="36f9093b386e03b4bcdc489cff2a708f7c0b8012e9a0fa78a7001bd3f125da1e"

START=0x0041B8F0
STOP=0x0041B941  # exclusive; includes first conditional jump (last instruction)
BRANCH_TARGET=0x0041BCE0
REG_OFFSETS={"EAX":0,"ECX":4,"EDX":8,"EBX":12,
             "ESP":16,"EBP":20,"ESI":24,"EDI":28}
FLAG_BITS={"CF":(0,0x200),"PF":(2,0x202),"ZF":(6,0x206),
           "SF":(7,0x207),"OF":(11,0x20b)}
REG_BYTES=0x2000
MEM_BYTES=0x601000
STACK_BASE=0x31ff00
ECX_BASE=0x34ff00
STATIC_ADDR=0x563940


class OracleError(RuntimeError):
    pass


def require_private_path(path: Path, expected_root: Path) -> None:
    p=path.resolve(strict=True)
    root=expected_root.resolve(strict=True)
    if not p.is_relative_to(root) or not p.is_file():
        raise OracleError("Private game binary must be inside .local/private")


def require_ignored_output(path: Path, working_root: Path) -> None:
    root=(working_root/".local/profiles").resolve()
    p=path.resolve()
    if not p.is_relative_to(root) or p==root or p.exists():
        raise OracleError("Output must be new and inside ignored .local/profiles")


def require_original_fingerprints(pe_digest: str, pcode_digest: str) -> None:
    if pe_digest!=EXPECTED_PE_SHA256 or pcode_digest!=EXPECTED_PCODE_SHA256:
        raise OracleError("Original CoDSP executable/p-code fingerprint does not match audited build")


def decode_and_validate(pe_path: Path, insns: list[dict]) -> tuple[bytes,int]:
    import pefile
    from capstone import Cs, CS_ARCH_X86, CS_MODE_32

    if not insns or insns[0]["pc"]!=START or insns[-1]["pc"]+insns[-1]["size"]!=STOP:
        raise OracleError("Unexpected initial/final guest PC")
    for left,right in zip(insns,insns[1:]):
        if left["pc"]+left["size"]!=right["pc"]:
            raise OracleError("Instruction gap or non-linear prefix")
    pe=pefile.PE(str(pe_path),fast_load=True)
    if pe.OPTIONAL_HEADER.ImageBase != 0x400000:
        raise OracleError("Unsupported PE image base")
    data=pe.get_data(START-0x400000,STOP-START)
    if len(data)!=STOP-START:
        raise OracleError("Truncated executable slice")
    decoded=list(Cs(CS_ARCH_X86,CS_MODE_32).disasm(data,START))
    if len(decoded)!=len(insns):
        raise OracleError("Capstone does not match raw p-code instruction count")
    for real,trans in zip(decoded,insns):
        if real.address!=trans["pc"] or real.size!=trans["size"]:
            raise OracleError("Raw PE instruction boundaries differ from p-code")
        if real.mnemonic not in {"sub","mov","xor","push","lea","add","cmp","je"}:
            raise OracleError("Unsupported x86 instruction in bounded oracle")
        if (real.mnemonic == "je") != (real.address == STOP-6):
            raise OracleError("Unexpected jump or opcode position")
        if real.mnemonic == "je" and int(real.op_str,0) != BRANCH_TARGET:
            raise OracleError("Original x86 branch target contradicts p-code")
    return data,len(decoded)


def generate_lowering(insns: list[dict]) -> str:
    """Use real pcode2c generator unchanged, not a hand-coded math proxy."""
    g=Gen({})
    body=[
        "/* PRIVATE GENERATED FROM LOCALLY SUPPLIED CoDSP p-code. DO NOT COMMIT. */",
        '#include "recomp_rt.h"',
        "uint8_t *MEM;",
        "uint8_t R[0x2000];",
        "uint8_t U[0x400000];",
        "uint32_t PC;",
        "int recomp_miss;",
        "__declspec(dllexport) uint32_t prefix_result_pc(void) { return PC; }",
        "__declspec(dllexport) void execute_prefix(uint8_t *initial_regs, uint8_t *guest_memory) {",
        "  MEM=guest_memory;",
        "  memcpy(R, initial_regs, sizeof(R));",
    ]
    for insn in insns:
        ops=insn["ops"]
        g.temp_offsets=temporary_layout(ops)
        if g.temp_offsets is None:
            raise OracleError("Undefined cross-instruction unique input")
        body.append("  {")
        body.append(f"    uint8_t T[{max(1,len(g.temp_offsets))}];")
        for mn,out,inputs in ops:
            if mn in {"BRANCH","CALL","BRANCHIND","CALLIND","RETURN"}:
                raise OracleError("Unsupported control transfer in the bounded prefix")
            if mn == "CBRANCH":
                if insn["pc"]!=STOP-6 or inputs[0]!=("m",BRANCH_TARGET,4):
                    raise OracleError("First conditional jump does not match verified target")
                jump=lambda v: f"PC=0x{v[1]:x}u; goto oracle_exit;"
            else:
                jump=lambda _v: (_ for _ in ()).throw(OracleError("Unexpected jump"))
            statement=g.op(mn,out,inputs,jump,None)
            if ("goto " in statement and mn != "CBRANCH") or "unsupported(" in statement:
                raise OracleError("Unsupported operation in translated prefix")
            body.append("    "+statement)
        body.append("  }")
    if g.unsupported:
        raise OracleError("Generator emitted unsupported operations")
    body.extend([
        f"  PC=0x{STOP:x}u;",
        "oracle_exit:",
        "  memcpy(initial_regs,R,sizeof(R));",
        "}",
    ])
    return "\n".join(body)+"\n"


def compile_lowering(source: Path, dll: Path, compiler: Path, include_dir: Path) -> None:
    command=[
        str(compiler),"-std=c11","-O1","-shared",
        "-I",str(include_dir),
        str(source),"-o",str(dll)
    ]
    r=subprocess.run(command,capture_output=True,text=True,check=False,timeout=120)
    if r.returncode:
        raise OracleError("Host compiler rejected generated C: "+r.stderr[:1200])
    if not dll.is_file():
        raise OracleError("Host dynamic library not created")


def trial_inputs(case: int) -> tuple[dict[str,int],int,list[tuple[int,bytes]]]:
    rng=random.Random(0x41B8F0 ^ (case*0x9e3779b1))
    regs={name:rng.getrandbits(32) for name in REG_OFFSETS}
    regs["ESP"]=0x320000
    regs["ECX"]=0x350000
    values=rng.getrandbits(6)
    eflags=2
    for n,(bit,_) in FLAG_BITS.items():
        if values&1:eflags |= 1<<bit
        values>>=1
    eflags|=(rng.getrandbits(1)<<4) # AF is not emitted by this p-code version.
    ecx_region=bytearray(rng.randbytes(0x400))
    # The source compares [ECX+0xf4] against EDI (forced zero);
    # force both JE paths to be exercised without changing the machine code.
    value=0 if case%2==0 else (rng.getrandbits(32) or 1)
    ecx_region[0x1f4:0x1f8]=value.to_bytes(4,"little")
    mem=[
        (STACK_BASE,rng.randbytes(0x300)),
        (ECX_BASE,bytes(ecx_region)),
        (STATIC_ADDR,rng.randbytes(4))
    ]
    return regs,eflags,mem


def test_case(machine_code: bytes, library, case: int) -> bool:
    from unicorn import Uc, UC_ARCH_X86, UC_MODE_32
    from unicorn.x86_const import (
        UC_X86_REG_EIP,UC_X86_REG_EFLAGS,UC_X86_REG_EAX,UC_X86_REG_ECX,
        UC_X86_REG_EDX,UC_X86_REG_EBX,UC_X86_REG_ESP,UC_X86_REG_EBP,
        UC_X86_REG_ESI,UC_X86_REG_EDI
    )
    uc_ids=dict(zip(REG_OFFSETS,[
        UC_X86_REG_EAX,UC_X86_REG_ECX,UC_X86_REG_EDX,UC_X86_REG_EBX,
        UC_X86_REG_ESP,UC_X86_REG_EBP,UC_X86_REG_ESI,UC_X86_REG_EDI
    ]))
    initial,eflags,regions=trial_inputs(case)
    uc=Uc(UC_ARCH_X86,UC_MODE_32)
    uc.mem_map(0x1000,MEM_BYTES-0x1000)
    uc.mem_write(START,machine_code)
    uc.reg_write(UC_X86_REG_EIP,START)
    uc.reg_write(UC_X86_REG_EFLAGS,eflags)
    for name,reg_id in uc_ids.items():
        uc.reg_write(reg_id,initial[name])
    regs=ctypes.create_string_buffer(REG_BYTES)
    host=ctypes.create_string_buffer(MEM_BYTES)
    for name,off in REG_OFFSETS.items():
        ctypes.memmove(ctypes.addressof(regs)+off,initial[name].to_bytes(4,"little"),4)
    for name,(bit,offset) in FLAG_BITS.items():
        regs[offset]=bytes([int(bool(eflags & (1<<bit)))])
    for address,data in regions:
        uc.mem_write(address,data)
        ctypes.memmove(ctypes.addressof(host)+address,data,len(data))
    try:
        uc.emu_start(START,0,timeout=500000,count=20)
    except Exception as ex:
        raise OracleError(f"Unicorn trap in case {case}: {ex}") from ex
    library.execute_prefix(ctypes.cast(regs,ctypes.c_void_p),
                           ctypes.cast(host,ctypes.c_void_p))
    actual_pc=uc.reg_read(UC_X86_REG_EIP)
    expected_pc=BRANCH_TARGET if case%2==0 else STOP
    if actual_pc!=expected_pc:
        raise OracleError(f"Unexpected Unicorn branch target in case {case}")
    translated_pc=library.prefix_result_pc()
    if translated_pc!=actual_pc:
        raise OracleError(f"case {case} translated PC differs from x86 branch")
    for name,reg_id in uc_ids.items():
        expected=uc.reg_read(reg_id)&0xffffffff
        actual=int.from_bytes(regs.raw[REG_OFFSETS[name]:REG_OFFSETS[name]+4],"little")
        if expected!=actual:
            raise OracleError(f"case {case} {name} mismatch (no state published)")
    for name,(bit,off) in FLAG_BITS.items():
        expected=(uc.reg_read(UC_X86_REG_EFLAGS)>>bit)&1
        actual=regs.raw[off]
        if expected!=actual:
            raise OracleError(f"case {case} {name} mismatch (no state published)")
    for addr,data in regions:
        expected=bytes(uc.mem_read(addr,len(data)))
        actual=ctypes.string_at(ctypes.addressof(host)+addr,len(data))
        if expected!=actual:
            raise OracleError(f"case {case} RAM mismatch at validated region")
    if int.from_bytes(regs.raw[0x10:0x14],"little") != 0x31ffa4:
        # 0x4c local allocation + four pushes => 0x320000-0x4c-16.
        raise OracleError(f"case {case} stack pointer check failed")
    return actual_pc==BRANCH_TARGET


def main() -> int:
    p=argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--pe",required=True,type=Path)
    p.add_argument("--pcode",required=True,type=Path)
    p.add_argument("--compiler",required=True,type=Path)
    p.add_argument("--output",required=True,type=Path)
    p.add_argument("--cases",type=int,default=256)
    args=p.parse_args()
    root=Path.cwd()
    if not 1<=args.cases<=2048:
        p.error("cases must be between 1 and 2048")
    for dep in ("unicorn","capstone","pefile"):
        try: __import__(dep)
        except ImportError as ex: p.error(f"Missing optional local dependency: {dep}: {ex}")
    try:
        require_private_path(args.pe,root/".local/private")
        require_private_path(args.pcode,root/"recomp_out")
        require_ignored_output(args.output,root)
        if not args.compiler.is_file():
            raise OracleError("Missing LLVM-MinGW host compiler")
        pe_digest=hashlib.sha256(args.pe.read_bytes()).hexdigest()
        pcode_digest=hashlib.sha256(args.pcode.read_bytes()).hexdigest()
        require_original_fingerprints(pe_digest,pcode_digest)
        insns=scan_pcode(args.pcode,[(START,STOP-1)])
        machine,number=decode_and_validate(args.pe,insns)
        source=generate_lowering(insns)
        args.output.mkdir(parents=True,exist_ok=False)
        generated=args.output/"translated_private.c"
        dll=args.output/"translated_private.dll"
        generated.write_text(source,encoding="utf8")
        compile_lowering(generated,dll,args.compiler,root/"tools/recomp")
        library=ctypes.CDLL(str(dll.resolve()))
        library.execute_prefix.argtypes=(ctypes.c_void_p,ctypes.c_void_p)
        library.execute_prefix.restype=None
        library.prefix_result_pc.argtypes=()
        library.prefix_result_pc.restype=ctypes.c_uint32
        taken=0
        for case in range(args.cases):
            taken+=int(test_case(machine,library,case))
        if not 0<taken<args.cases:
            raise OracleError("Both conditional branch outcomes must be tested")
        report={
            "oracle":"Unicorn x86 32-bit REAL user-supplied PE bytes, independent of p-code",
            "translator":"project pcode2c.Gen lowered private real CoDSP p-code, LLVM-MinGW host C",
            "source_sha256":pe_digest,
            "pcode_sha256":pcode_digest,
            "range_exclusive":[hex(START),hex(STOP)],
            "x86_instructions_verified":number,
            "seeded_cases":args.cases,
            "branch_taken":taken,
            "branch_not_taken":args.cases-taken,
            "checked":["8 general purpose x86 registers","CF PF ZF SF OF",
                       "guest stack bytes","ECX referenced memory","static data bytes",
                       "x86 and translated PC on both branch outcomes"],
            "not_checked":["AF because generated translator does not materialize it",
                           "x87 state beyond the first conditional branch","behavior beyond bounded prefix",
                           "full program, ARM64 performance, or TECNO FPS"],
            "status":"passed",
            "game_runtime_patched":False
        }
        (args.output/"summary.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf8")
        print(json.dumps(report,indent=2))
        return 0
    except (OSError,ValueError,OracleError,subprocess.TimeoutExpired) as ex:
        print("Differential oracle FAILED/CANCELLED:",str(ex),file=sys.stderr)
        return 2


if __name__=="__main__":
    raise SystemExit(main())
