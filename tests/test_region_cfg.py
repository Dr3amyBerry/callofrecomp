"""Tests for phase14 exact instruction micro-CFG and original-body boundaries.

All synthetic. No original CoD code/assets, saved games, APKs or phone needed.
"""
from pathlib import Path
import sys
import tempfile
import unittest
from copy import deepcopy

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools/recomp"))
from region_cfg import (
    CFGError, Exit, micro_exits, signed_relative,
    extract_function, recover_function_cfg,
)
from diagnostics.analyze_cfg_regions import (
    build_report, validate_paths, verify_inputs, PCODE_SHA256,
)


def r(off=0, sz=4):
    return ("r", off, sz)


def c(value, sz=8):
    return ("c", value, sz)


def m(value, sz=4):
    return ("m", value, sz)


def op(name, result=None, *args):
    return name, result, list(args)


def fixture():
    # PC address order intentionally includes two noncontiguous B ranges and
    # two external call/jump sources; no source is from commercial material.
    insns = [
        (0x0fff, 1, [op("BRANCH", None, m(0x1010))]),
        (0x1000, 1, [op("COPY", r(0), c(5)),
                     op("CBRANCH", None, m(0x1010), r(0)),
                     op("COPY", r(16), c(9))]),
        (0x1001, 1, [op("CALL", None, m(0x2000))]),
        (0x1002, 1, [op("COPY", r(0), r(16))]),
        (0x1010, 1, [op("LOAD", r(4), c(0), r(16)),
                     op("COPY", r(0x206, 1), c(1, 1))]),
        (0x1011, 1, [op("CBRANCH", None, m(0x1013), r(4))]),
        (0x1012, 1, [op("RETURN", None, r(0))]),
        (0x1013, 1, []),  # missing p-code is a risk, never a zero-op fallthrough.
        (0x2000, 1, [op("CALL", None, m(0x1000))]),
    ]
    func_ranges = [
        {"entry_va": "0x00001000", "start_va": "0x00001000",
         "end_va_inclusive": "0x00001002"},
        {"entry_va": "0x00001000", "start_va": "0x00001010",
         "end_va_inclusive": "0x00001013"},
        {"entry_va": "0x00002000", "start_va": "0x00002000",
         "end_va_inclusive": "0x00002000"},
    ]
    mapping = {
        "module": "CoDSP.exe", "schema_version": 2,
        "instruction_count": len(insns),
        "functions": [
            {"entry_va": "0x00001000", "entry_in_translation": True,
             "body_uniquely_owned_instruction_count": 7},
            {"entry_va": "0x00002000", "entry_in_translation": True,
             "body_uniquely_owned_instruction_count": 1},
        ],
        "ghidra_body_ranges": func_ranges,
    }
    return insns, mapping


class MicroControlFlowTests(unittest.TestCase):
    def test_micro_conditional_target_and_fallthrough(self):
        instructions = [
            op("COPY", r(0), c(8)),
            op("CBRANCH", None, c(2), r(0)),
            op("BRANCH", None, m(0x3000)),
            op("COPY", r(8), c(1)),
        ]
        edges, hazards = micro_exits(instructions, 0x2000)
        self.assertEqual(edges, (Exit("direct_jump", 0x3000),
                                 Exit("fallthrough", 0x2000)))
        self.assertEqual(hazards, ())

    def test_local_relative_branch_end_uses_generator_semantics(self):
        self.assertEqual(micro_exits([op("BRANCH", None, c(99))], 0x2222)[0],
                         (Exit("relative_end", 0x2222),))
        self.assertEqual(signed_relative((1 << 64) - 1), -1)
        with self.assertRaises(CFGError):
            signed_relative(1 << 64)

    def test_microcycle_is_explicit_and_does_not_spin(self):
        instructions = [
            op("CBRANCH", None, c(2), r(0)),
            op("BRANCH", None, c((1 << 64) - 1)),
            op("COPY", r(4), c(2)),
        ]
        edges, issues = micro_exits(instructions, 0x2003)
        self.assertIn(Exit("fallthrough", 0x2003), edges)
        self.assertIn("micro_cycle_possible", issues)

    def test_dynamic_or_missing_code_is_never_normal_fallthrough(self):
        self.assertEqual(micro_exits([], 0x4000)[0],
                         (Exit("unknown_missing_pcode"),))
        self.assertEqual(micro_exits([op("CALLIND", None, r(0))], 0x4000)[0],
                         (Exit("dynamic_callind"),))
        self.assertEqual(micro_exits([op("RETURN", None, r(16))], 0x4000)[0],
                         (Exit("dynamic_return"),))
        self.assertEqual(micro_exits([op("BRANCH", None)], 0x4000)[1],
                         ("missing_branch_operand",))
        self.assertIn("invalid_micro_target",
                      micro_exits([op("BRANCH", None, c((1 << 64) - 1))],
                                  0x4000)[1])


class RegionBoundariesTests(unittest.TestCase):
    def test_exact_discontiguous_body_and_side_entries(self):
        insns, mapping = fixture()
        body, ranges, _ = extract_function(insns, mapping, 0x1000)
        self.assertEqual([insn[0] for insn in body],
                         [0x1000, 0x1001, 0x1002, 0x1010,
                          0x1011, 0x1012, 0x1013])
        self.assertEqual(ranges, [(0x1000, 0x1002), (0x1010, 0x1013)])
        cfg = recover_function_cfg(insns, mapping, 0x1000)
        self.assertEqual(cfg["instruction_count"], 7)
        self.assertEqual(sum(b["instruction_count"] for b in cfg["basic_blocks"]), 7)
        self.assertEqual(set(cfg["known_incoming_pc"]), {"0x00001000", "0x00001010"})
        self.assertEqual(cfg["hazards"]["missing_pcode"], 1)
        self.assertGreaterEqual(cfg["hazards"]["unresolved_dynamic_exits"], 2)
        self.assertFalse(cfg["eligible_for_automatic_native_replacement"])
        self.assertTrue(any(x["kind"] == "direct_call"
                            for x in cfg["outgoing_external_edges"]))
        self.assertEqual(cfg["instructions_touching_eflags"]["writes"], 1)

    def test_body_overlap_and_stale_maps_refused(self):
        insns, mapping = fixture()
        broken = deepcopy(mapping)
        broken["ghidra_body_ranges"].append({
            "entry_va": "0x00002000", "start_va": "0x00001010",
            "end_va_inclusive": "0x00001010",
        })
        with self.assertRaisesRegex(CFGError, "ownership"):
            extract_function(insns, broken, 0x1000)
        broken = deepcopy(mapping)
        broken["functions"][0]["body_uniquely_owned_instruction_count"] += 1
        with self.assertRaisesRegex(CFGError, "stale"):
            extract_function(insns, broken, 0x1000)
        broken = deepcopy(mapping)
        broken["schema_version"] = 1
        with self.assertRaisesRegex(CFGError, "B body"):
            extract_function(insns, broken, 0x1000)

    def test_instruction_partially_overlaps_body_is_refused(self):
        insns, mapping = fixture()
        insns = [(a, 2 if a == 0x1002 else length, ops)
                 for a, length, ops in insns]
        with self.assertRaisesRegex(CFGError, "straddles"):
            extract_function(insns, mapping, 0x1000)

    def test_duplicate_pcs_and_unknown_entry_refused(self):
        insns, mapping = fixture()
        with self.assertRaisesRegex(CFGError, "unique"):
            extract_function([*insns, insns[0]], mapping, 0x1000)
        with self.assertRaisesRegex(CFGError, "not a verified"):
            extract_function(insns, mapping, 0x1234)


class DiagnosticsSafetyTests(unittest.TestCase):
    def test_private_paths_required_without_overwriting(self):
        with tempfile.TemporaryDirectory() as folder:
            work = Path(folder)
            private = work / "recomp_out"
            private.mkdir()
            local = work / ".local" / "profiles"
            local.mkdir(parents=True)
            pcode = private / "codsp.pcode"
            mapping = private / "codsp_function_map_v2.json"
            pcode.write_text("test")
            mapping.write_text("test")
            output = local / "new.json"
            validate_paths(pcode, mapping, output, work)
            output.write_text("old")
            with self.assertRaises(ValueError):
                validate_paths(pcode, mapping, output, work)
            with self.assertRaisesRegex(ValueError, "recomp_out"):
                validate_paths(pcode, mapping, work / "docs/report.json", work)
            with self.assertRaisesRegex(ValueError, "SHA-256"):
                verify_inputs(pcode, mapping)

    def test_report_schema_and_no_duplicate_entries(self):
        insns, mapping = fixture()
        report = build_report(insns, mapping, (0x1000,), "a" * 64, "b" * 64)
        self.assertEqual(report["schema"], "callofrecomp-phase14-cfg-v1")
        self.assertEqual(len(report["summary"]), 1)
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            build_report(insns, mapping, (0x1000, 0x1000), "a" * 64, "b" * 64)


if __name__ == "__main__":
    unittest.main()
