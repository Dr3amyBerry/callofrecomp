"""Pure Python exact rational reference vectors; never changes Android APK."""
from fractions import Fraction
import sys
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.recomp.diagnostics.binary80_arithmetic_reference import (
    UnsupportedBinary80,exact_value,encode_finite,operate,to_binary32_bits,unpack,
)


class NumericBinary80ReferenceTests(unittest.TestCase):
    def pack(self,n,d=1):
        return encode_finite(Fraction(n,d))

    def test_binary80_constants(self):
        self.assertEqual(self.pack(1),bytes.fromhex("0000000000000080ff3f"))
        self.assertEqual(self.pack(-1),bytes.fromhex("0000000000000080ffbf"))
        self.assertEqual(self.pack(2),bytes.fromhex("00000000000000800040"))
        self.assertEqual(exact_value(self.pack(1,2)),Fraction(1,2))

    def test_exact_excess_precision_cancellation(self):
        big=self.pack(1<<60)
        one=self.pack(1)
        summed=operate("add",big,one)
        self.assertEqual(exact_value(summed),Fraction((1<<60)+1))
        self.assertEqual(exact_value(operate("sub",summed,big)),Fraction(1))

    def test_nearest_even_halfway_and_above(self):
        halfway=Fraction(1)+(Fraction(1,1<<64))
        self.assertEqual(self.pack(1),encode_finite(halfway))
        above=halfway+Fraction(1,1<<100)
        self.assertEqual(exact_value(encode_finite(above)),Fraction(1)+Fraction(1,1<<63))

    def test_x87_extended_changes_binary32_rounding(self):
        # Independent original-x86 research counterexample:
        # 1 + 2^-24 + 2^-54. Double erases the 2^-54 before float32 storage.
        result=operate("add",self.pack(1),self.pack(1,1<<24))
        result=operate("add",result,self.pack(1,1<<54))
        self.assertEqual(to_binary32_bits(result),0x3f800001)

    def test_exact_product(self):
        self.assertEqual(exact_value(operate("mul",self.pack(3,2),self.pack(-5,4))),
                         Fraction(-15,8))

    def test_exact_division_rounded_to_64_bits(self):
        result=operate("div",self.pack(1),self.pack(3))
        self.assertEqual(unpack(result)[2],0xaaaaaaaaaaaaaaab)
        self.assertEqual(unpack(result)[1],16381)

    def test_rounding_and_underflow(self):
        tiny=Fraction(1,1<<16445)
        self.assertEqual(unpack(self.pack(tiny.numerator,tiny.denominator)),(0,0,1))
        normal=Fraction(1,1<<16382)
        self.assertEqual(unpack(self.pack(normal.numerator,normal.denominator))[1],1)
        self.assertEqual(to_binary32_bits(self.pack(1,1<<149)),1)

    def test_signed_zeros_for_multiplication(self):
        zero=self.pack(0)
        result=operate("mul",zero,self.pack(-1))
        self.assertEqual(to_binary32_bits(result),0x80000000)

    def test_explicit_fail_closed_unsupported(self):
        with self.assertRaises(UnsupportedBinary80):
            operate("add",self.pack(1),self.pack(1),cw=0x007f)
        with self.assertRaises(UnsupportedBinary80):
            operate("div",self.pack(1),self.pack(0))
        with self.assertRaises(UnsupportedBinary80):
            exact_value(bytes.fromhex("0000000000000080ff7f"))
        with self.assertRaises(UnsupportedBinary80):
            exact_value(bytes.fromhex("0000000000000040ff3f"))
        with self.assertRaises(UnsupportedBinary80):
            self.pack(1<<16384)

    def test_reject_host_float_input(self):
        with self.assertRaises(TypeError):
            encode_finite(1.0)


if __name__=="__main__":
    unittest.main()
