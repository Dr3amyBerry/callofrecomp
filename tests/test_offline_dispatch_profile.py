"""Deterministic unit tests: native offline profiling summary and identity checks."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools/recomp/diagnostics"))
from offline_dispatch_profile import (parse_elf_build_id, recorded_build_id,
                                     symbol_range, aggregate_annotations)


class OfflineDispatchProfileTests(unittest.TestCase):
    def test_elf_build_id_normalization_and_missing(self):
        example = "note: Build ID: " + "ab" * 20 + "\n"
        self.assertEqual(parse_elf_build_id(example), "ab" * 20)
        with self.assertRaises(ValueError):
            parse_elf_build_id("no build id")
        with self.assertRaises(ValueError):
            parse_elf_build_id(example * 2)

    def test_exact_recorded_library_id(self):
        self.assertEqual(recorded_build_id({
            "/data/app/lib/libmain.so": "0x" + "a1" * 20,
            "/data/app/lib/libGL.so": "0x" + "b2" * 20}), "a1" * 20)
        with self.assertRaises(ValueError):
            recorded_build_id({"/a/libmain.so": "0x" + "a1" * 20,
                               "/b/libmain.so": "0x" + "a1" * 20})
        with self.assertRaises(ValueError):
            recorded_build_id({"/data/lib/libmain.so": "invalid"})

    def test_exact_nonempty_elf_symbol(self):
        text = ("00000000004f4724 00000000000007c8 T guest_run\n"
                "00000000004f5500 0000000000000000 T unused\n"
                "00000000004f5000 0000000000000020 t local\n")
        self.assertEqual(symbol_range(text, "guest_run"), (0x4f4724, 0x4f4eec))
        with self.assertRaises(ValueError):
            symbol_range(text, "unused")
        with self.assertRaises(ValueError):
            symbol_range(text + text, "guest_run")

    def test_aggregate_counts_avoid_private_paths(self):
        rows = [
            ("guest_run", "C:\\source\\runtime\\guest.c:777", 8),
            ("dispatch_index_find", "C:/project/dispatch_index.h:18", 5),
            ("dispatch_index_find", "/private/game/dispatch_index.h:23", 9),
            ("codsp_hot_transform_5061b0", "/private/hot_x87_transform.h:56", 3),
        ]
        data = aggregate_annotations(rows, 100)
        self.assertEqual(data["symbol_samples"], 25)
        self.assertEqual(data["symbol_process_share_pct"], 25.)
        self.assertEqual(data["inline_function_counts"][0],
                         {"name": "dispatch_index_find", "samples": 14})
        self.assertNotIn("private", str(data))
        self.assertEqual(data["source_file_counts"][0],
                         {"name": "dispatch_index.h", "samples": 14})
        with self.assertRaises(ValueError):
            aggregate_annotations(rows, 20)
        with self.assertRaises(ValueError):
            aggregate_annotations([("guest_run", "guest.c:8", 0)], 1)

if __name__ == "__main__":
    unittest.main()
