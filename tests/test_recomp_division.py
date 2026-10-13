import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/recomp'))
from pcode2c import Gen


class DivisionTests(unittest.TestCase):
    def test_native_signed_division_selected_only_for_narrow_inputs(self):
        gen = Gen({})
        for name in ('INT_SDIV', 'INT_SREM'):
            for size in range(1, 9):
                code = gen.op(name, ('r', 16, 16), [('r', 0, size), ('r', 8, size)], None, None)
                self.assertIn('(int64_t)', code)
                if size == 8:
                    self.assertIn('INT64_MIN', code)
            code = gen.op(name, ('r', 32, 16), [('r', 0, 16), ('r', 16, 16)], None, None)
            self.assertNotIn('(int64_t)', code)

    def test_compiled_division_matches_wide_reference(self):
        compiler = os.environ.get('RECOMP_TEST_CC') or shutil.which('cc')
        if not compiler:
            self.skipTest('CTest supplies a C compiler')
        gen = Gen({})
        functions = []
        pairs = [(a, b) for a in range(1, 9) for b in range(1, 9)]
        for size, other_size in pairs:
            for name in ('INT_SDIV', 'INT_SREM'):
                code = gen.op(name, ('r', 32, 16), [('r', 0, size), ('r', 16, other_size)], None, None)
                functions.append(f'void {name}_{size}_{other_size}(void) {{ {code} }}')
        calls = ','.join('{INT_SDIV_%d_%d,INT_SREM_%d_%d}' % (a, b, a, b) for a, b in pairs)
        host = r'''
#include "recomp_rt.h"
#include <stdlib.h>
uint8_t R[0x2000], U[0x400000], *MEM; uint32_t PC; int recomp_miss;
FUNCTIONS
int main(void) {
    void (*ops[64][2])(void) = {CALLS};
    uint64_t values[] = {0,1,2,3,127,128,255,32768,65535,0x80000000u,
        0xffffffffu,UINT64_C(0x8000000000000000),UINT64_MAX,UINT64_MAX-1};
    uint64_t random = 123;
    for(int width=0;width<64;width++) {
        int size=width/8+1, other_size=width%8+1;
        for(int trial=0;trial<2000;trial++) {
            random=random*UINT64_C(6364136223846793005)+1;
            uint64_t a=trial<196 ? values[trial/14] : random;
            random=random*UINT64_C(6364136223846793005)+1;
            uint64_t b=trial<196 ? values[trial%14] : random;
            s128 sa=sx(a,size), sb=sx(b,other_size); if(!sb)continue;
            wr(R,16,a); wr(R+16,16,b);
            for(int rem=0;rem<2;rem++) {
                u128 expected=(u128)(rem ? sa%sb : sa/sb);
                ops[width][rem]();
                if(rd(R+32,16)!=expected)return 1;
            }
        }
    }
    return 0;
}
'''.replace('FUNCTIONS', '\n'.join(functions)).replace('CALLS', calls)
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'division.c'
            source.write_text(host)
            executable = Path(directory) / 'division.exe'
            built = subprocess.run([compiler, '-O1', '-I' + str(ROOT / 'tools/recomp'),
                                    str(source), '-o', str(executable)], capture_output=True, text=True)
            self.assertEqual(built.returncode, 0, built.stderr)
            subprocess.run([str(executable)], check=True, timeout=20)


if __name__ == '__main__':
    unittest.main()
