import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools/recomp'))
from patch_codsp_x87_nan import patch, HEADER, INCLUDE

class X87NanPatchTests(unittest.TestCase):
    def sample(self, filename="codsp_recomp_p1.c"):
        label="L_41b8f0:" if filename.endswith("p1.c") else "L_4d8280:"
        return (HEADER+'\n#include "recomp_rt.h"\n'+label+
                '\n wr(T+2,1,(u128)isnan(f2d(rd(T+16,10),10)));\n'+
                ' wr(guest_regs+0x206,1,(u128)isnan(f2d(rd(guest_regs+0x1100,10),10)));\n')
    def test_exact_private_expression_and_idempotence(self):
        for name in ["codsp_recomp_p1.c","codsp_recomp_p8.c"]:
            s=self.sample(name)
            out,modified=patch(s,name,expected=2)
            self.assertTrue(modified)
            self.assertEqual(out.count("CODSP_X87_ISNAN("),2)
            self.assertIn(INCLUDE,out)
            self.assertEqual(s.count("\n"),out.count("\n"))
            self.assertEqual(patch(out,name,expected=2),(out,False))
    def test_fail_closed_on_mismatched_private_code(self):
        s=self.sample()
        with self.assertRaises(ValueError):patch(s,"unrelated.c",expected=2)
        with self.assertRaises(ValueError):patch(s.replace("L_41b8f0:","L_41b8f1:"),"codsp_recomp_p1.c",expected=2)
        with self.assertRaises(ValueError):patch(s.replace("isnan(f2d(rd(T+16,10),10))","isnan(f2d(rd(T+16,8),8))"),"codsp_recomp_p1.c",expected=2)
        with self.assertRaises(ValueError):patch(s+INCLUDE,"codsp_recomp_p1.c",expected=2)
        with self.assertRaises(ValueError):patch(s.replace("isnan(f2d(rd(T+16,10),10))","CODSP_X87_ISNAN(rd(T+16,10))"),"codsp_recomp_p1.c",expected=2)
if __name__ == "__main__": unittest.main()
