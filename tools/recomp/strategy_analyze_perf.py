#!/usr/bin/env python3
"""Resolve one real Simpleperf sample capture to original guest functions.

Use exact unstripped ELF from the APK, verified by capture_android_strategy.py.
All p-code, Ghidra maps, PE-derived addresses, app traces and outputs remain
PRIVATE in ignored local paths. This report is statistical, NOT a call stack.
"""
from __future__ import annotations
import argparse
from collections import Counter
import json,os
from pathlib import Path
import sys

from resolve_guest_samples import (
    parse_native_pcs,symbolize_native_pcs,resolve_native_samples
)

DEFAULT_MODULES=('codsp','cgamex86','gamex86','uix86')

def aggregate_sample_rows(rows):
    """Pure aggregation over (DSO basename, ELF PC, CPU, PID, TID, symbol)."""
    dso=Counter()
    cpu=Counter()
    thread=Counter()
    main_pcs=Counter()
    symbols=Counter()
    n=0
    for name,pc,core,pid,tid,symbol in rows:
        n+=1
        dso[name]+=1
        cpu[int(core)]+=1
        thread[(int(pid),int(tid))]+=1
        if name=='libmain.so':
            main_pcs[int(pc)]+=1
            symbols[symbol]+=1
    if n==0: raise ValueError('The profiler returned no samples')
    return {
        'total_cpu_samples':n,
        'libmain_cpu_samples':sum(main_pcs.values()),
        'by_dso':dict(dso.most_common()),
        'by_cpu':dict(cpu),
        'by_thread':[{'pid':p,'tid':t,'samples':v} for (p,t),v in thread.most_common()],
        'top_main_symbols':symbols.most_common(30),
        '_main_pcs':main_pcs,
    }

def ndk_directory(arg):
    if arg:return Path(arg).resolve()
    sdk=os.environ.get('ANDROID_HOME')
    if not sdk:raise ValueError('Supply --ndk or set ANDROID_HOME')
    items=sorted((Path(sdk)/'ndk').glob('*/simpleperf/app_profiler.py'))
    if not items:raise ValueError('Android NDK Simpleperf is not installed')
    return items[-1].parents[1]

def analyze(perf_data: Path,elf: Path,generated: Path,maps: Path,
            output: Path,ndk: Path,top: int=75):
    if top<=0:raise ValueError('--top must be positive')
    if output.exists(): raise ValueError('Refuse overwriting earlier profiler analysis')
    for x in (perf_data,elf,generated,maps):
        if not x.exists():raise ValueError(f'Missing required private path {x}')
    sys.path.insert(0,str(ndk/'simpleperf'))
    from simpleperf_report_lib import ReportLib
    lib=ReportLib()
    lib.SetRecordFile(str(perf_data))
    rows=[]
    while (sample:=lib.GetNextSample()) is not None:
        sym=lib.GetSymbolOfCurrentSample()
        if sym:
            # Note: vaddr_in_file is ELF-relative according to Simpleperf,
            # not a raw Android process virtual address.
            name=Path(sym.dso_name).name
            pc=int(sym.vaddr_in_file)
            symbol=sym.symbol_name
        else:
            name='(unresolved)'
            pc=0
            symbol='(unresolved)'
        rows.append((name,pc,sample.cpu,sample.pid,sample.tid,symbol))
    payload=aggregate_sample_rows(rows)
    native_pcs=payload.pop('_main_pcs')
    if not native_pcs:raise ValueError('No libmain samples: cannot attribute guest functions')
    tsv=output.with_name(output.stem+'.native_pcs.tsv')
    if tsv.exists():raise ValueError('Private TSV already exists; choose a new output')
    with tsv.open('w',encoding='utf-8') as f:
        f.write('elf_pc\tsamples\n')
        for pc,weight in sorted(native_pcs.items()):
            f.write(f'0x{pc:x}\t{weight}\n')
    addr2line=list((ndk/'toolchains/llvm/prebuilt').glob('*/bin/llvm-addr2line*'))
    if not addr2line:raise ValueError('NDK addr2line unavailable')
    native_source=symbolize_native_pcs(parse_native_pcs(tsv),elf,addr2line[0])
    documents=[]
    for mod in DEFAULT_MODULES:
        path=maps/(mod+'_function_map_v2.json')
        if not path.is_file():
            raise ValueError(f'Missing Ghidra v2 body map: {path}')
        documents.append(json.loads(path.read_text('utf-8')))
    generated_sources=sorted(generated.glob('*_recomp*.c'))
    if not generated_sources:raise ValueError('Missing private generated C sources')
    guest=resolve_native_samples(native_source,generated_sources,documents,top=top)
    payload['resolved_guest']=guest
    payload['warning']='ELF Build ID must match installed APK; samples are sampled CPU user time, not GPU or exact function duration.'
    output.write_text(json.dumps(payload,indent=2,ensure_ascii=False)+'\n',
                      encoding='utf-8')
    return payload

def main():
    p=argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument('--perf',required=True,type=Path)
    p.add_argument('--elf',required=True,type=Path)
    p.add_argument('--generated',required=True,type=Path)
    p.add_argument('--maps',required=True,type=Path)
    p.add_argument('--ndk')
    p.add_argument('--out',required=True,type=Path)
    p.add_argument('--top',type=int,default=75)
    args=p.parse_args()
    result=analyze(args.perf,args.elf,args.generated,args.maps,
                   args.out,ndk_directory(args.ndk),args.top)
    print('CPU samples:',result['total_cpu_samples'],
          'libmain samples:',result['libmain_cpu_samples'])
    for f in result['resolved_guest']['top_body_function_samples'][:12]:
        print(f['module'],f['entry_va'],f['samples'])

if __name__=='__main__':main()
