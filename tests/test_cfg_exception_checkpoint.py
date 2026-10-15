"""Synthetic-only guest exception checkpoint and safe flag-order tests.

Production helper and proprietary PE bytes are intentionally not imported.
"""
from __future__ import annotations
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools/recomp"))
from cfg_region_lab import (
    Region,CFGError,may_fault_guest_memory,exception_atomic_memory_ops,
    generate_region_c
)
from diagnostics.verify_cfg_fault_restart_unicorn import (
    eflags_from_checkpoint,registers_from_checkpoint
)
from diagnostics.verify_x86_prefix_oracle import FLAG_BITS,REG_OFFSETS

def r(off,size=4):return ("r",off,size)
def c(val,size=4):return ("c",val,size)
def m(addr,size=4):return ("m",addr,size)
def o(name,out=None,*inputs):return (name,out,list(inputs))

def test_region():
    return Region(0x1000,0x1000,(
        (0x1000,1,[o("COPY",r(0),c(2)),
                   o("INT_ADD",r(0),r(0),c(3))]),
        (0x1001,1,[o("LOAD",r(4),c(0x1a1,8),r(0))]),
        (0x1002,1,[o("COPY",r(8),m(0x3300))]),
    ))


class GuestMemoryEffects(unittest.TestCase):
    def test_distinguish_direct_absolute_mem_from_control_target(self):
        self.assertTrue(may_fault_guest_memory("COPY",r(0),[m(0x1234)]))
        self.assertTrue(may_fault_guest_memory("LOAD",r(4),[c(0x1a1,8),r(0)]))
        self.assertTrue(may_fault_guest_memory("STORE",None,
                                             [c(0x1a1,8),r(0),r(4)]))
        self.assertFalse(may_fault_guest_memory("BRANCH",None,[m(0x2222)]))
        self.assertFalse(may_fault_guest_memory("INT_ADD",r(0),[r(0),c(2)]))

    def test_no_memory_instruction_keeps_original_pcode(self):
        ops=[o("INT_ADD",r(0),r(0),c(3)),
             o("INT_XOR",r(4),r(4),r(0))]
        self.assertEqual(exception_atomic_memory_ops(ops,0x1000),ops)

    def test_flag_clears_are_delayed_until_after_faultable_load(self):
        ops=[
            o("INT_ADD",("u",4,4),r(0),c(4)),
            o("COPY",r(0x200,1),c(0,1)),
            o("COPY",r(0x20b,1),c(0,1)),
            o("LOAD",("u",8,4),c(0x1a1,8),("u",4,4)),
            o("INT_XOR",r(4),r(4),("u",8,4)),
        ]
        moved=exception_atomic_memory_ops(ops,0x41c073)
        self.assertEqual([t[0] for t in moved],
                         ["INT_ADD","LOAD","COPY","COPY","INT_XOR"])
        self.assertEqual(moved[2:4],ops[1:3])
        self.assertEqual(moved[0],ops[0])
        self.assertEqual(moved[-1],ops[-1])

    def test_reject_dirty_arch_state_before_fault_except_known_flag_clears(self):
        for corrupt in (
            [o("COPY",r(0),c(3)),o("LOAD",r(4),c(0x1a1,8),r(8))],
            [o("COPY",r(0x200,1),c(1,1)),o("LOAD",r(4),c(0x1a1,8),r(8))],
            [o("INT_SUB",r(0x200,1),r(0x200,1),c(1,1)),
             o("LOAD",r(4),c(0x1a1,8),r(8))],
        ):
            with self.subTest(code=corrupt),self.assertRaises(CFGError):
                exception_atomic_memory_ops(corrupt,0x1000)

    def test_reject_guest_store_that_would_be_replayed_on_fault(self):
        unsafe=[
            o("STORE",None,c(0x1a1,8),r(0),r(4)),
            o("LOAD",r(8),c(0x1a1,8),r(16)),
        ]
        with self.assertRaisesRegex(CFGError,"partial guest STORE"):
            exception_atomic_memory_ops(unsafe,0x1000)

    def test_reject_flag_consumer_before_load(self):
        unsafe=[
            o("COPY",r(0x200,1),c(0,1)),
            o("BOOL_NEGATE",r(0x206,1),r(0x200,1)),
            o("LOAD",r(4),c(0x1a1,8),r(8))
        ]
        with self.assertRaisesRegex(CFGError,"consumed"):
            exception_atomic_memory_ops(unsafe,0x1000)

    def test_reject_moving_flags_across_micro_control(self):
        unsafe=[
            o("COPY",r(0x200,1),c(0,1)),
            o("CBRANCH",None,c(2,8),r(0x206,1)),
            o("LOAD",r(8),c(0x1a1,8),r(4))
        ]
        with self.assertRaisesRegex(CFGError,"micro-CFG"):
            exception_atomic_memory_ops(unsafe,0x1000)


class OriginalTranslatorResumeSnapshot(unittest.TestCase):
    def test_reconstruct_only_materialized_x86_flags(self):
        state=bytearray(0x2000)
        expected=2
        for index,(_name,(bit,offset)) in enumerate(FLAG_BITS.items()):
            state[offset]=index%2
            expected|=(index%2)<<bit
        self.assertEqual(eflags_from_checkpoint(state),expected)
        # No hidden TF, AF, DF, or x87 condition bits are invented.
        self.assertEqual(eflags_from_checkpoint(state)&(1<<8),0)

    def test_original_dispatcher_receives_all_eight_registers_at_resume(self):
        state=bytearray(0x2000)
        for index,(name,offset) in enumerate(REG_OFFSETS.items()):
            state[offset:offset+4]=(0x12340000+index).to_bytes(4,"little")
        restored=registers_from_checkpoint(state)
        self.assertEqual(len(restored),8)
        for index,name in enumerate(REG_OFFSETS):
            self.assertEqual(restored[name],0x12340000+index)


class RegionCheckpointGeneration(unittest.TestCase):
    def test_checkpoint_before_dynamic_and_direct_absolute_accesses(self):
        source,fields=generate_region_c(
            test_region(),cache_count=1,entry_policy="start_only",
            memory_model="exact",fault_policy="checkpoint")
        self.assertIn(r(0),fields)
        left=source.split("B_1001: {",1)[1].split("B_1002: {",1)[0]
        right=source.split("B_1002: {",1)[1].split("dispatch:",1)[0]
        self.assertIn("wr(R+0x0,4,reg_0_4);",left)
        self.assertIn("PC=0x1001u;",left)
        self.assertIn("PC=0x1002u;",right)
        self.assertNotIn("wr(R+0x0,4,reg_0_4);",right.split("uint8_t T[",1)[0])

    def test_unmodified_legacy_source_is_default_and_has_no_checkpoints(self):
        original,_=generate_region_c(test_region(),cache_count=1)
        explicit,_=generate_region_c(test_region(),cache_count=1,
                                     fault_policy="legacy")
        self.assertEqual(original,explicit)
        self.assertNotIn("PC=0x1001u;",original.split("B_1001: {",1)[1]
                         .split("B_1002: {",1)[0])

    def test_unsupported_fault_policy_fails_closed(self):
        with self.assertRaisesRegex(CFGError,"fault boundary"):
            generate_region_c(test_region(),fault_policy="ignore_faults")


if __name__=="__main__":unittest.main()
