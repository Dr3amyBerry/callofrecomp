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


    def test_body_ranges_are_noncontiguous_and_not_inferred_from_next_entry(self):
        from function_map import scan_pcode_provenance
        # 1000 is discontiguous: there is no inferred ownership of 1002/1003.
        ins = [(0x1000, 1), (0x1001, 1), (0x1002, 1), (0x1003, 1),
               (0x1004, 1), (0x1005, 1), (0x1006, 1)]
        bodies = [(0x1000, 0x1000, 0x1001), (0x1000, 0x1005, 0x1006),
                  (0x1004, 0x1003, 0x1004), (0x1004, 0x1006, 0x1006)]
        mapping = build_function_map(ins, [0x1000, 0x1004], "synthetic.exe",
                                     chunk_size=3, parts=2, function_bodies=bodies)
        self.assertEqual(mapping["schema_version"], 2)
        self.assertEqual(mapping["ghidra_body_range_count"], 4)
        self.assertEqual(mapping["body_uniquely_owned_instruction_count"], 5)
        self.assertEqual(mapping["body_unmapped_instruction_count"], 1)  # 1002
        self.assertEqual(mapping["body_ambiguous_instruction_count"], 1)  # 1006
        self.assertEqual([c["body_unmapped_instructions"] for c in mapping["chunks"]],
                         [1, 0, 0])
        self.assertEqual([c["body_ambiguous_instructions"] for c in mapping["chunks"]],
                         [0, 0, 1])
        self.assertEqual(mapping["chunks"][0]["body_function_instruction_counts"],
                         [{"entry_va": "0x00001000", "instruction_count": 2}])
        self.assertEqual(mapping["chunks"][1]["body_function_instruction_counts"],
                         [{"entry_va": "0x00001000", "instruction_count": 1},
                          {"entry_va": "0x00001004", "instruction_count": 2}])
        self.assertEqual(mapping["functions"][0]["body_uniquely_owned_instruction_count"], 3)
        self.assertEqual(mapping["functions"][1]["body_uniquely_owned_instruction_count"], 2)
        with tempfile.TemporaryDirectory() as temp:
            file = Path(temp) / "with_b.pcode"
            file.write_text("U 7 FSUB\nF 4096\nF 4100\n"
                            "B 4096 4096 4097\nB 4096 4101 4102\n"
                            "B 4100 4099 4100\nB 4100 4102 4102\n"
                            "I 4096 1\nP COPY r:0:4 c:1:4\nI 4100 1\n")
            headers, entries, ranges = scan_pcode_provenance(file)
            self.assertEqual(headers, [(0x1000, 1), (0x1004, 1)])
            self.assertEqual(entries, [0x1000, 0x1004])
            self.assertEqual(len(ranges), 4)
            # Generator must ignore B records exactly like old raw p-code.
            self.assertEqual([a for a, _, _ in pcode2c.parse(file)[0]],
                             [0x1000, 0x1004])

    def test_body_range_validation_and_crossed_instruction(self):
        for bodies in ([(0x2000, 0x2000, 0x1fff)],
                       [(0x3000, 0x2000, 0x2001)],
                       [(0x2000, 0x2000, 2**32)]):
            with self.subTest(bodies=bodies):
                with self.assertRaises(ValueError):
                    build_function_map([(0x2000, 2)], [0x2000],
                                       "x", function_bodies=bodies)
        # A body ending at 0x2000 cannot own a 2-byte instruction.
        result = build_function_map([(0x2000, 2)], [0x2000], "x",
                                    function_bodies=[(0x2000, 0x2000, 0x2000)])
        self.assertEqual(result["body_unmapped_instruction_count"], 1)
        self.assertEqual(result["body_uniquely_owned_instruction_count"], 0)

    def test_opt_in_generator_uses_B_without_changing_generated_C(self):
        pe = SimpleNamespace(imports=lambda: [], exports=lambda: [],
                             image_base=0x1000, size_of_image=0x1000, entry_rva=0)
        with tempfile.TemporaryDirectory() as d:
            inp, exe = Path(d) / "pcode.pcode", Path(d) / "fake.exe"
            out, sidecar = Path(d) / "guest.c", Path(d) / "function_map.json"
            inp.write_text("I 4096 1\nP COPY r:0:4 c:1:4\n"
                           "I 4097 1\nP COPY r:4:4 c:2:4\n"
                           "F 4096\nF 4097\nB 4096 4096 4096\nB 4097 4097 4097\n")
            with mock.patch.object(pcode2c, "PEFile", return_value=pe):
                with mock.patch.object(sys, "argv", ["pcode2c.py", str(inp),
                                                      str(exe), "-o", str(out)]):
                    self.assertEqual(pcode2c.main(), 0)
                unchanged = out.read_bytes()
                with mock.patch.object(sys, "argv", ["pcode2c.py", str(inp),
                                                      str(exe), "-o", str(out),
                                                      "--function-map-out", str(sidecar)]):
                    self.assertEqual(pcode2c.main(), 0)
            self.assertEqual(unchanged, out.read_bytes())
            report = json.loads(sidecar.read_text())
            self.assertEqual(report["schema_version"], 2)
            self.assertEqual(report["body_uniquely_owned_instruction_count"], 2)


    def test_separate_saved_ghidra_body_export_is_checked_against_F(self):
        import function_map
        with tempfile.TemporaryDirectory() as temp:
            raw, bodies, out = (Path(temp)/name for name in
                                ("raw.pcode", "bodies.txt", "report.json"))
            raw.write_text("F 4096\nF 4098\nI 4096 1\nI 4098 1\n")
            bodies.write_text("F 4096\nF 4098\n"
                              "B 4096 4096 4096\nB 4098 4098 4098\n")
            with mock.patch.object(sys, "argv", ["function_map.py", str(raw),
                                                  "--body-records", str(bodies),
                                                  "--out", str(out)]):
                self.assertEqual(function_map.main(), 0)
            data = json.loads(out.read_text())
            self.assertEqual(data["schema_version"], 2)
            self.assertEqual(data["body_uniquely_owned_instruction_count"], 2)
            self.assertEqual(len(data["ghidra_body_ranges"]), 2)
            # A Ghidra project analyzed against another file must be refused.
            bodies.write_text("F 4096\nB 4096 4096 4096\n")
            with mock.patch.object(sys, "argv", ["function_map.py", str(raw),
                                                  "--body-records", str(bodies),
                                                  "--out", str(out)]):
                with mock.patch.object(sys, "stderr"):
                    with self.assertRaises(SystemExit):
                        function_map.main()
            bodies.write_text("F 4096\nF 4098\n")
            with mock.patch.object(sys, "argv", ["function_map.py", str(raw),
                                                  "--body-records", str(bodies),
                                                  "--out", str(out)]):
                with mock.patch.object(sys, "stderr"):
                    with self.assertRaises(SystemExit):
                        function_map.main()
            bodies.write_text("F 4096\nF 4098\n"
                              "I 4099 1\nB 4096 4096 4096\n")
            with mock.patch.object(sys, "argv", ["function_map.py", str(raw),
                                                  "--body-records", str(bodies),
                                                  "--out", str(out)]):
                with mock.patch.object(sys, "stderr"):
                    with self.assertRaises(SystemExit):
                        function_map.main()
            self.assertEqual(data, json.loads(out.read_text()))

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
