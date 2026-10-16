"""Hash-pinned and reversible ARM64 visibility FLD32 patch (OFF by default)."""
from __future__ import annotations

from hashlib import sha256
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import os
import shutil
import tempfile
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools/recomp"))
import patch_codsp_x87_fld32_visibility as patch


def fixture(patched=False, newline="\n"):
    rows = [patch.SOURCE_HEADER, '#include "recomp_rt.h"']
    for pc in patch.PC_SITES:
        old = "d2f((f2d(rd(T+4,4),4)),10)"
        new = f"codsp_x87_fld32_normal(rd(T+4,4)) /* {patch.MARKER} */"
        rows += [
            f"L_{pc:x}:",
            " { uint8_t T[16];",
            f" wr(guest_regs+0x10ac,4,(u128)0x{pc:x}ULL);",
            f" wr(guest_regs+0x1100,10,{new if patched else old});",
            " }",
        ]
    return (newline.join(rows) + newline).encode()


class FLD32VisibilityTests(unittest.TestCase):
    def test_compiled_actual_pcode_full_register_ram_unique_and_pc(self):
        """10 original instructions: 800 A/B cases per O level, full R/U/RAM/PC."""
        pcode = ROOT / "recomp_out/codsp.pcode"
        compiler = os.environ.get("RECOMP_TEST_CC") or shutil.which("cc")
        if not pcode.is_file():
            self.skipTest("Private original p-code unavailable in public checkout")
        if not compiler:
            self.skipTest("C compiler unavailable")
        self.assertEqual(sha256(pcode.read_bytes()).hexdigest(), patch.PCODE_SHA256)
        from pcode2c import parse, generate

        instructions, _, _ = parse(pcode)
        selected = [ins for ins in instructions if ins[0] in patch.PC_SITES]
        self.assertEqual(len(selected), len(patch.PC_SITES))
        pe = SimpleNamespace(
            imports=lambda: [], exports=lambda: [], image_base=0x400000,
            size_of_image=0x200000, entry_rva=0,
        )
        original = generate(
            selected, {}, pe, "CoDSP.exe", "codsp", parts=1
        )[0][0]
        optimized = patch.transform(original.encode(), apply=True).decode()
        source = (
            original.replace("codsp_chunk_0", "baseline_chunk_0")
            + "\n"
            + optimized.replace("codsp_chunk_0", "candidate_chunk_0")
            + "\n"
            + (ROOT / "tests/fld32_visibility_state_smoke.c").read_text()
        )
        # Keep any ephemeral proprietary C inside the ignored private output.
        with tempfile.TemporaryDirectory(dir=ROOT / "recomp_out") as directory:
            path = Path(directory) / "visibility_oracle.c"
            path.write_text(source)
            exe = Path(directory) / ("oracle.exe" if os.name == "nt" else "oracle")
            for optimization in ("-O0", "-O1", "-O2"):
                with self.subTest(optimization=optimization):
                    compiled = subprocess.run(
                        [compiler, optimization, "-I" + str(ROOT / "tools/recomp"),
                         str(path), "-lm", "-o", str(exe)],
                        capture_output=True, text=True, timeout=150,
                    )
                    self.assertEqual(compiled.returncode, 0, compiled.stderr)
                    execution = subprocess.run(
                        [str(exe)], capture_output=True, text=True, timeout=100
                    )
                    self.assertEqual(execution.returncode, 0, execution.stderr)

    def test_10_pcode_sites_pinned_and_valid(self):
        src = ROOT / "recomp_out/codsp.pcode"
        if not src.is_file():
            self.skipTest("Private p-code not in public repository")
        self.assertEqual(sha256(src.read_bytes()).hexdigest(), patch.PCODE_SHA256)
        patch.verify_original_pcode(src)

    def test_synthetic_lf_crlf_roundtrip(self):
        for sep in ("\n", "\r\n"):
            with self.subTest(newline=repr(sep)):
                reference = fixture(newline=sep)
                actual = patch.transform(reference, apply=True)
                self.assertEqual(actual, fixture(True, newline=sep))
                self.assertEqual(patch.transform(actual, apply=False), reference)
                self.assertEqual(reference.count(b"\n"), actual.count(b"\n"))

    def test_real_private_p8_roundtrip_only_in_memory(self):
        path = ROOT / "recomp_out/codsp_recomp_p8.c"
        if not path.is_file():
            self.skipTest("Private generated p8 not in public checkout")
        before = path.read_bytes()
        self.assertEqual(sha256(before).hexdigest(), patch.SOURCE_SHA256)
        modified = patch.transform_file(before, apply=True)
        self.assertEqual(modified.count(patch.MARKER.encode()), len(patch.PC_SITES))
        self.assertEqual(modified.count(b"codsp_x87_fld32_normal("), len(patch.PC_SITES))
        self.assertEqual(patch.transform_file(modified, apply=False), before)
        # Tests must NEVER persist changes to proprietary generated C.
        self.assertEqual(path.read_bytes(), before)

    def test_fail_closed_missing_guest_pc_and_conversion(self):
        origin = fixture()
        changes = (
            origin.replace(b"L_4d82d4:", b"L_4d82d5:", 1),
            origin.replace(b"wr(guest_regs+0x10ac,4,", b"wr(guest_regs+0x10aa,4,", 1),
            origin.replace(b"f2d(rd(T+4,4),4)", b"f2d(rd(T+4,8),8)", 1),
            origin.replace(b"CoDSP.exe", b"Unknown.exe", 1),
            origin.replace(b"L_4d82d4:", b"L_4d82d4:\nL_4d82d4:", 1),
        )
        for changed in changes:
            with self.subTest(change=changed[:80]):
                with self.assertRaises(ValueError):
                    patch.transform(changed, apply=True)

    def test_double_apply_partial_restore_and_unknown_source(self):
        base = fixture()
        edited = patch.transform(base, apply=True)
        with self.assertRaises(ValueError):
            patch.transform(edited, apply=True)
        with self.assertRaises(ValueError):
            patch.transform_file(edited.replace(patch.MARKER.encode(), b"BAD", 1),
                                 apply=False)
        with self.assertRaises(ValueError):
            patch.transform_file(base, apply=True)  # Fixture is not pinned private source.
        self.assertEqual(patch.transform_file(base + b"// unrelated source\n", apply=False),
                         base + b"// unrelated source\n")

    def test_reject_mixed_endings_and_changed_line_count(self):
        changed = fixture().replace(b"\n", b"\r\n", 1)
        with self.assertRaises(ValueError):
            patch.transform(changed, apply=True)

    def test_builder_abi_guard_and_incompatible_source_patches(self):
        builder = ROOT / "tools/recomp/build_android.py"
        cases = [
            (["--abi", "x86_64"], "requires arm64-v8a"),
            (["--package-only"], "cannot use --package-only"),
            (["--x87-stack-shift-outline"], "cannot combine"),
            (["--x87-nan-bits"], "cannot combine"),
            (["--x87-fcom-fastpath"], "cannot combine"),
        ]
        for flags, expected in cases:
            with self.subTest(flags=flags):
                result = subprocess.run(
                    [sys.executable, str(builder), "--arm64-x87-fld32-visibility", *flags],
                    capture_output=True, text=True, timeout=30,
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(expected, result.stderr)

    def test_option_off_by_default_and_restores_p8(self):
        builder = (ROOT / "tools/recomp/build_android.py").read_text(encoding="utf8")
        self.assertIn('args.arm64_x87_fld32_visibility', builder)
        self.assertIn("vis_fld32_script", builder)
        self.assertIn("pcode_path, '--restore'", builder)
        result = subprocess.run(
            [sys.executable, str(ROOT / "tools/recomp/build_android.py"), "--help"],
            capture_output=True, text=True, check=True, timeout=15,
        )
        self.assertIn("--arm64-x87-fld32-visibility", result.stdout)


if __name__ == "__main__":
    unittest.main()
