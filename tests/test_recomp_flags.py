"""Compiled full-state equivalence for architectural flag elimination."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/recomp'))
from pcode2c import generate


def flags(value):
    return [('COPY', ('r', offset, 1), [value])
            for offset in (0x200, 0x202, 0x206, 0x207, 0x20b)]


def fixture():
    return [
        (0x1000, 1, flags(('r', 0, 1))),
        (0x1001, 1, [('INT_CARRY', ('r', 0x200, 1), [('r', 0, 4), ('r', 4, 4)])]
         + flags(('r', 8, 1))),
        (0x1002, 1, [('CBRANCH', None, [('m', 0x1005, 4), ('r', 0x200, 1)])]),
        (0x1003, 1, [('COPY', ('r', 64, 1), [('r', 0x205, 3)])]
         + flags(('c', 7, 1)) + [('BRANCH', None, [('m', 0x1006, 4)])]),
        (0x1004, 1, [
            ('COPY', ('r', 0x200, 1), [('c', 0, 1)]),
            ('INT_SUB', ('r', 80, 4), [('r', 80, 4), ('c', 1, 4)]),
            ('INT_EQUAL', ('r', 0x206, 1), [('r', 80, 4), ('c', 0, 4)]),
            ('BOOL_NEGATE', ('u', 100, 1), [('r', 0x206, 1)]),
            ('CBRANCH', None, [('c', (1 << 64) - 3, 8), ('u', 100, 1)]),
        ]),
        (0x1005, 1, flags(('r', 12, 1))),
        (0x1006, 1, [
            ('STORE', None, [('c', 0, 4), ('c', 128, 4), ('r', 0x200, 8)]),
            ('RETURN', None, [('r', 72, 4)]),
        ]),
    ]


class CompiledFlagsTests(unittest.TestCase):
    def test_full_state_for_every_entry_branch_and_loop(self):
        cc = os.environ.get('RECOMP_TEST_CC') or shutil.which('cc')
        if not cc:
            self.skipTest('C compiler unavailable')
        pe = SimpleNamespace(imports=lambda: [], exports=lambda: [], image_base=0x1000,
                             size_of_image=0x1000, entry_rva=0)
        sources = [generate(fixture(), {}, pe, 'synthetic', name,
                            eliminate_dead_flags=enabled)[0][0]
                   for name, enabled in [('baseline', False), ('optimized', True)]]
        harness = r'''
#include <stdlib.h>
uint8_t *MEM,R[8192],U[0x400000];uint32_t PC;int recomp_miss;
int main(void) {
    uint8_t initial[8192],expected[8192],memory[256],expected_memory[256];MEM=memory;
    uint32_t random=1234;
    for(int trial=0;trial<1000;trial++) {
        for(unsigned i=0;i<sizeof R;i++) {
            random=random*1664525u+1013904223u;initial[i]=(uint8_t)(random>>24);
        }
        for(uint32_t entry=0x1000;entry<=0x1006;entry++) for(int mode=0;mode<2;mode++) {
            memcpy(R,initial,sizeof R);memset(MEM,0,256);memset(U,0xa5,sizeof U);
            wr(R+72,4,0x2000);wr(R+80,4,1+(trial&7));PC=entry;recomp_miss=0;
            if(mode)optimized_chunk_0();else baseline_chunk_0();
            if(PC!=0x2000||recomp_miss!=1)return 1;
            if(!mode){memcpy(expected,R,sizeof R);memcpy(expected_memory,MEM,256);}
            else if(memcmp(expected,R,sizeof R)||memcmp(expected_memory,MEM,256))return 2;
        }
    }
    return 0;
}
'''
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'flags.c'
            executable = Path(directory) / ('flags.exe' if os.name == 'nt' else 'flags')
            source.write_text('\n'.join(sources) + harness)
            for optimization in ('-O1', '-O2'):
                subprocess.run([cc, optimization, '-I' + str(ROOT / 'tools/recomp'),
                                str(source), '-lm', '-o', str(executable)], check=True)
                subprocess.run([str(executable)], check=True, timeout=20)
