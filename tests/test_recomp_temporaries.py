import sys
import unittest
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools/recomp'))
from pcode2c import generate, temporary_layout


def copy(out, value):
    return ('COPY', out, [value])


class TemporaryTests(unittest.TestCase):
    def test_compiled_local_and_global_state_match(self):
        compiler = os.environ.get('RECOMP_TEST_CC') or shutil.which('cc')
        if not compiler:
            self.skipTest('C compiler unavailable; CTest supplies RECOMP_TEST_CC')
        pe = SimpleNamespace(imports=lambda: [], exports=lambda: [], image_base=0x1000,
                             size_of_image=0x1000, entry_rva=0)
        ops = [copy(('u', 100, 8), ('r', 0, 8)),
               copy(('u', 102, 2), ('c', 0xabcd, 2)),
               ('INT_ADD', ('u', 900, 8), [('u', 100, 8), ('r', 8, 8)]),
               copy(('r', 16, 8), ('u', 900, 8)),
               ('CBRANCH', None, [('c', 3, 8), ('r', 0, 1)]),
               copy(('u', 200, 4), ('c', 1, 4)),
               ('BRANCH', None, [('c', 2, 8)]),
               copy(('u', 200, 4), ('c', 2, 4)),
               copy(('r', 24, 4), ('u', 200, 4)),
               ('STORE', None, [('c', 0, 8), ('c', 128, 4), ('r', 16, 8)]),
               ('FLOAT2FLOAT', ('u', 1000, 10), [('r', 32, 4)]),
               ('FLOAT_ADD', ('u', 1010, 10), [('u', 1000, 10), ('u', 1000, 10)]),
               ('FLOAT2FLOAT', ('r', 36, 4), [('u', 1010, 10)])]
        insns = [(0x1000, 1, ops)]
        sources = [generate(insns, {}, pe, 'synthetic', name, local_temporaries=local)[0][0]
                   for name, local in [('global', False), ('local', True)]]
        self.assertIn('uint8_t T[', sources[1])
        host = r'''
#include "recomp_rt.h"
#include <stdlib.h>
uint8_t *MEM, R[0x2000], U[0x400000]; uint32_t PC; int recomp_miss;
void global_chunk_0(void); void local_chunk_0(void);
int main(void) {
    uint8_t initial[sizeof R], expected[sizeof R], expected_memory[256];
    MEM = calloc(1,256); if(!MEM)return 1;
    uint32_t random = 1234;
    for(int trial=0;trial<1000;trial++) {
        for(unsigned i=0;i<sizeof R;i++) {
            random = random*1664525u+1013904223u; initial[i]=(uint8_t)(random>>24);
        }
        for(int local=0;local<2;local++) {
            memcpy(R,initial,sizeof R); memset(MEM,0,256); memset(U,0xa5,sizeof U);
            PC=0x1000; recomp_miss=0;
            if(local)local_chunk_0();else global_chunk_0();
            if(PC!=0x1001 || recomp_miss)return 2;
            if(!local){memcpy(expected,R,sizeof R);memcpy(expected_memory,MEM,256);}
            else if(memcmp(expected,R,sizeof R)||memcmp(expected_memory,MEM,256))return 3;
        }
    }
    return 0;
}
'''
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'fixture.c'
            source.write_text('\n'.join(sources) + host)
            executable = Path(directory) / ('fixture.exe' if os.name == 'nt' else 'fixture')
            built = subprocess.run([compiler, '-O1', '-I' + str(root / 'tools/recomp'),
                                    str(source), '-lm', '-o', str(executable)],
                                   capture_output=True, text=True)
            self.assertEqual(built.returncode, 0, built.stderr)
            subprocess.run([str(executable)], check=True, timeout=20)

    def test_overlapping_bytes_keep_their_aliases(self):
        ops = [copy(('u', 0x100, 8), ('c', 123, 8)),
               copy(('r', 0, 2), ('u', 0x102, 2)),
               copy(('u', 0x900, 4), ('c', 2, 4))]
        layout = temporary_layout(ops)
        self.assertEqual(layout[0x102], layout[0x100] + 2)
        self.assertEqual(layout[0x900], 8)
        self.assertEqual(len(layout), 12)

    def test_both_conditional_paths_define_input(self):
        ops = [('CBRANCH', None, [('c', 3, 8), ('r', 0, 1)]),
               copy(('u', 100, 4), ('c', 1, 4)),
               ('BRANCH', None, [('c', 2, 8)]),
               copy(('u', 100, 4), ('c', 2, 4)),
               copy(('r', 4, 4), ('u', 100, 4))]
        self.assertIsNotNone(temporary_layout(ops))

    def test_unwritten_input_on_one_path_is_rejected(self):
        ops = [('CBRANCH', None, [('c', 2, 8), ('r', 0, 1)]),
               copy(('u', 100, 4), ('c', 1, 4)),
               copy(('r', 4, 4), ('u', 100, 4))]
        self.assertIsNone(temporary_layout(ops))

    def test_partial_initialization_is_rejected(self):
        self.assertIsNone(temporary_layout([
            copy(('u', 100, 4), ('c', 1, 4)),
            copy(('r', 0, 4), ('u', 102, 4))]))

    def test_loop_preserves_defined_temporaries(self):
        ops = [copy(('u', 100, 4), ('c', 1, 4)),
               ('INT_ADD', ('u', 100, 4), [('u', 100, 4), ('c', 1, 4)]),
               ('CBRANCH', None, [('c', (1 << 64) - 1, 8), ('r', 0, 1)]),
               copy(('r', 4, 4), ('u', 100, 4))]
        self.assertIsNotNone(temporary_layout(ops))

    def test_cross_instruction_use_requires_explicit_global_storage(self):
        pe = SimpleNamespace(imports=lambda: [], exports=lambda: [], image_base=0x1000,
                             size_of_image=0x1000, entry_rva=0)
        insns = [(0x1000, 1, [copy(('u', 100, 4), ('c', 5, 4))]),
                 (0x1001, 1, [copy(('r', 0, 4), ('u', 100, 4))])]
        with self.assertRaisesRegex(ValueError, 'ALL linked'):
            generate(insns, {}, pe, 'test', 'test')
        bodies, _, _ = generate(insns, {}, pe, 'test', 'test', local_temporaries=False)
        self.assertIn('U+0x64', bodies[0])
        self.assertNotIn('uint8_t T[', bodies[0])

    def test_cross_module_reader_cannot_silently_fall_back(self):
        pe = SimpleNamespace(imports=lambda: [], exports=lambda: [], image_base=0x1000,
                             size_of_image=0x1000, entry_rva=0)
        writer = [(0x1000, 1, [copy(('u', 100, 4), ('c', 42, 4)),
                              ('BRANCH', None, [('m', 0x2000, 4)])])]
        reader = [(0x2000, 1, [copy(('r', 0, 4), ('u', 100, 4))])]
        generated, _, _ = generate(writer, {}, pe, 'A', 'A')
        self.assertIn('uint8_t T[', generated[0])
        with self.assertRaisesRegex(ValueError, 'ALL linked'):
            generate(reader, {}, pe, 'B', 'B')
        for name, insns in [('A', writer), ('B', reader)]:
            generated, _, _ = generate(insns, {}, pe, name, name, local_temporaries=False)
            self.assertIn('U+0x64', generated[0])
            self.assertNotIn('uint8_t T[', generated[0])


if __name__ == '__main__':
    unittest.main()
