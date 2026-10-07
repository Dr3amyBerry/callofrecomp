"""Synthetic fixtures for bounded disassembly ABI signatures; no game data needed."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from syscall_signature_probe import parse_asm  # noqa: E402


class TestSignatureProbe(unittest.TestCase):
    def test_direct_slots_and_forced_zero(self):
        asm = """
  44a49f: 8b 4d 0c        mov    ecx,DWORD PTR [ebp+0xc]
  44a4a2: 8b 55 08        mov    edx,DWORD PTR [ebp+0x8]
  44a4a5: 8b 45 04        mov    eax,DWORD PTR [ebp+0x4]
  44a4ab: e8 60 8b fd ff  call   0x423010
  44a4b6: 33 c0           xor    eax,eax
  44a4b9: c3              ret
"""
        result = parse_asm(asm, 0x44a49f, 0x44a4ba)
        self.assertEqual(result["direct_arg_indices"], [0, 1, 2])
        self.assertEqual(result["direct_arg_count_lower_bound"], 3)
        self.assertEqual(result["return_shape"], "forced_zero_eax")

    def test_tail_jump_and_no_direct_slots(self):
        result = parse_asm("  44a503: e9 f8 6a fb ff  jmp  0x401000\n", 0x44a503, 0x44a508)
        self.assertEqual(result["direct_arg_indices"], [])
        self.assertEqual(result["return_shape"], "tail_jump_delegated")

    def test_preserved_eax_is_not_called_return_type(self):
        result = parse_asm(
            "  44a486: 8b 45 04 mov eax,DWORD PTR [ebp+0x4]\n"
            "  44a492: e8 39 bb fd ff call 0x425fd0\n"
            "  44a49e: c3 ret\n", 0x44a486, 0x44a49f)
        self.assertEqual(result["return_shape"], "eax_not_forced_zero")

    def test_command_word_not_user_argument(self):
        result = parse_asm(
            "  44a306: 8b 45 00 mov eax,DWORD PTR [ebp+0x0]\n"
            "  44a30a: c3 ret\n", 0x44a306, 0x44a30b)
        self.assertEqual(result["direct_arg_indices"], [])

    def test_refuses_empty_window(self):
        with self.assertRaises(ValueError):
            parse_asm("  44a486: c3 ret\n", 0x44a500, 0x44a510)


if __name__ == "__main__":
    unittest.main()
