"""Synthetic-only strict page-fault state safety tests for CoDSP CFG14.

No original game data or private C/DLL is checked into Git.
"""
from __future__ import annotations
import sys
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools/recomp/diagnostics"))
from audit_cfg_region_fault_state import strict_fault_safety_gate

def state(*,pc="0x0041c017",dirty=None,address_same=True,good=True):
    return {
        "fault_pc":pc,"memory_access":1,"guest_memory_address_same":address_same,
        "dirty_fields_on_fault":[] if dirty is None else dirty,
        "safely_maintains_arch_state":good,
    }

class ExceptionStateGateTests(unittest.TestCase):
    def test_requires_actual_tested_memory_faults(self):
        self.assertFalse(strict_fault_safety_gate([]))

    def test_true_only_when_every_fault_observation_is_clean(self):
        self.assertTrue(strict_fault_safety_gate([
            state(pc="0x0041c017"),state(pc="0x0041c01b")]))
        self.assertFalse(strict_fault_safety_gate([
            state(),state(pc="0x0041c023",dirty=["EDX","PC"],good=False)]))

    def test_mismatching_address_rejected_even_when_arch_registers_match(self):
        self.assertFalse(strict_fault_safety_gate([state(address_same=False)]))

    def test_inconsistent_report_fields_fail_closed(self):
        row=state()
        del row["guest_memory_address_same"]
        self.assertFalse(strict_fault_safety_gate([row]))
        row=state()
        del row["safely_maintains_arch_state"]
        self.assertFalse(strict_fault_safety_gate([row]))
        row=state()
        del row["dirty_fields_on_fault"]
        self.assertFalse(strict_fault_safety_gate([row]))

    def test_status_flag_cannot_override_unflushed_register_evidence(self):
        self.assertFalse(strict_fault_safety_gate([
            state(dirty=["EAX"],good=True)]))

if __name__=="__main__":
    unittest.main()
