import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools/recomp'))
from patch_codsp_fcom import patch, identify, HEADER, ANCHOR

class CodspFcomPatchTests(unittest.TestCase):
    def test_nonmatching_source_fails_closed(self):
        s=HEADER+'\n#include "x87_nan_bits.h"\nL_41ae6b:\n { uint8_t T[4];\n }\n'
        with self.assertRaisesRegex(ValueError,'partial/stale'):
            patch(s,'codsp_recomp_p1.c')
        with self.assertRaisesRegex(ValueError,'Only verified'):
            patch(s,'other_module.c')
    def test_bad_generated_header(self):
        with self.assertRaisesRegex(ValueError,'Not original'):
            patch('arbitrary C source','codsp_recomp_p1.c')
    def test_does_not_accept_partial_pcode_shape(self):
        self.assertIsNone(identify(' { uint8_t T[42];\n'+ANCHOR+' }\n','41ae6b'))
    def test_marker_counts_do_not_count_unrelated_code(self):
        s=HEADER+'\n#include "x87_nan_bits.h"\nL_41ae6b:\n { if(CODSP_FCOM_GUARD(a,b,c,d)) goto L_41ae6c; }\nL_41ae6c:\n {}\n'
        with self.assertRaisesRegex(ValueError,'partial/stale'):
            patch(s,'codsp_recomp_p1.c')
if __name__=='__main__':unittest.main()
