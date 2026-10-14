#!/usr/bin/env python3
"""Capture an actual CallofRecomp WSA gameplay FPS baseline.

Requires an already loaded stationary 3D gameplay scene and opt-in frame_stats.
Captures new windows only, rejects menu/loading-like CPU profiles, and stores
raw frame summaries plus JSON. No game APK or save modification.
"""
from __future__ import annotations
from datetime import datetime,timezone
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from analyze_frame_stats import parse_frames,selected_stats

DEFAULT_SERIAL="127.0.0.1:58526"

from angle_wsa_trial import logcat_verdict

def verify_renderer(serial: str, pid: str, backend: str) -> dict:
    """Refuse to label a gameplay sample ANGLE without current-process Vulkan evidence."""
    def setting(key: str) -> str:
        return android(serial, 'shell', 'settings', 'get', 'global', key).decode('utf-8','replace').strip()
    debug=setting('angle_debug_package')
    package=setting('angle_gl_driver_selection_pkgs')
    values=setting('angle_gl_driver_selection_values')
    all_angle=setting('angle_gl_driver_all_angle')
    if backend=='gl4es':
        if any(x not in ('', 'null') for x in (debug,package,values,all_angle)):
            raise ValueError('GL4ES reference requires all ANGLE overrides disabled')
        return {'backend':'gl4es','driver_settings_clear':True,'vulkan_verified':False}
    if (debug,package,values)!=( 'org.chromium.angle','org.callofrecomp','angle'):
        raise ValueError('ANGLE is not selected exclusively for CallofRecomp')
    if all_angle not in ('','null'):
        raise ValueError('Global ANGLE override is unsafe for comparison')
    installed=android(serial,'shell','pm','path','org.chromium.angle').decode('utf-8','replace')
    if 'package:' not in installed:
        raise ValueError('ANGLE package not installed')
    epoch=int(android(serial,'shell','date','+%s').decode().strip())
    log=android(serial,'logcat','-d','-v','epoch','-t','5000').decode('utf-8','replace')
    evidence=logcat_verdict(log,epoch-600,pid)
    if not evidence['angle_vulkan_execution_verified']:
        raise ValueError('ANGLE Vulkan not verified in this game PID')
    return {'backend':'angle','driver_settings_clear':False,'vulkan_verified':True,
            'log_evidence':evidence}



def isolate_fresh_windows(before: str,after: str,last: int):
    """Extract after-only summary windows; fail closed if a log was rotated."""
    if not after.startswith(before):
        raise ValueError("log file rotated/truncated during capture; repeat with a stable log")
    fresh=after[len(before):]
    rows=parse_frames(fresh)
    if len(rows)<last:
        raise ValueError(f"Only {len(rows)} new windows; wanted {last}")
    selected=selected_stats(rows,last=last)
    if selected['likely_mixed_loading_or_menu']:
        raise ValueError("Likely mixed menu/loading windows; repeat with fixed camera")
    if selected['median_cpu_ms']<5.0:
        raise ValueError("Likely main menu or unloaded game; require real gameplay CPU time")
    return fresh,selected

def android(serial: str,*args,timeout=20)->bytes:
    p=subprocess.run(['adb','-s',serial,*args],capture_output=True,timeout=timeout)
    if p.returncode:raise RuntimeError(p.stderr.decode('utf-8','replace')[-900:])
    return p.stdout

def read_log(serial: str)->str:
    return android(serial,'exec-out','run-as','org.callofrecomp','cat',
                   'files/profile/codrecomp.log').decode('utf-8','replace')

def main():
    ap=argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--serial',default=DEFAULT_SERIAL)
    ap.add_argument('--backend',choices=('gl4es','angle'),default='gl4es',
                    help='Verify and label the actual EGL/GLES backend; ANGLE requires Vulkan Logcat proof')
    ap.add_argument('--seconds',type=int,default=75)
    ap.add_argument('--last',type=int,default=60)
    ap.add_argument('--out',type=Path,required=True,help='output stem; .log and .json')
    ap.add_argument('--uncapped-diagnostic',action='store_true',
                    help='metadata ONLY: APK is an experimental x86_64 build without the 60-FPS host cap')
    args=ap.parse_args()
    if not 10<=args.seconds<=180:ap.error('--seconds must be 10..180')
    if not 10<=args.last<=150:ap.error('--last must be 10..150')
    out_json=args.out.with_suffix('.json')
    out_log=args.out.with_suffix('.log')
    if out_json.exists() or out_log.exists():ap.error('refusing to overwrite previous trial')
    args.out.parent.mkdir(parents=True,exist_ok=True)
    abi=android(args.serial,'shell','getprop','ro.product.cpu.abi').decode().strip()
    if abi!='x86_64':ap.error(f'target must be WSA x86_64, got {abi!r}')
    pid=android(args.serial,'shell','pidof','org.callofrecomp').decode().strip()
    if not pid:ap.error('game is not running')
    backend_before=verify_renderer(args.serial,pid,args.backend)
    before=read_log(args.serial)
    stamp=datetime.now(timezone.utc).isoformat()
    started=time.monotonic()
    print(f"Collecting {args.seconds}s of real WSA gameplay windows, PID {pid}",
          flush=True)
    time.sleep(args.seconds)
    after_pid=android(args.serial,'shell','pidof','org.callofrecomp').decode().strip()
    if pid!=after_pid: raise ValueError('Game PID changed during benchmark; refuse this capture')
    backend_after=verify_renderer(args.serial,pid,args.backend)
    if backend_before['backend']!=backend_after['backend']:
        raise ValueError('Renderer changed during benchmark')
    after=read_log(args.serial)
    elapsed=time.monotonic()-started
    fresh,stats=isolate_fresh_windows(before,after,args.last)
    out_log.write_text(fresh,encoding='utf-8')
    result={
        'type':'actual CallofRecomp GAMEPLAY, WSA x86_64',
        'stage':('ANGLE Vulkan gameplay in WSA, experimental' if args.backend=='angle'
                 else 'GL4ES gameplay uncapped WSA diagnostic (NOT Vulkan)'
                 if args.uncapped_diagnostic else 'GL4ES gameplay baseline/control, NOT Vulkan renderer'),
        'backend':args.backend,
        'backend_before':backend_before,
        'backend_after':backend_after,
        'uncapped_diagnostic':args.uncapped_diagnostic,
        'capture_started_utc':stamp,
        'capture_duration_s':round(elapsed,2),
        'device':args.serial,'pid':pid,'scene':'Camp Toccoa training, static spawn',
        'profile':'Equilibrado','frame_summary_windows':len(parse_frames(fresh)),
        'analyzed_last_windows':args.last,
        'stats':stats,'file_sha256':hashlib.sha256(fresh.encode()).hexdigest(),
        'limitations':[
            'FPS percentiles are of ~one-second averages, not raw frames',
            ('WSA diagnostic host 60-FPS cap removed; STILL GL4ES, NOT Vulkan'
             if args.uncapped_diagnostic else
             'GL4ES→ANGLE/GLES2→Vulkan active ONLY on WSA; still 60-FPS host cap'
             if args.backend=='angle' else
             'Regular engine host 60-FPS cap is enabled; no Vulkan integration'),
            'WSA is an x86_64 emulator and not a physical ARM64 Android GPU',
            'Manual screenshot and matching scene required for valid A/B/A'
        ]
    }
    out_json.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',
                        encoding='utf-8')
    print(json.dumps(result,ensure_ascii=True,indent=2),flush=True)

if __name__=='__main__':main()
