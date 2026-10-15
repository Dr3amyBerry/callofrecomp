"""Synthetic-only CPU cost triage; never loads private PE or perf data."""
from __future__ import annotations

from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools/recomp/diagnostics"))
from prioritize_profiled_cpu import (
    compare_profiles, profile_counts, function_complexity
)


def capture(samples,*,total=1000,host=800,entry="0x0042b0a0"):
    return {
        "total_cpu_samples":total,
        "libmain_cpu_samples":host,
        "resolved_guest":{
            "native_samples_total":host,
            "guest_label_resolved_samples":600,
            "unique_ghidra_body_samples":500,
            "top_body_function_samples":[
                {"module":"codsp","entry_va":entry,"samples":samples},
                {"module":"uix86","entry_va":"0x30001000","samples":10},
            ],
        },
    }


class OriginalNativeCPUProfileTriage(unittest.TestCase):
    def test_two_captures_and_illustrative_amdahl_are_precise(self):
        report=compare_profiles(capture(100),capture(80),
                                {0x0042B0A0:"integer_geometry_state"},
                                reference_cpu_ms=40,target_cpu_ms=1000/60)
        row=report["ranked_original_function_sample_targets"][0]
        self.assertEqual(row["native_samples_A1"],100)
        self.assertEqual(row["native_samples_A2"],80)
        self.assertEqual(row["process_sample_pct_A1"],10.0)
        self.assertEqual(row["process_sample_pct_A2"],8.0)
        self.assertEqual(report["overall_required_CPU_ms_reduction_pct_if_CPU_bound"],58.333)
        upper=report["selected_8_function_combined_sample_share"][0]
        self.assertEqual(upper["illustrative_Amdahl_ceiling_if_these_sampled_contributions_were_exclusive"]
                         ["remaining_cpu_ms_per_frame_at_100pct_elimination"],36.0)
        self.assertIn("NOT exclusive CPU time",report["warning"])

    def test_no_double_count_from_unrelated_modules(self):
        self.assertEqual(profile_counts(capture(60)),{0x42B0A0:60})

    def test_reject_missing_required_target_from_truncated_profile(self):
        with self.assertRaisesRegex(ValueError,"truncated"):
            compare_profiles(capture(20),capture(20),
                             {0x0041B8F0:"geometry"})

    def test_reject_ambiguous_function_labels(self):
        a=capture(50)
        a["resolved_guest"]["top_body_function_samples"].append(
            {"module":"codsp","entry_va":"0x0042b0a0","samples":99})
        with self.assertRaisesRegex(ValueError,"ambiguous"):
            profile_counts(a)

    def test_reject_unsupported_sampling_populations(self):
        a=capture(50)
        a["libmain_cpu_samples"]=1001
        with self.assertRaisesRegex(ValueError,"exceed"):
            compare_profiles(a,capture(30),{0x42B0A0:"state"})
        a=capture(50)
        a["resolved_guest"]["unique_ghidra_body_samples"]=601
        with self.assertRaisesRegex(ValueError,"unique labels"):
            compare_profiles(a,capture(30),{0x42B0A0:"state"})

    def test_reject_impossible_time_budget(self):
        with self.assertRaises(ValueError):
            compare_profiles(capture(50),capture(30),
                             {0x42B0A0:"state"},
                             reference_cpu_ms=16,target_cpu_ms=17)

    def test_structural_opcode_counts_no_x87_or_memory_assumption(self):
        instructions=[
            (0x1000,1,[("COPY",("r",0,4),[("c",1,4)])]),
            (0x1001,1,[("LOAD",("r",4,4),[("c",0x1a1,8),("r",0,4)]),
                       ("POPCOUNT",("u",4,1),[("u",8,4)])]),
            (0x1002,1,[("COPY",("r",0x1000,10),[("r",0x1010,10)]),
                       ("FLOAT_ADD",("r",0x1000,10),
                        [("r",0x1000,10),("r",0x1010,10)])]),
        ]
        m={"schema_version":2,
           "functions":[{"entry_va":"0x00001000",
                         "entry_in_translation":True,
                         "body_uniquely_owned_instruction_count":3}],
           "ghidra_body_ranges":[{"entry_va":"0x00001000",
                                   "start_va":"0x00001000",
                                   "end_va_inclusive":"0x00001002"}]}
        info=function_complexity(instructions,m,0x1000)
        self.assertEqual(info["pcode_mem_LOAD_ops"],1)
        self.assertEqual(info["pcode_POPCOUNT_ops"],1)
        self.assertEqual(info["pcode_FLOAT_operators"],1)
        self.assertEqual(info["pcode_x87_touching_original_insns"],1)
        self.assertFalse(info["integer_only_no_x87_body"])


if __name__=="__main__":
    unittest.main()
