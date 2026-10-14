"""Function-entry metadata is diagnostic, deterministic and never CPU attribution."""
import json
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase, main, mock
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools/recomp"))
from function_map import build_function_map, scan_pcode_headers, write_function_map
import pcode2c


class FunctionMapTest(TestCase):
    def test_exact_markers_cross_chunk_and_part_boundaries(self):
        insns = [(0x1000, 1), (0x1001, 1), (0x1002, 2),
                 (0x1010, 1), (0x1011, 1)]
        result = build_function_map(insns, [0x1000, 0x1002, 0x1010, 0x9999],
                                    "example", chunk_size=2, parts=2)
        self.assertEqual(result["chunk_count"], 3)
        self.assertEqual(result["matched_function_entry_count"], 3)
        self.assertEqual(result["unmatched_function_entry_count"], 1)
        self.assertEqual(result["chunks_with_multiple_function_entries"], 1)
        self.assertEqual([c["generated_part"] for c in result["chunks"]], [0, 0, 1])
        self.assertEqual(result["chunks"][1]["start_va"], "0x00001002")
        self.assertEqual(result["chunks"][1]["end_va_exclusive"], "0x00001011")
        self.assertEqual(result["chunks"][1]["function_entries_in_chunk"],
                         ["0x00001002", "0x00001010"])
        self.assertEqual(result["chunks"][2]["function_entries_in_chunk"], [])
        self.assertEqual(result["chunks"][2]["preceding_entry_context"], "0x00001010")
        self.assertIsNone(result["functions"][-1]["entry_chunk_index"])

    def test_empty_no_entries_duplicate_and_unsorted_inputs(self):
        self.assertEqual(build_function_map([], [], "empty")["chunks"], [])
        data = build_function_map([(0x11, 1), (0x10, 1)], [0x11, 0x11], "x")
        self.assertEqual(data["matched_function_entry_count"], 1)
        self.assertEqual(data["chunks"][0]["start_va"], "0x00000010")
        self.assertIsNone(data["chunks"][0]["preceding_entry_context"])
        for bad in ([(0x10, 1), (0x10, 2)], [(0x20, 0)], [(2**32-1, 2)]):
            with self.assertRaises(ValueError):
                build_function_map(bad, [], "bad")
        with self.assertRaises(ValueError):
            build_function_map([], [], "bad", chunk_size=0)

    def test_streaming_matches_pcode_parser_and_json_is_stable(self):
        text = ("I 4097 1\nP COPY r:0:4 c:1:4\n"
                "I 4096 1\nP COPY r:4:4 c:2:4\n"
                "F 4096\nF 4097\nF 4100\nU 12 test\n")
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "fixture.pcode"
            path.write_text(text, encoding="utf-8")
            inst, fn = scan_pcode_headers(path)
            parsed, _, original = pcode2c.parse(path)
            self.assertEqual(sorted(inst), [(a, n) for a, n, _ in parsed])
            self.assertEqual(fn, original)
            data = build_function_map(inst, fn, "fixture")
            out = Path(d) / "fixture.json"
            write_function_map(out, data)
            content = out.read_bytes()
            write_function_map(out, data)
            self.assertEqual(content, out.read_bytes())
            self.assertEqual(json.loads(content)["unmatched_function_entry_count"], 1)

    def test_map_cli_rejects_overwriting_input(self):
        import function_map
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "raw.pcode"
            path.write_text("I 4096 1\\nF 4096\\n")
            before = path.read_bytes()
            with mock.patch.object(sys, "argv", ["function_map.py", str(path),
                                                  "--out", str(path)]):
                with mock.patch.object(sys, "stderr"):
                    with self.assertRaises(SystemExit):
                        function_map.main()
            self.assertEqual(path.read_bytes(), before)

    def test_generator_optional_sidecar_does_not_modify_game_code(self):
        pe = SimpleNamespace(imports=lambda: [], exports=lambda: [],
                             image_base=0x1000, size_of_image=0x1000, entry_rva=0)
        pcode = ("I 4096 1\nP COPY r:0:4 c:1:4\n"
                 "I 4097 1\nP COPY r:4:4 c:2:4\nF 4096\nF 4097\n")
        with tempfile.TemporaryDirectory() as d:
            inp, pe_path = Path(d)/"fixture.pcode", Path(d)/"dummy.exe"
            out, sidecar = Path(d)/"out.c", Path(d)/"function_map.json"
            inp.write_text(pcode)
            with mock.patch.object(pcode2c, "PEFile", return_value=pe):
                with mock.patch.object(sys, "argv", ["pcode2c.py", str(inp),
                                                      str(pe_path), "-o", str(out)]):
                    self.assertEqual(pcode2c.main(), 0)
                original_code = out.read_bytes()
                self.assertFalse(sidecar.exists())
                with mock.patch.object(sys, "argv", ["pcode2c.py", str(inp),
                                                      str(pe_path), "-o", str(out),
                                                      "--function-map-out", str(sidecar)]):
                    self.assertEqual(pcode2c.main(), 0)
            self.assertEqual(original_code, out.read_bytes())
            with mock.patch.object(pcode2c, "PEFile", return_value=pe):
                with mock.patch.object(sys, "argv", ["pcode2c.py", str(inp),
                                                      str(pe_path), "-o", str(out),
                                                      "--function-map-out", str(out)]):
                    with mock.patch.object(sys, "stderr"):
                        with self.assertRaises(SystemExit):
                            pcode2c.main()
            self.assertEqual(original_code, out.read_bytes())
            result = json.loads(sidecar.read_text())
            self.assertEqual(result["matched_function_entry_count"], 2)
            self.assertEqual(result["chunks"][0]["function_entries_in_chunk"],
                             ["0x00001000", "0x00001001"])


if __name__ == "__main__":
    main()
