"""Offline native-PC line samples are hints, not exclusive guest function CPU."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools/recomp"))
from function_map import build_function_map
from resolve_guest_samples import (
    parse_native_pcs, parse_resolved_samples, resolve_native_samples,
    resolve_source_lines, symbolize_native_pcs,
)


class ResolveGuestSamplesTest(unittest.TestCase):
    def test_line_mapping_never_leaks_across_dispatcher_or_chunks(self):
        example = """// generated
void codsp_chunk_0(void) {
 goto dyn;
L_1000:
 statement();
 L_1000_2:;
 next_step();
L_1002:
 statement();
dyn:
 switch (PC) {}
}
void codsp_chunk_1(void) {
 goto dyn;
L_1010:
 statement();
dyn:
 switch (PC) {}
}
static const int chunks[] = {1};
"""
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp) / "codsp_recomp_p0.c"
            p.write_text(example)
            expected = {
                3: None, 4: 0x1000, 5: 0x1000, 6: 0x1000,
                7: 0x1000, 8: 0x1002, 9: 0x1002, 10: None,
                12: None, 13: None, 14: None, 15: 0x1010,
                16: 0x1010, 17: None, 20: None, 24: None,
            }
            actual = resolve_source_lines(p, set(expected))
            self.assertEqual(actual, expected)
            with self.assertRaises(ValueError):
                resolve_source_lines(p, {0})

    def test_discontiguous_unique_shared_and_missing_body_attribution(self):
        src = """void codsp_chunk_0(void) {
 goto dyn;
L_1000:
 op();
L_1001:
 op();
L_1002:
 op();
L_1003:
 op();
dyn:
 switch (PC) {}
}
"""
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "codsp_recomp_p0.c"
            path.write_text(src)
            data = build_function_map(
                [(0x1000, 1), (0x1001, 1), (0x1002, 1), (0x1003, 1)],
                [0x1000, 0x1002], "CoDSP.exe",
                function_bodies=[(0x1000, 0x1000, 0x1000),
                                 (0x1000, 0x1003, 0x1003),
                                 (0x1002, 0x1002, 0x1003)])
            self.assertEqual(data["schema_version"], 2)
            self.assertEqual(len(data["ghidra_body_ranges"]), 3)
            rows = [
                ("codsp_recomp_p0.c", 3, 10),   # 1000: unique F1000
                ("codsp_recomp_p0.c", 5, 20),   # 1001: no body
                ("codsp_recomp_p0.c", 7, 30),   # 1002: unique F1002
                ("codsp_recomp_p0.c", 9, 40),   # 1003: both F1000 + F1002
                ("codsp_recomp_p0.c", 11, 50),  # dyn: no PC
                ("unknown.c", 1, 60),          # unrelated source
            ]
            report = resolve_native_samples(rows, [path], [data])
            self.assertEqual(report["native_samples_total"], 210)
            self.assertEqual(report["guest_label_resolved_samples"], 100)
            self.assertEqual(report["unresolved_source_samples"], 110)
            self.assertEqual(report["unique_ghidra_body_samples"], 40)
            self.assertEqual(report["ambiguous_ghidra_body_samples"], 40)
            self.assertEqual(report["unowned_ghidra_body_samples"], 20)
            self.assertEqual(report["functions_with_unique_samples"], 2)
            self.assertEqual(report["top_body_function_samples"], [
                {"module": "codsp", "entry_va": "0x00001002", "samples": 30},
                {"module": "codsp", "entry_va": "0x00001000", "samples": 10},
            ])
            # Legacy v1 entry marker maps lack B ownership data.
            old = build_function_map([(0x1000, 1)], [0x1000], "CoDSP.exe")
            legacy = resolve_native_samples(rows, [path], [old])
            self.assertEqual(legacy["unique_ghidra_body_samples"], 0)
            self.assertEqual(legacy["unowned_ghidra_body_samples"], 100)

    def test_tsv_strict_and_windows_paths(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "resolved.tsv"
            path.write_text("source_file\tsource_line\tsamples\n"
                            "C:\\private\\codsp_recomp_p10.c\t84\t17\n"
                            "/local/cgamex86_recomp_p2.c\t3\t4\n")
            self.assertEqual(parse_resolved_samples(path),
                             [("codsp_recomp_p10.c", 84, 17),
                              ("cgamex86_recomp_p2.c", 3, 4)])
            for bad in ("source_file\tsource_line\tsamples\nbad\t0\t2\n",
                        "bad\t3\t0\n", "bad\tA\t1\n", "bad\t1\n"):
                path.write_text(bad)
                with self.assertRaises(ValueError):
                    parse_resolved_samples(path)


    def test_native_elf_pc_normalization_and_batched_addr2line(self):
        with tempfile.TemporaryDirectory() as temp:
            tsv = Path(temp) / "native.tsv"
            elf = Path(temp) / "libmain.so"
            sym = Path(temp) / "llvm-addr2line.exe"
            tsv.write_text("elf_pc\tsamples\n0x1000\t4\n0x2000\t9\n0x1000\t3\n")
            elf.write_bytes(b"test-only")
            sym.write_bytes(b"test-only")
            rows = parse_native_pcs(tsv)
            self.assertEqual(rows, [(0x1000, 4), (0x2000, 9), (0x1000, 3)])
            with mock.patch("resolve_guest_samples.subprocess.run") as run:
                run.return_value = SimpleNamespace(
                    stdout="0x1000\nrd\nC:/runtime/recomp_rt.h:18\n"
                           "codsp_chunk_207_spaces\nC:\\code\\codsp_recomp_p10.c:123\n"
                           "0x2000\nmemcpy\nC:/ndk/string.h:55\n"
                           "codsp_chunk_207_spaces\nC:/recomp_out/codsp_recomp_p10.c:0\n")
                translated = symbolize_native_pcs(rows, elf, sym)
                self.assertEqual(run.call_count, 1)
                self.assertEqual(run.call_args.args[0][-2:], ["0x1000", "0x2000"])
                self.assertIn("-i", run.call_args.args[0])
                self.assertIn("-a", run.call_args.args[0])
            self.assertEqual(translated, [
                ("codsp_recomp_p10.c", 123, 4),
                ("(unresolved)", 1, 9),
                ("codsp_recomp_p10.c", 123, 3),
            ])
            for invalid in ("0xdeadbeef\n", "1000\t2\n", "0x1000\t0\n",
                            "0x1000\t-1\n", "0x10000000000000000\t1\n"):
                tsv.write_text(invalid)
                with self.assertRaises(ValueError):
                    parse_native_pcs(tsv)

    def test_symbolizer_rejects_incomplete_or_missing_outputs(self):
        with tempfile.TemporaryDirectory() as temp:
            elf = Path(temp) / "libmain.so"
            sym = Path(temp) / "llvm-addr2line.exe"
            elf.write_bytes(b"synthetic")
            sym.write_bytes(b"synthetic")
            with self.assertRaises(ValueError):
                symbolize_native_pcs([(0x1000, 1)], elf, Path(temp) / "missing")
            with mock.patch("resolve_guest_samples.subprocess.run") as run:
                run.return_value = SimpleNamespace(stdout="")
                with self.assertRaises(ValueError):
                    symbolize_native_pcs([(0x1000, 1)], elf, sym)
                run.return_value = SimpleNamespace(stdout="0x1000\nfunction\n")
                with self.assertRaises(ValueError):
                    symbolize_native_pcs([(0x1000, 1)], elf, sym)

    def test_ambiguous_sources_and_maps_fail_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            file = Path(temp) / "codsp_recomp_p0.c"
            file.write_text("L_1000:\n call();\n")
            rows = [("codsp_recomp_p0.c", 1, 1)]
            with self.assertRaises(ValueError):
                resolve_native_samples(rows, [file, file], [])
            map1 = build_function_map([(0x1000, 1)], [0x1000], "CoDSP.exe")
            with self.assertRaises(ValueError):
                resolve_native_samples(rows, [file], [map1, map1])
            with self.assertRaises(ValueError):
                resolve_native_samples(rows, [file], [], top=0)


if __name__ == "__main__":
    unittest.main()
