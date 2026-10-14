"""Offline fail-closed tests for independent x87 guest-output oracle.

Fixtures deliberately contain no commercial game instruction bytes.
"""
from __future__ import annotations

import struct
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools/recomp/diagnostics"))

from verify_x86_prefix_oracle import OracleError
from verify_x87_window_oracle import (
    EXPECTED_INSNS,validate_x87_instruction_layout,
    generate_x87_lowering,case_input_bits,
)


def fake_window():
    result=[]
    for index,(pc,n,mn) in enumerate(EXPECTED_INSNS):
        if index == 0:
            ops=[("FLOAT2FLOAT",("r",0x1100,10),[("r",0,4)])]
        elif index==1:
            ops=[("FLOAT_SUB",("r",0x1100,10),[
                ("r",0x1100,10),("r",0x1110,10)])]
        else:
            ops=[("COPY",("r",0x1170,10),[("r",0x1100,10)])]
        result.append({"pc":pc,"size":n,"ops":ops})
    return result


class X87OracleOfflineTests(unittest.TestCase):
    def test_correct_bounded_layout_accepted(self):
        validate_x87_instruction_layout(fake_window())

    def test_reject_bad_instruction_lengths_and_missing_operations(self):
        x=fake_window()
        x[2]["size"]+=1
        with self.assertRaises(OracleError):
            validate_x87_instruction_layout(x)
        x=fake_window()
        x[0]["ops"]=[]
        with self.assertRaises(OracleError):
            validate_x87_instruction_layout(x)

    def test_actual_pcode_generator_is_used(self):
        src=generate_x87_lowering(fake_window())
        self.assertIn("f2d(",src)
        self.assertIn("d2f(",src)
        self.assertIn("PC=0x41b973u;",src)
        self.assertIn("memcpy(regs,R,sizeof(R))",src)

    def test_refuse_unhandled_branch_or_user_operation(self):
        x=fake_window()
        x[3]["ops"]=[("CBRANCH",None,[("m",0x41b986,4),("r",0x206,1)])]
        with self.assertRaisesRegex(OracleError,"Control transfer"):
            generate_x87_lowering(x)
        x=fake_window()
        x[3]["ops"]=[("CALLOTHER",None,[("c",0xdeaf,4)])]
        with self.assertRaisesRegex(OracleError,"Unsupported"):
            generate_x87_lowering(x)

    def test_finite_seeded_float_inputs_are_reproducible(self):
        for case in range(16,64):
            self.assertEqual(case_input_bits(case),case_input_bits(case))
            for value in case_input_bits(case):
                self.assertNotEqual((value>>23)&0xff,255)
                self.assertNotEqual((value>>23)&0xff,0)
        # Signed zero and simple exact values also belong to edge corpus.
        self.assertEqual(
            struct.unpack("<f",case_input_bits(0)[0].to_bytes(4,"little"))[0],0.0
        )


if __name__=="__main__":
    unittest.main()
