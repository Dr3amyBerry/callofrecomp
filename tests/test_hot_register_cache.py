"""Register cache emitted only for disjoint, straight-line hot CoDSP blocks.

Use compiled complete-register/RAM equivalence at several Clang optimization
levels. This is not a substitute for independent Intel x86 compatibility.
"""
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
from pcode2c import generate,instruction_register_cache

def r(o,n=4):return ('r',o,n)
def u(o,n=4):return ('u',o,n)
def c(v,n=4):return ('c',v,n)
def op(name,out,*ins):return (name,out,list(ins))

def synthetic():
    return [
        (0x4196f0,1,[
            op('COPY',u(0x100),r(0)),
            op('INT_ADD',u(0x104),r(0),c(3)),
            op('INT_XOR',r(0),u(0x104),r(4)),
            op('INT_MULT',u(0x108),r(0),r(8)),
            op('COPY',r(4),u(0x108)),
            op('FLOAT2FLOAT',u(0x200,10),r(0x1100,10)),
            op('FLOAT_ADD',u(0x210,10),u(0x200,10),r(0x1100,10)),
            op('COPY',r(0x1100,10),u(0x210,10)),
            op('FLOAT2FLOAT',u(0x220,10),r(0x1100,10)),
            op('COPY',r(0x1120,10),u(0x220,10)),
            op('STORE',None,c(0),c(128),r(4)),
        ]),
        # A partial byte alias invalidates caching of either slice.
        (0x4196f1,1,[
            op('COPY',u(0x300),r(16)),
            op('COPY',r(17,2),c(0xbeef,2)),
            op('INT_ADD',u(0x304),r(16),c(2)),
            op('COPY',r(20),u(0x304)),
        ]),
        (0x4196f2,1,[
            op('INT_ADD',r(24),r(24),c(1)),
            op('COPY',u(0x400,1),r(24,1)),
            op('CBRANCH',None,c(2,8),u(0x400,1)),
            op('INT_SUB',r(24),r(24),c(1)),
            op('COPY',r(28),r(24)),
        ]),
        # A nearby cold PC is entirely unchanged.
        (0x700010,1,[op('COPY',r(36),r(32))]),
    ]

class HotRegisterCacheTests(unittest.TestCase):
    def test_candidate_selection_and_bailouts(self):
        ops=synthetic()[0][2]
        plan=instruction_register_cache(ops)
        self.assertIn(r(0),plan)
        self.assertEqual(plan[r(0)],(True,True))
        self.assertIn(r(0x1100,10),plan)
        self.assertNotIn(r(16),instruction_register_cache(synthetic()[1][2]))
        self.assertEqual(instruction_register_cache(synthetic()[2][2]),{})
        self.assertEqual(instruction_register_cache([op('CALLOTHER',r(0),c(2))]),{})
        self.assertNotIn(r(0),instruction_register_cache(ops, removed={0,1,2,3}))

    def test_only_hot_codsp_opt_in_emits_cache(self):
        pe=SimpleNamespace(imports=lambda:[],exports=lambda:[],image_base=0x1000,
                           size_of_image=0x1000,entry_rva=0)
        source=generate(synthetic(),{},pe,'CoDSP.exe','codsp',
                        cache_hot_registers=True)[0][0]
        baseline=generate(synthetic(),{},pe,'CoDSP.exe','codsp')[0][0]
        self.assertIn('regcache_1100_10',source)
        self.assertNotIn('regcache_',baseline)
        self.assertIn('wr(guest_regs+0x1100,10,regcache_1100_10);',source)
        self.assertNotIn('regcache_10_4',source) # partial overlap
        self.assertNotIn('regcache_18_4',source) # branch
        self.assertNotIn('regcache_20_4',source) # cold pc
        other=generate(synthetic(),{},pe,'other.dll','other',cache_hot_registers=True)[0][0]
        self.assertNotIn('regcache_',other)

    def test_opt_in_rejects_unverified_codsp_export(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            pcode=root/'codsp.pcode'
            pe=root/'CoDSP.exe'
            pcode.write_text('I 4096 1\nP COPY r:0:4 c:1:4\n')
            pe.write_bytes(b'not the verified CoDSP')
            result=subprocess.run([sys.executable,str(ROOT/'tools/recomp/pcode2c.py'),
                str(pcode),str(pe),'--cache-hot-registers',
                '-o',str(root/'out.c')],capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0)
            self.assertIn('verified CoDSP.exe 1.5',result.stderr)

    def test_compiled_complete_arch_state_and_memory(self):
        compiler=os.environ.get('RECOMP_TEST_CC') or shutil.which('cc')
        if not compiler:self.skipTest('No host C compiler')
        pe=SimpleNamespace(imports=lambda:[],exports=lambda:[],image_base=0x1000,
                           size_of_image=0x1000,entry_rva=0)
        instr=synthetic()
        generated=[]
        for name,cached in [('ref',False),('opt',True)]:
            source=generate(instr,{},pe,'CoDSP.exe','codsp',
                            cache_hot_registers=cached)[0][0]
            generated.append(source.replace('codsp_chunk_0',name+'_chunk_0'))
        harness=r"""
#include "recomp_rt.h"
#include <stdlib.h>
uint8_t *MEM,R[0x2000],U[0x400000];uint32_t PC;int recomp_miss;
void ref_chunk_0(void);void opt_chunk_0(void);
static uint32_t seed=0xbadea55u;
static uint32_t rnd(void){seed=seed*1664525u+1013904223u;return seed;}
int main(void){
 uint8_t before[sizeof R],reference[sizeof R],ram[512],ref_ram[512],ref_u[0x500];
 MEM=ram;
 for(int trial=0;trial<4000;trial++){
   for(int i=0;i<(int)sizeof R;i++)before[i]=(uint8_t)(rnd()>>24);
   for(int which=0;which<2;which++){
     memcpy(R,before,sizeof R);memset(U,0xa5,sizeof U);
     for(int i=0;i<(int)sizeof ram;i++)ram[i]=(uint8_t)(i ^ trial);
     PC=0x4196f0;recomp_miss=0;
     if(which)opt_chunk_0();else ref_chunk_0();
     if(PC!=0x4196f3||recomp_miss!=0)return 9;
     if(!which){memcpy(reference,R,sizeof R);memcpy(ref_ram,ram,sizeof ram);
               memcpy(ref_u,U,sizeof ref_u);}
     else if(memcmp(R,reference,sizeof R)||memcmp(ram,ref_ram,sizeof ram)||
             memcmp(U,ref_u,sizeof ref_u))return 10;
   }
 }
 return 0;
}
"""
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            src=root/'fixture.c'
            src.write_text('\n'.join(generated)+harness)
            exe=root/('fixture.exe' if os.name=='nt' else 'fixture')
            for mode in ('-O0','-O1','-O2'):
                proc=subprocess.run([compiler,mode,'-I'+str(ROOT/'tools/recomp'),
                                     str(src),'-lm','-o',str(exe)],
                                     capture_output=True,text=True,timeout=45)
                self.assertEqual(proc.returncode,0,proc.stderr)
                subprocess.run([str(exe)],check=True,timeout=40)

if __name__=='__main__':
    unittest.main()
