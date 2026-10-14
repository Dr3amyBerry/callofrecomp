"""Architectural register liveness: multi-instruction CFG + native C equivalence."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools/recomp"))
from pcode2c import generate, HOT_CODSP_DEAD_REGISTER_RANGES
from register_liveness import dead_arch_register_writes


def r(off, size=4):
    return ("r", off, size)

def u(off, size=4):
    return ("u", off, size)

def c(value, size=4):
    return ("c", value, size)

def instr(name, output, *inputs):
    return (name, output, list(inputs))


def fixture():
    return [
        (0x4196f0, 1, [
            instr("COPY", r(40), c(1)),
            instr("COPY", r(40), r(4)),
            instr("COPY", r(44, 8), c(0x0102030405060708, 8)),
            instr("COPY", r(45, 2), c(0xbeef, 2)),
            instr("STORE", None, c(0), c(128), r(40)),
            instr("COPY", r(0x1100, 10), r(0x1120, 10)),
            instr("COPY", r(0x1100, 10), r(0x1130, 10)),
        ]),
        (0x4196f1, 1, [
            instr("COPY", r(52), c(3)),
            instr("CBRANCH", None, ("m", 0x4196f3, 4), r(0, 1)),
            instr("COPY", r(52), c(4)),
        ]),
        (0x4196f2, 1, [
            instr("COPY", r(52), c(5)),
            instr("COPY", r(60), c(9)),
            instr("COPY", r(60), c(10)),
        ]),
        (0x4196f3, 1, [
            instr("COPY", r(56), r(52)),
            instr("COPY", r(0x200, 1), c(1, 1)),
            instr("COPY", r(0x200, 1), c(0, 1)),
            instr("COPY", r(0x206, 1), r(0, 1)),
        ]),
    ]


class DeadRegisterWriteTests(unittest.TestCase):
    def test_cross_instruction_and_partial_aliases(self):
        chunk = fixture()
        removed = dead_arch_register_writes(
            chunk, eligible_ranges=((0x4196f0, 0x4196f4),))
        self.assertIn((0, 0), removed)
        self.assertNotIn((0, 1), removed)     # Read by guest STORE
        self.assertNotIn((0, 2), removed)     # Partial byte overwrite
        self.assertNotIn((0, 3), removed)
        self.assertIn((0, 5), removed)         # x87 write overwritten
        self.assertNotIn((0, 6), removed)     # final x87 state observed
        self.assertNotIn((1, 0), removed)     # true branch observes r52
        self.assertIn((1, 2), removed)         # overwritten on fallthrough
        self.assertNotIn((2, 0), removed)     # read by next PC
        self.assertIn((2, 1), removed)         # overwritten even at boundary
        self.assertNotIn((2, 2), removed)     # final state observed
        self.assertNotIn((3, 1), removed)     # owned by flag DCE, not generic
        self.assertNotIn((3, 2), removed)

    def test_all_exits_and_unknown_are_barriers(self):
        exit_chunk = [(0x4196f0, 1, [
            instr("COPY", r(40), c(1)),
            instr("BRANCH", None, ("m", 0x500000, 4)),
        ])]
        self.assertEqual(dead_arch_register_writes(
            exit_chunk, eligible_ranges=HOT_CODSP_DEAD_REGISTER_RANGES), set())
        opaque = [(0x4196f0, 1, [
            instr("COPY", r(40), c(1)),
            instr("CALLOTHER", None, c(0)),
            instr("COPY", r(40), c(2)),
        ])]
        self.assertEqual(dead_arch_register_writes(
            opaque, eligible_ranges=HOT_CODSP_DEAD_REGISTER_RANGES), set())

    def test_flag_output_and_cross_chunk_are_preserved(self):
        ineligible = [(0x4196f0, 1, [instr("COPY", r(64), c(1)),
                                    instr("COPY", r(64), c(2))])]
        self.assertEqual(dead_arch_register_writes(
            ineligible, eligible_ranges=((0x800000, 0x800100),)), set())
        self.assertEqual(dead_arch_register_writes(
            fixture(), eligible_ranges=()), set())
        with self.assertRaises(ValueError):
            dead_arch_register_writes(fixture(), removed_flags={(12, 0)},
                                      eligible_ranges=HOT_CODSP_DEAD_REGISTER_RANGES)

    def test_compiled_full_state_all_entry_points(self):
        cc = os.environ.get("RECOMP_TEST_CC") or shutil.which("cc")
        if not cc:
            self.skipTest("C compiler not available")
        pe = SimpleNamespace(imports=lambda: [], exports=lambda: [],
                             image_base=0x400000, size_of_image=0x400000,
                             entry_rva=0)
        variants = []
        for tag, enabled in (("baseline", False), ("candidate", True)):
            source = generate(
                fixture(), {}, pe, "CoDSP.exe", "codsp", parts=1,
                prune_hot_register_writes=enabled)[0][0]
            variants.append(source.replace("codsp_chunk_0", tag + "_chunk_0"))
        self.assertNotEqual(variants[0], variants[1])
        self.assertGreater(variants[1].count(" ;"), variants[0].count(" ;"))
        harness = r"""
#include "recomp_rt.h"
#include <stdlib.h>
#include <stdio.h>
uint8_t *MEM, R[0x2000], U[0x400000];uint32_t PC;int recomp_miss;
void baseline_chunk_0(void);void candidate_chunk_0(void);
static uint32_t seed=0x12345fa3;
static uint32_t rng(void){seed=seed*1664525u+1013904223u;return seed;}
int main(void) {
 uint8_t before[0x2000], initial_mem[256], expected[0x2000], expected_mem[256];
 MEM=malloc(256);if(!MEM)return 11;
 for(unsigned entry=0x4196f0;entry<=0x4196f3;entry++) {
  for(int trial=0;trial<1500;trial++) {
   for(int i=0;i<0x2000;i++) before[i]=(uint8_t)(rng()>>24);
   for(int i=0;i<256;i++) initial_mem[i]=(uint8_t)(rng()>>24);
   for(int which=0;which<2;which++){
    memcpy(R,before,sizeof R);memcpy(MEM,initial_mem,256);memset(U,0x7a,sizeof U);
    PC=entry;recomp_miss=0;
    if(which)candidate_chunk_0();else baseline_chunk_0();
    if(PC!=0x4196f4||recomp_miss){fprintf(stderr,"bad PC %u %d\n",entry,which);return 12;}
    if(!which){memcpy(expected,R,sizeof R);memcpy(expected_mem,MEM,256);}
    else if(memcmp(R,expected,sizeof R) || memcmp(MEM,expected_mem,256)) {
     fprintf(stderr,"state differs at %u trial %d\n",entry,trial);return 13;
    }
   }
  }
 }
 return 0;
}
"""
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            source = root / "equivalence.c"
            source.write_text("\n".join(variants) + harness)
            executable = root / ("equivalence.exe" if os.name == "nt" else "equivalence")
            for flag in ("-O0", "-O1", "-O2"):
                p = subprocess.run(
                    [cc, flag, "-I" + str(ROOT / "tools/recomp"),
                     str(source), "-lm", "-o", str(executable)],
                    capture_output=True, text=True, timeout=45)
                self.assertEqual(p.returncode, 0, p.stderr)
                subprocess.run([str(executable)], check=True, timeout=35)


if __name__ == "__main__":
    unittest.main()
