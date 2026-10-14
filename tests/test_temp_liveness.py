"""Safe dead local temporary elimination, including orphaned flag operands."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/recomp'))
from pcode2c import generate, temporary_layout
from temp_liveness import dead_unique_writes


def r(x,n=4):return ('r',x,n)
def u(x,n=4):return ('u',x,n)
def c(x,n=4):return ('c',x,n)
def op(name,out,*inputs):return (name,out,list(inputs))


def fixture():
    # Branch 5 jumps forward to 9; branch 7 jumps to 10.
    # Both paths define u120 before it is observed. u104/u108 only
    # feed the architectural carry overwritten by statement 4.
    return [
        op('COPY',u(100),r(0)),
        op('INT_CARRY',u(104,1),r(0),r(4)),
        op('INT_ADD',u(108,1),u(104,1),c(1,1)),
        op('COPY',r(0x200,1),u(108,1)),
        op('COPY',r(0x200,1),c(0,1)),
        op('CBRANCH',None,c(4,8),r(8,1)),
        op('INT_ADD',u(120),r(0),c(3)),
        op('BRANCH',None,c(3,8)),
        op('COPY',u(900),c(99)),
        op('COPY',u(120),c(2)),
        op('INT_ADD',u(128),u(120),c(1)),
        op('COPY',r(16),u(128)),
        op('COPY',u(140),r(20)),
        op('INT_MULT',u(144),u(140),c(2)),
        op('COPY',r(0x206,1),c(1,1)),
        op('RETURN',None,r(24)),
    ]


class DeadUniqueTests(unittest.TestCase):
    def test_orphaned_flag_chain_and_loop(self):
        ops=fixture()
        self.assertIsNotNone(temporary_layout(ops))
        removed=dead_unique_writes(ops, removed_flags={3})
        self.assertTrue({0,1,2,8,12,13}.issubset(removed),removed)
        self.assertFalse({6,9,10,11}.intersection(removed),removed)
        # Retain unique bytes consumed by the backward branch.
        loop=[
            op('COPY',u(100),c(1)),
            op('INT_ADD',u(100),u(100),c(1)),
            op('CBRANCH',None,c((1<<64)-1,8),r(0,1)),
            op('COPY',r(4),u(100))
        ]
        self.assertNotIn(1,dead_unique_writes(loop))
        self.assertNotIn(0,dead_unique_writes(loop))

    def test_branch_paths_protect_data(self):
        ops=[op('CBRANCH',None,c(3,8),r(0,1)),
             op('COPY',u(200),c(11)),
             op('BRANCH',None,c(2,8)),
             op('COPY',u(200),c(22)),
             op('COPY',r(4),u(200))]
        self.assertEqual(dead_unique_writes(ops),set())
        # Overlapping writes of the same bytes must preserve live ranges.
        overlap=[op('COPY',u(100,8),r(0,8)),
                 op('COPY',u(102,2),c(0xabcd,2)),
                 op('COPY',r(8,8),u(100,8))]
        self.assertEqual(dead_unique_writes(overlap),set())

    def test_unsafe_operations_and_barriers_retained(self):
        self.assertEqual(dead_unique_writes([op('LOAD',u(100),c(0),r(4))]),set())
        self.assertEqual(dead_unique_writes([op('INT_DIV',u(100),r(0),r(4))]),set())
        self.assertEqual(dead_unique_writes([op('INT_ADD',u(100),('m',0x1000,4),c(1))]),set())
        self.assertEqual(dead_unique_writes([op('FLOAT_ADD',u(100,10),r(0,10),r(16,10))]),set())
        self.assertEqual(dead_unique_writes([op('COPY',u(100),r(0)),
                                             op('CALLOTHER',None,c(12))]),set())

    def test_removed_flag_inputs_no_longer_live(self):
        ops=[op('INT_ADD',u(100),r(0),c(1)), op('COPY',r(0x200,1),u(100,1)),
             op('COPY',r(0x200,1),c(0,1))]
        self.assertNotIn(0,dead_unique_writes(ops))
        self.assertEqual(dead_unique_writes(ops,removed_flags={1}),{0})
        with self.assertRaises(ValueError):
            dead_unique_writes(ops,removed_flags={10})

    def test_codegen_keeps_exact_pcode_indices_and_part_scope(self):
        pe=SimpleNamespace(imports=lambda:[],exports=lambda:[],image_base=4096,
                           size_of_image=4096,entry_rva=0)
        inst=[(0x1000,1,fixture())]
        b,_,_=generate(inst,{},pe,'test','normal',eliminate_dead_temporaries=False)
        a,_,_=generate(inst,{},pe,'test','opt',eliminate_dead_temporaries=True)
        unchanged,_,_=generate(inst,{},pe,'test','off',eliminate_dead_temporaries=True,
                               dead_temp_parts=frozenset({1}))
        self.assertGreater(a[0].count(' ;'),b[0].count(' ;'))
        self.assertEqual(b[0].count(' ;'),unchanged[0].count(' ;'))
        self.assertEqual(a[0].count('\n'),b[0].count('\n'))
        self.assertIn('L_1000_9:',a[0])

    def test_compiled_full_state_randomized_arm_compatible(self):
        cc=os.environ.get('RECOMP_TEST_CC') or shutil.which('cc')
        if not cc:self.skipTest('C compiler unavailable')
        pe=SimpleNamespace(imports=lambda:[],exports=lambda:[],image_base=4096,
                           size_of_image=4096,entry_rva=0)
        insns=[(0x1000,1,fixture())]
        sources=[generate(insns,{},pe,'test',name,eliminate_dead_temporaries=enabled)[0][0]
                 for name,enabled in [('baseline',False),('candidate',True)]]
        host=r'''
#include <stdio.h>
uint8_t *MEM,R[8192],U[0x400000];uint32_t PC;int recomp_miss;
static unsigned seed=0xabc12345u;
static unsigned rnd(void){seed=seed*1664525u+1013904223u;return seed;}
int main(void){
    uint8_t before[8192],expected[8192],ram[256],mem_expected[256];
    MEM=ram;
    for(int trial=0;trial<2048;trial++){
        for(unsigned i=0;i<sizeof R;i++)before[i]=(uint8_t)(rnd()>>24);
        for(unsigned i=0;i<sizeof ram;i++)ram[i]=(uint8_t)(rnd()>>24);
        for(int mode=0;mode<2;mode++){
            memcpy(R,before,sizeof R);
            wr(R+8,1,(trial&1));wr(R+24,4,0x2000);
            PC=0x1000;recomp_miss=0;memset(U,0xa5,sizeof U);
            if(mode)candidate_chunk_0();else baseline_chunk_0();
            if(PC!=0x2000||recomp_miss!=1)return 3;
            if(!mode){memcpy(expected,R,sizeof R);memcpy(mem_expected,MEM,256);}
            else if(memcmp(expected,R,sizeof R) || memcmp(mem_expected,MEM,256))
                return 4;
        }
    }
    return 0;
}
'''
        with tempfile.TemporaryDirectory() as tmp:
            src=Path(tmp)/'candidate.c';src.write_text('\n'.join(sources)+host)
            exe=Path(tmp)/('candidate.exe' if os.name=='nt' else 'candidate')
            for optimization in ('-O1','-O2'):
                built=subprocess.run([cc,optimization,'-I'+str(ROOT/'tools/recomp'),
                                      str(src),'-lm','-o',str(exe)],capture_output=True,text=True)
                self.assertEqual(built.returncode,0,built.stderr)
                subprocess.run([str(exe)],check=True,timeout=30)


if __name__=='__main__':unittest.main()
