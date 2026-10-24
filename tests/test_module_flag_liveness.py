"""Whole-module (cross-chunk) flag liveness: static proofs + compiled differential."""
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools/recomp"))
import pcode2c  # noqa: E402
from flag_liveness import (  # noqa: E402
    OPAQUE_ENTRY_PCS, dead_flag_writes, dead_flag_writes_module)

FL = (0x200, 0x202, 0x206, 0x207, 0x20b)


def r(offset=0x200, size=1):
    return ('r', offset, size)


def c(value=0, size=1):
    return ('c', value, size)


def w(offset=0x200, inputs=None, mn='COPY'):
    return (mn, r(offset), [c()] if inputs is None else inputs)


def jmp(address, mn='BRANCH'):
    return (mn, None, [('m', address, 4)])


def cjmp(address, flag=0x206):
    return ('CBRANCH', None, [('m', address, 4), r(flag)])


class StaticTests(unittest.TestCase):
    def test_overwrite_in_next_chunk_is_dead_only_in_module_mode(self):
        chunks = [[(0x1000, 1, [w(), jmp(0x2000)])], [(0x2000, 1, [w()])]]
        self.assertEqual(dead_flag_writes(chunks[0]), set())
        self.assertEqual(dead_flag_writes_module(chunks), [{(0, 0)}, set()])

    def test_fallthrough_between_chunks_and_call(self):
        chunks = [[(0x1000, 1, [w()])], [(0x1001, 1, [w()])]]
        self.assertEqual(dead_flag_writes_module(chunks)[0], {(0, 0)})
        chunks = [[(0x1000, 1, [w(), jmp(0x3000, 'CALL')])], [(0x3000, 1, [w(), ('RETURN', None, [r(0x10, 4)])])]]
        self.assertEqual(dead_flag_writes_module(chunks)[0], {(0, 0)})

    def test_reader_return_and_indirect_in_target_keep_flag_live(self):
        for tail in (('COPY', r(0x10), [r(0x200)]), cjmp(0x1000, 0x200), ('RETURN', None, [r(0x10, 4)]),
                     ('CALLIND', None, [r(0x10, 4)]), ('BRANCHIND', None, [r(0x10, 4)]),
                     ('CALLOTHER', None, [c()]), ('NEW_UNKNOWN', None, [c()])):
            chunks = [[(0x1000, 1, [w(), jmp(0x2000)])], [(0x2000, 1, [tail, w()])]]
            self.assertEqual(dead_flag_writes_module(chunks)[0], set(), tail)

    def test_only_overwritten_bytes_are_dead(self):
        chunks = [[(0x1000, 1, [w(0x200), w(0x206), jmp(0x2000)])],
                  [(0x2000, 1, [w(0x200), ('COPY', r(0x10), [r(0x206)])])]]
        self.assertEqual(dead_flag_writes_module(chunks)[0], {(0, 0)})

    def test_unknown_target_and_opaque_hook_pcs_observe_flags(self):
        chunks = [[(0x1000, 1, [w(), jmp(0x9000)])], [(0x2000, 1, [w()])]]
        self.assertEqual(dead_flag_writes_module(chunks)[0], set())
        hooked = [[(0x1000, 1, [w(), jmp(0x5061b0)])], [(0x5061b0, 1, [w()])]]
        self.assertEqual(dead_flag_writes_module(hooked)[0], set())
        self.assertEqual(dead_flag_writes_module(hooked, opaque_pcs=frozenset())[0], {(0, 0)})
        self.assertEqual(dead_flag_writes_module([[(0x1000, 1, [w()])]])[0], set())

    def test_gap_at_chunk_end_and_unrelated_next_address_are_conservative(self):
        chunks = [[(0x1000, 1, [w()]), (0x1005, 1, [w()])], [(0x1006, 1, [w()])]]
        result = dead_flag_writes_module(chunks)
        self.assertEqual(result[0], {(1, 0)})   # 0x1000 has a gap (stays live); 0x1005 -> 0x1006 dies
        self.assertEqual(result[1], set())      # final chunk: unknown successor

    def test_empty_instruction_chain_across_chunk_boundary(self):
        chunks = [[(0x1000, 1, [w(), jmp(0x2000)])], [(0x2000, 1, []), ],
                  [(0x2001, 1, [w()])]]
        self.assertEqual(dead_flag_writes_module(chunks)[0], {(0, 0)})
        chunks[2] = [(0x2001, 1, [('COPY', r(0x10), [r(0x200)])])]
        self.assertEqual(dead_flag_writes_module(chunks)[0], set())

    def test_cross_chunk_cycle_reaches_fixpoint(self):
        # A: w; B ... reader reachable only after a back edge through the cycle.
        chunks = [[(0x1000, 1, [w(), jmp(0x2000)])],
                  [(0x2000, 1, [cjmp(0x1000, 0x10), jmp(0x3000)])],
                  [(0x3000, 1, [('COPY', r(0x11), [r(0x200)]), jmp(0x1000)])]]
        self.assertEqual(dead_flag_writes_module(chunks)[0], set())
        chunks[2] = [(0x3000, 1, [w(), jmp(0x1000)])]
        self.assertEqual(dead_flag_writes_module(chunks)[0], {(0, 0)})

    def test_superset_of_single_chunk_result_and_no_mutation(self):
        chunks = [[(0x1000, 1, [w(), w(), jmp(0x2000)])], [(0x2000, 1, [w(), w(0x206)])]]
        module = dead_flag_writes_module(chunks)
        for base, mod in zip(map(dead_flag_writes, chunks), module):
            self.assertTrue(base <= mod)

    def test_opaque_set_covers_every_native_hook_pc_in_runtime(self):
        text = (ROOT / "tools/recomp/runtime/guest.c").read_text(errors="replace")
        literals = {int(m.group(1), 16) for m in re.finditer(
            r"\bPC\s*==\s*(?:UINT32_C\()?(0x[0-9a-fA-F]+)", text)}
        self.assertTrue(literals)
        self.assertLessEqual(literals, set(OPAQUE_ENTRY_PCS))


def build_program(rng, count=28, chunk_size=4):
    """Random multi-chunk p-code with forward/earlier-chunk control flow only."""
    base = 0x1000
    insns = []
    regs = [0x10, 0x18, 0x20, 0x28]
    for k in range(count):
        ops = []
        chunk_index = k // chunk_size

        def target():
            choices = list(range(k + 1, count)) + list(range(0, chunk_index * chunk_size))
            if choices and rng.random() < 0.96:
                return base + rng.choice(choices)
            return 0x7000  # outside the module
        for _ in range(rng.randint(1, 4)):
            roll = rng.random()
            f = rng.choice(FL)
            if roll < 0.30:
                ops.append(('COPY', r(f), [c(rng.randint(0, 1))]))
            elif roll < 0.45:
                ops.append(('INT_EQUAL', r(f), [r(rng.choice(regs), 4), r(rng.choice(regs), 4)]))
            elif roll < 0.55:
                ops.append(('INT_CARRY', r(f), [r(rng.choice(regs), 4), c(rng.randint(0, 99), 4)]))
            elif roll < 0.65:
                ops.append(('COPY', r(rng.choice(regs), 4), [r(f, 1)]))  # flag consumer
            elif roll < 0.72:
                ops.append(('INT_ADD', ('r', rng.choice(regs), 4), [r(rng.choice(regs), 4), c(rng.randint(1, 9), 4)]))
            elif roll < 0.80:
                ops.append(('CBRANCH', None, [('m', target(), 4), r(f)]))
            elif roll < 0.86:
                ops.append(('BRANCH', None, [('m', target(), 4)]))
            elif roll < 0.90:
                ops.append(('CALL', None, [('m', target(), 4)]))
            elif roll < 0.94:
                ops.append(('COPY', r(0x40, 4), [c(target(), 4)]))
                ops.append(('BRANCHIND', None, [r(0x40, 4)]))
            elif roll < 0.97:
                ops.append(('RETURN', None, [r(0x44, 4)]))
            else:
                ops.append(('CBRANCH', None, [c(2), r(f)]))  # relative skip
        insns.append((base + k, 1, ops))
    return insns


HARNESS = r"""
#include "recomp_rt.h"
#include <stdio.h>
#include <stdlib.h>
uint8_t *MEM, R[0x2000], U[0x400000]; uint32_t PC; int recomp_miss;
%(decls)s
typedef void (*fn_t)(void);
static fn_t base_fn[] = {%(base)s}, cand_fn[] = {%(cand)s};
static const uint32_t starts[] = {%(starts)s}, ends[] = {%(ends)s};
#define NCHUNKS %(n)d
static uint32_t seed = 0x2468ace1u;
static uint32_t rng(void) { seed = seed * 1664525u + 1013904223u; return seed >> 8; }
static int run(fn_t *table, int limit) {
  for (int step = 0; step < limit; step++) {
    int found = -1;
    for (int i = 0; i < NCHUNKS; i++) if (PC >= starts[i] && PC < ends[i]) found = i;
    if (found < 0) return 0;
    recomp_miss = 0; table[found]();
    if (recomp_miss) return 0;
  }
  return 1;
}
int main(void) {
  static uint8_t init[0x2000], a[0x2000], mem0[4096];
  MEM = calloc(1, 1u << 16);
  int mismatched = 0, trials = %(trials)d, capped = 0, compared = 0;
  for (int t = 0; t < trials; t++) {
    for (int i = 0; i < 0x2000; i++) init[i] = (uint8_t)rng();
    for (int i = 0; i < 0x20c - 0x200; i++) if (rng() & 1) init[0x200 + i] &= 1;
    unsigned entry = %(first)d + (rng() %% %(count)d);
    int cap0 = 0; uint32_t pc0 = 0;
    for (int which = 0; which < 2; which++) {
      memcpy(R, init, sizeof R); memset(U, 0x5a, sizeof U); memset(MEM, 0, 1u << 16);
      PC = entry;
      int hit = run(which ? cand_fn : base_fn, 60);
      if (!which) { memcpy(a, R, sizeof a); memcpy(mem0, MEM, 4096); cap0 = hit; pc0 = PC; }
      else if (hit != cap0 || PC != pc0) { fprintf(stderr, "trajectory differs: trial %%d entry %%x\n", t, entry); mismatched++; }
      else if (hit) capped++;
      else {
        compared++;  /* left the module: every flag byte is observable here */
        if (memcmp(a, R, sizeof a) || memcmp(mem0, MEM, 4096)) {
          fprintf(stderr, "differs: trial %%d entry %%x\n", t, entry); mismatched++;
        }
      }
    }
  }
  printf("trials=%%d compared_at_exit=%%d capped_skipped=%%d mismatches=%%d\n", trials, compared, capped, mismatched);
  return mismatched || compared < trials / 4 ? 1 : 0;
}
"""


def find_cc():
    return (os.environ.get("RECOMP_TEST_CC") or shutil.which("cc") or shutil.which("gcc")
            or shutil.which("clang"))


class CompiledDifferentialTests(unittest.TestCase):
    def test_random_programs_match_default_flag_dce_at_every_exit(self):
        cc = find_cc()
        if not cc:
            self.skipTest("C compiler not available")
        pe = SimpleNamespace(imports=lambda: [], exports=lambda: [], image_base=0x400000,
                             size_of_image=0x400000, entry_rva=0)
        saved = pcode2c.CHUNK
        pcode2c.CHUNK = 4
        extra_dead_total = 0
        try:
            with tempfile.TemporaryDirectory() as directory:
                for seed in range(6):
                    rng = random.Random(seed)
                    insns = build_program(rng)
                    sources, extra = [], 0
                    for ident, module in (("bas", False), ("can", True)):
                        parts, _, unsupported = pcode2c.generate(
                            insns, {}, pe, "T.exe", ident, parts=1,
                            module_flag_liveness=module)
                        self.assertFalse(unsupported)
                        sources.append(parts[0])
                    extra = sources[1].count(" ;") - sources[0].count(" ;")
                    self.assertGreaterEqual(extra, 0)
                    extra_dead_total += extra
                    count = len(insns)
                    n = (count + 3) // 4
                    decls = "".join(f"void {i}_chunk_{k}(void);" for i in ("bas", "can") for k in range(n))
                    starts = [insns[k * 4][0] for k in range(n)]
                    ends = [insns[min(k * 4 + 3, count - 1)][0] + 1 for k in range(n)]
                    harness = HARNESS % dict(
                        decls=decls, n=n, count=count, first=insns[0][0], trials=1500,
                        base=",".join(f"bas_chunk_{k}" for k in range(n)),
                        cand=",".join(f"can_chunk_{k}" for k in range(n)),
                        starts=",".join(f"{s}u" for s in starts),
                        ends=",".join(f"{e}u" for e in ends))
                    source = Path(directory) / f"d{seed}.c"
                    source.write_text("\n".join(sources) + harness)
                    exe = Path(directory) / f"d{seed}.exe"
                    for opt in ("-O0", "-O2"):
                        p = subprocess.run([cc, opt, "-I" + str(ROOT / "tools/recomp"), str(source),
                                            "-lm", "-o", str(exe)], capture_output=True, text=True,
                                           timeout=120)
                        self.assertEqual(p.returncode, 0, p.stderr[:2000])
                        q = subprocess.run([str(exe)], capture_output=True, text=True, timeout=60)
                        self.assertEqual(q.returncode, 0, f"seed {seed} {opt}: {q.stderr[:500]}")
        finally:
            pcode2c.CHUNK = saved
        self.assertGreater(extra_dead_total, 0, "random programs never exercised the new proof")


if __name__ == "__main__":
    unittest.main()
