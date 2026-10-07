"""Synthetic and optional exact-binary tests for the startup scan evidence."""
from __future__ import annotations

import os
import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from searchpath_startup_probe import (  # noqa: E402
    SCAN_SIZE, SCAN_VA, EXPECTED_HELPER, decode_scan, analyze,
)


def fake_scan() -> bytes:
    # Synthetic instructions with just the narrow formats used by the probe;
    # this fixture is *not* copied from any original executable.
    raw = bytearray(SCAN_SIZE)
    for at, value in ((1, 0x6A), (3, 0x6A), (8, 0xE8), (16, 0xBE),
                      (21, 0x56), (22, 0x6A), (23, 1), (27, 0xE8),
                      (35, 0x4E), (36, 0x79), (38, 0x5E), (39, 0xC3)):
        raw[at] = value
    struct.pack_into("<I", raw, 17, 13)
    for at in (8, 27):
        struct.pack_into("<i", raw, at + 1, EXPECTED_HELPER - (SCAN_VA + at + 5))
    return bytes(raw)


class TestStartupScan(unittest.TestCase):
    def test_decodes_narrow_scan_with_explicit_bounds(self):
        result = decode_scan(fake_scan())
        self.assertEqual(result["first_call"]["target_va"], EXPECTED_HELPER)
        self.assertEqual(result["first_call"]["observed_immediate_arguments"], [0, 0])
        self.assertEqual(result["indexed_calls"]["index_first"], 13)
        self.assertEqual(result["indexed_calls"]["index_last"], 0)
        self.assertEqual(result["indexed_calls"]["index_count"], 14)

    def test_rejects_wrong_branch_opcode(self):
        data = bytearray(fake_scan())
        data[36] = 0
        with self.assertRaises(ValueError):
            decode_scan(bytes(data))

    def test_rejects_wrong_helper(self):
        data = bytearray(fake_scan())
        data[28] ^= 0x01
        with self.assertRaises(ValueError):
            decode_scan(bytes(data))

    def test_rejects_overwide_loop(self):
        data = bytearray(fake_scan())
        struct.pack_into("<I", data, 17, 0xffffffff)
        with self.assertRaises(ValueError):
            decode_scan(bytes(data))

    @unittest.skipUnless(os.getenv("CODRECOMP_ORIGINALS"),
                         "exact CoD PC 1.5 original is optional")
    def test_original_profile(self):
        report = analyze(Path(os.environ["CODRECOMP_ORIGINALS"]) / "CoDSP.exe")
        self.assertEqual(report["indexed_calls"]["index_count"], 14)
        self.assertEqual(report["scan_va"], SCAN_VA)


if __name__ == "__main__":
    unittest.main()
