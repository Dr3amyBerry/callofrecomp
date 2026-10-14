#!/usr/bin/env python3
"""Evidence-based CPU hot-spot report for CallofRecomp on physical Android.

Takes private/simpleperf analysis JSON and an independent, stationary gameplay
frame-stat capture. Sample-to-ms estimates assume a configured task-clock
frequency and the observed median FPS persist during the profiled interval;
they are rough on-CPU *attribution estimates*, not measured function times.
GPU execution, blocked waiting, and unresolved samples are NOT represented.
"""
from __future__ import annotations
import argparse,json
from pathlib import Path
from analyze_frame_stats import selected_stats,parse_frames

def sample_time_ms(samples: int, *, hz: float, duration_s: float, fps: float) -> float:
    if min(hz,duration_s,fps)<=0: raise ValueError('Hz/duration/FPS must be positive')
    if samples<0: raise ValueError('Sample count must be nonnegative')
    return (samples/hz)*1000.0/(duration_s*fps)

def make_report(analysis: dict, frame_log: str, *, hz: float,duration_s: float,top: int=16) -> dict:
    if top<=0:raise ValueError('top must be >0')
    frames=selected_stats(parse_frames(frame_log),last=40)
    total=int(analysis['total_cpu_samples'])
    if total<=0:raise ValueError('Cannot extrapolate empty profile')
    fps=float(frames['median_fps'])
    def row(name,count):
        v=int(count)
        return {
            'name':name,'samples':v,'share_process_cpu_samples_pct':round(100*v/total,2),
            'indicative_cpu_ms_per_frame':round(sample_time_ms(v,hz=hz,duration_s=duration_s,fps=fps),3)
        }
    def rank(rows):
        return sorted(rows,key=lambda x:-x['samples'])
    sources=rank([row(n,c) for n,c in analysis['by_dso'].items()])
    functions=rank([row(x['module']+'/'+x['entry_va'],x['samples'])
                    for x in analysis['resolved_guest']['top_body_function_samples']])[:top]
    nmain=int(analysis['libmain_cpu_samples'])
    first=analysis.get('by_thread',[])
    threads=rank([row(str(t['tid']),t['samples']) for t in first])
    min_cpu_target=1000/60
    return {
        'goal_fps':60,
        'reference':frames,
        'cpu_frame_budget_for_60fps_ms':round(min_cpu_target,3),
        'reference_cpu_budget_excess_ms':round(frames['median_cpu_ms']-min_cpu_target,3),
        'profile':{
            'duration_s':duration_s,'sampling_rate_hz':hz,'sample_count':total,
            'libmain_samples':nmain,
            'libmain_fraction_pct':round(nmain/total*100,2),
            'sampling_estimated_process_cpu_seconds':round(total/hz,2),
            'dsos':sources,'threads':threads[:top],
            'guest_functions':functions,
            'unresolved_native_source_samples':analysis['resolved_guest'].get('unresolved_source_samples'),
            'unique_ghidra_body_samples':analysis['resolved_guest'].get('unique_ghidra_body_samples')
        },
        'status':'DIAGNOSTIC_ONLY_NOT_A_PERFORMANCE_ATTEMPT',
        'limitations':[
            'CPU samples are user-space task-clock, not GPU execution time.',
            'Estimated ms/frame = (function samples / sampling rate) / (profile duration * separate median FPS) * 1000; indicative only, not measured inclusive/exclusive function time.',
            'Sampled original function identity relies on Ghidra recovered body and compiler line attribution, not a complete guest call stack.',
            'Graphics driver CPU samples do not imply GPU hardware utilization. The renderer can block outside sampled user-space.',
            'Frame stats are ~one-second window medians, not individual-frame percentiles.',
            'The five-failed-attempts counter stays unchanged: diagnostic capture is not an A/B optimization experiment.'
        ]
    }

def main():
    p=argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument('--analysis',type=Path,required=True)
    p.add_argument('--frames',type=Path,required=True)
    p.add_argument('--duration',type=float,required=True)
    p.add_argument('--rate',type=float,default=350)
    p.add_argument('--top',type=int,default=16)
    p.add_argument('--output',type=Path)
    args=p.parse_args()
    doc=make_report(json.loads(args.analysis.read_text(encoding='utf-8')),
                    args.frames.read_text(encoding='utf-8',errors='replace'),
                    hz=args.rate,duration_s=args.duration,top=args.top)
    text=json.dumps(doc,ensure_ascii=False,indent=2,sort_keys=True)+'\n'
    if args.output:
        args.output.write_text(text,encoding='utf-8')
        print('Report saved:',args.output)
    else:print(text)
if __name__=='__main__':
    main()
