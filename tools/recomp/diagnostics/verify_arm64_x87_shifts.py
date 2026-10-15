#!/usr/bin/env python3
"""Compile and emulate real AArch64 x87 byte shifts; never a device FPS test.

Exercises ordered p-code copies and outlined helpers against a byte-copy model.
No original game data, binary80 arithmetic or physical-device access is used.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import random
import subprocess

ROOT=Path(__file__).resolve().parents[3]


def verify(llvm: Path, out: Path, cases: int=1000, icf: str='none') -> dict:
    if not __debug__:
        raise RuntimeError('Do not run this auditor with optimized Python (-O/-OO)')
    if not 4 <= cases <= 100000:
        raise ValueError('cases must be 4..100000')
    if not out.resolve().is_relative_to((ROOT/'.local/profiles/runs').resolve()):
        raise ValueError('Output must be in a private run')
    out.mkdir(parents=True,exist_ok=False)
    def tool(name):
        return str(llvm/(name+'.exe' if (llvm/(name+'.exe')).exists() else name))
    def run(args):
        p=subprocess.run(args,check=True,capture_output=True,text=True,timeout=120)
        return p.stdout
    if icf not in ('none','safe'):
        raise ValueError('Only none/safe ICF supported')
    modes=('reference','outlined','second')
    for mode in modes:
        source='#include "runtime/x87_stack_shift.h"\n'
        for direction in ('push','pop'):
            if mode=='reference':
                indices=range(6,-1,-1) if direction=='push' else range(7)
                source+=f'void reference_{direction}(uint8_t*r){{\n'
                for i in indices:
                    dest,src=((i+1,i) if direction=='push' else (i,i+1))
                    source+=f'{{unsigned __int128 v=0;memcpy(&v,r+{0x1100+16*src},10);memcpy(r+{0x1100+16*dest},&v,10);}}\n'
                source+='}\n'
            else:
                source+=f'void {mode}_{direction}(uint8_t*r){{codsp_x87_shift_{direction}(r);}}\n'
        if mode=='reference':
            source+='static void taken_a(uint8_t*r){r[0]^=1;}\nstatic void taken_b(uint8_t*r){r[0]^=1;}\n'
            source+='void(*volatile address_probes[])(uint8_t*)={taken_a,taken_b};\n'
        (out/f'{mode}.c').write_text(source)
    elf=out/'shifts.elf'
    command=[tool('clang'),'--target=aarch64-linux-android26','-O1','-fno-pic','-fno-pie','-ffunction-sections','-faddrsig',
             '-nostdlib','-Wl,-Ttext=0x100000','-Wl,-e,reference_push','-Wl,--build-id=none',
             '-Wl,--icf='+icf,'-I'+str(ROOT/'tools/recomp'),
             *(str(out/f'{mode}.c') for mode in modes),'-o',str(elf)]
    run(command)
    disassembly=run([tool('llvm-objdump'),'-d',str(elf)])
    (out/'disassembly.txt').write_text(disassembly)
    run([tool('llvm-objcopy'),'-O','binary','--only-section=.text',str(elf),str(out/'text.bin')])
    symbols={};helper_addresses={'push':set(),'pop':set()}
    for line in run([tool('llvm-nm'),'-S','--defined-only',str(elf)]).splitlines():
        fields=line.split()
        if len(fields)==4:
            symbols[fields[3]]={'address':int(fields[0],16),'size':int(fields[1],16)}
            for direction in helper_addresses:
                if fields[3]=='codsp_x87_shift_'+direction:
                    helper_addresses[direction].add(int(fields[0],16))
    assert symbols['taken_a']['address']!=symbols['taken_b']['address'],'Address-observed functions folded'
    for addresses in helper_addresses.values():
        assert len(addresses)==(1 if icf=='safe' else 2),'Unexpected helper folding'
    from unicorn import Uc,UC_ARCH_ARM64,UC_MODE_ARM,UC_HOOK_MEM_WRITE
    from unicorn.arm64_const import UC_ARM64_REG_X0,UC_ARM64_REG_LR,UC_ARM64_REG_SP,UC_ARM64_REG_FPCR,UC_ARM64_REG_FPSR,UC_ARM64_REG_PC
    uc=Uc(UC_ARCH_ARM64,UC_MODE_ARM)
    uc.mem_map(0x100000,0x10000);uc.mem_map(0x200000,0x10000);uc.mem_map(0x300000,0x10000)
    text=(out/'text.bin').read_bytes();uc.mem_write(0x100000,text)
    rng=random.Random(0x8015)
    current={'base':0,'destinations':[]}
    def write_guard(_uc,_access,address,size,_value,_data):
        if 0x200000 <= address < 0x210000:
            if not any(start<=address and address+size<=start+10 for start in current['destinations']):
                raise AssertionError(f'Write outside architectural ten-byte slots: {address:x}/{size}')
    uc.hook_add(UC_HOOK_MEM_WRITE,write_guard)
    for trial in range(cases):
        initial=(bytes(0x2000) if trial==0 else bytes([255])*0x2000 if trial==1
                 else bytes(range(256))*32 if trial==2 else rng.randbytes(0x2000))
        base=0x200080+trial%16
        for direction in ('push','pop'):
            indices=range(6,-1,-1) if direction=='push' else range(7)
            pairs=[(0x1100+16*(i+1),0x1100+16*i) if direction=='push'
                   else (0x1100+16*i,0x1100+16*(i+1)) for i in indices]
            expected=bytearray(initial)
            for dest,src in pairs:expected[dest:dest+10]=expected[src:src+10]
            current['destinations']=[base+dest for dest,_ in pairs]
            for mode in modes:
                uc.mem_write(0x200000,bytes([0xA7])*0x3000)
                uc.mem_write(base,initial)
                uc.reg_write(UC_ARM64_REG_X0,base);uc.reg_write(UC_ARM64_REG_LR,0x10fff0)
                uc.reg_write(UC_ARM64_REG_SP,0x30fff0)
                uc.reg_write(UC_ARM64_REG_FPCR,0x400000);uc.reg_write(UC_ARM64_REG_FPSR,0x80)
                uc.emu_start(symbols[f'{mode}_{direction}']['address'],0x10fff0,count=4096)
                assert uc.reg_read(UC_ARM64_REG_PC)==0x10fff0,'Did not return within instruction limit'
                assert uc.reg_read(UC_ARM64_REG_SP)==0x30fff0,'Stack pointer not restored'
                assert uc.mem_read(base,len(initial))==expected,(trial,mode,direction)
                assert uc.mem_read(base-32,32)==bytes([0xA7])*32
                assert uc.mem_read(base+len(initial),32)==bytes([0xA7])*32
                assert uc.reg_read(UC_ARM64_REG_FPCR)==0x400000
                assert uc.reg_read(UC_ARM64_REG_FPSR)==0x80
    result={'status':'pass','cases_per_direction':cases,'emulated_calls':6*cases,'icf':icf,
            'unique_helper_bodies':{name:len(values) for name,values in helper_addresses.items()},
            'address_observed_functions_distinct':True,
            'seed':0x8015,'unaligned_offsets':min(cases,16),'symbols':symbols,
            'text_sha256':hashlib.sha256(text).hexdigest(),'compile_command':command,
            'scope':'Full R bytes/padding, write extents and FPCR/FPSR; no arithmetic, guest RAM faults or FPS claim'}
    (out/'result.json').write_text(json.dumps(result,indent=2))
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument('--llvm-bin',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--cases',type=int,default=1000)
    p.add_argument('--icf',choices=('none','safe'),default='none')
    args=p.parse_args()
    result=verify(args.llvm_bin,args.out,args.cases,args.icf)
    print(json.dumps({k:v for k,v in result.items() if k not in ('compile_command','symbols')},indent=2))


if __name__=='__main__':main()
