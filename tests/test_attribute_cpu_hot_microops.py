"""Synthetic-only native-sample/guest-instruction classification guard tests."""
from __future__ import annotations
import sys
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools/recomp/diagnostics"))
from attribute_cpu_hot_microops import (
    opcode_presence,categorize_guest_label_samples
)

def o(name,out=None,*args):return (name,out,list(args))
def row(pc,n,module="codsp"):return {
    "module":module,"guest_pc":f"0x{pc:08x}","samples":n}

class InstructionOperatorPresenceNotTime(unittest.TestCase):
    def test_x87_and_float_pcode_are_two_distinct_signals(self):
        ops=[o("FLOAT_ADD",("r",0x1100,10),("r",0x1100,10),("r",0x1110,10))]
        labels=opcode_presence(ops)
        self.assertIn("float_pcode",labels)
        self.assertIn("x87_state_pcode",labels)

    def test_direct_memory_and_pcode_store_flagged_even_without_load(self):
        direct=opcode_presence([o("COPY",("r",0,4),("m",0x400000,4))])
        store=opcode_presence([o("STORE",None,("c",0x1a1,8),("r",0,4),
                                ("r",4,4))])
        branch=opcode_presence([o("BRANCH",None,("m",0x2000,4))])
        self.assertIn("guest_mem_pcode",direct)
        self.assertIn("guest_mem_pcode",store)
        self.assertNotIn("guest_mem_pcode",branch)

    def test_overlapping_annotations_are_not_exclusive_cpu_time(self):
        indexed={
            0x1000:[o("LOAD",("u",0,4),("c",0x1a1,8),("r",0,4)),
                    o("FLOAT2FLOAT",("r",0x1100,10),("u",0,4)),
                    o("POPCOUNT",("u",20,1),("u",32,4))],
            0x1001:[o("INT_MULT",("r",4,4),("r",0,4),("c",8,4))],
            0x1002:[o("INT_ADD",("r",0,4),("r",0,4),("c",4,4))]
        }
        report=categorize_guest_label_samples([
            row(0x1000,15),row(0x1001,9),row(0x1002,6),
            row(0x2000,13),row(0x1000,4,"gamex86")
        ],indexed,{0x1000,0x1001,0x1002})
        self.assertEqual(report["selected_original_function_guest_PC_samples"],30)
        self.assertEqual(report["exclusive_instruction_annotation_buckets"],
                         {"x87-associated":15,"integer-other":15})
        self.assertEqual(report["overlapping_pcode_presence_sample_counts"]["parity_pcode"],15)
        self.assertEqual(report["overlapping_pcode_presence_sample_counts"]["float_pcode"],15)
        self.assertEqual(report["overlapping_pcode_presence_sample_counts"]["integer_math_pcode"],9)
        self.assertTrue(report["not_a_cpu_time_breakdown"] if "not_a_cpu_time_breakdown" in report else
                        "not CPU time" in report["warning"])

    def test_reject_positive_weight_on_missing_selected_pc(self):
        with self.assertRaisesRegex(ValueError,"outside exact"):
            categorize_guest_label_samples([row(0x1100,8)],
                                           {0x1000:[]},{0x1100})

    def test_omit_non_target_codsp_labels_without_dropping_source_total(self):
        report=categorize_guest_label_samples([
            row(0x1000,2),row(0x2000,5),row(0x1000,7,"cgamex86")
        ],{0x1000:[]},{0x1000})
        self.assertEqual(report["selected_original_function_guest_PC_samples"],2)
        self.assertEqual(report["all_codsp_guest_PC_resolved_samples"],7)

    def test_invalid_negative_sample_rejected(self):
        with self.assertRaisesRegex(ValueError,"invalid"):
            categorize_guest_label_samples([row(0x1000,-1)],
                                           {0x1000:[]},{0x1000})

if __name__=="__main__":unittest.main()
