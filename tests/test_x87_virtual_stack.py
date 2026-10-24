"""x87 virtual stack renaming: parallel-move unit tests + compiled differential."""
import random
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools/recomp"))
sys.path.insert(0, str(ROOT / "tests"))
import pcode2c  # noqa: E402
from x87_virtual_stack import SLOTS, VirtualStack, eligible  # noqa: E402
from test_module_flag_liveness import HARNESS as FLAG_HARNESS, find_cc  # noqa: E402

# Signalling NaN bits are injected at run time: a compile-time NaN constant lets
# LLVM fold x+NaN to the constant, while hardware returns x's NaN (C leaves NaN
# sign/payload unspecified), which would test the compiler, not the translation.
HARNESS = FLAG_HARNESS.replace(
    "unsigned entry =",
    "if (rng() & 1) { uint64_t sn = 0x7ff0000000000001ull | (((uint64_t)rng() << 24) & 0x0007ffffff000000ull);"
    " if (rng() & 1) sn |= 1ull << 63; memcpy(init + 0x58, &sn, 8); }\n    unsigned entry =")
assert HARNESS != FLAG_HARNESS

# With -O2 LLVM may commute FADD/FMUL operands; when both are NaN, hardware
# returns the first one, so the surviving payload is the compiler's choice for
# base and candidate alike. -O0 stays strictly bitwise; -O2 tolerates a
# difference only where both sides hold a NaN of the same storage format.
NAN_EQUIV = r"""
static int nan80(const uint8_t *p) { uint64_t m; memcpy(&m, p, 8);
  return (((p[9] & 0x7f) << 8 | p[8]) == 0x7fff) && (m << 1); }
static int nan64(const uint8_t *p) { uint64_t b; memcpy(&b, p, 8);
  return (b & 0x7ff0000000000000ull) == 0x7ff0000000000000ull && (b & 0xfffffffffffffull); }
static int equiv(const uint8_t *x, const uint8_t *y) {
#ifdef STRICT
  return !memcmp(x, y, 0x2000);
#else
  static const int f80[] = {0x1100,0x1110,0x1120,0x1130,0x1140,0x1150,0x1160,0x1170,0x30,0x40};
  for (int z = 0; z < 0x2000; z++) {
    if (x[z] == y[z]) continue;
    int ok = 0;
    for (unsigned k = 0; k < sizeof f80 / sizeof *f80; k++)
      if (z >= f80[k] && z < f80[k] + 10 && nan80(x + f80[k]) && nan80(y + f80[k])) ok = 1;
    if (z >= 0x50 && z < 0x58 && nan64(x + 0x50) && nan64(y + 0x50)) ok = 1;
    if (!ok) return 0;
  }
  return 1;
#endif
}
"""
HARNESS = HARNESS.replace("int main(void) {", NAN_EQUIV + "int main(void) {").replace(
    "memcmp(a, R, sizeof a)", "!equiv(a, R)")
assert "!equiv(a, R)" in HARNESS


def st(k):
    return ('r', SLOTS[k], 10)


def run_flush(loc):
    """Interpret flush_code over symbolic slot contents."""
    vs = VirtualStack()
    vs.loc = list(loc)
    code = vs.flush_code()
    mem = {SLOTS[p]: f'v{p}' for p in range(8)}
    scratch = {}
    for stmt in filter(None, (s.strip() for s in code.strip('{} ').split(';'))):
        m = re.fullmatch(r'u128 (\w+)=rd\(R\+0x([0-9a-f]+),10\)', stmt)
        if m:
            scratch[m.group(1)] = mem[int(m.group(2), 16)]
            continue
        m = re.fullmatch(r'wr\(R\+0x([0-9a-f]+),10,(?:rd\(R\+0x([0-9a-f]+),10\)|(\w+))\)', stmt)
        assert m, stmt
        mem[int(m.group(1), 16)] = mem[int(m.group(2), 16)] if m.group(2) else scratch[m.group(3)]
    return [mem[SLOTS[k]] for k in range(8)], code


class FlushTests(unittest.TestCase):
    def test_random_maps_restore_canonical(self):
        rng = random.Random(7)
        for _ in range(3000):
            loc = [rng.randrange(8) for _ in range(8)] if rng.random() < 0.5 else rng.sample(range(8), 8)
            got, code = run_flush(loc)
            self.assertEqual(got, [f'v{p}' for p in loc], (loc, code))

    def test_identity_is_empty_and_push_is_cheap(self):
        self.assertEqual(VirtualStack().flush_code(), '')
        vs = VirtualStack()
        # FLD: rotate down by aliasing, new value written to the freed slot.
        vs.loc = [7, 0, 1, 2, 3, 4, 5, 6]
        self.assertEqual(vs.flush_code().count('wr('), 8)  # one 8-cycle, single scratch
        self.assertEqual(vs.flush_code().count('u128 '), 1)

    def test_write_to_shared_slot_allocates_free_slot(self):
        vs = VirtualStack()
        vs.alias(1, 0)              # st1 = st0, physical 1 now unreferenced
        self.assertEqual(vs.dest(0), SLOTS[1])
        self.assertEqual(vs.loc, [1, 0, 2, 3, 4, 5, 6, 7])

    def test_partial_stack_access_and_callother_are_ineligible(self):
        self.assertTrue(eligible([('COPY', st(0), [st(1)])]))
        self.assertFalse(eligible([('COPY', ('r', 0x10, 2), [('r', SLOTS[0], 2)])]))
        self.assertFalse(eligible([('CALLOTHER', None, [('c', 1, 4)])]))
        self.assertFalse(eligible([('COPY', st(0), [st(1)])], rel_targets={1}))


PUSH = [('COPY', ('u', 0x100, 10), [st(7)])] + [('COPY', st(k + 1), [st(k)]) for k in range(6, -1, -1)] + [
    ('COPY', st(0), [('u', 0x100, 10)])]
POP = [('COPY', st(k), [st(k + 1)]) for k in range(7)]


def fxch(k):
    return [('COPY', ('u', 0x200, 10), [st(0)]), ('COPY', st(0), [st(k)]), ('COPY', st(k), [('u', 0x200, 10)])]


def build_program(rng, count=32):
    base = 0x1000
    regs = [0x10, 0x18, 0x20, 0x28]
    insns = []

    def target(k):
        # Forward, or into an earlier chunk (the harness counts chunk steps);
        # a backward goto inside one chunk would spin without returning.
        choices = list(range(k + 1, count)) + list(range(0, (k // 8) * 8))
        if choices and rng.random() < 0.8:
            return base + rng.choice(choices)
        return 0x7000
    for k in range(count):
        roll = rng.random()
        ops = []
        if roll < 0.22:      # FILD/FLD
            ops = list(PUSH) + [('INT2FLOAT', st(0), [('r', rng.choice(regs), 4)])]
        elif roll < 0.34:    # FSTP to integer-ish storage (keeps bits) + pop
            ops = [('COPY', ('r', 0x30 + 16 * rng.randrange(3), 10), [st(0)])] + list(POP)
        elif roll < 0.44:
            ops = fxch(rng.randrange(1, 8))
        elif roll < 0.62:    # arithmetic between stack slots
            a, b = rng.randrange(8), rng.randrange(8)
            mn = rng.choice(['FLOAT_ADD', 'FLOAT_MULT', 'FLOAT_SUB'])
            ops = [(mn, st(a), [st(a), st(b)])]
        elif roll < 0.68:    # FADDP-like: op then pop
            ops = [('FLOAT_ADD', st(1), [st(1), st(0)])] + list(POP)
        elif roll < 0.70:    # FLD m64 from raw register bits (may be a signalling NaN)
            ops = list(PUSH) + [('FLOAT2FLOAT', st(0), [('r', rng.choice(regs), 8)])]
        elif roll < 0.705:   # FLD m64 of a runtime signalling NaN (see SNAN_HARNESS)
            ops = list(PUSH) + [('FLOAT2FLOAT', st(0), [('r', 0x58, 8)])]
        elif roll < 0.715:   # FCHS / FABS keep signalling NaNs
            ops = [(rng.choice(['FLOAT_NEG', 'FLOAT_ABS']), st(0), [st(0)])]
        elif roll < 0.725:   # FST m64 / FCOM
            ops = [('FLOAT2FLOAT', ('r', 0x50, 8), [st(rng.randrange(8))]),
                   ('FLOAT_LESS', ('r', 0x72, 1), [st(0), st(1)])]
        elif roll < 0.735:   # partial view of a slot: ineligible
            ops = [('COPY', ('r', 0x60, 2), [('r', SLOTS[rng.randrange(8)] + 8, 2)])]
        elif roll < 0.76:    # relative internal branch: ineligible
            ops = [('CBRANCH', None, [('c', 2, 4), ('r', 0x70, 1)]), ('COPY', st(0), [st(1)]),
                   ('COPY', ('r', 0x71, 1), [('c', 1, 1)])]
        elif roll < 0.84:
            ops = [('CBRANCH', None, [('m', target(k), 4), ('r', 0x70 + rng.randrange(4), 1)])]
        elif roll < 0.88:
            ops = [('BRANCH', None, [('m', target(k), 4)])]
        elif roll < 0.91:
            ops = [('CALL', None, [('m', target(k), 4)])]
        elif roll < 0.94:
            ops = [('COPY', ('r', 0x40, 4), [('c', target(k), 4)]), ('BRANCHIND', None, [('r', 0x40, 4)])]
        elif roll < 0.96:
            ops = [('RETURN', None, [('r', 0x44, 4)])]
        else:
            ops = [('INT_ADD', ('r', rng.choice(regs), 4), [('r', rng.choice(regs), 4), ('c', 3, 4)])]
        insns.append((base + k, 1, ops))
    return insns


class CompiledDifferentialTests(unittest.TestCase):
    def test_random_x87_programs_match_canonical_translation(self):
        cc = find_cc()
        if not cc:
            self.skipTest("C compiler not available")
        pe = SimpleNamespace(imports=lambda: [], exports=lambda: [], image_base=0x400000,
                             size_of_image=0x400000, entry_rva=0)
        saved = pcode2c.CHUNK
        pcode2c.CHUNK = 8
        removed_moves = 0
        try:
            with tempfile.TemporaryDirectory() as directory:
                for seed in range(12):
                    insns = build_program(random.Random(seed))
                    sources = []
                    for ident, virtual in (("bas", 0), ("can", seed % 2 + 1)):
                        parts, _, unsupported = pcode2c.generate(
                            insns, {}, pe, "T.exe", ident, parts=1, x87_virtual_stack=virtual > 0,
                            x87_value_cache=virtual == 2)
                        self.assertFalse(unsupported)
                        sources.append(parts[0])
                    moves = [len(re.findall(r'wr\(guest_regs\+0x11[0-7]0,10,', s)) for s in sources]
                    removed_moves += moves[0] - moves[1]
                    count = len(insns)
                    n = (count + 7) // 8
                    decls = "".join(f"void {i}_chunk_{k}(void);" for i in ("bas", "can") for k in range(n))
                    starts = [insns[k * 8][0] for k in range(n)]
                    ends = [insns[min(k * 8 + 7, count - 1)][0] + 1 for k in range(n)]
                    harness = HARNESS % dict(
                        decls=decls, n=n, count=count, first=insns[0][0], trials=2000,
                        base=",".join(f"bas_chunk_{k}" for k in range(n)),
                        cand=",".join(f"can_chunk_{k}" for k in range(n)),
                        starts=",".join(f"{s}u" for s in starts),
                        ends=",".join(f"{e}u" for e in ends))
                    source = Path(directory) / f"x{seed}.c"
                    source.write_text("\n".join(sources) + harness)
                    exe = Path(directory) / f"x{seed}.exe"
                    for opt, strict in (("-O0", ["-DSTRICT"]), ("-O2", [])):
                        p = subprocess.run([cc, opt, *strict, "-I" + str(ROOT / "tools/recomp"), str(source),
                                            "-lm", "-o", str(exe)], capture_output=True, text=True,
                                           timeout=120)
                        self.assertEqual(p.returncode, 0, p.stderr[:3000])
                        q = subprocess.run([str(exe)], capture_output=True, text=True, timeout=60)
                        self.assertEqual(q.returncode, 0, f"seed {seed} {opt}: {q.stdout} {q.stderr[:800]}")
        finally:
            pcode2c.CHUNK = saved

    def test_straight_line_math_drops_most_stack_moves(self):
        # Shape of the hot vector transform: FLD/FMUL/FADDP runs, one exit.
        rng = random.Random(3)
        insns = []
        for k in range(48):
            r = k % 4
            ops = (list(PUSH) + [('INT2FLOAT', st(0), [('r', 0x10, 4)])] if r in (0, 1) else
                   [('FLOAT_MULT', st(0), [st(0), st(1)])] if r == 2 else
                   [('FLOAT_ADD', st(1), [st(1), st(0)])] + list(POP))
            insns.append((0x1000 + k, 1, ops))
        insns.append((0x1000 + 48, 1, [('RETURN', None, [('r', 0x44, 4)])]))
        pe = SimpleNamespace(imports=lambda: [], exports=lambda: [], image_base=0x400000,
                             size_of_image=0x400000, entry_rva=0)
        counts = []
        for virtual in (False, True):
            parts, _, _ = pcode2c.generate(insns, {}, pe, "T.exe", "t", x87_virtual_stack=virtual)
            fast = parts[0].split('PC=(uint32_t)')[0]  # fast lane up to the RETURN
            counts.append(len(re.findall(r'wr\(guest_regs\+0x11[0-7]0,10,', fast)))
        self.assertLess(counts[1] * 3, counts[0], counts)


if __name__ == "__main__":
    unittest.main()
