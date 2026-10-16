"""Host semantics + hash-pinned p0/p8 narrow left-shift source patch."""
from __future__ import annotations
from hashlib import sha256
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools/recomp"))
import patch_codsp_narrow_left_shift as patch


def fixtures():
    pc = 0x419a51
    before = "wr(T+18,4,mask(shl(rd(T+16,4),rd(T+12,4)),4));"
    after = ("wr(T+18,4,mask(codsp_arm64_narrow_shl"
             "(rd(T+16,4),rd(T+12,4),4),4));")
    return pc, before, after


class NarrowLeftTests(unittest.TestCase):
    def test_host_bitwise_oracle_all_widths(self):
        compiler = os.environ.get("RECOMP_TEST_CC") or shutil.which("cc")
        if not compiler:
            self.skipTest("C compiler unavailable")
        source = ROOT / "tests/recomp_left_shift_smoke.c"
        with tempfile.TemporaryDirectory() as d:
            target = Path(d) / ("shl_oracle.exe" if os.name == "nt" else "shl_oracle")
            for optimization in ("-O0", "-O1", "-O2"):
                with self.subTest(optimization=optimization):
                    p = subprocess.run(
                        [compiler, optimization, "-I" + str(ROOT / "tools/recomp"),
                         str(source), "-o", str(target)],
                        capture_output=True, text=True, timeout=65,
                    )
                    self.assertEqual(p.returncode, 0, p.stderr)
                    r = subprocess.run(
                        [str(target)], capture_output=True, text=True, timeout=65,
                    )
                    self.assertEqual(r.returncode, 0, r.stderr)
                    self.assertIn("12288 bitwise oracle cases PASS", r.stdout)

    def test_synthetic_patch_preserves_every_line_lf_crlf(self):
        pc, old, new = fixtures()
        plans = [(pc, 4, old, new)]
        for newline in ("\n", "\r\n"):
            original = (
                patch.SOURCE_HEADER + newline
                + "#include \"recomp_rt.h\"" + newline
                + f"L_{pc:x}:" + newline
                + " " + old + newline
                + "L_419a52:" + newline
            ).encode()
            b = patch.transform(original, part=0, replacements=plans, apply=True)
            self.assertEqual(b.count(patch.MARKER.encode()), 1)
            self.assertEqual(len(b.splitlines()), len(original.splitlines()))
            self.assertEqual(patch.transform(
                b, part=0, replacements=plans, apply=False), original)

    def test_fail_closed_wrong_line_label_and_marker(self):
        pc, old, new = fixtures()
        lines = (patch.SOURCE_HEADER + "\nL_419a51:\n " + old + "\n").encode()
        replacements = [(pc, 0, old, new)]
        for broken in (
            lines.replace(b"L_419a51:", b"L_419a52:"),
            lines.replace(old.encode(), b";"),
            lines.replace(b"\n", b"\r\n", 1),
        ):
            with self.subTest(broken=broken[-25:]):
                with self.assertRaises(ValueError):
                    patch.transform(broken, part=0, replacements=replacements, apply=True)
        with self.assertRaises(ValueError):
            patch.transform(lines, part=8, replacements=replacements, apply=True)

    def test_original_p0_p8_exact_roundtrip_without_filesystem_mutation(self):
        pcode = ROOT / "recomp_out/codsp.pcode"
        sources = {
            0: ROOT / "recomp_out/codsp_recomp_p0.c",
            8: ROOT / "recomp_out/codsp_recomp_p8.c",
        }
        if not pcode.is_file() or any(not x.is_file() for x in sources.values()):
            self.skipTest("Private original CoDSP sources unavailable")
        originals, updated = patch.stage_transform(sources, pcode, apply=True)
        planned = patch.plan(pcode)
        self.assertEqual(sum(len(x) for x in planned.values()), 16)
        for part in sources:
            self.assertNotEqual(originals[part], updated[part])
            self.assertEqual(updated[part].count(patch.MARKER.encode()), len(planned[part]))
            self.assertEqual(
                patch.transform(updated[part], part=part,
                                replacements=planned[part], apply=False),
                originals[part],
            )
            self.assertEqual(sha256(originals[part]).hexdigest(),
                             patch.SOURCE_SHA256[part])
            self.assertEqual(sources[part].read_bytes(), originals[part])

    def test_builder_default_and_invalid_flag_combinations(self):
        builder = ROOT / "tools/recomp/build_android.py"
        text = builder.read_text()
        self.assertIn("--arm64-narrow-left-shift", text)
        self.assertIn("narrow_left_script", text)
        self.assertIn("'--restore'", text)
        cmd = [sys.executable, str(builder), "--arm64-narrow-left-shift"]
        for extra, error in (
            (["--abi", "x86_64"], "requires arm64-v8a"),
            (["--package-only"], "cannot use --package-only"),
            (["--x87-nan-bits"], "cannot combine"),
            (["--x87-stack-shift-outline"], "cannot combine"),
            (["--arm64-x87-fld32-visibility"], "cannot combine"),
            (["--arm64-x87-sign-bits"], "cannot combine"),
            (["--x87-fcom-fastpath"], "cannot combine"),
        ):
            with self.subTest(flags=extra):
                proc = subprocess.run(cmd + extra, capture_output=True,
                                      text=True, timeout=25)
                self.assertNotEqual(proc.returncode, 0)
                self.assertIn(error, proc.stderr)


if __name__ == "__main__":
    unittest.main()
