"""Verify opt-in CoDSP copy32 insertion never changes unrecognized C."""
import sys
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools/recomp"))
from patch_codsp_copy32 import patch_generated_source, HEADER, ANCHOR, HOOK, INCLUDE, LABELS

class Copy32PatchTests(unittest.TestCase):
    def sample(self):
        labels="\n".join(f"L_{a:x}:\n {{ uint8_t T[16];\n"
                         " wr(R+0x0,4,rd(R+0xc,4));\n"
                         " wr(R+0x18,4,rd(R+0x8,4));\n"
                         " wr(R+0x1c,4,rd(R+0x1c,4));\n }\n"
                         for a in LABELS)
        return HEADER+"\n#include \"recomp_rt.h\"\n"+labels+" goto L_42b100;\nL_42b141:\n {}"

    def test_patch_is_idempotent_and_opt_in(self):
        start=self.sample()
        out,changed=patch_generated_source(start)
        self.assertTrue(changed)
        self.assertEqual(out.count(HOOK),1)
        self.assertEqual(out.count(INCLUDE),1)
        self.assertTrue(out.index("L_42b100:") < out.index(HOOK) < out.index("L_42b103:"))
        self.assertEqual(patch_generated_source(out),(out,False))
        self.assertIn("#if defined(CODRECOMP_CODSP_COPY32_FASTPATH)",out)

    def test_refuses_wrong_file_and_changed_loops(self):
        with self.assertRaises(ValueError):
            patch_generated_source(self.sample().replace("from CoDSP.exe","from another.exe"))
        with self.assertRaises(ValueError):
            patch_generated_source(self.sample().replace("L_42b13e:","L_42b13f:"))
        with self.assertRaises(ValueError):
            patch_generated_source(self.sample().replace("goto L_42b100;","goto L_42b210;"))
        with self.assertRaises(ValueError):
            patch_generated_source(self.sample().replace("L_42b100:","L_42b100:\n"+HOOK))

if __name__=="__main__":
    unittest.main()
