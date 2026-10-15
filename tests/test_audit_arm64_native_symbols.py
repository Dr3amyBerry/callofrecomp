"""Synthetic unit tests for offline AArch64 native symbol-size/opcode auditing."""
from collections import Counter
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools/recomp/diagnostics"))
from audit_arm64_native_symbols import symbol_sizes, mnemonic_histogram, comparison


class ARM64SymbolAuditTests(unittest.TestCase):
    def test_llvm_nm_size_rows_and_ignored_data(self):
        sample = (
            "0000000000000000 0000000000000010 T codsp_chunk_83_spaces\n"
            "0000000000000020 0000000000000008 t local_helper\n"
            "0000000000000050 0000000000000004 D a_data\n"
            "                 U external\n"
        )
        self.assertEqual(symbol_sizes(sample),
                         {"codsp_chunk_83_spaces": 16, "local_helper": 8})
        with self.assertRaises(ValueError):
            symbol_sizes(sample + sample.splitlines()[0] + "\n")

    def test_llvm_objdump_native_symbols(self):
        data = (
            "0000 <some_native_symbol>:\n"
            "       0: mov x0, x1\n"
            "       4: add x0, x0, #1\n"
            "       8: b.ne 0x24\n"
            "      0c: mov x1, x2\n"
        )
        self.assertEqual(mnemonic_histogram(data),
                         Counter({"mov": 2, "add": 1, "b.ne": 1}))

    def test_no_change_is_not_claimed_as_perf_improvement(self):
        freq = Counter({"mov": 2, "cmp": 1, "b.ne": 1})
        result = comparison(16,16,freq,freq.copy())
        self.assertEqual(result["delta_bytes"],0)
        self.assertEqual(result["delta_instructions"],0)
        self.assertEqual(result["opcode_changes"],[])

    def test_detects_removed_arm64_opcode_without_relying_on_byte_offsets(self):
        before = Counter({"and": 1, "add": 1, "mov": 2})
        after = Counter({"add": 1, "mov": 2})
        result = comparison(16,12,before,after)
        self.assertEqual(result["delta_bytes"],-4)
        self.assertEqual(result["delta_instructions"],-1)
        self.assertEqual(result["opcode_changes"],
                         [{"opcode": "and", "delta": -1}])
        with self.assertRaises(ValueError):
            comparison(16,11,before,after)
        with self.assertRaises(ValueError):
            comparison(16,16,Counter(),after)


if __name__ == "__main__":
    unittest.main()
