"""Phase14F synthetic-only multi-block original CFG tests; no game bytes."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools/recomp"))
from cfg_superregion import (
    discover_superregions, plan_superregions, safe_instruction, description,
)
from cfg_region_lab import generate_region_c, CFGError
from region_cfg import recover_function_cfg
from diagnostics.benchmark_cfg_superregion import update_conditional_coverage


def r(off, length=4): return ("r", off, length)
def c(value, length=4): return ("c", value, length)
def m(addr, length=4): return ("m", addr, length)
def op(name, out=None, *inputs): return (name, out, list(inputs))


def diamond():
    """8 original x86 PCs in 4 whole blocks, a diamond with external exit."""
    instructions=[
        (0x1000,1,[op("COPY",r(0),c(1))]),
        (0x1001,1,[op("CBRANCH",None,m(0x1004),r(0x206,1))]),
        (0x1002,1,[op("INT_ADD",r(0),r(0),c(3))]),
        (0x1003,1,[op("BRANCH",None,m(0x1006))]),
        (0x1004,1,[op("INT_XOR",r(0),r(0),c(8))]),
        (0x1005,1,[op("BRANCH",None,m(0x1006))]),
        (0x1006,1,[op("COPY",r(4),r(0))]),
        (0x1007,1,[op("BRANCH",None,m(0x2004))]),
        # Known external entry to interior original block. Existing dispatcher
        # must remain capable of landing there, outside fast-path calls.
        (0x2000,1,[op("BRANCH",None,m(0x1004))]),
    ]
    mapping={
        "module":"CoDSP.exe", "schema_version":2,
        "functions":[{"entry_va":"0x00001000","entry_in_translation":True,
                      "body_uniquely_owned_instruction_count":8}],
        "ghidra_body_ranges":[{"entry_va":"0x00001000",
                               "start_va":"0x00001000",
                               "end_va_inclusive":"0x00001007"}],
    }
    return instructions,mapping


class WholeOriginalCFGSuperregions(unittest.TestCase):
    def test_branch_diamond_is_four_complete_original_blocks(self):
        insns,mapping=diamond()
        candidate=next(x for x in discover_superregions(insns,mapping,0x1000)
                       if x.region.start==0x1000)
        self.assertEqual(len(candidate.region.instructions),8)
        self.assertEqual(candidate.block_starts,(0x1000,0x1002,0x1004,0x1006))
        self.assertEqual(len(candidate.internal_edges),4)
        self.assertIn((0x1007,0x2004),candidate.exits)
        self.assertIn(0x1004,candidate.side_entry_pcs)
        self.assertTrue(description(candidate)["all_guest_data_memory_accesses_excluded"])
        self.assertFalse(description(candidate)["candidate_is_safe_to_deploy"])

    def test_generator_must_jump_both_branch_arms_directly_without_reloading_R(self):
        insns,mapping=diamond()
        candidate=next(x for x in discover_superregions(insns,mapping,0x1000)
                       if x.region.start==0x1000)
        src,selected=generate_region_c(candidate.region,cache_count=1,
                                      entry_policy="start_only",memory_model="exact")
        self.assertIn(r(0),selected)
        for pc in range(0x1000,0x1008):
            self.assertIn(f"B_{pc:x}:",src)
            if pc!=0x1000:
                self.assertNotIn(f"L_{pc:x}:",src)
        self.assertIn("goto B_1004;",src)
        self.assertIn("goto B_1002;",src)
        self.assertIn("goto B_1006;",src)
        self.assertIn("PC=0x2004u; goto finished;",src)
        self.assertNotIn("MEM + ((uint32_t)(a) %",src)
        self.assertIn("case 0x1000u: goto L_1000;",src)
        self.assertNotIn("case 0x1004u:",src)

    def test_unselected_guest_memory_branch_exits_to_original_dispatcher(self):
        insns,mapping=diamond()
        changed=deepcopy(insns)
        changed[4][2].insert(0,op("LOAD",r(8),c(0x1a1,8),r(4)))
        found=discover_superregions(changed,mapping,0x1000,
                                    minimum_instructions=2)
        candidate=next(item for item in found if item.region.start==0x1000)
        pcs={pc for pc,_,_ in candidate.region.instructions}
        self.assertNotIn(0x1004,pcs)
        src,_=generate_region_c(candidate.region,cache_count=0,
                                entry_policy="start_only")
        self.assertIn("PC=0x1004u; goto finished;",src)

    def test_backward_edge_inside_region_prevents_native_cache_loop(self):
        insns,mapping=diamond()
        changed=deepcopy(insns)
        changed[7]=(0x1007,1,[op("BRANCH",None,m(0x1000))])
        regions=discover_superregions(changed,mapping,0x1000)
        self.assertFalse(any(s.region.start==0x1000 for s in regions))

    def test_branch_coverage_is_observed_not_fabricated(self):
        cond={0x1001:1,0x1005:1}
        observed={pc:{"taken":0,"fallthrough":0} for pc in cond}
        update_conditional_coverage([0x1000,0x1001,0x1006],cond,observed)
        self.assertEqual(observed[0x1001],{"taken":1,"fallthrough":0})
        self.assertEqual(observed[0x1005],{"taken":0,"fallthrough":0})
        update_conditional_coverage([0x1000,0x1001,0x1002,0x1005,0x1006],
                                    cond,observed)
        self.assertEqual(observed[0x1001],{"taken":1,"fallthrough":1})
        self.assertEqual(observed[0x1005],{"taken":0,"fallthrough":1})

    def test_no_guest_memory_data_or_x87_can_be_included(self):
        for operands in (
            [op("COPY",r(4),m(0x401000))],
            [op("STORE",None,c(0x1a1,8),r(4),r(0))],
            [op("FLOAT_ADD",r(4),r(4),r(8))],
            [op("COPY",r(0x1090,2),c(0,2))],
            [op("CALLOTHER",None,c(1))],
        ):
            with self.subTest(ops=operands):
                self.assertFalse(safe_instruction(0x1000,1,operands))

    def test_entry_is_exact_original_gcfg_not_arbitrary_PC(self):
        insns,mapping=diamond()
        cfg=recover_function_cfg(insns,mapping,0x1000)
        corrupted=dict(cfg,source="handwritten_static_guess")
        with self.assertRaisesRegex(CFGError,"unverified"):
            plan_superregions(insns,corrupted)

    def test_bounds_guarded_and_deterministic(self):
        insns,mapping=diamond()
        cfg=recover_function_cfg(insns,mapping,0x1000)
        first=plan_superregions(insns,cfg)
        second=plan_superregions(insns,cfg)
        self.assertEqual(first,second)
        self.assertFalse(plan_superregions(insns,cfg,maximum_instructions=2,minimum_instructions=2))
        with self.assertRaises(CFGError):
            plan_superregions(insns,cfg,maximum_blocks=0)


if __name__=="__main__":
    unittest.main()
