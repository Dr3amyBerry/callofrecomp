#!/usr/bin/env python3
"""AArch64 machine-code differential for CoDSP FLD32 in hot function 0x5061b0.

Original generated order: architectural PC write, seven x87 ordered moves,
guest 4-byte memory LOAD, ST0 binary80 write. Compare original f2d/d2f vs
opt-in normal bit mapper, checking full R, padding, guest memory and fault
checkpoint. Counts are dynamic Unicorn instructions, NOT cycles or FPS.
"""
from __future__ import annotations
import argparse
from hashlib import sha256
import json
from pathlib import Path
import random
import struct
import subprocess

ROOT = Path(__file__).resolve().parents[3]
CODE = 0x100000
RETURN = 0x10fff0
REGIONS = {"r":0x200000,"stack":0x300000,"guest":0x400000}
REG_BASE = REGIONS["r"] + 0x100
GUEST_BASE = REGIONS["guest"] + 0x100

BINARY32_CLASSES = ("normal", "signed_zero", "subnormal", "infinity", "nan")


def classify_binary32(bits: int) -> str:
    """Classify 32-bit IEEE inputs using bits only, including signed zero."""
    if type(bits) is not int or not 0 <= bits <= 0xffffffff:
        raise ValueError("Expected exact unsigned 32-bit input")
    exponent = (bits >> 23) & 0xff
    fraction = bits & 0x7fffff
    if exponent == 0:
        return "signed_zero" if fraction == 0 else "subnormal"
    if exponent == 0xff:
        return "infinity" if fraction == 0 else "nan"
    return "normal"


def verify(llvm: Path, out: Path, cases: int=2048) -> dict:
    if not __debug__:
        raise RuntimeError("Do not run differential tests with Python -O")
    if not 32 <= cases <= 20000:
        raise ValueError("Use 32..20000 cases")
    if not out.resolve().is_relative_to((ROOT / ".local/profiles/runs").resolve()):
        raise ValueError("Use a private run directory for evidence")
    out.mkdir(parents=True, exist_ok=False)
    def tool(n):
        p=llvm/(n+".exe")
        return str(p if p.is_file() else llvm/n)
    def run(args):
        p=subprocess.run(args,capture_output=True,text=True,timeout=100)
        if p.returncode:
            raise RuntimeError(f"Failed {args[0]}: {p.stdout[-1000:]} {p.stderr[-1800:]}")
        return p.stdout
    src=out/"fld32.c"
    src.write_text(r"""
#include "recomp_rt.h"
static inline void shift_push(uint8_t *r) {
    u128 last = rd(r + 0x1170, 10);
    wr(r + 0x1170, 10, rd(r + 0x1160, 10));
    wr(r + 0x1160, 10, rd(r + 0x1150, 10));
    wr(r + 0x1150, 10, rd(r + 0x1140, 10));
    wr(r + 0x1140, 10, rd(r + 0x1130, 10));
    wr(r + 0x1130, 10, rd(r + 0x1120, 10));
    wr(r + 0x1120, 10, rd(r + 0x1110, 10));
    wr(r + 0x1110, 10, rd(r + 0x1100, 10));
    wr(r + 0x1100, 10, last);
}
__attribute__((noinline, used))
void reference_fld32(uint8_t *r, const uint8_t *g) {
    wr(r + 0x10ac, 4, (u128)0x5061b0u);
    shift_push(r);
    u128 bits = rd(g,4);
    wr(r + 0x1100,10,d2f(f2d(bits,4),10));
}
__attribute__((noinline, used))
void candidate_fld32(uint8_t *r, const uint8_t *g) {
    wr(r + 0x10ac, 4, (u128)0x5061b0u);
    shift_push(r);
    u128 bits = rd(g,4);
    wr(r + 0x1100,10,codsp_x87_fld32_normal(bits));
}
""",encoding="utf8")
    elf=out/"fld32.elf"
    cmd=[tool("clang"),"--target=aarch64-linux-android26","-O1",
         "-fno-fast-math","-fno-pic","-fno-pie","-nostdlib",
         "-Wl,-Ttext=0x100000","-Wl,-e,reference_fld32",
         "-Wl,--build-id=none",
         "-I"+str(ROOT/"tools/recomp"),
         "-I"+str(ROOT/"tools/recomp/runtime"),
         str(src),"-o",str(elf)]
    run(cmd)
    assembly=run([tool("llvm-objdump"),"-d",str(elf)])
    (out/"disassembly.txt").write_text(assembly,encoding="utf8")
    code=out/"text.bin"
    run([tool("llvm-objcopy"),"-O","binary","--only-section=.text",
         str(elf),str(code)])
    symbols={}
    for line in run([tool("llvm-nm"),"-S","--defined-only",str(elf)]).splitlines():
        fields=line.split()
        if len(fields)==4 and fields[3] in ("reference_fld32","candidate_fld32"):
            symbols[fields[3]]={"address":int(fields[0],16),"size":int(fields[1],16)}
    if len(symbols)!=2:
        raise RuntimeError("Missing the two AArch64 functions")
    from unicorn import Uc,UcError,UC_ARCH_ARM64,UC_MODE_ARM,UC_HOOK_CODE,UC_HOOK_MEM_WRITE
    from unicorn.arm64_const import (
        UC_ARM64_REG_X0,UC_ARM64_REG_X1,UC_ARM64_REG_LR,UC_ARM64_REG_PC,
        UC_ARM64_REG_SP,UC_ARM64_REG_FPCR,UC_ARM64_REG_FPSR,
    )
    uc=Uc(UC_ARCH_ARM64,UC_MODE_ARM)
    uc.mem_map(CODE,0x10000)
    uc.mem_map(REGIONS["r"],0x10000)
    uc.mem_map(REGIONS["guest"],0x10000)
    uc.mem_map(REGIONS["stack"],0x10000)
    data=code.read_bytes()
    if len(data)>0x10000:
        raise RuntimeError("Untrusted ELF text size")
    uc.mem_write(CODE,data)
    current={"count":0,"r":0,"writes":[]}
    def codehook(_uc,address,size,_userdata):
        current["count"]+=1
    def memwrite(_uc,access,address,size,value,_userdata):
        r=current["r"]
        if r <= address < r+0x2000:
            if not ((r+0x10ac <= address and address+size <= r+0x10b0)
                    or any(r+off <= address and address+size <= r+off+10
                           for off in range(0x1100,0x1180,0x10))):
                raise AssertionError(f"Unexpected x87 R write into padding/flags {address:x}/{size}")
            current["writes"].append((address,size))
    uc.hook_add(UC_HOOK_CODE,codehook)
    uc.hook_add(UC_HOOK_MEM_WRITE,memwrite)
    rng=random.Random(0x5061b0)
    specials=[
        0,0x80000000,1,0x80000001,0x007fffff,0x807fffff,
        0x00800000,0x80800000,0x7f7fffff,0xff7fffff,
        0x7f800000,0xff800000,0x7fc00001,0xffcfffff,
        0x7f800001,0x7fa00001,0xffa00001,0xffffffff,
    ]
    vectors = list(specials)
    vectors += [ ((i%2)<<31) | (((i//2)%254+1)<<23) |
                 (rng.getrandbits(23)) for i in range(max(0,cases//3))]
    vectors += [rng.getrandbits(32) for _ in range(max(0,cases-len(vectors)))]
    vectors=vectors[:cases]
    normal_instruction_counts={"reference_fld32":[],"candidate_fld32":[]}
    special_instruction_counts={"reference_fld32":[],"candidate_fld32":[]}
    class_samples = {kind: {"reference_fld32": [], "candidate_fld32": []}
                     for kind in BINARY32_CLASSES}
    class_instruction_totals = {kind: {"reference_fld32": 0, "candidate_fld32": 0}
                                for kind in BINARY32_CLASSES}
    class_case_counts = {kind: 0 for kind in BINARY32_CLASSES}
    samples=0
    for i,bits in enumerate(vectors):
        kind = classify_binary32(bits)
        class_case_counts[kind] += 1
        initial=(bytes(0x2000) if i==0 else bytes([0xff])*0x2000 if i==1
                 else bytes(range(256))*32 if i==2 else rng.randbytes(0x2000))
        rbase=REG_BASE+(i%16)
        mem=GUEST_BASE+(i%16)
        snapshots={}
        for name in ("reference_fld32","candidate_fld32"):
            uc.mem_write(REGIONS["r"],b"\xa7"*0x3000)
            uc.mem_write(rbase,initial)
            uc.mem_write(REGIONS["guest"],b"\xb5"*0x1000)
            uc.mem_write(mem,struct.pack("<I",bits))
            uc.reg_write(UC_ARM64_REG_X0,rbase)
            uc.reg_write(UC_ARM64_REG_X1,mem)
            uc.reg_write(UC_ARM64_REG_LR,RETURN)
            uc.reg_write(UC_ARM64_REG_SP,REGIONS["stack"]+0xfff0)
            uc.reg_write(UC_ARM64_REG_FPCR,0x400000)
            uc.reg_write(UC_ARM64_REG_FPSR,0x80)
            current.update({"count":0,"r":rbase,"writes":[]})
            uc.emu_start(symbols[name]["address"],RETURN,count=10000)
            if (uc.reg_read(UC_ARM64_REG_PC)!=RETURN or
                    uc.reg_read(UC_ARM64_REG_SP)!=REGIONS["stack"]+0xfff0 or
                    uc.reg_read(UC_ARM64_REG_FPCR)!=0x400000):
                raise AssertionError(f"Return/SP/FPCR altered {i}/{name}")
            # Signaling NaNs can legitimately set FPSR.IOC in the original.
            # Compare exact final FPSR against the reference, not a fixed
            # 'unchanged' expectation for exceptional inputs.
            fpsr=uc.reg_read(UC_ARM64_REG_FPSR)
            if 1 <= ((bits>>23)&255) <= 254 and fpsr!=0x80:
                raise AssertionError(f"Normal float changed FPSR {i}/{name}")
            rbytes=bytes(uc.mem_read(rbase,0x2000))
            if rbytes[0x110a:0x1110]!=initial[0x110a:0x1110]:
                raise AssertionError("ST0 padding changed")
            if bytes(uc.mem_read(rbase-32,32)) != b"\xa7"*32:
                raise AssertionError("Out-of-bounds write before R")
            if bytes(uc.mem_read(rbase+0x2000,32)) != b"\xa7"*32:
                raise AssertionError("Out-of-bounds write after R")
            if bytes(uc.mem_read(mem,4))!=struct.pack("<I",bits):
                raise AssertionError("Guest float memory modified")
            if not current["writes"]:
                raise AssertionError("Missing architectural register writes")
            snapshots[name]=(rbytes,fpsr)
            bucket=normal_instruction_counts if 1 <= ((bits>>23)&0xff) <= 254 else special_instruction_counts
            if len(bucket[name])<512:
                bucket[name].append(current["count"])
            if len(class_samples[kind][name]) < 512:
                class_samples[kind][name].append(current["count"])
            class_instruction_totals[kind][name] += current["count"]
        if snapshots["reference_fld32"] != snapshots["candidate_fld32"]:
            raise AssertionError(f"Full architectural R mismatch case={i} raw={bits:08x}")
        samples+=1
    # Unmapped guest read: both variants must leave exact same partial R,
    # including the guest instruction PC written BEFORE the LOAD.
    fault_count=0
    for i in range(16):
        initial=rng.randbytes(0x2000)
        rbase=REG_BASE+i
        pending={}
        for name in ("reference_fld32","candidate_fld32"):
            uc.mem_write(REGIONS["r"],b"\xa7"*0x3000)
            uc.mem_write(rbase,initial)
            uc.reg_write(UC_ARM64_REG_X0,rbase)
            uc.reg_write(UC_ARM64_REG_X1,0x600000)  # intentionally not mapped
            uc.reg_write(UC_ARM64_REG_LR,RETURN)
            uc.reg_write(UC_ARM64_REG_SP,REGIONS["stack"]+0xfff0)
            uc.reg_write(UC_ARM64_REG_FPCR,0x400000)
            uc.reg_write(UC_ARM64_REG_FPSR,0x80)
            current.update({"count":0,"r":rbase,"writes":[]})
            try:
                uc.emu_start(symbols[name]["address"],RETURN,count=10000)
            except UcError as exc:
                if "UC_ERR_READ_UNMAPPED" not in str(exc):
                    raise RuntimeError(f"Unexpected exception type: {exc}") from exc
            else:
                raise AssertionError("Unmapped guest RAM read did not fault")
            partial=bytes(uc.mem_read(rbase,0x2000))
            if partial[0x10ac:0x10b0]!=struct.pack("<I",0x5061b0):
                raise AssertionError("Guest PC not preserved at RAM fault")
            pending[name]=partial
        if pending["reference_fld32"]!=pending["candidate_fld32"]:
            raise AssertionError(f"Guest RAM fault state changed alignment={i}")
        fault_count+=1
    def stats(data):
        if not data: return None
        vals=sorted(data)
        return {"median_instructions": vals[len(vals)//2], "min":vals[0],
                "max":vals[-1],"count":len(vals)}
    result={
        "status":"pass","aarch64_elf_sha256":sha256(elf.read_bytes()).hexdigest(),
        "source_sha256":sha256(src.read_bytes()).hexdigest(),
        "cases":samples,"executions":samples*2,
        "unmapped_guest_load_fault_cases":fault_count,
        "full_8192_byte_R_and_padding_equal":True,
        "guest_PC_and_full_R_equal_on_fault":True,
        "guest_memory_untouched":True,"reference_candidate_fpcr_fpsr_sp_equal":True,
        "normal_instructions":{k:stats(v) for k,v in normal_instruction_counts.items()},
        "special_instructions":{k:stats(v) for k,v in special_instruction_counts.items()},
        "binary32_class_telemetry":{
            kind:{
                "cases":class_case_counts[kind],
                "reference":stats(class_samples[kind]["reference_fld32"]),
                "candidate":stats(class_samples[kind]["candidate_fld32"]),
                "reference_total_instructions":class_instruction_totals[kind]["reference_fld32"],
                "candidate_total_instructions":class_instruction_totals[kind]["candidate_fld32"],
                "saved_dynamic_instructions_in_sample":
                    class_instruction_totals[kind]["reference_fld32"]
                    - class_instruction_totals[kind]["candidate_fld32"],
            }
            for kind in BINARY32_CLASSES
        },
        "symbols":symbols,"compile_command":cmd,
        "limits":"Isolated FLD m32+stack instruction only; per-class dynamic counts reflect synthetic vectors (not game value frequencies), not binary80 math/CW/SW/TOP/tag/fault model, CPU cycles or gameplay FPS."
    }
    (out/"result.json").write_text(json.dumps(result,indent=2),encoding="utf8")
    return result


def main():
    ap=argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--llvm-bin",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    ap.add_argument("--cases",type=int,default=2048)
    args=ap.parse_args()
    print(json.dumps(verify(args.llvm_bin,args.out,args.cases),indent=2))


if __name__=="__main__":
    main()
