"""Offline fail-closed tests of the bounded independent x86 oracle.

All instruction fixtures are synthetic: CI never requires commercial game
code, Unicorn, Capstone, pefile, Android, or the generated private DLL.
"""
from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools/recomp/diagnostics"))
from verify_x86_prefix_oracle import (
    START, STOP, BRANCH_TARGET, OracleError, require_private_path,
    require_ignored_output, require_original_fingerprints, generate_lowering,
    trial_inputs, EXPECTED_PE_SHA256, EXPECTED_PCODE_SHA256
)


def fake_insn(pc, ops):
    return {"pc":pc,"size":3,"ops":ops}


class OracleFailClosedTests(unittest.TestCase):
    def test_pinned_build_identity(self):
        require_original_fingerprints(EXPECTED_PE_SHA256,EXPECTED_PCODE_SHA256)
        for pe,pcode in (("0"*64,EXPECTED_PCODE_SHA256),
                         (EXPECTED_PE_SHA256,"0"*64)):
            with self.assertRaisesRegex(OracleError,"fingerprint"):
                require_original_fingerprints(pe,pcode)

    def test_private_pe_must_stay_in_private_area(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            private=root/".local"/"private"
            private.mkdir(parents=True)
            allowed=private/"synthetic.exe"
            allowed.write_bytes(b"synthetic")
            require_private_path(allowed,private)
            escaped=root/"unrelated.exe"
            escaped.write_bytes(b"x")
            with self.assertRaises(OracleError):
                require_private_path(escaped,private)

    def test_report_output_must_be_new_and_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            folder=root/".local"/"profiles"
            folder.mkdir(parents=True)
            p=folder/"new_diff_report"
            require_ignored_output(p,root)
            p.mkdir()
            with self.assertRaises(OracleError):
                require_ignored_output(p,root)
            with self.assertRaises(OracleError):
                require_ignored_output(root/"outputs"/"illegal",root)

    def test_lowering_uses_current_generator_and_bound_jump(self):
        instrs=[
            fake_insn(START,[("COPY",("r",0,4),[("c",7,4)])]),
            fake_insn(STOP-6,[("CBRANCH",None,[
                ("m",BRANCH_TARGET,4),("r",0x206,1)
            ])])
        ]
        src=generate_lowering(instrs)
        self.assertIn("PC=0x41bce0u; goto oracle_exit;",src)
        self.assertIn("PC=0x41b941u;",src)
        self.assertIn("rd(R+0x206,1)",src)
        self.assertIn("memcpy(initial_regs,R,sizeof(R))",src)

    def test_lowering_rejects_wrong_target_and_extra_control(self):
        branch=fake_insn(STOP-6,[("CBRANCH",None,[
            ("m",BRANCH_TARGET+8,4),("r",0x206,1)
        ])])
        with self.assertRaisesRegex(OracleError,"conditional jump"):
            generate_lowering([branch])
        with self.assertRaisesRegex(OracleError,"Unsupported control"):
            generate_lowering([fake_insn(START,[("RETURN",None,[("r",16,4)])])])

    def test_unsupported_userop_fails_without_outputting_code(self):
        bad=[fake_insn(START,[("CALLOTHER",None,[("c",987,4)])])]
        with self.assertRaisesRegex(OracleError,"Unsupported operation"):
            generate_lowering(bad)

    def test_branch_cases_balanced_and_seed_deterministic(self):
        for case in range(24):
            one=trial_inputs(case)
            two=trial_inputs(case)
            self.assertEqual(one,two)
            regs,flags,memory=one
            self.assertEqual(regs["ECX"],0x350000)
            self.assertEqual(regs["ESP"],0x320000)
            addr,ecx_buffer=memory[1]
            val=int.from_bytes(ecx_buffer[0x1f4:0x1f8],"little")
            self.assertEqual(val==0,case%2==0)
            self.assertGreaterEqual(flags,2)

if __name__=="__main__":
    unittest.main()
