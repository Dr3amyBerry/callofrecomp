"""Synthetic wrapper-provenance tests; proprietary game binaries are optional."""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from module_wrapper_probe import decode_instructions, recover_push_provenance, inspect
from pe_inspect import PEFile


class TestWrapperProvenance(unittest.TestCase):
    def test_three_register_arguments(self):
        asm = (
            "20042840: 50 push eax\n"
            "20042841: 51 push ecx\n"
            "20042842: 52 push edx\n"
            "20042843: 6a 15 push 0x15\n"
            "20042845: ff 15 34 48 0a 20 call DWORD PTR ds:0x200a4834\n"
        )
        report = recover_push_provenance(
            decode_instructions(asm, 0x20042840, 0x2004284B), 0x200A4834, 21
        )
        self.assertEqual(report["argument_origins"], ["edx", "ecx", "eax"])
        self.assertEqual(report["argument_words_pushed"], 3)

    def test_caller_stack_argument_and_saved_register(self):
        asm = (
            "20042980: 50 push eax\n"
            "20042981: 8b 44 24 08 mov eax,DWORD PTR [esp+0x8]\n"
            "20042985: 51 push ecx\n"
            "20042986: 52 push edx\n"
            "20042987: 50 push eax\n"
            "20042988: 6a 28 push 0x28\n"
            "2004298a: ff 15 34 48 0a 20 call DWORD PTR ds:0x200a4834\n"
        )
        report = recover_push_provenance(
            decode_instructions(asm, 0x20042980, 0x20042990), 0x200A4834, 40
        )
        self.assertEqual(
            report["argument_origins"],
            ["stack_arg_0", "edx", "ecx", "eax"],
        )

    def test_command_mismatch_fails_closed(self):
        asm = (
            "20042843: 6a 16 push 0x16\n"
            "20042845: ff 15 34 48 0a 20 call DWORD PTR ds:0x200a4834\n"
        )
        with self.assertRaisesRegex(ValueError, "syscall ID"):
            recover_push_provenance(
                decode_instructions(asm, 0x20042843, 0x2004284B), 0x200A4834, 21
            )

    def test_unknown_stack_mutation_fails_closed(self):
        instructions = [
            {"opcode": "sub", "operands": "esp,0x4", "va": 1},
            {"opcode": "push", "operands": "0x15", "va": 2},
            {"opcode": "call", "operands": "DWORD PTR ds:0x200a4834", "va": 3},
        ]
        with self.assertRaisesRegex(ValueError, "unsupported"):
            recover_push_provenance(instructions, 0x200A4834, 21)

    @unittest.skipUnless(
        os.getenv("CODRECOMP_ORIGINALS"),
        "set CODRECOMP_ORIGINALS to run against the exact CoD 1.5 input",
    )
    def test_original_dll_wrapper_map(self):
        import hashlib
        pe = PEFile(Path(os.environ["CODRECOMP_ORIGINALS"]) / "gamex86.dll")
        expected_sha256 = "27930aa3f663d0af39a90e6956c980be1e599e0f0c98191a9fb7eaba61481577"
        self.assertEqual(hashlib.sha256(pe.data).hexdigest(), expected_sha256)
        report = inspect(pe, [21, 22, 23, 36, 37, 40, 41])
        expected = {
            21: (0x20042840, ["edx", "ecx", "eax"]),
            22: (0x20042850, ["edx", "ecx", "eax"]),
            23: (0x20042860, ["edx", "ecx", "eax"]),
            36: (0x20042940, ["ecx", "eax"]),
            37: (0x20042950, ["eax"]),
            40: (0x20042980, ["stack_arg_0", "edx", "ecx", "eax"]),
            41: (0x200429A0, ["ecx", "eax"]),
        }
        for item in report["cases"]:
            with self.subTest(id=item["id"]):
                va, origins = expected[item["id"]]
                self.assertEqual(item["wrapper_va"], va)
                self.assertEqual(item["argument_origins"], origins)


if __name__ == "__main__":
    unittest.main()
