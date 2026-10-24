"""Host differential oracle for --arm64-x87-conv-fast (d2f/f2d binary80 fast paths).

Reference (flag undefined) and candidate (CODRECOMP_ARM64_X87_CONV_FAST) are
compiled from the same recomp_rt.h in separate translation units and compared
bit-for-bit over every sign/exponent and structured+random significands.
"""
from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CC = shutil.which("clang") or shutil.which("gcc")


@unittest.skipUnless(CC, "no host C compiler")
class X87ConvFastHostOracle(unittest.TestCase):
    def test_bit_exact_vs_reference(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            common = [CC, "-O2", f"-I{ROOT/'tools/recomp'}", "-c"]
            unit = str(ROOT / "tests/x87_conv_fast_unit.c")
            subprocess.run(common + ["-DCONV_PREFIX=ref", unit, "-o", str(d/"ref.o")], check=True)
            subprocess.run(common + ["-DCONV_PREFIX=fast", "-DCODRECOMP_ARM64_X87_CONV_FAST",
                                     unit, "-o", str(d/"fast.o")], check=True)
            exe = d / "conv.exe"
            subprocess.run([CC, "-O2", str(ROOT/"tests/x87_conv_fast_main.c"),
                            str(d/"ref.o"), str(d/"fast.o"), "-lm", "-o", str(exe)], check=True)
            p = subprocess.run([str(exe), "2000000"], capture_output=True, text=True, timeout=300)
            self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
            self.assertTrue(p.stdout.startswith("PASS"), p.stdout)

    def test_flag_wired_off_by_default(self):
        build = (ROOT / "tools/recomp/build_android.py").read_text(encoding="utf8")
        self.assertIn('"--arm64-x87-conv-fast", action="store_true"', build)
        self.assertIn("CODRECOMP_ARM64_X87_CONV_FAST={'ON' if args.arm64_x87_conv_fast else 'OFF'}", build)
        cmake = (ROOT / "android/CMakeLists.txt").read_text(encoding="utf8")
        self.assertIn('option(CODRECOMP_ARM64_X87_CONV_FAST', cmake)
        self.assertIn('" OFF)', cmake)


if __name__ == "__main__":
    unittest.main()
