"""Fail-closed synthetic tests of phase14 x87 intermediate state verifier.

Commercial CoDSP bytes, Ghidra p-code and Unicorn are NOT necessary in CI.
"""
from __future__ import annotations
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools/recomp/diagnostics"))
from verify_x87_internal_state import (
    OracleError,START,STOP,CHECKPOINTS,EXPECTED_INSNS,
    fp80_bytes,build_checkpoint_lowering,st0_fidelity_gate,make_report
)

def var(space,off,size):return (space,off,size)

def synthetic_instruction(pc,size):
    return {"pc":pc,"size":size,"ops":[
        ("COPY",var("r",0,4),[var("c",0x123456,4)])
    ]}


class Binary80EncodingTests(unittest.TestCase):
    def test_integer_tuple_matches_little_endian_binary80_layout(self):
        b=fp80_bytes(0xc000000000000000,0x3fff)
        self.assertEqual(b,bytes.fromhex("00000000000000c0ff3f"))
        self.assertEqual(len(b),10)

    def test_negative_sign_is_encoded_in_signexponent_word(self):
        b=fp80_bytes(0x8000000000000000,0xbfff)
        self.assertEqual(int.from_bytes(b[8:],"little"),0xbfff)

    def test_invalid_unicorn_tuple_rejected(self):
        for mant,exp in [(-1,0),(1<<64,0),(0,-1),(0,1<<16)]:
            with self.subTest(mant=mant,exp=exp):
                with self.assertRaises(OracleError):
                    fp80_bytes(mant,exp)


class CheckpointLoweringTests(unittest.TestCase):
    def fixture(self):
        return [synthetic_instruction(pc,sz) for pc,sz,_ in EXPECTED_INSNS]

    def test_every_original_instruction_boundary_is_pinned(self):
        self.assertEqual(len(CHECKPOINTS),5)
        self.assertEqual(CHECKPOINTS[-1],STOP)
        for i,checkpoint in enumerate(CHECKPOINTS):
            source=build_checkpoint_lowering(self.fixture(),checkpoint)
            self.assertIn(f"PC=0x{checkpoint:x}u;",source)
            self.assertIn("memcpy(regs,R,sizeof(R));",source)
            self.assertEqual(source.count(" uint8_t T["),i+1)

    def test_unapproved_boundary_and_layout_rejected(self):
        with self.assertRaisesRegex(OracleError,"not an audited"):
            build_checkpoint_lowering(self.fixture(),0x41b966+1)
        bad=self.fixture()
        bad[2]["size"]+=1
        with self.assertRaisesRegex(OracleError,"pinned"):
            build_checkpoint_lowering(bad,CHECKPOINTS[-1])

    def test_opaque_pcode_rejected(self):
        bad=self.fixture()
        bad[1]["ops"]=[("CALLOTHER",None,[var("c",44,4)])]
        with self.assertRaisesRegex(OracleError,"opaque"):
            build_checkpoint_lowering(bad,CHECKPOINTS[1])
        bad=self.fixture()
        bad[0]["ops"]=[]
        with self.assertRaisesRegex(OracleError,"Missing"):
            build_checkpoint_lowering(bad,CHECKPOINTS[0])


def counts(cases,matched,live=True):
    return {
        "gpr_match":cases,"memory_match":cases,
        "binary80_match":matched if live else 0,
        "binary80_differ":(cases-matched) if live else 0,
        "binary80_not_live":0 if live else cases,
        "mismatch_signexp_match":0,
        "mismatch_upper53_significand_match":0,
        "mismatch_original_low11_nonzero":0,
        "mismatch_translated_low11_zero":0,
    }


class StrictFidelityGateTests(unittest.TestCase):
    def test_complete_live_st0_exactness_is_required(self):
        matching=[{"counts":counts(32,32)},{"counts":counts(32,0,live=False)}]
        self.assertTrue(st0_fidelity_gate(matching,32))
        mismatch=[{"counts":counts(32,31)},{"counts":counts(32,0,live=False)}]
        self.assertFalse(st0_fidelity_gate(mismatch,32))
        corrupt=[{"counts":dict(counts(32,32),memory_match=31)}]
        self.assertFalse(st0_fidelity_gate(corrupt,32))
        self.assertFalse(st0_fidelity_gate([{"counts":counts(32,0,live=False)}],32))
        self.assertFalse(st0_fidelity_gate([],32))
        self.assertFalse(st0_fidelity_gate(matching,0))

    def test_aggregate_evidence_preserves_mismatch_counts(self):
        rows=[
            {"gpr_match":True,"memory_match":True,
             "binary80_st0_live":True,"binary80_st0_match":True,
             "binary80_mismatch_shape":{},
             "unicorn_status_word":0x3800},
            {"gpr_match":True,"memory_match":True,
             "binary80_st0_live":True,"binary80_st0_match":False,
             "binary80_mismatch_shape":{
                "signexp_match":True,
                "upper53_significand_match":True,
                "original_low11_nonzero":True,
                "translated_low11_zero":True},
             "unicorn_status_word":0x3800},
        ]
        with patch("verify_x87_internal_state.audit_case",side_effect=rows):
            out=make_report([],b"",CHECKPOINTS[0],object(),2)
        self.assertEqual(out["counts"]["binary80_differ"],1)
        self.assertEqual(out["counts"]["binary80_match"],1)
        self.assertEqual(out["counts"]["mismatch_translated_low11_zero"],1)
        self.assertEqual(out["status"],"mismatch_or_incomplete")


if __name__=="__main__":
    unittest.main()
