"""Phase14C region ABI/CFG/reentry tests; all inputs synthetic, no game data."""
from copy import deepcopy
from pathlib import Path
import ctypes
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools/recomp"))
from cfg_region_lab import (
    Region,CFGError,select_block,cache_candidates,generate_region_c
)
from diagnostics.benchmark_cfg_region import differential


def v(space,off,length=4):return (space,off,length)

def op(name,out=None,*inputs):return (name,out,list(inputs))


def sample():
    insns=[
        (0x1000,1,[
            op("COPY",v("r",0),v("c",2)),
            op("INT_ADD",v("r",0),v("r",0),v("c",3))]),
        (0x1001,1,[
            op("COPY",v("r",4),v("r",0)),
            op("INT_XOR",v("r",0),v("r",0),v("r",4))]),
        (0x1002,1,[op("CBRANCH",None,v("m",0x2000),v("r",0x206,1))]),
    ]
    mapping={
        "module":"CoDSP.exe","schema_version":2,
        "functions":[{"entry_va":"0x00001000","entry_in_translation":True,
                      "body_uniquely_owned_instruction_count":3}],
        "ghidra_body_ranges":[{"entry_va":"0x00001000",
                               "start_va":"0x00001000",
                               "end_va_inclusive":"0x00001002"}],
    }
    return insns,mapping


class SelectConservativeRegions(unittest.TestCase):
    def test_real_instruction_cfg_block_with_branch_and_side_entries(self):
        instr,mapping=sample()
        candidate=select_block(instr,mapping,0x1000,0x1000)
        self.assertEqual(len(candidate.instructions),3)
        chosen=cache_candidates(candidate)
        self.assertEqual(chosen[0][0],v("r",0))
        self.assertTrue(chosen[0][2])

    def test_whole_x87_metadata_register_range_excluded(self):
        insns,mapping=sample()
        for off in (0x1090,0x10a2,0x10ac,0x1100,0x1170):
            corrupt=deepcopy(insns)
            corrupt[0][2].append(op("COPY",v("r",off,1),v("c",1,1)))
            with self.subTest(off=hex(off)),self.assertRaisesRegex(CFGError,"x87"):
                select_block(corrupt,mapping,0x1000,0x1000)

    def test_opaque_or_floating_point_operations_block_region(self):
        insns,mapping=sample()
        for mnemonic in ("CALLOTHER","FLOAT_ADD","CALL","RETURN","BRANCHIND",
                         "INT_DIV","INT_SDIV"):
            corrupt=deepcopy(insns)
            corrupt[0][2].append(op(mnemonic,v("r",0),v("r",0),v("c",2)))
            with self.subTest(op=mnemonic),self.assertRaises(CFGError):
                select_block(corrupt,mapping,0x1000,0x1000)

    def test_ghidra_function_body_and_guest_target_are_guarded(self):
        insns,mapping=sample()
        with self.assertRaises(CFGError):
            select_block(insns,mapping,0x1000,0x1001)
        bad=deepcopy(insns)
        bad[-1][2][0]=(bad[-1][2][0][0],None,[v("m",1<<33),v("r",0x206,1)])
        with self.assertRaises(CFGError):
            select_block(bad,mapping,0x1000,0x1000)

    def test_overlapping_register_views_cannot_be_cached(self):
        insns,mapping=sample()
        insns[1][2].append(op("COPY",v("r",1,1),v("c",3,1)))
        region=select_block(insns,mapping,0x1000,0x1000)
        self.assertNotIn(v("r",0),[v for v,uses,writes in cache_candidates(region)])


class ReentryAndStateFlushABI(unittest.TestCase):
    def test_all_entries_reinitialize_and_internal_path_does_not(self):
        insns,mapping=sample()
        region=select_block(insns,mapping,0x1000,0x1000)
        a,chosen_a=generate_region_c(region,cache_count=0)
        b,chosen_b=generate_region_c(region,cache_count=1)
        self.assertEqual(chosen_a,())
        self.assertEqual(chosen_b,(v("r",0),))
        for pc in (0x1000,0x1001,0x1002):
            self.assertIn(f"L_{pc:x}:",b)
            self.assertIn(f"B_{pc:x}:",b)
            self.assertIn(f"case 0x{pc:x}u: goto L_{pc:x};",b)
            self.assertIn(f"reg_0_4=rd(R+0x0,4);",b)
            self.assertIn(f"B_{pc:x}:",a)
        self.assertIn("wr(R+0x0,4,reg_0_4);",b)
        self.assertIn("PC=0x2000u; goto finished;",b)
        self.assertIn("PC=0x1003u; goto finished;",b)
        self.assertNotIn("reg_0_4=rd(R+0x0,4);",a)

    def test_start_only_requires_original_fallback_for_all_interior_pcs(self):
        insns,mapping=sample()
        region=select_block(insns,mapping,0x1000,0x1000)
        source,selected=generate_region_c(region,cache_count=1,
                                          entry_policy="start_only")
        self.assertIn("L_1000:",source)
        self.assertNotIn("L_1001:",source)
        self.assertNotIn("case 0x1001u:",source)
        self.assertIn("B_1001:",source)
        self.assertIn("default: goto finished;",source)

    def test_invalid_options_rejected(self):
        insns,mapping=sample()
        region=select_block(insns,mapping,0x1000,0x1000)
        with self.assertRaises(CFGError):
            generate_region_c(region,cache_count=999)
        with self.assertRaises(CFGError):
            generate_region_c(region,entry_policy="unknown")

    def test_fast_entry_and_dispatcher_fallback_cases_are_separate(self):
        class DLL:
            def __init__(self):
                self.pc=0
                self.calls=0
            def execute_region(self,reg,mem,pc):
                self.pc=0x4000
                self.calls+=1
            def result_pc(self):
                return self.pc
        original=DLL()
        fast=DLL()
        outcome=differential(original,fast,(0x1000,0x1001,0x1002),3,
                             fast_start_pc=0x1000)
        self.assertTrue(outcome["all_equal"])
        self.assertEqual(outcome["fast_entry_cases"],3)
        self.assertEqual(outcome["delegated_original_baseline_cases"],6)
        self.assertEqual(fast.calls,3)
        self.assertEqual(original.calls,15) # 9 reference + 6 delegated.
        self.assertTrue(outcome["fallback_is_host_simulation_not_android_integration"])

    def test_unsafe_mutation_to_register_state_is_detected(self):
        class DLL:
            def __init__(self,corrupt=False):
                self.corrupt=corrupt
                self.pc=0
            def execute_region(self,reg,mem,pc):
                self.pc=0x1001
                if self.corrupt:
                    ctypes.memmove(reg,b"\xff",1)
            def result_pc(self):
                return self.pc
        with self.assertRaisesRegex(RuntimeError,"mismatch"):
            differential(DLL(),DLL(corrupt=True),(0x1000,),1)
        self.assertTrue(differential(DLL(),DLL(),(0x1000,),1)["all_equal"])


if __name__=="__main__":
    unittest.main()
