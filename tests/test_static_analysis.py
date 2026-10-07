"""Offline tests for PE32 and the narrow Call of Duty VM probe.

CI uses synthetic inputs only. Set CODRECOMP_ORIGINALS to run the same
assertions against a legally held local copy of the exact 1.5 binaries.
"""
from __future__ import annotations

import hashlib
import os
import struct
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from pe_inspect import PEFile, PEFormatError, Section  # noqa: E402
from vm_abi_probe import (  # noqa: E402
    _find_dispatch_limit, recover_dllentry_callback,
    recover_syscall_sites, recover_vm_dispatch,
)

BASELINE_SHA256 = {
    "CoDSP.exe": "c755c7da411c87039ade462a2299402c3c4ca5c4fc4f1ae5cea6e25b05c69f47",
    "gamex86.dll": "27930aa3f663d0af39a90e6956c980be1e599e0f0c98191a9fb7eaba61481577",
    "cgamex86.dll": "6e51c61f3780654cbaecdef149810ccf3ab665aaeafa5ae75a13f714abc0f29b",
    "uix86.dll": "dd0738043c287a923357afe53bf2084fda8dd121ece20fcd57828bf5d8c68a4e",
}


def make_synthetic_pe() -> bytes:
    """Small valid PE32 with a backed executable section and no imports/exports."""
    b = bytearray(0x600)
    b[:2] = b"MZ"
    struct.pack_into("<I", b, 0x3C, 0x80)
    b[0x80:0x84] = b"PE\0\0"
    coff = 0x84
    struct.pack_into("<HHIIIHH", b, coff, 0x14C, 1, 0, 0, 0, 224, 0x0102)
    opt = coff + 20
    struct.pack_into("<H", b, opt, 0x10B)
    for offset, value in [
        (16, 0x1000), (28, 0x400000), (32, 0x1000),
        (36, 0x200), (56, 0x2000), (60, 0x200), (92, 16),
    ]:
        struct.pack_into("<I", b, opt + offset, value)
    struct.pack_into("<H", b, opt + 68, 2)
    struct.pack_into(
        "<8sIIIIIIHHI", b, opt + 224, b".text\0\0\0",
        0x300, 0x1000, 0x200, 0x200, 0, 0, 0, 0, 0x60000020,
    )
    return bytes(b)


class TestPe32(unittest.TestCase):
    def test_headers_and_sections(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "mock.exe"
            p.write_bytes(make_synthetic_pe())
            pe = PEFile(p)
            self.assertEqual(pe.image_base, 0x400000)
            self.assertEqual(pe.machine, 0x14C)
            self.assertEqual(pe.rva_to_offset(0x1000), 0x200)
            self.assertEqual(pe.rva_to_offset(0x11FF), 0x3FF)
            self.assertEqual(pe.imports(), [])
            self.assertEqual(pe.exports(), [])
            self.assertEqual(pe.report()["entry_point"]["va"], 0x401000)
            with self.assertRaises(PEFormatError):
                pe.rva_to_offset(0x1200)  # virtual but not file-backed
            with self.assertRaises(PEFormatError):
                pe.rva_to_offset(0x5000)

    def test_bad_signatures(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "mock.exe"
            p.write_bytes(b"X" * 512)
            with self.assertRaises(PEFormatError):
                PEFile(p)
            p.write_bytes(b"MZ" + b"\0" * 62)
            with self.assertRaises(PEFormatError):
                PEFile(p)

    def test_terminal_ascii_string(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "mock.exe"
            b = bytearray(make_synthetic_pe())
            b[-7:] = b"UNENDED"
            p.write_bytes(b)
            self.assertIn((len(b) - 7, "UNENDED"), list(PEFile(p).ascii_strings(7)))


class TestVmAbi(unittest.TestCase):
    def test_command_limit_encoding(self):
        self.assertEqual(_find_dispatch_limit(b"\x90\x83\xF8\x18\x77\x03"), 24)
        self.assertEqual(_find_dispatch_limit(b"\x90\x3D\x30\x01\x00\x00"), 304)
        self.assertIsNone(_find_dispatch_limit(b"\x90\x90\x90"))

    def test_immediate_syscalls_and_unresolved_sites(self):
        slot = 0x20102030
        call = b"\xFF\x15" + struct.pack("<I", slot)
        raw = (
            b"\x6A\x05" + call + b"\x90" +
            b"\x68\xC8\x00\x00\x00" + call + b"\x90\x90" + call
        )
        fake = SimpleNamespace(
            data=raw, image_base=0x20000000,
            sections=[Section(".text", len(raw), 0x1000, len(raw), 0, 0x60000020)],
        )
        report = recover_syscall_sites(fake, slot)
        self.assertEqual(report["indirect_call_count"], 3)
        self.assertEqual(report["resolved_command_count"], 2)
        self.assertEqual([entry["command"] for entry in report["commands"]], [5, 200])
        self.assertEqual(report["unresolved_call_rvas"], [0x1016])
        self.assertEqual(report["sites"][0]["call_rva"], 0x1002)


class TestOriginalBinaryRegression(unittest.TestCase):
    @unittest.skipUnless(
        os.getenv("CODRECOMP_ORIGINALS"),
        "set CODRECOMP_ORIGINALS to validate the private game inputs",
    )
    def test_known_1_5_fingerprints_and_dispatches(self):
        root = Path(os.environ["CODRECOMP_ORIGINALS"])
        for name, expected in BASELINE_SHA256.items():
            with self.subTest(name=name):
                path = root / name
                self.assertTrue(path.is_file(), f"missing {path}")
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), expected)
                self.assertEqual(PEFile(path).machine, 0x14C)

        expectations = {
            "gamex86.dll": (24, 0xA4834),
            "cgamex86.dll": (25, 0x657E8),
            "uix86.dll": (13, 0x34030),
        }
        for name, (last_command, callback_rva) in expectations.items():
            with self.subTest(module=name):
                pe = PEFile(root / name)
                self.assertEqual(recover_vm_dispatch(pe)["max_command"], last_command)
                self.assertEqual(recover_dllentry_callback(pe)["callback_slot_rva"], callback_rva)


if __name__ == "__main__":
    unittest.main()
