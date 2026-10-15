#!/usr/bin/env python3
"""Execute the dispatch smoke and lookup loops in AArch64 Unicorn.

Reuses tests/dispatch_index_smoke.c for boundary/reload/callback correctness.
Synthetic instruction and table-read counts are NOT TECNO timings or FPS.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import random
import struct
import subprocess

ROOT=Path(__file__).resolve().parents[3]
STACK=0x8000000
STOP=0x8020000
INDEX=0x4000000
TABLE=0x5000000
TRACE=0x5010000


def load_elf(path):
    from unicorn import Uc,UC_ARCH_ARM64,UC_MODE_ARM
    data=path.read_bytes()
    if data[:6]!=b'\x7fELF\x02\x01' or struct.unpack_from('<H',data,18)[0]!=183:
        raise ValueError('Expected little-endian AArch64 ELF64')
    offset=struct.unpack_from('<Q',data,32)[0]
    stride,count=struct.unpack_from('<HH',data,54)
    segments=[struct.unpack_from('<IIQQQQQQ',data,offset+i*stride) for i in range(count)]
    segments=[s for s in segments if s[0]==1 and s[6]]
    begin=min(s[3] for s in segments)&~4095
    end=(max(s[3]+s[6] for s in segments)+4095)&~4095
    if end>=INDEX:raise ValueError('ELF overlaps test-data mapping')
    uc=Uc(UC_ARCH_ARM64,UC_MODE_ARM);uc.mem_map(begin,end-begin)
    for s in segments:uc.mem_write(s[3],data[s[2]:s[2]+s[5]])
    uc.mem_map(STACK,0x10000);uc.mem_map(STOP,0x1000)
    return uc


def verify(llvm:Path,out:Path,iterations:int=512):
    if not __debug__:raise RuntimeError('Do not audit with optimized Python')
    if not 16<=iterations<=4096:raise ValueError('iterations must be 16..4096')
    if not out.resolve().is_relative_to((ROOT/'.local/profiles/runs').resolve()):
        raise ValueError('Use a private run output directory')
    out.mkdir(parents=True,exist_ok=False)
    def tool(name):return str(llvm/(name+'.exe' if (llvm/(name+'.exe')).exists() else name))
    def run(args):
        try:return subprocess.check_output(args,text=True,stderr=subprocess.STDOUT,timeout=120)
        except subprocess.CalledProcessError as exc:
            raise RuntimeError('Compiler/tool failed:\n'+exc.output[-4000:]) from exc
    common=[tool('clang'),'--target=aarch64-linux-android26','-O1','-fno-pic','-fno-pie',
            '-fno-stack-protector','-static','-nostdlib','-I'+str(ROOT/'tools/recomp'),
            '-I'+str(ROOT/'tools/recomp/runtime'),'-Wl,-Ttext=0x400000','-Wl,--build-id=none']
    shim=out/'shim.c'
    shim.write_text('#include <stdio.h>\n#include <stddef.h>\nFILE *stderr;\n'
                    'int puts(const char*s){(void)s;return 0;}\n'
                    'int fprintf(FILE*f,const char*s,...){(void)f;(void)s;return -1;}\n'
                    'void*memset(void*p,int c,size_t n){volatile unsigned char*d=p;'
                    'for(size_t i=0;i<n;i++)d[i]=(unsigned char)c;return p;}\n')
    smoke=out/'smoke.elf'
    smoke_command=common+['-fno-builtin',str(ROOT/'tests/dispatch_index_smoke.c'),str(shim),'-Wl,-e,main','-o',str(smoke)]
    run(smoke_command)
    def symbols(elf):
        return {p[2]:int(p[0],16) for line in run([tool('llvm-nm'),'--defined-only',str(elf)]).splitlines()
                if len(p:=line.split())==3}
    from unicorn import UC_HOOK_CODE,UC_HOOK_MEM_READ
    from unicorn.arm64_const import UC_ARM64_REG_X0,UC_ARM64_REG_X1,UC_ARM64_REG_X2,UC_ARM64_REG_X3,UC_ARM64_REG_X4,UC_ARM64_REG_LR,UC_ARM64_REG_SP,UC_ARM64_REG_PC
    def execute(uc,start,args,limit):
        for reg,value in zip((UC_ARM64_REG_X0,UC_ARM64_REG_X1,UC_ARM64_REG_X2,UC_ARM64_REG_X3,UC_ARM64_REG_X4),args):uc.reg_write(reg,value)
        uc.reg_write(UC_ARM64_REG_LR,STOP);uc.reg_write(UC_ARM64_REG_SP,STACK+0xfff0)
        uc.emu_start(start,STOP,timeout=60_000_000,count=limit)
        if uc.reg_read(UC_ARM64_REG_PC)!=STOP or uc.reg_read(UC_ARM64_REG_SP)!=STACK+0xfff0:
            raise ValueError('Did not return with intact SP within execution limit')
        return uc.reg_read(UC_ARM64_REG_X0)&0xffffffff
    uc=load_elf(smoke)
    if execute(uc,symbols(smoke)['main'],[],200_000_000)!=0:
        raise ValueError('Compiled dispatch smoke failed')
    source='#include "recomp_rt.h"\n#include "dispatch_index.h"\n'
    for mode in ('reference','recent','entry'):
        init={'reference':'','recent':'dispatch_recent h={.last_chunk=-1};',
              'entry':'dispatch_entry_recent h={.owner=i,.last_chunk=-1};'}[mode]
        lookup={'reference':'dispatch_index_find(i,c,n,p[k])','recent':'dispatch_index_find_recent(i,c,n,p[k],&h)',
                'entry':'dispatch_index_find_entry(i,c,n,p[k],&h)'}[mode]
        call='h.entry.fn()' if mode=='entry' else 'c[f].fn()'
        source+=f'unsigned run_{mode}(const dispatch_index*i,const recomp_chunk*c,int n,const uint32_t*p,unsigned count){{'
        source+=f'{init}unsigned sum=0;for(unsigned k=0;k<count;k++){{int f={lookup};if(f>=0){{{call};sum+=(unsigned)f+1;}}}}return sum;}}\n'
    (out/'loops.c').write_text(source)
    (out/'callback.c').write_text('volatile unsigned callback_count;void callback(void){callback_count++;}\n')
    elf=out/'loops.elf'
    loop_command=common+[str(out/'loops.c'),str(out/'callback.c'),'-Wl,-e,run_reference','-o',str(elf)]
    run(loop_command);syms=symbols(elf)
    (out/'disassembly.txt').write_text(run([tool('llvm-objdump'),'-d',str(elf)]))
    chunks=[];cursor=0x401000
    for k in range(403):
        length=0x1200+(k%13)*47;chunks.append((cursor,cursor+length));cursor+=length+(7 if k%19==0 else 0)
    rng=random.Random(0x4038015);results={}
    for pattern in ('same','burst8','alternate2','random403'):
        selected=[201 if pattern=='same' else 190+(k//8)%16 if pattern=='burst8'
                  else 201+k%2 if pattern=='alternate2' else rng.randrange(403) for k in range(iterations)]
        pcs=[chunks[k][0]+rng.randrange(chunks[k][1]-chunks[k][0]) for k in selected]
        for mode in ('reference','recent','entry'):
            uc=load_elf(elf);uc.mem_map(INDEX,0x201000);uc.mem_map(TABLE,0x20000)
            uc.mem_write(INDEX+(1<<21),struct.pack('<Q',1))
            for k,(start,end) in enumerate(chunks):
                uc.mem_write(TABLE+16*k,struct.pack('<IIQ',start,end,syms['callback']))
                for page in range(start>>12,((end-1)>>12)+1):uc.mem_write(INDEX+page*2,struct.pack('<H',k+1))
            uc.mem_write(TRACE,struct.pack('<'+'I'*len(pcs),*pcs))
            counts={'instructions':0,'table_read_bytes':0}
            def code(_uc,_address,_size,_data):counts['instructions']+=1
            def read(_uc,_access,address,size,_value,_data):
                if TABLE<=address<TABLE+16*len(chunks):counts['table_read_bytes']+=size
            uc.hook_add(UC_HOOK_CODE,code);uc.hook_add(UC_HOOK_MEM_READ,read)
            total=execute(uc,syms['run_'+mode],[INDEX,TABLE,len(chunks),TRACE,iterations],10_000_000)
            callbacks=struct.unpack('<I',uc.mem_read(syms['callback_count'],4))[0]
            if total!=sum(k+1 for k in selected) or callbacks!=iterations:
                raise ValueError('Lookup/callback mismatch in '+pattern+'/'+mode)
            results.setdefault(pattern,{})[mode]=counts
    result={'status':'pass','smoke':'full C boundary/reload/owner/callback smoke passed in AArch64',
            'iterations_per_pattern':iterations,'seed':0x4038015,'synthetic_results':results,
            'compile_commands':[smoke_command,loop_command],
            'scope':'Synthetic counts, not CPU cycles, physical TECNO FPS or whole-game equivalence'}
    (out/'result.json').write_text(json.dumps(result,indent=2));return result


def main():
    p=argparse.ArgumentParser(description=__doc__.splitlines()[0]);p.add_argument('--llvm-bin',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True);p.add_argument('--iterations',type=int,default=512);args=p.parse_args()
    r=verify(args.llvm_bin,args.out,args.iterations)
    print(json.dumps({k:v for k,v in r.items() if k!='compile_commands'},indent=2))


if __name__=='__main__':main()
