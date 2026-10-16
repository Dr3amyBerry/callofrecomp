#!/usr/bin/env python3
"""Offline verify one-byte FCHS value transform as real AArch64 machine code.

Checks every byte of 8192-byte CoDSP R, adjacent padding, write extent,
unaligned R pointers, FPCR/FPSR, SP and return. Compare an independent
10-byte sign-toggle value model, not host double conversion.
Does not model x87 C1/status exceptions, guest RAM faults, or TECNO FPS.
"""
from __future__ import annotations
import argparse
from hashlib import sha256
import json
from pathlib import Path
import random
import subprocess

ROOT=Path(__file__).resolve().parents[3]


def verify(llvm:Path,out:Path, cases:int=2000)->dict:
    if not __debug__:
        raise RuntimeError("Run without Python -O; assertions verify state")
    if not 16<=cases<=100000:
        raise ValueError("Use 16..100000 cases")
    private=(ROOT/".local/profiles/runs").resolve()
    if not out.resolve().is_relative_to(private):
        raise ValueError("Output must belong to a private study session")
    out.mkdir(parents=True,exist_ok=False)
    def bin(name):
        exe=llvm/(name+".exe")
        return str(exe if exe.is_file() else llvm/name)
    def run(args):
        return subprocess.run(args,capture_output=True,text=True,
                              check=True,timeout=120).stdout
    src=out/"sign.c"
    src.write_text(
        '#include <stdint.h>\n'
        '__attribute__((noinline,used))\n'
        'void reference_sign(uint8_t*r){\n'
        ' uint8_t bytes[10];\n'
        ' __builtin_memcpy(bytes,r+0x1100,10);\n'
        ' bytes[9]^=0x80;\n'
        ' __builtin_memcpy(r+0x1100,bytes,10);\n'
        '}\n'
        '__attribute__((noinline,used))\n'
        'void candidate_sign(uint8_t*r){r[0x1109]^=0x80;}\n',
        encoding="utf8")
    elf=out/"sign.elf"
    cmd=[bin("clang"),"--target=aarch64-linux-android26","-O1",
         "-fno-pic","-fno-pie","-nostdlib",
         "-Wl,-Ttext=0x100000","-Wl,-e,reference_sign",
         "-Wl,--build-id=none",str(src),"-o",str(elf)]
    run(cmd)
    asm=run([bin("llvm-objdump"),"-d",str(elf)])
    (out/"disassembly.txt").write_text(asm,encoding="utf8")
    binary=out/"text.bin"
    run([bin("llvm-objcopy"),"-O","binary","--only-section=.text",
         str(elf),str(binary)])
    symbols={}
    for line in run([bin("llvm-nm"),"-S","--defined-only",str(elf)]).splitlines():
        parts=line.split()
        if len(parts)==4 and parts[3] in ("reference_sign","candidate_sign"):
            symbols[parts[3]]={"address":int(parts[0],16),
                               "size":int(parts[1],16)}
    if len(symbols)!=2:
        raise AssertionError("Missing both source and optimized AArch64 functions")
    from unicorn import Uc,UC_ARCH_ARM64,UC_MODE_ARM,UC_HOOK_MEM_WRITE
    from unicorn.arm64_const import (UC_ARM64_REG_X0,UC_ARM64_REG_LR,
        UC_ARM64_REG_PC,UC_ARM64_REG_SP,UC_ARM64_REG_FPCR,UC_ARM64_REG_FPSR)
    emu=Uc(UC_ARCH_ARM64,UC_MODE_ARM)
    emu.mem_map(0x100000,0x10000)
    emu.mem_map(0x200000,0x10000)
    emu.mem_map(0x300000,0x10000)
    data=binary.read_bytes()
    emu.mem_write(0x100000,data)
    current={"writes":[],"function":""}
    def guard(_emu,_access,address,size,_value,_user):
        lo=current["base"]+0x1100
        hi=lo+10
        if not(lo<=address and address+size<=hi):
            raise AssertionError(f"Write outside 10 byte ST0 payload: {address:x} {size}")
        if current["function"]=="candidate_sign" and not (
                address==lo+9 and size==1):
            raise AssertionError(f"Candidate writes beyond ST0 sign byte: {address:x}/{size}")
        current["writes"].append((address,size))
    emu.hook_add(UC_HOOK_MEM_WRITE,guard)
    rng=random.Random(0x41975e)
    for trial in range(cases):
        pattern=(bytes(0x2000) if trial==0 else
                 bytes([0xff])*0x2000 if trial==1 else
                 bytes(range(256))*32 if trial==2 else
                 rng.randbytes(0x2000))
        expected=bytearray(pattern)
        expected[0x1109]^=0x80
        addr=0x200080+trial%16
        for func in symbols:
            emu.mem_write(0x200000,b"\xa7"*0x3000)
            emu.mem_write(addr,pattern)
            emu.reg_write(UC_ARM64_REG_X0,addr)
            emu.reg_write(UC_ARM64_REG_LR,0x10fff0)
            emu.reg_write(UC_ARM64_REG_SP,0x30fff0)
            emu.reg_write(UC_ARM64_REG_FPCR,0x400000)
            emu.reg_write(UC_ARM64_REG_FPSR,0x80)
            current.clear()
            current.update({"base":addr,"writes":[],"function":func})
            emu.emu_start(symbols[func]["address"],0x10fff0,count=4096)
            if emu.reg_read(UC_ARM64_REG_PC)!=0x10fff0:
                raise AssertionError("Did not return to LR")
            if emu.reg_read(UC_ARM64_REG_SP)!=0x30fff0:
                raise AssertionError("SP modified")
            if emu.reg_read(UC_ARM64_REG_FPCR)!=0x400000:
                raise AssertionError("FPCR changed")
            if emu.reg_read(UC_ARM64_REG_FPSR)!=0x80:
                raise AssertionError("FPSR changed")
            if bytes(emu.mem_read(addr,0x2000))!=bytes(expected):
                raise AssertionError(f"R bytes mismatch trial={trial} function={func}")
            if bytes(emu.mem_read(addr-32,32))!=b"\xa7"*32:
                raise AssertionError("Memory changed before R")
            if bytes(emu.mem_read(addr+0x2000,32))!=b"\xa7"*32:
                raise AssertionError("Memory changed after R")
            if not current["writes"]:
                raise AssertionError("No memory writes")
    result={"status":"pass","cases":cases,"executions":cases*2,
            "unaligned_offsets":min(cases,16),
            "candidate_writes_only_sign_byte":True,
            "full_architectural_R_and_padding_equal":True,
            "fpcr_fpsr_sp_unchanged":True,
            "symbols":symbols,
            "text_sha256":sha256(data).hexdigest(),
            "compilation":cmd,
            "limits":"Value-only FCHS semantics. No x87 C1/status exceptions, memory faults, FPS or game execution."}
    (out/"result.json").write_text(json.dumps(result,indent=2),encoding="utf8")
    return result


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--llvm-bin",type=Path,required=True)
    parser.add_argument("--out",type=Path,required=True)
    parser.add_argument("--cases",type=int,default=2000)
    args=parser.parse_args(argv)
    result=verify(args.llvm_bin,args.out,args.cases)
    print(json.dumps({k:v for k,v in result.items()
                      if k not in ("compilation","symbols")},indent=2))


if __name__=="__main__":main()
