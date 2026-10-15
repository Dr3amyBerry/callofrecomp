"""Independent x86 decode vs p-code CFG phase14 verifier: synthetic unit tests.

Never depends on a commercial PE file. Deliberately wrong x86 branches and
translation mismatches must be detected rather than silently accepted.
"""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools/recomp"))
from diagnostics.verify_cfg_against_x86 import (
    X86Instruction, check_edges,
)


def r(off=0):
    return ("r", off, 4)


def m(target):
    return ("m", target, 4)


def op(name, out=None, *ins):
    return name, out, list(ins)


class IndependentX86CFGChecks(unittest.TestCase):
    def test_verified_realistic_branch_kinds(self):
        insns = [
            (0x1000, 2, [op("CBRANCH", None, m(0x1009), r())]),
            (0x1002, 5, [op("CALL", None, m(0x2000))]),
            (0x1007, 2, [op("BRANCH", None, m(0x1000))]),
            (0x1009, 2, [op("BRANCHIND", None, r())]),
            (0x100b, 2, [op("CALLIND", None, r())]),
            (0x100d, 1, [op("RETURN", None, r())]),
            (0x100e, 3, [op("COPY", r(4), r())]),
        ]
        x86 = [
            X86Instruction(0x1000, 2, "conditional", 0x1009),
            X86Instruction(0x1002, 5, "direct_call", 0x2000),
            X86Instruction(0x1007, 2, "direct_jump", 0x1000),
            X86Instruction(0x1009, 2, "indirect_jump"),
            X86Instruction(0x100b, 2, "indirect_call"),
            X86Instruction(0x100d, 1, "return"),
            X86Instruction(0x100e, 3, "normal"),
        ]
        result = check_edges(insns, x86)
        self.assertTrue(result["all_edges_agree_where_decoded"])
        self.assertEqual(result["counts"]["control_targets_matching"], 6)
        self.assertEqual(result["counts"]["ordinary_instructions_matching"], 1)

    def test_wrong_target_detected(self):
        insns = [(0x1000, 2, [op("CBRANCH", None, m(0x1009), r())])]
        verified = [X86Instruction(0x1000, 2, "conditional", 0x1009)]
        corrupted = [X86Instruction(0x1000, 2, "conditional", 0x100a)]
        self.assertTrue(check_edges(insns, verified)["all_edges_agree_where_decoded"])
        result = check_edges(insns, corrupted)
        self.assertFalse(result["all_edges_agree_where_decoded"])
        self.assertEqual(result["counts"]["control_target_mismatch"], 1)
        self.assertEqual(result["mismatch_samples"][0]["pc"], "0x00001000")

    def test_wrong_size_detected(self):
        insns = [(0x1000, 2, [op("COPY", r(0), r(4))])]
        result = check_edges(insns, [X86Instruction(0x1000, 3, "normal")])
        self.assertFalse(result["all_edges_agree_where_decoded"])
        self.assertEqual(result["counts"]["instruction_length_mismatch"], 1)

    def test_missing_source_pcode_not_counted_as_verified_semantics(self):
        insns = [(0x1000, 2, [])]
        result = check_edges(insns, [X86Instruction(0x1000, 2, "return")])
        self.assertEqual(result["unverified_pcode_insns"], 1)
        self.assertEqual(result["counts"].get("control_targets_matching", 0), 0)

    def test_missing_decoded_pc_detected(self):
        insns = [(0x1000, 2, [op("RETURN", None, r())])]
        result = check_edges(insns, [])
        self.assertFalse(result["all_edges_agree_where_decoded"])
        self.assertEqual(result["counts"]["missing_x86_decode"], 1)


if __name__ == "__main__":
    unittest.main()
