"""Synthetic fail-closed validation of CoDSP shared epilogue CFG contract."""
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools/recomp"))
from region_cfg import CFGError
from diagnostics.verify_cfg_against_x86 import X86Instruction
from diagnostics.verify_shared_epilogue import (
    verify_epilogue_contract, assert_direct_control, SHARED_ENTRY,
    FAILURE_TARGET, GEOMETRY_JMPS, TAIL_JCC, TAIL_RET, TAIL_FAILURE_JMP
)


def arg(s,a,n=4):return (s,a,n)

def insn(pc,size,ops):return (pc,size,ops)

def op(mn,out=None,*args):return (mn,out,list(args))


def fixture():
    original=[
        insn(0x0041b8f0,1,[op("COPY",arg("r",0),arg("c",1))]),
        *[insn(addr,1,[op("BRANCH",None,arg("m",SHARED_ENTRY))])
          for addr in GEOMETRY_JMPS],
        insn(SHARED_ENTRY,6,[op("COPY",arg("r",0x206,1),arg("c",1,1))]),
        insn(TAIL_JCC,2,[op("CBRANCH",None,arg("m",TAIL_FAILURE_JMP),
                               arg("r",0x206,1))]),
        insn(TAIL_RET,1,[op("RETURN",None,arg("r",0x10))]),
        insn(TAIL_FAILURE_JMP,5,[op("BRANCH",None,arg("m",FAILURE_TARGET))]),
    ]
    sources=[(0x0041b8f0,0x0041b8f0)]
    sources.extend((pc,pc) for pc in GEOMETRY_JMPS)
    mapping={
        "schema_version":2,
        "functions":[
            {"entry_va":"0x0041b8f0","entry_in_translation":True,
             "body_uniquely_owned_instruction_count":4},
            {"entry_va":"0x00523cd9","entry_in_translation":True,
             "body_uniquely_owned_instruction_count":4},
        ],
        "ghidra_body_ranges":[
            *[{"entry_va":"0x0041b8f0","start_va":f"0x{lo:08x}",
                "end_va_inclusive":f"0x{hi:08x}"} for lo,hi in sources],
            {"entry_va":"0x00523cd9",
             "start_va":f"0x{SHARED_ENTRY:08x}",
             "end_va_inclusive":f"0x{TAIL_FAILURE_JMP+4:08x}"},
        ]
    }
    decoded={
        **{pc:X86Instruction(pc,1,"direct_jump",SHARED_ENTRY)
            for pc in GEOMETRY_JMPS},
        SHARED_ENTRY:X86Instruction(SHARED_ENTRY,6,"normal"),
        TAIL_JCC:X86Instruction(TAIL_JCC,2,"conditional",TAIL_FAILURE_JMP),
        TAIL_RET:X86Instruction(TAIL_RET,1,"return"),
        TAIL_FAILURE_JMP:X86Instruction(TAIL_FAILURE_JMP,5,
                                       "direct_jump",FAILURE_TARGET),
    }
    return original,mapping,decoded


class SharedEpilogueContractTests(unittest.TestCase):
    def decode(self, records):
        def take(pc,size):
            return records[pc]
        return take

    def test_valid_shared_function_remains_external(self):
        insns,mapping,decoded=fixture()
        result=verify_epilogue_contract(insns,mapping,self.decode(decoded))
        self.assertEqual(result["shared_entry"],"0x00523cd9")
        self.assertEqual(result["external_jumps"],[f"0x{pc:08x}" for pc in GEOMETRY_JMPS])
        self.assertFalse(result["safe_to_inline_or_omit"])
        self.assertTrue(result["must_preserve_shared_tail"])
        self.assertFalse(result["has_full_state_oracle"])

    def test_mutated_geometry_target_is_detected(self):
        insns,mapping,decoded=fixture()
        pc=GEOMETRY_JMPS[0]
        modified=[]
        for address,size,ops in insns:
            if address==pc:
                ops=[op("BRANCH",None,arg("m",SHARED_ENTRY+2))]
            modified.append((address,size,ops))
        with self.assertRaisesRegex(CFGError,"control flow"):
            verify_epilogue_contract(modified,mapping,self.decode(decoded))

    def test_mutated_original_x86_decode_is_detected(self):
        insns,mapping,decoded=fixture()
        decoded[GEOMETRY_JMPS[1]]=X86Instruction(GEOMETRY_JMPS[1],1,
                                                  "direct_jump",SHARED_ENTRY+5)
        with self.assertRaisesRegex(CFGError,"Original x86"):
            verify_epilogue_contract(insns,mapping,self.decode(decoded))

    def test_unexpected_conditional_fallthrough_or_failure_target_rejected(self):
        insns,mapping,decoded=fixture()
        bad=[]
        for pc,size,ops in insns:
            if pc==TAIL_JCC:
                ops=[op("BRANCH",None,arg("m",TAIL_FAILURE_JMP))]
            bad.append((pc,size,ops))
        with self.assertRaisesRegex(CFGError,"control flow"):
            verify_epilogue_contract(bad,mapping,self.decode(decoded))

    def test_shared_exit_must_remain_separate_ghidra_function(self):
        insns,mapping,decoded=fixture()
        mapping["functions"][1]["entry_in_translation"]=False
        with self.assertRaisesRegex(CFGError,"distinct verified"):
            verify_epilogue_contract(insns,mapping,self.decode(decoded))

    def test_opaque_pcode_blocks_static_proof(self):
        with self.assertRaises(CFGError):
            assert_direct_control([op("CALLOTHER",None,arg("c",3)),
                                   op("BRANCH",None,arg("m",SHARED_ENTRY))],
                                  0x1111,"direct_jump",SHARED_ENTRY)


if __name__=="__main__":
    unittest.main()
