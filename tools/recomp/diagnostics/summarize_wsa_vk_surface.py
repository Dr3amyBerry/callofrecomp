#!/usr/bin/env python3
"""Parse native WSA Vulkan presentation-probe logs.

Input workload is an isolated Vulkan clear, indexed-mesh or sampled-texture swapchain demo,
never full CallofRecomp gameplay. Do not claim an in-game FPS improvement.
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
SCENE = re.compile(r'VK_SCENE name=(clear|mesh|texture), integration=standalone, gameplay=0')
TEXTURE_READY = re.compile(r'VK_TEXTURE_READY width=(\d+) height=(\d+) mip_levels=(\d+) descriptor_sets=(\d+) sampler=(\w+) transfer=(\w+) image_layout=(\w+)')
MESH_READY = re.compile(r'VK_MESH_READY vertices=(\d+) indices=(\d+) draws_per_frame=(\d+) procedural_checker=(\d+)')
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
    scenes=SCENE.findall(latest)
    if len(scenes)>1:raise ValueError('Conflicting scene markers in one session')
    scene=scenes[0] if scenes else 'clear'  # Older clear-only builds have no marker.
    meshes=MESH_READY.findall(latest)
    if scene in ('mesh','texture') and len(meshes)!=1:
        raise ValueError('Mesh/texture scene missing pipeline/buffer/draw readiness marker')
    if scene=='clear' and meshes:
        raise ValueError('Clear scene unexpectedly reports indexed mesh resources')
    textures=TEXTURE_READY.findall(latest)
    if scene=='texture' and len(textures)!=1:
        raise ValueError('Texture scene missing Vulkan VkImage/descriptor readiness marker')
    if scene!='texture' and textures:
        raise ValueError('Nontexture scene unexpectedly reports sampled VkImage')
    if scene=='texture' and (meshes[0][3]!='0' or textures[0][5]!='staging' or
                             textures[0][6]!='shader_read_only'):
        raise ValueError('Texture scene has inconsistent sampled-image configuration')
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
        'type':'Standalone Vulkan Android '+scene+' benchmark, NOT CallofRecomp',
        'scene':scene,
        'workload':('indexed quad with sampled VkImage RGBA8, staging copy, descriptor/sampler and shaders; no game assets/simulation/HUD'
                    if scene=='texture' else
                    'indexed quad (4 vertices, 6 indices), vertex+fragment SPIR-V, procedural checker; no game assets/simulation/HUD'
                    if scene=='mesh' else
                    'single solid-color render pass, no geometry/textures/shaders/game logic/HUD'),
        'mesh':({'vertices':int(meshes[0][0]),'indices':int(meshes[0][1]),
                 'draws_per_frame':int(meshes[0][2]),
                 'procedural_checker':bool(int(meshes[0][3]))}
                if scene in ('mesh','texture') else None),
        'texture':({'width':int(textures[0][0]),'height':int(textures[0][1]),
                    'mip_levels':int(textures[0][2]),
                    'descriptor_sets':int(textures[0][3]),
                    'sampler':textures[0][4],
                    'transfer':textures[0][5],
                    'image_layout':textures[0][6]}
                   if scene=='texture' else None),
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
