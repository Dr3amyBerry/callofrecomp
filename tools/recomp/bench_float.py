#!/usr/bin/env python3
"""Common binary80 conversion throughput; not a game or GPU benchmark."""
import argparse
import os
from pathlib import Path
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cc', default=os.environ.get('RECOMP_TEST_CC', 'cc'))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    harness = r'''
#include "recomp_rt.h"
#include "tests/fixtures/recomp_float_reference.h"
#include <stdio.h>
#include <time.h>
__attribute__((noinline)) double baseline(u128 v){return reference_f2d(v,10);}
__attribute__((noinline)) double optimized(u128 v){return f2d(v,10);}
int main(void) {
    u128 inputs[1024];for(int i=0;i<1024;i++)inputs[i]=d2f(i*0.125+0.1,10);
    for(int repeat=0;repeat<3;repeat++) {
        uint64_t expected=0;
        for(int mode=0;mode<2;mode++) {
            uint64_t sum=0;clock_t start=clock();
            for(int i=0;i<10000000;i++) {
                double d=mode?optimized(inputs[i&1023]):baseline(inputs[i&1023]);
                uint64_t b;memcpy(&b,&d,8);sum+=b;
            }
            if(!mode)expected=sum;else if(sum!=expected)return 1;
            printf("%s %.3f ms checksum %llu\n",mode?"optimized":"baseline",
                   1000.0*(clock()-start)/CLOCKS_PER_SEC,(unsigned long long)sum);
        }
    }
    return 0;
}
'''
    with tempfile.TemporaryDirectory() as directory:
        source = Path(directory) / 'bench.c'
        executable = Path(directory) / ('bench.exe' if os.name == 'nt' else 'bench')
        source.write_text(harness)
        subprocess.run([args.cc, '-O1', '-I' + str(root / 'tools/recomp'),
                        '-I' + str(root), str(source), '-o', str(executable)], check=True)
        subprocess.run([str(executable)], check=True)


if __name__ == '__main__':
    main()
