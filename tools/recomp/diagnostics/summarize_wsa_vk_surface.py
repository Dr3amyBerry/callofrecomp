#!/usr/bin/env python3
"""Parse native WSA Vulkan presentation-probe logs.

Input workload is ONLY Vulkan clear-to-color swapchain frames. Do not use
these FPS figures as CallofRecomp FPS or claim an in-game improvement.
"""
from __future__ import annotations
import argparse
import json
import re
from pathlib import Path
from statistics import median

WINDOW = re.compile(
    r"VK_WINDOW fps=(\d+(?:\.\d+)?) frames=(\d+) elapsed=(\d+(?:\.\d+)?) "
    r"thread_cpu_ms_per_frame=(\d+(?:\.\d+)?)"
)
RESULT = re.compile(
    r"VK_RESULT fps=(\d+(?:\.\d+)?) frames=(\d+) seconds=(\d+(?:\.\d+)?) "
    r"thread_cpu_ms_per_frame=(\d+(?:\.\d+)?) "
    r"acquire_wall_ms_per_frame=(\d+(?:\.\d+)?) "
    r"present_wall_ms_per_frame=(\d+(?:\.\d+)?) "
    r"present_mode=(\w+) resolution=(\d+)x(\d+)"
)
READY = re.compile(
    r"VK_READY width=(\d+) height=(\d+) gpu=(.+?) image_count=(\d+) "
    r"fifo=(\d+) immediate_available=(\d+) present_mode=(\d+)"
)

def parse_one(text: str)->dict:
    parts=text.split('VK_INIT NativeActivity created; waiting for Android surface')
    if len(parts)<2:raise ValueError('No NativeActivity run found in logcat')
    latest=parts[-1]
    r=RESULT.findall(latest)
    w=WINDOW.findall(latest)
    p=READY.findall(latest)
    if len(r)!=1 or len(p)!=1 or len(w)<10:
        raise ValueError(f'Incomplete Vulkan presentation run: result={len(r)} ready={len(p)} windows={len(w)}')
    fps=float(r[0][0])
    frame_count=int(r[0][1])
    seconds=float(r[0][2])
    windows=sorted(float(x[0]) for x in w)
    if not (10<seconds<35_000 and frame_count>0 and fps>0):
        raise ValueError('Invalid Vulkan measurement')
    if abs(frame_count/seconds-fps)>0.3:
        raise ValueError('Invalid FPS/frame count consistency')
    n=len(windows)
    return {
        'type':'Vulkan native Android swapchain clear-only, NOT CallofRecomp',
        'workload':'single solid-color render pass, no geometry/textures/shaders/game logic/HUD',
        'wsa_only':True,
        'gameplay_fps_comparable':False,
        'gpu_name':p[0][2],
        'present_mode':r[0][6],
        'immediate_available':bool(int(p[0][5])),
        'resolution_px':[int(r[0][7]),int(r[0][8])],
        'frame_count':frame_count,
        'elapsed_s':seconds,
        'average_fps':fps,
        'median_one_second_fps':median(windows),
        'p10_one_second_fps':windows[max(0,(n+9)//10-1)],
        'one_second_windows':n,
        'thread_cpu_ms_per_frame':float(r[0][3]),
        'acquire_wall_ms_per_frame':float(r[0][4]),
        'present_wall_ms_per_frame':float(r[0][5]),
    }

def main():
    p=argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument('--log',required=True,type=Path)
    p.add_argument('--json-out',type=Path)
    args=p.parse_args()
    d=parse_one(args.log.read_text(encoding='utf-8',errors='replace'))
    out=json.dumps(d,ensure_ascii=False,indent=2)+'\n'
    if args.json_out:
        if args.json_out.exists():p.error('output already exists')
        args.json_out.write_text(out,encoding='utf-8')
    print(out)
if __name__=='__main__':main()
