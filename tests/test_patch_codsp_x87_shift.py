"""Reversible post-generation CoDSP x87 stack shift patching tests."""
from pathlib import Path
import os
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools/recomp"))
from patch_codsp_x87_shift import transform, HEADER,MARKER
from x87_stack_fusion import PUSH,POP


def sample(nl="\n",base="guest_regs"):
    lines=[HEADER, '#include "recomp_rt.h"', 'void codsp_chunk_0(void){',
           'L_41b8f0:', ' { uint8_t T[1];']
    for seq in (PUSH,POP):
        lines.extend(f" wr({base}+0x{dest:x},10,rd({base}+0x{src:x},10));"
                     for dest,src in seq)
    lines.extend([' PC=0x41b8f1u;return;','}'])
    return (nl.join(lines)+nl).encode()

class X87StackPatcherTests(unittest.TestCase):
    def test_exact_byte_roundtrip_lf_and_crlf(self):
        for newline in ("\n","\r\n"):
            for base in ("guest_regs","R"):
                raw=sample(newline,base)
                new,counts=transform(raw,apply=True)
                self.assertEqual(counts,{"push":1,"pop":1})
                self.assertIn(MARKER.encode(),new)
                self.assertEqual(len(raw.splitlines()),len(new.splitlines()))
                recovered,counts=transform(new,apply=False)
                self.assertEqual(recovered,raw)
                self.assertEqual(counts,{"push":1,"pop":1})
                restored,counts=transform(raw,apply=False)
                self.assertEqual(restored,raw)
                self.assertEqual(counts,{"push":0,"pop":0})
                with self.assertRaisesRegex(ValueError,"Already outlined"):
                    transform(new,apply=True)

    def test_no_branch_crossing_or_partial_copy_fuses(self):
        original=sample()
        lines=original.decode().splitlines()
        lines.insert(7," L_41b8f0_4:;")
        original=("\n".join(lines)+"\n").encode()
        fast,counts=transform(original,apply=True)
        self.assertEqual(counts["push"],0)
        self.assertEqual(counts["pop"],1)
        self.assertEqual(transform(fast,apply=False)[0],original)

    def test_bad_header_and_corrupt_marker_rejected(self):
        with self.assertRaisesRegex(ValueError,"verified pcode2c"):
            transform(b"fake source\n",apply=True)
        fast,_=transform(sample(),apply=True)
        broken=fast.replace(b" ;\n",b" x;\n",1)
        with self.assertRaisesRegex(ValueError,"Malformed"):
            transform(broken,apply=False)

if __name__=="__main__":
    unittest.main()
