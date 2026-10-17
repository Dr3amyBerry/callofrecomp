"""Pure IEEE binary32 case classification for AArch64 FLD32 performance audit."""
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools/recomp/diagnostics"))
from verify_arm64_x87_fld32 import BINARY32_CLASSES, classify_binary32


class Binary32ClassTelemetryTests(unittest.TestCase):
    def test_classification_signs_and_exponent_boundaries(self):
        samples={
            "signed_zero": (0x00000000, 0x80000000),
            "subnormal": (0x00000001, 0x007fffff, 0x80000001, 0x807fffff),
            "normal": (
                0x00800000,0x80800000,0x3f800000,0xbf800000,
                0x7f7fffff,0xff7fffff,0x3f000001
            ),
            "infinity": (0x7f800000, 0xff800000),
            "nan": (
                0x7f800001,0x7fc00000,0x7fffffff,
                0xff800001,0xffc00000,0xffffffff
            ),
        }
        self.assertEqual(set(samples), set(BINARY32_CLASSES))
        for kind,bits_set in samples.items():
            for bits in bits_set:
                with self.subTest(kind=kind,bits=f"{bits:08x}"):
                    self.assertEqual(classify_binary32(bits),kind)

    def test_classification_is_sign_invariant(self):
        for bits in (0,1,0x7fffff,0x800000,0x3f800000,
                     0x7f7fffff,0x7f800000,0x7f800001,0x7fc00000):
            self.assertEqual(classify_binary32(bits),
                             classify_binary32(bits|0x80000000))

    def test_reject_invalid_inputs_instead_of_truncating(self):
        for bad in (-1,0x100000000,None,3.14,"0x7f800000",True):
            with self.subTest(value=bad):
                with self.assertRaises(ValueError):
                    classify_binary32(bad)


if __name__=="__main__":
    unittest.main()
