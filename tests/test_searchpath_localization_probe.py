"""Localization evidence tests; none require proprietary game files in CI."""
from __future__ import annotations

import os
import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from searchpath_localization_probe import (  # noqa: E402
    LANGUAGE_TABLE_COUNT, LANGUAGE_TABLE_VA, classify_pkg_name,
    languages_from_pe, analyze,
)
from pe_inspect import PEFormatError  # noqa: E402


class FakePe:
    image_base = 0x00400000

    def __init__(self):
        self.data = bytearray(LANGUAGE_TABLE_COUNT * 8)
        self.names = {}
        labels = ["alfa", "bravo", "charlie", "delta", "echo", "foxtrot", "golf",
                  "hotel", "india", "juliet", "kilo", "lima", "mike", "november"]
        for i in range(LANGUAGE_TABLE_COUNT):
            name_va = 0x0054EC08 + i * 32
            self.names[name_va - self.image_base] = labels[i]
            struct.pack_into("<II", self.data, i * 8, name_va, 0)

    def rva_to_offset(self, rva: int) -> int:
        return rva - (LANGUAGE_TABLE_VA - self.image_base)

    def c_string_at_rva(self, rva: int, max_len: int = 48) -> str:
        return self.names[rva]


class TestLocalization(unittest.TestCase):
    def test_extracts_contiguous_table(self):
        result = languages_from_pe(FakePe())
        self.assertEqual(len(result), 14)
        self.assertEqual(result[4]["index"], 4)
        self.assertEqual(result[4]["language"], "echo")

    def test_rejects_duplicate_labels(self):
        pe = FakePe()
        first = next(iter(pe.names))
        last = list(pe.names)[1]
        pe.names[last] = pe.names[first]
        with self.assertRaisesRegex(PEFormatError, "invalid/duplicate"):
            languages_from_pe(pe)

    def test_rejects_corrupted_dword(self):
        pe = FakePe()
        struct.pack_into("<I", pe.data, 7 * 8 + 4, 12)
        with self.assertRaisesRegex(PEFormatError, "unexpected static"):
            languages_from_pe(pe)

    def test_filename_candidates_do_not_infer_priority(self):
        langs = {"spanish": 4, "english": 0}
        ordinary = classify_pkg_name("main/pakb.pk3", langs)
        localized = classify_pkg_name("LOCALIZED_Spanish_PAK4.PK3", langs)
        unknown = classify_pkg_name("localized_klingon_pak5.pk3", langs)
        other = classify_pkg_name("sp_pak0.pk3", langs)
        self.assertEqual(ordinary, {"name": "main/pakb.pk3", "kind": "plain_candidate", "pak_suffix": "b"})
        self.assertEqual(localized["kind"], "localized_candidate")
        self.assertEqual(localized["language_index"], 4)
        self.assertEqual(unknown["kind"], "unknown_language_candidate")
        self.assertEqual(other["kind"], "unclassified")

    def test_rejects_empty_static_pointer(self):
        pe = FakePe()
        struct.pack_into("<I", pe.data, 0, 0)
        with self.assertRaises(PEFormatError):
            languages_from_pe(pe)

    @unittest.skipUnless(os.getenv("CODRECOMP_ORIGINALS"),
                         "exact PC 1.5 original is optional")
    def test_exact_binary_and_spanish(self):
        result = analyze(Path(os.environ["CODRECOMP_ORIGINALS"]) / "CoDSP.exe",
                         ["localized_spanish_pak4.pk3", "pakb.pk3"])
        self.assertEqual(result["language_count"], 14)
        self.assertEqual(result["languages"][4]["language"], "spanish")
        self.assertEqual(result["filename_candidates"][0]["language_index"], 4)
        self.assertEqual(len(result["fingerprints"]), 7)
        self.assertEqual(result["lookup_language_filter"]["global_value_offset"], 32)


if __name__ == "__main__":
    unittest.main()
