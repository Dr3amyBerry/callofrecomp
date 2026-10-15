"""Summarize opt-in guest GL windows. CPU timings are not GPU execution time."""
import argparse
import json
from pathlib import Path
import re

PROFILE=('arrays elements ranges array_verts indices tex_bind tex_image tex_sub '
         'buf_bind buf_data_bytes buf_sub_bytes lock unlock active_tex').split()
CATEGORIES=('draw','tex_bind','tex_upload','array','lock','state','buffer')

def windows(text,prefix,keys,last):
    records=[]
    for line in text.splitlines():
        if not line.startswith(prefix):continue
        values=dict(re.findall(r'(\w+)=(-?\d+)',line[len(prefix):]))
        if any(key not in values for key in ('frames',*keys)):
            raise ValueError('incomplete GL window')
        row={key:int(values[key]) for key in ('frames',*keys)}
        if row['frames']<=0 or any(value<0 for value in row.values()):
            raise ValueError('invalid GL counter')
        records.append(row)
    if last<1 or len(records)<last:raise ValueError('insufficient GL windows')
    return records[-last:]

def analyze(text,last=6):
    profile=windows(text,'gl profile: ',PROFILE,last)
    timing_keys=[name+suffix for name in CATEGORIES for suffix in ('_calls','_us')]
    timing=windows(text,'gl cpu: ',timing_keys,last)
    frames=sum(row['frames'] for row in profile)
    timed_frames=sum(row['frames'] for row in timing)
    return {'windows_per_series':last,'profile_frames':frames,'timed_frames':timed_frames,
            'guest_counters_per_frame':{key:sum(row[key] for row in profile)/frames for key in PROFILE},
            'thread_cpu_ms_per_frame':{name:sum(row[name+'_us'] for row in timing)/timed_frames/1000 for name in CATEGORIES},
            'timed_calls_per_frame':{name:sum(row[name+'_calls'] for row in timing)/timed_frames for name in CATEGORIES},
            'limitations':'instrumented APK; calling-thread CPU includes timer overhead, not GPU time; guest calls are not GLES submissions; payload/VBO counters do not prove geometry reusability; tail selection requires externally verified gameplay'}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('log',type=Path);parser.add_argument('--last',type=int,default=6)
    parser.add_argument('--out',type=Path)
    args=parser.parse_args()
    try:result=analyze(args.log.read_text(encoding='utf-8',errors='replace'),args.last)
    except ValueError as error:parser.error(str(error))
    output=json.dumps(result,indent=2)
    if args.out:args.out.write_text(output,encoding='utf-8')
    print(output)

if __name__=='__main__':main()
