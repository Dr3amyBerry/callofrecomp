"""Offline synthetic tests for the x87 FCOMP condition-bit oracle."""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools/recomp/diagnostics"))
from verify_x86_prefix_oracle import OracleError
from verify_fcom_condition_oracle import (
    FIXED_CASES,COND_MASK,FLD_PC,FCOMP_PC,
    operand_pairs,validate_decoded_fcomp,source_wrapper,
)


def fake(pc,size,name):
    return SimpleNamespace(address=pc,size=size,mnemonic=name)


class FcomConditionOracleTests(unittest.TestCase):
    def test_expected_original_opcodes(self):
        validate_decoded_fcomp([fake(FLD_PC,6,"fld")],
                               [fake(FCOMP_PC,6,"fcomp")])

    def test_reject_unexpected_instruction_and_length(self):
        bad=([fake(FLD_PC,4,"fld")],[fake(FCOMP_PC,6,"fcomp")])
        with self.assertRaises(OracleError):
            validate_decoded_fcomp(*bad)
        bad=([fake(FLD_PC,6,"fld")],[fake(FCOMP_PC,6,"fcom")])
        with self.assertRaises(OracleError):
            validate_decoded_fcomp(*bad)

    def test_fixed_edge_corpus_includes_nan_infinity_signed_zero(self):
        self.assertIn((0x80000000,0x00000000),FIXED_CASES)
        self.assertIn((0x7fc12345,0x3f800000),FIXED_CASES)
        self.assertIn((0x7f800000,0x7f800000),FIXED_CASES)
        self.assertEqual(COND_MASK,0x100|0x200|0x400|0x4000)

    def test_finite_random_corpus_is_deterministic(self):
        a=operand_pairs(50)
        b=operand_pairs(50)
        self.assertEqual(a,b)
        self.assertEqual(len(a),len(FIXED_CASES)+50)
        for x,y in a[len(FIXED_CASES):]:
            self.assertNotIn((x>>23)&255,(0,255))
            self.assertNotIn((y>>23)&255,(0,255))

    def test_reject_unsafe_case_counts(self):
        for n in (-1,10001):
            with self.assertRaisesRegex(OracleError,"Invalid"):
                operand_pairs(n)

    def test_wrapper_is_explicitly_opt_in_and_has_no_pe_bytes(self):
        c=source_wrapper()
        self.assertIn("#define CODRECOMP_X87_FCOM_FASTPATH 1",c)
        self.assertIn("codsp_fcom_pop_float32",c)
        self.assertIn("R+0x10a2",c)
        self.assertNotIn("CoDSP.exe",c)


if __name__=="__main__":
    unittest.main()
