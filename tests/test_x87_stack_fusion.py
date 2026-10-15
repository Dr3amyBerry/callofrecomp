"""Exact seven-copy x87 stack outlining: matcher, branch guard and full-state oracle."""
from pathlib import Path
from types import SimpleNamespace
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools/recomp"))
from pcode2c import generate
from x87_stack_fusion import plan_x87_shift, PUSH, POP


def copies(pattern):
    return [("COPY",("r",d,10),[("r",s,10)]) for d,s in pattern]

def pe():
    return SimpleNamespace(imports=lambda:[],exports=lambda:[],
                           image_base=0x400000,size_of_image=0x200000,entry_rva=0)

class X87StackFusionTests(unittest.TestCase):
    def test_exact_patterns(self):
        self.assertEqual(plan_x87_shift(copies(PUSH)),
                         {0:"push",1:None,2:None,3:None,4:None,5:None,6:None})
        self.assertEqual(plan_x87_shift(copies(POP))[0],"pop")
        self.assertEqual(len(plan_x87_shift(copies(POP)+copies(PUSH))),14)

    def test_reject_partial_writes_and_branch_into_group(self):
        for bad in (("r",0x1100,16),("r",0x1100,9),("u",0x1100,10)):
            pattern=copies(POP)
            pattern[0]=("COPY",bad,[("r",0x1110,10)])
            self.assertFalse(plan_x87_shift(pattern))
        self.assertFalse(plan_x87_shift(copies(POP),branch_targets={2}))
        self.assertFalse(plan_x87_shift(copies(POP),removed={5}))
        self.assertEqual(plan_x87_shift(copies(POP),branch_targets={0})[0],"pop")
        with self.assertRaises(ValueError):
            plan_x87_shift(copies(POP),removed={8})
        with self.assertRaises(ValueError):
            plan_x87_shift(copies(POP),branch_targets={-1})

    def test_codegen_preserves_every_index_and_rejects_non_codsp(self):
        instructions=[(0x41b8f0,1,copies(PUSH)),
                      (0x41b8f1,1,copies(POP))]
        normal=generate(instructions,{},pe(),"CoDSP.exe","codsp")[0][0]
        packed=generate(instructions,{},pe(),"CoDSP.exe","codsp",
                        x87_stack_shift_outline=True)[0][0]
        self.assertNotIn("codsp_x87_shift_push",normal)
        self.assertEqual(packed.count("codsp_x87_shift_push("),1)
        self.assertEqual(packed.count("codsp_x87_shift_pop("),1)
        self.assertIn("codsp_x87_shift_push(guest_regs)",packed)
        self.assertEqual(len(packed.splitlines()),len(normal.splitlines()))
        from patch_codsp_x87_shift import transform
        self.assertEqual(transform(packed.encode(),apply=False)[0],normal.encode())
        cold=generate(instructions,{},pe(),"other.dll","other",
                      x87_stack_shift_outline=True)[0][0]
        self.assertNotIn("codsp_x87_shift_push",cold)

    def test_guard_against_local_jump_into_stack_shifts(self):
        # Jump from op zero to index four inside an otherwise exact copy run.
        ops=[("CBRANCH",None,[("c",4,8),("r",0,1)])]+copies(POP)
        generated=generate([(0x41b8f0,1,ops)],{},pe(),"CoDSP.exe","codsp",
                           x87_stack_shift_outline=True)[0][0]
        self.assertNotIn("codsp_x87_shift_pop(",generated)
        self.assertIn("L_41b8f0_4:",generated)

    def test_compiled_full_register_ram_pc_equivalence(self):
        compiler=os.environ.get("RECOMP_TEST_CC") or shutil.which("cc")
        if not compiler:self.skipTest("C compiler missing")
        instr=[(0x41b8f0,1,copies(PUSH)+[("COPY",("r",0x500,4),[("c",0xaabbccdd,4)])]),
               (0x41b8f1,1,copies(POP)+[("COPY",("r",0x504,4),[("r",0x500,4)])])]
        generated=[]
        for name,flag in (("ref",False),("fast",True)):
            source=generate(instr,{},pe(),"CoDSP.exe","codsp",
                            x87_stack_shift_outline=flag)[0][0]
            generated.append(source.replace("codsp_chunk_0",name+"_chunk_0"))
        harness=r"""
#include "recomp_rt.h"
#include <stdio.h>
#include <stdlib.h>
uint8_t *MEM,R[0x2000],U[0x400000];
uint32_t PC;int recomp_miss;
void ref_chunk_0(void);void fast_chunk_0(void);
static uint32_t seed=0xc0ffee99;
static uint32_t rng(void){seed=seed*1664525u+1013904223u;return seed;}
int main(void){
 uint8_t original[sizeof R],ref[sizeof R],mem[512],mem_ref[512],u_ref[256];
 MEM=mem;
 for(int trial=0;trial<1000;trial++){
   for(size_t i=0;i<sizeof R;i++)original[i]=(uint8_t)(rng()>>24);
   for(int entry=0;entry<2;entry++){
     for(int candidate=0;candidate<2;candidate++){
       memcpy(R,original,sizeof R);
       memset(U,0x83,sizeof U);memset(MEM,0x34,sizeof mem);
       PC=0x41b8f0+entry;recomp_miss=0;
       if(candidate)fast_chunk_0();else ref_chunk_0();
       if(PC!=0x41b8f2||recomp_miss)return 10;
       if(!candidate){
         memcpy(ref,R,sizeof R);memcpy(mem_ref,MEM,sizeof mem);
         memcpy(u_ref,U,sizeof u_ref);
       } else if(memcmp(R,ref,sizeof R)||memcmp(MEM,mem_ref,sizeof mem)||
                 memcmp(U,u_ref,sizeof u_ref)){fprintf(stderr,"diff %d,%d",trial,entry);return 11;}
     }
   }
 }
 return 0;
}
"""
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"oracle.c"
            path.write_text("\n".join(generated)+harness)
            exe=Path(folder)/("oracle.exe" if os.name=="nt" else "oracle")
            for opt in ("-O0","-O1","-O2"):
                cmd=[compiler,opt,"-I"+str(ROOT/"tools/recomp"),str(path),"-lm","-o",str(exe)]
                proc=subprocess.run(cmd,capture_output=True,text=True,timeout=80)
                self.assertEqual(proc.returncode,0,proc.stderr)
                run=subprocess.run([str(exe)],capture_output=True,text=True,timeout=60)
                self.assertEqual(run.returncode,0,run.stderr)

if __name__=="__main__":
    unittest.main()
