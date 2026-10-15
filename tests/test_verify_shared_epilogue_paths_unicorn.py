"""Synthetic checks for independent shared-epilogue branch-oracle safety."""
from __future__ import annotations
import sys
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools/recomp/diagnostics"))
from verify_shared_epilogue_paths_unicorn import (
    case_input,generate_private_epilogue,REG_OFFSETS,FLAG_BITS,
    COOKIE_GLOBAL_ADDRESS,STACK,PC_SUCCESS,TAIL_RET,TAIL_JCC,
    TAIL_FAILURE_JMP,SHARED_ENTRY,FAILURE_TARGET,OracleError,
    ERROR_SETUP_PCS,ERROR_CALL_TARGET
)

def v(sp,off,size=4):return (sp,off,size)
def op(name,out=None,*ins):return (name,out,list(ins))


def fixture():
    # Synthetic microprogram, not any original game's decoded bytes.
    return {
        SHARED_ENTRY:(6,[op("COPY",v("r",0x206,1),v("c",0,1))]),
        TAIL_JCC:(2,[op("CBRANCH",None,v("m",TAIL_FAILURE_JMP),v("r",0x206,1))]),
        TAIL_RET:(1,[op("LOAD",v("r",0x284),v("c",0x1a1),v("r",0x10)),
                     op("INT_ADD",v("r",0x10),v("r",0x10),v("c",4)),
                     op("RETURN",None,v("r",0x284))]),
        TAIL_FAILURE_JMP:(5,[op("BRANCH",None,v("m",FAILURE_TARGET))]),
    }


def full_error_fixture():
    selected=fixture()
    first,second,third=ERROR_SETUP_PCS
    selected[first]=(2,[
        op("INT_SUB",v("r",0x10),v("r",0x10),v("c",4)),
        op("STORE",None,v("c",0x1a1,8),v("r",0x10),v("c",8))
    ])
    selected[second]=(5,[
        op("INT_SUB",v("r",0x10),v("r",0x10),v("c",4)),
        op("STORE",None,v("c",0x1a1,8),v("r",0x10),v("c",0x533b68))
    ])
    selected[third]=(5,[
        op("INT_SUB",v("r",0x10),v("r",0x10),v("c",4)),
        op("STORE",None,v("c",0x1a1,8),v("r",0x10),v("c",0x523cb4)),
        op("CALL",None,v("m",ERROR_CALL_TARGET))
    ])
    return selected


class PinnedEpilogueOracleTests(unittest.TestCase):
    def test_each_seed_forces_intended_cookie_branch_without_tf(self):
        for success in (True,False):
            for index in range(12):
                regs,mem,all_gpr,flags=case_input(index,success)
                val=int.from_bytes(mem[COOKIE_GLOBAL_ADDRESS:COOKIE_GLOBAL_ADDRESS+4],"little")
                self.assertEqual(all_gpr["ECX"]==val,success)
                self.assertEqual(flags&(1<<8),0,"Unicorn single-step trap must stay off")
                self.assertEqual(int.from_bytes(mem[STACK:STACK+4],"little"),PC_SUCCESS)
                for name,off in REG_OFFSETS.items():
                    self.assertEqual(int.from_bytes(regs[off:off+4],"little"),all_gpr[name])
                for _name,(bit,off) in FLAG_BITS.items():
                    self.assertEqual(regs[off],(flags>>bit)&1)

    def test_translated_branch_and_guest_pc_shadow_are_not_omitted(self):
        emitted=generate_private_epilogue(fixture())
        self.assertIn("goto p_523ce2",emitted)
        self.assertIn("goto dyn",emitted)
        self.assertIn("R+0x284",emitted)
        self.assertIn("PC=0x523ca8u; goto finish;",emitted)
        self.assertIn("memcpy(regs,R,0x2000)",emitted)

    def test_wrong_original_failure_target_rejected(self):
        bad=fixture()
        bad[TAIL_FAILURE_JMP]=(5,[op("BRANCH",None,v("m",FAILURE_TARGET+4))])
        with self.assertRaisesRegex(OracleError,"unexpected original"):
            generate_private_epilogue(bad)

    def test_error_handler_prologue_pushes_and_pinned_first_call(self):
        emitted=generate_private_epilogue(full_error_fixture(),
                                          follow_error_call=True)
        self.assertIn("goto p_523ca8;",emitted)
        self.assertIn("p_523caa:",emitted)
        self.assertIn("p_523caf:",emitted)
        self.assertIn("PC=0x51ff90u; goto finish;",emitted)

    def test_error_handler_first_call_wrong_target_is_not_accepted(self):
        incorrect=full_error_fixture()
        final=ERROR_SETUP_PCS[-1]
        ops=list(incorrect[final][1])
        ops[-1]=op("CALL",None,v("m",ERROR_CALL_TARGET+16))
        incorrect[final]=(5,ops)
        with self.assertRaisesRegex(OracleError,"unexpected original"):
            generate_private_epilogue(incorrect,follow_error_call=True)

    def test_opaque_userop_cannot_inherit_success_from_other_route(self):
        bad=fixture()
        bad[TAIL_RET]=(1,[op("CALLOTHER",None,v("c",9))])
        with self.assertRaisesRegex(OracleError,"opaque"):
            generate_private_epilogue(bad)

if __name__=="__main__":unittest.main()
