"""Phase14B byte-granular architectural boundary proof tests (synthetic only)."""
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools/recomp"))
from region_cfg import CFGError
from region_state_contract import (
    ALL_REGISTER_BYTES,InstructionState,mask,mask_ranges,
    analyze_instruction,region_contract
)

def r(off,size=4):return ("r",off,size)
def c(v,size=4):return ("c",v,size)
def m(a):return ("m",a,4)
def op(name,out=None,*args):return (name,out,list(args))


class MicroStateTests(unittest.TestCase):
    def test_exact_byte_masks_and_partial_overwrites(self):
        self.assertEqual(mask(r(3,2)),(1<<3)|(1<<4))
        self.assertEqual(mask_ranges(mask(r(0,2))|mask(r(4,1))),[[0,2],[4,5]])
        self.assertEqual(mask_ranges(0),[])
        self.assertEqual(mask_ranges(ALL_REGISTER_BYTES),[[0,0x2000]])
        for invalid in (r(-1),r(0x2000),r(0x1fff,4)):
            with self.assertRaises(CFGError):
                mask(invalid)

    def test_unconditional_overwrite_before_read_is_not_live_in(self):
        analysis=analyze_instruction([
            op("COPY",r(0,4),c(1)),
            op("COPY",r(4,4),r(0,4)),
            op("COPY",r(6,2),r(0,2)),
        ])
        self.assertEqual(analysis.read_before_write,0)
        self.assertEqual(analysis.must_write&mask(r(0,4)),mask(r(0,4)))
        self.assertIn("may_write",analysis._fields)

    def test_branch_skipped_partial_write_requires_live_input(self):
        analysis=analyze_instruction([
            op("CBRANCH",None,c(2,8),r(0x206,1)),
            op("COPY",r(0x10,2),c(7)),
            op("COPY",r(0x20,4),r(0x10,4)),
        ])
        self.assertEqual(analysis.read_before_write&mask(r(0x10,4)),
                         mask(r(0x10,4)))
        self.assertEqual(analysis.must_write&mask(r(0x10,2)),0)
        self.assertEqual(analysis.must_write&mask(r(0x20,4)),mask(r(0x20,4)))
        self.assertEqual(analysis.read_before_write&mask(r(0x206,1)),
                         mask(r(0x206,1)))

    def test_micro_loop_intersection_is_not_an_infinite_loop(self):
        result=analyze_instruction([
            op("CBRANCH",None,c(2,8),r(0x206,1)),
            op("BRANCH",None,c((1<<64)-1,8)),
            op("COPY",r(0,4),r(8,4)),
        ])
        self.assertIn("possible_micro_cycle",result.hazards)
        self.assertTrue(result.read_before_write&mask(r(8,4)))

    def test_invalid_micro_target_never_defines_safe_arch_state(self):
        result=analyze_instruction([
            op("BRANCH",None,c((1<<64)-1,8)),
        ])
        self.assertIn("invalid_micro_target",result.hazards)
        self.assertEqual(result.read_before_write,ALL_REGISTER_BYTES)
        self.assertEqual(result.must_write,0)

    def test_opaque_effects_cannot_enable_promotion(self):
        missing=analyze_instruction([])
        self.assertEqual(missing.read_before_write,ALL_REGISTER_BYTES)
        self.assertEqual(missing.must_write,0)
        self.assertIn("missing_pcode",missing.hazards)
        unknown=analyze_instruction([op("FUTURE_UNKNOWN",r(0,4),r(8,4))])
        self.assertEqual(unknown.read_before_write,ALL_REGISTER_BYTES)
        self.assertEqual(unknown.must_write,0)
        for kind,terms in [
            ("CALLOTHER",("opaque_callother",)),
            ("LOAD",("opaque_load",)),
            ("STORE",("opaque_store",)),
            ("CALL",("opaque_call",)),
            ("RETURN",("opaque_return",)),
        ]:
            with self.subTest(kind=kind):
                args=(m(0x1234),) if kind=="CALL" else (r(4),)
                result=analyze_instruction([op(kind,None,*args)])
                self.assertTrue(all(t in result.hazards for t in terms))


def fixture():
    insns=[
        (0x1000,1,[op("COPY",r(0),c(0x1234))]),
        (0x1001,1,[op("CBRANCH",None,m(0x1003),r(0x206,1))]),
        (0x1002,1,[op("COPY",r(4),r(0))]),
        (0x1003,1,[op("RETURN",None,r(16))]),
    ]
    mapping={
        "module":"CoDSP.exe","schema_version":2,
        "functions":[{"entry_va":"0x00001000","entry_in_translation":True,
                      "body_uniquely_owned_instruction_count":4}],
        "ghidra_body_ranges":[{"entry_va":"0x00001000",
                               "start_va":"0x00001000",
                               "end_va_inclusive":"0x00001003"}],
    }
    return insns,mapping


class RegionBoundaryTests(unittest.TestCase):
    def test_entire_register_state_live_out_at_dispatch_exits(self):
        insns,mapping=fixture()
        result=region_contract(insns,mapping,0x1000)
        self.assertEqual(result["instruction_count"],4)
        self.assertFalse(result["promote_registers_in_production"])
        self.assertTrue(result["external_cfg_exits"]>=1)
        last=result["blocks"][-1]
        self.assertTrue(last["needs_full_R_flush_on_external_exit"])
        self.assertEqual(last["live_out_bytes"],[[0,0x2000]])
        self.assertEqual(result["eflags_bytes_read"],1)

    def test_missing_pcode_does_not_claim_safe_liveness(self):
        insns,mapping=fixture()
        insns[-1]=(0x1003,1,[])
        report=region_contract(insns,mapping,0x1000)
        self.assertGreater(report["hazards"].get("missing_pcode",0),0)
        self.assertEqual(report["promote_registers_in_production"],False)

    def test_ambiguous_function_body_fails_closed(self):
        insns,mapping=fixture()
        mapping["ghidra_body_ranges"].append({
            "entry_va":"0x00002000","start_va":"0x00001002",
            "end_va_inclusive":"0x00001003",
        })
        with self.assertRaises(CFGError):
            region_contract(insns,mapping,0x1000)


if __name__=="__main__":
    unittest.main()
