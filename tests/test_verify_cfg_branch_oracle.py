"""Fail-closed synthetic tests of two-path real-x86 execution oracle."""
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools/recomp/diagnostics"))
from verify_cfg_branch_oracle import (
    generate_two_path_lowering, OracleError, ARCH_OBSERVED, TAKEN_EXPECTED,
    BRANCH_TARGET, TAKEN_END, START, STOP
)


def r(offset,size=4):return ("r",offset,size)
def c(value,size=4):return ("c",value,size)
def m(addr):return ("m",addr,4)
def op(name,out=None,*args):return name,out,list(args)
def instr(pc,ops):return {"pc":pc,"size":3,"ops":ops}

class TwoPathOracleTests(unittest.TestCase):
    def prefix(self):
        return [
            instr(START,[op("COPY",r(0),c(3))]),
            instr(STOP-6,[op("CBRANCH",None,m(BRANCH_TARGET),r(0x206,1))]),
        ]
    def taken(self):
        return [instr(BRANCH_TARGET,[op("INT_ADD",r(12),r(0),c(5))]),
                instr(BRANCH_TARGET+4,[op("COPY",r(8),r(12))])]

    def test_two_paths_are_generated_from_current_pcode2c(self):
        text=generate_two_path_lowering(self.prefix(),self.taken())
        self.assertEqual(text.count("goto oracle_taken;"),1)
        self.assertIn("oracle_taken:",text)
        self.assertIn(f"PC=0x{TAKEN_END:x}u;",text)
        self.assertIn(f"PC=0x{STOP:x}u;",text)
        self.assertEqual(text.count("oracle_exit:"),1)
        self.assertIn("wr(R+0xc,4",text)
        self.assertIn("memcpy(initial_regs,R,sizeof(R))",text)

    def test_invalid_prefix_branch_refused(self):
        source=self.prefix()
        source[1]=instr(STOP-6,[
            op("CBRANCH",None,m(BRANCH_TARGET+4),r(0x206,1))])
        with self.assertRaisesRegex(OracleError,"conditional jump"):
            generate_two_path_lowering(source,self.taken())

    def test_opaque_pcode_and_new_control_refused(self):
        for opn in ("CALLOTHER","RETURN","BRANCH"):
            with self.subTest(opn=opn):
                unsafe=self.taken()+[instr(BRANCH_TARGET+8,[op(opn,None,c(1))])]
                with self.assertRaises(OracleError):
                    generate_two_path_lowering(self.prefix(),unsafe)

    def test_x87_is_not_inside_verified_window(self):
        self.assertEqual(len(TAKEN_EXPECTED),7)
        self.assertEqual(TAKEN_EXPECTED[0][0],BRANCH_TARGET)
        self.assertEqual(TAKEN_EXPECTED[-1][0]+TAKEN_EXPECTED[-1][1],TAKEN_END)
        self.assertEqual([entry[2] for entry in TAKEN_EXPECTED],
                         ["lea","xor","sub","mov","mov","mov","lea"])

    def test_architectural_byte_observation_set(self):
        self.assertEqual(len(ARCH_OBSERVED),8*4+5)
        self.assertIn(0x206,ARCH_OBSERVED)
        self.assertIn(16,ARCH_OBSERVED)
        self.assertNotIn(0x1100,ARCH_OBSERVED)
        self.assertNotIn(0x20,ARCH_OBSERVED)

if __name__=="__main__":
    unittest.main()
