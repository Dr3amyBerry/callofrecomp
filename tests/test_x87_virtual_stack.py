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
from test_module_flag_liveness import HARNESS, find_cc  # noqa: E402


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
        elif roll < 0.72:    # partial view of a slot: ineligible
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
                for seed in range(8):
                    insns = build_program(random.Random(seed))
                    sources = []
                    for ident, virtual in (("bas", False), ("can", True)):
                        parts, _, unsupported = pcode2c.generate(
                            insns, {}, pe, "T.exe", ident, parts=1, x87_virtual_stack=virtual)
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
                    for opt in ("-O0", "-O2"):
                        p = subprocess.run([cc, opt, "-I" + str(ROOT / "tools/recomp"), str(source),
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
