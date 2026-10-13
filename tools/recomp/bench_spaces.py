#!/usr/bin/env python3
"""Owned synthetic RAM/register workload; not a whole-game FPS benchmark."""
import argparse
import os
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace

from pcode2c import generate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cc', default=os.environ.get('RECOMP_TEST_CC', 'cc'))
    args = parser.parse_args()
    pe = SimpleNamespace(imports=lambda: [], exports=lambda: [], image_base=4096,
                         size_of_image=4096, entry_rva=0)
    ops = []
    for _ in range(64):
        ops += [('INT_ADD', ('r', 0, 4), [('r', 0, 4), ('c', 1, 4)]),
                ('STORE', None, [('c', 0, 8), ('r', 4, 4), ('r', 0, 4)])]
    sources = [generate([(4096, 1, ops)], {}, pe, 'synthetic', name,
                        separate_spaces=separate)[0][0]
               for name, separate in [('baseline', False), ('optimized', True)]]
    harness = r'''
#include <stdio.h>
#include <time.h>
uint8_t *MEM,R[8192],U[0x400000];uint32_t PC;int recomp_miss;
int main(void) {
    static uint8_t memory[256]; MEM=memory;
    for(int repeat=0;repeat<3;repeat++) for(int mode=0;mode<2;mode++) {
        memset(R,0,sizeof R);memset(MEM,0,256);wr(R+4,4,128);
        clock_t start=clock();
        for(int i=0;i<2000000;i++) {
            PC=4096;if(mode)optimized_chunk_0();else baseline_chunk_0();
        }
        if(rd(R,4)!=128000000 || rd(MEM+128,4)!=128000000 || PC!=4097)return 1;
        printf("%s %.3f ms checksum 128000000\n",mode?"optimized":"baseline",
               1000.0*(clock()-start)/CLOCKS_PER_SEC);
    }
    return 0;
}
'''
    with tempfile.TemporaryDirectory() as directory:
        source = Path(directory) / 'bench.c'
        executable = Path(directory) / ('bench.exe' if os.name == 'nt' else 'bench')
        source.write_text('\n'.join(sources) + harness)
        subprocess.run([args.cc, '-O1', '-I' + str(Path(__file__).parent),
                        str(source), '-o', str(executable)], check=True)
        subprocess.run([str(executable)], check=True)


if __name__ == '__main__':
    main()
