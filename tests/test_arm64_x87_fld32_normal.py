"""CoDSP hot FLD m32 exact-normal ARM64 experiment, OFF by default."""
from __future__ import annotations

from hashlib import sha256
import importlib.util
from pathlib import Path
import random
import struct
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
PATCH = ROOT / "tools/recomp/patch_codsp_x87_fld32.py"
spec = importlib.util.spec_from_file_location("fld32_patch", PATCH)
patch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(patch)


def fixture(*, patched=False):
    src = patch.SOURCE_HEADER + "\n#include \"recomp_rt.h\"\n"
    for pc in patch.PC_SITES:
        old = f" wr(guest_regs+0x1100,10,d2f((f2d(rd(T+4,4),4)),10));"
        new = f" wr(guest_regs+0x1100,10,codsp_x87_fld32_normal(rd(T+4,4)) /* {patch.MARKER} */);"
        src += (
            f"L_{pc:x}:\n {{ uint8_t T[16];\n"
            f" wr(guest_regs+0x10ac,4,(u128)0x{pc:x}ULL);\n"
            + (new if patched else old) + "\n }\n"
        )
    return src.encode()


class HotFLD32ARM64Tests(unittest.TestCase):
    def test_39_original_pcode_provenance(self):
        sys.path.insert(0, str(ROOT / "tools/recomp"))
        from pcode2c import parse
        p = ROOT / "recomp_out/codsp.pcode"
        self.assertEqual(sha256(p.read_bytes()).hexdigest(), patch.PCODE_SHA256)
        instructions, _, _ = parse(p)
        matching = []
        for pc, _, ops in instructions:
            if not 0x5061b0 <= pc < 0x506245:
                continue
            for name, out, inputs in ops:
                if name == "FLOAT2FLOAT" and out and out[2] == 10 and (
                    len(inputs) == 1 and inputs[0][2] == 4
                ):
                    matching.append(pc)
        self.assertEqual(tuple(matching), patch.PC_SITES)

    def test_source_roundtrip_byte_exact_without_other_pc_changes(self):
        source = ROOT / "recomp_out/codsp_recomp_p10.c"
        original = source.read_bytes()
        self.assertEqual(sha256(original).hexdigest(), patch.SOURCE_SHA256)
        edited, pcs = patch.transform_file(original, apply=True)
        self.assertEqual(pcs, patch.PC_SITES)
        self.assertEqual(edited.count(patch.MARKER.encode()), 39)
        self.assertEqual(edited.count(b"codsp_x87_fld32_normal("), 39)
        self.assertEqual(len(edited.splitlines()), len(original.splitlines()))
        restored, _ = patch.transform_file(edited, apply=False)
        self.assertEqual(restored, original)
        self.assertEqual(patch.transform_file(original, apply=False)[0], original)

    def test_synthetic_fixture_transform_and_recovery(self):
        original = fixture()
        patched, _ = patch.transform(original, apply=True)
        self.assertEqual(patched, fixture(patched=True))
        self.assertEqual(patch.transform(patched, apply=False)[0], original)

    def test_reject_missing_label_or_pc_write_or_conversion(self):
        original = fixture()
        changes = [
            original.replace(b"L_5061b0:", b"L_5061b1:", 1),
            original.replace(b"wr(guest_regs+0x10ac,4,", b"wr(guest_regs+0x10aa,4,", 1),
            original.replace(b"f2d(rd(T+4,4),4)", b"f2d(rd(T+4,8),8)", 1),
            original.replace(b"CoDSP.exe", b"Unknown.exe", 1),
        ]
        for source in changes:
            with self.subTest(source=source[:80]):
                with self.assertRaises(ValueError):
                    patch.transform(source, apply=True)

    def test_reject_partial_mixed_or_double_apply(self):
        patched = fixture(patched=True)
        with self.assertRaises(ValueError):
            patch.transform(patched, apply=True)
        with self.assertRaises(ValueError):
            patch.transform(fixture().replace(b"\n", b"\r\n", 1), apply=True)
        with self.assertRaises(ValueError):
            patch.transform_file(patched.replace(patch.MARKER.encode(), b"BAD", 1), apply=False)

    def test_bit_mapping_matches_independent_float64_reference_for_normals(self):
        rng = random.Random(0x5061b0)
        words = []
        for exp in range(1, 255):
            for sign in (0, 0x80000000):
                for fraction in (0, 1, 0x3fffff, 0x7fffff):
                    words.append(sign | (exp << 23) | fraction)
        words += [
            (rng.randrange(2) << 31) | (rng.randrange(1, 255) << 23)
            | rng.getrandbits(23) for _ in range(25000)
        ]
        for word in words:
            exp = (word >> 23) & 255
            direct_significand = (1 << 63) | ((word & 0x7fffff) << 40)
            direct_se = ((word >> 16) & 0x8000) | (exp + 16256)
            direct = (direct_se << 64) | direct_significand

            f = struct.unpack("<f", struct.pack("<I", word))[0]
            d = struct.unpack("<Q", struct.pack("<d", f))[0]
            exp64 = (d >> 52) & 0x7ff
            frac64 = d & ((1 << 52) - 1)
            reference_se = ((d >> 48) & 0x8000) | (exp64 + 15360)
            reference = ((reference_se << 64) |
                         (1 << 63) | (frac64 << 11))
            self.assertEqual(direct, reference, hex(word))

    def test_default_and_other_abi_stay_off(self):
        builder = (ROOT / "tools/recomp/build_android.py").read_text(encoding="utf8")
        self.assertIn('args.arm64_x87_fld32_normal', builder)
        self.assertIn("fld32_script", builder)
        for options, error in (
            (["--abi", "x86_64"], "requires arm64-v8a"),
            (["--abi", "arm64-v8a", "--package-only"], "cannot use --package-only"),
            (["--abi", "arm64-v8a", "--x87-stack-shift-outline"], "cannot combine"),
            (["--abi", "arm64-v8a", "--hot-x87-transform"],
             "ORIGINAL_X87_PRECISION_UNSAFE"),
        ):
            proc = subprocess.run(
                [sys.executable, str(ROOT / "tools/recomp/build_android.py"),
                 "--arm64-x87-fld32-normal", *options],
                text=True, capture_output=True, timeout=25,
            )
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn(error, proc.stderr)


if __name__ == "__main__":
    unittest.main()
