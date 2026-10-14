#!/usr/bin/env python3
"""Reproducible private CPU capture on physical Android for CallofRecomp.

Refuses to symbolize an APK against an unmatched unstripped ELF Build ID.
Does NOT change APK, game assets, saves or build flags; runs Simpleperf
and lightweight CPU-frequency/thermal telemetry on an already-open scene.
Traces remain under ignored .local/profiles. GPU counters must be obtained
separately using supported AGI/Perfetto tracing; this is CPU-only.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import threading
import time
import zipfile

ROOT=Path(__file__).resolve().parents[2]
PRIVATE=ROOT/'.local/profiles'
BUILD_ID=re.compile(r'Build ID:\s*([0-9a-fA-F]+)')

def safe_prefix(prefix: str) -> bool:
    return bool(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}',prefix))

def parse_build_id(output: str) -> str:
    found=BUILD_ID.findall(output)
    if len(found)!=1:raise ValueError('A unique ELF Build ID is required')
    return found[0].lower()

def base_apk_path(output: str) -> str:
    paths=[x.split('package:',1)[1].strip() for x in output.splitlines()
           if x.startswith('package:')]
    found=[x for x in paths if x.endswith('/base.apk')]
    if len(found)!=1:raise ValueError('Cannot uniquely identify installed base.apk')
    return found[0]

def ndk_path(explicit: str|None) -> Path:
    if explicit:return Path(explicit).resolve()
    sdk=os.environ.get('ANDROID_HOME')
    if not sdk:raise ValueError('Supply --ndk or set ANDROID_HOME')
    candidates=sorted((Path(sdk)/'ndk').glob('*/simpleperf/app_profiler.py'))
    if not candidates:raise ValueError('Android NDK Simpleperf not found')
    return candidates[-1].parents[1]

def llvm_readelf(ndk: Path) -> Path:
    for bin_dir in (ndk/'toolchains/llvm/prebuilt').glob('*/bin'):
        for name in ('llvm-readelf.exe','llvm-readelf'):
            exe=bin_dir/name
            if exe.is_file():return exe
    raise ValueError('NDK llvm-readelf missing')

def capture(serial,package,unstripped,ndk,duration,prefix):
    if not safe_prefix(prefix):raise ValueError('Use an ASCII prefix without path separators')
    if not 10<=duration<=90:raise ValueError('Duration must be 10..90 seconds')
    PRIVATE.mkdir(exist_ok=True)
    out=PRIVATE/(prefix+'.perf.data')
    meta=PRIVATE/(prefix+'.json')
    raw=PRIVATE/(prefix+'.installed.apk')
    pulled=PRIVATE/(prefix+'.installed.libmain.so')
    symdir=PRIVATE/(prefix+'_symbols')
    if any(x.exists() for x in (out,meta,raw,pulled,symdir)):
        raise ValueError('This prefix already has results; never overwrite an earlier capture')
    if not unstripped.is_file():raise ValueError('Unstripped ELF missing')
    adb=['adb','-s',serial]
    def call(cmd,*,timeout=25):
        return subprocess.run(cmd,capture_output=True,text=True,timeout=timeout)
    def shell(cmd):
        p=call(adb+['shell',cmd],timeout=17)
        return {'ok':p.returncode==0,
                'stdout':p.stdout.strip()[:9000],
                'error':p.stderr.strip()[:500]}
    proc=call(adb+['shell','pm','path',package])
    if proc.returncode:raise RuntimeError('Package not installed on selected device')
    installed=base_apk_path(proc.stdout)
    subprocess.run(adb+['pull',installed,str(raw)],check=True,timeout=150)
    with zipfile.ZipFile(raw) as archive:
        pulled.write_bytes(archive.read('lib/arm64-v8a/libmain.so'))
    readelf=llvm_readelf(ndk)
    ids=[]
    for elf in (pulled,unstripped):
        result=subprocess.run([str(readelf),'-n',str(elf)],
                              check=True,capture_output=True,text=True,timeout=35)
        ids.append(parse_build_id(result.stdout))
    if ids[0]!=ids[1]:
        raise RuntimeError('Installed APK and unstripped ELF Build IDs DIFFER; refusing misleading profile')
    symdir.mkdir()
    shutil.copy2(unstripped,symdir/'libmain.so')
    for file in ('libGL.so','libSDL2.so'):
        origin=ROOT/'build-android-native/lib'/file
        if origin.is_file():shutil.copy2(origin,symdir/file)
    report={'utc':datetime.now(timezone.utc).isoformat(),'package':package,
            'duration_requested_sec':duration,'installed_unstripped_build_id':ids[0],
            'gpu_counters_not_claimed':True,
            'before_thermal':shell('dumpsys thermalservice'),
            'gpu_devfreq_probe':shell('cat /sys/class/devfreq/13040000.mali/cur_freq'),
            'freq_samples':[]}
    done=threading.Event()
    def sample_loop():
        start=time.monotonic()
        while not done.is_set():
            report['freq_samples'].append({
                't_sec':round(time.monotonic()-start,1),
                'cpu6':shell('cat /sys/devices/system/cpu/cpu6/cpufreq/scaling_cur_freq'),
                'cpu7':shell('cat /sys/devices/system/cpu/cpu7/cpufreq/scaling_cur_freq')})
            done.wait(2)
    sampler=threading.Thread(target=sample_loop,daemon=True)
    cmd=[sys.executable,str(ndk/'simpleperf/app_profiler.py'),'-p',package,
         '--unrepresentative_profile_debug_app','--disable_adb_root',
         '-r',f'-e task-clock:u -f 350 --duration {duration}',
         '-lib',str(symdir),'-o',str(out),'-nb','--ndk_path',str(ndk)]
    started=time.monotonic()
    sampler.start()
    try:
        subprocess.run(cmd,cwd=ROOT,env=dict(os.environ,ANDROID_SERIAL=serial),
                       check=True,timeout=duration+150)
        report['status']='complete'
    except Exception as error:
        report['status']='failed'
        report['error']=str(error)[:350]
        raise
    finally:
        done.set()
        sampler.join(timeout=3)
        report['elapsed_seconds']=round(time.monotonic()-started,2)
        report['after_thermal']=shell('dumpsys thermalservice')
        meta.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',
                        encoding='utf-8')
    print('Verified build ID:',ids[0], 'Perf data:',out, 'size:',out.stat().st_size)

def main():
    p=argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument('--serial',required=True)
    p.add_argument('--package',default='org.callofrecomp')
    p.add_argument('--unstripped',type=Path,required=True)
    p.add_argument('--ndk',help='Android NDK directory, default latest under ANDROID_HOME')
    p.add_argument('--duration',type=int,default=20)
    p.add_argument('--prefix',required=True)
    a=p.parse_args()
    capture(a.serial,a.package,a.unstripped,ndk_path(a.ndk),a.duration,a.prefix)

if __name__=='__main__':
    main()
