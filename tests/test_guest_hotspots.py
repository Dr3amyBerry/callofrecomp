"""Never overattribute guest chunk CPU samples to neighboring Ghidra functions."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools/recomp"))
from function_map import build_function_map
from analyze_guest_hotspots import annotate


class HotspotTest(unittest.TestCase):
    def test_multiple_entries_are_candidates_not_cpu_owners(self):
        mapping = build_function_map([(0x1000, 1), (0x1001, 1),
                                      (0x1002, 1), (0x1003, 1)],
                                     [0x1000, 0x1001, 0x1002],
                                     "synthetic.exe", chunk_size=4)
        log = ("cpu sample: chunk 00001000-00001004 time_us=120 calls=3\n"
               "cpu sample: host libc!foo time_us=90 calls=2\n"
               "cpu sample: chunk 00001000-00001004 time_us=30 calls=1\n")
        result = annotate(log, [mapping])
        self.assertEqual(result["sample_records"], 2)
        self.assertEqual(result["sampled_chunk_count"], 1)
        self.assertEqual(result["chunk_rows_without_unique_map"], 0)
        row = result["hot_chunks"][0]
        self.assertEqual(row["sampled_time_us"], 150)
        self.assertEqual(row["sampled_calls"], 4)
        self.assertEqual(len(row["matches"][0]["function_entries_in_chunk"]), 3)
        self.assertEqual(row["function_cpu_attribution"], "NOT_AVAILABLE")

    def test_missing_or_duplicate_mapping_cannot_claim_unique_chunk(self):
        first = build_function_map([(0x2000, 1)], [0x2000], "one")
        second = build_function_map([(0x2000, 1)], [0x2000], "two")
        log = ("cpu sample: chunk 00002000-00002001 time_us=5 calls=1\n"
               "cpu sample: chunk 00003000-00003001 time_us=10 calls=2\n")
        result = annotate(log, [first, second])
        self.assertEqual(result["chunk_rows_without_unique_map"], 2)
        self.assertFalse(result["hot_chunks"][0]["exact_chunk_match"])
        self.assertEqual(len(result["hot_chunks"][1]["matches"]), 2)
        self.assertFalse(result["hot_chunks"][1]["exact_chunk_match"])
        with self.assertRaises(ValueError):
            annotate(log, [first], top=0)
        with self.assertRaises(ValueError):
            annotate(log, [{"schema_version": 2}], top=1)

    def test_top_sort_and_ignored_non_profile_lines(self):
        data = annotate("cpu sample: chunk 00000010-00000011 time_us=3 calls=1\n"
                        "UNRELATED\n"
                        "cpu sample: chunk 00000020-00000021 time_us=7 calls=1\n",
                        [], top=1)
        self.assertEqual(len(data["hot_chunks"]), 1)
        self.assertEqual(data["hot_chunks"][0]["start_va"], "0x00000020")
        self.assertEqual(data["sampled_chunk_count"], 2)


if __name__ == "__main__":
    unittest.main()
