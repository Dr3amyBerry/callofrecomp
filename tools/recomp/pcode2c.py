#!/usr/bin/env python3
"""Static recompiler prototype: Ghidra raw p-code (ExportPcode.java) -> portable C.

Every guest instruction becomes a labelled block of C statements operating on
the register (R), unique (U) and guest RAM spaces. Control flow is a whole-
program state machine: direct branches inside a chunk are gotos, anything else
sets PC and returns to the dispatcher in recomp_rt.c. CALL/RETURN are plain
jumps because the p-code already pushes/pops the guest return address.

The generated C is derived from proprietary code: write it under recomp_out/.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pe_inspect import PEFile  # noqa: E402

CHUNK = 1500


def rel(off: int) -> int:
    """Signed relative p-code branch offset (Ghidra prints it as unsigned 64-bit)."""
    return off - (1 << 64) if off >= 1 << 63 else off


def parse(path: Path):
    insns, userops, funcs = [], {}, []
    cur = None
    for line in path.read_text().splitlines():
        tag = line[:1]
        if tag == 'I':
            _, a, n = line.split()
            cur = (int(a), int(n), [])
            insns.append(cur)
        elif tag == 'P':
            parts = line.split()
            vns = [None if v == '-' else (lambda s: (s[0], int(s[1], 16), int(s[2])))(v.split(':'))
                   for v in parts[2:]]
            cur[2].append((parts[1], vns[0], vns[1:]))
        elif tag == 'U':
            _, i, name = line.split(maxsplit=2)
            userops[int(i)] = name
        elif tag == 'F':
            funcs.append(int(line.split()[1]))
    insns.sort()
    return insns, userops, funcs


class Gen:
    def __init__(self, userops):
        self.userops = userops
        self.unsupported = {}

    def rd(self, v):
        sp, off, sz = v
        if sp == 'c':
            return f'(u128)0x{off & ((1 << (8 * min(sz, 8))) - 1):x}ULL'
        base = {'r': f'R+0x{off:x}', 'u': f'U+0x{off:x}', 'm': f'G(0x{off:x}u)'}[sp]
        return f'rd({base},{sz})'

    def wr(self, v, expr):
        sp, off, sz = v
        base = {'r': f'R+0x{off:x}', 'u': f'U+0x{off:x}', 'm': f'G(0x{off:x}u)'}[sp]
        return f'wr({base},{sz},{expr});'

    def op(self, mnem, out, ins, jump, rel_label):
        a = self.rd(ins[0]) if ins and ins[0] else None
        b = self.rd(ins[1]) if len(ins) > 1 else None
        osz = out[2] if out else 0
        isz = ins[0][2] if ins else 0
        m = lambda e: f'mask({e},{osz})'  # noqa: E731
        sa = lambda x, n: f'sx({x},{n})'  # noqa: E731
        bin_ops = {'INT_ADD': '+', 'INT_SUB': '-', 'INT_MULT': '*', 'INT_AND': '&',
                   'INT_OR': '|', 'INT_XOR': '^'}
        cmp_ops = {'INT_EQUAL': '==', 'INT_NOTEQUAL': '!=', 'INT_LESS': '<', 'INT_LESSEQUAL': '<='}
        scmp = {'INT_SLESS': '<', 'INT_SLESSEQUAL': '<='}
        fbin = {'FLOAT_ADD': '+', 'FLOAT_SUB': '-', 'FLOAT_MULT': '*', 'FLOAT_DIV': '/'}
        fcmp = {'FLOAT_EQUAL': '==', 'FLOAT_NOTEQUAL': '!=', 'FLOAT_LESS': '<', 'FLOAT_LESSEQUAL': '<='}
        fa = lambda i: f'f2d({self.rd(ins[i])},{ins[i][2]})'  # noqa: E731

        if mnem == 'COPY':
            return self.wr(out, a)
        if mnem == 'LOAD':
            return self.wr(out, f'rd(G((uint32_t){b}),{osz})')
        if mnem == 'STORE':
            return f'wr(G((uint32_t){b}),{ins[2][2]},{self.rd(ins[2])});'
        if mnem in bin_ops:
            return self.wr(out, m(f'({a}{bin_ops[mnem]}{b})'))
        if mnem in ('INT_DIV', 'INT_REM'):
            return self.wr(out, m(f'({a}{"/" if mnem == "INT_DIV" else "%"}{b})'))
        if mnem in ('INT_SDIV', 'INT_SREM'):
            o = '/' if mnem == 'INT_SDIV' else '%'
            return self.wr(out, m(f'(u128)({sa(a, isz)}{o}{sa(b, ins[1][2])})'))
        if mnem == 'INT_LEFT':
            return self.wr(out, m(f'shl({a},{b})'))
        if mnem == 'INT_RIGHT':
            return self.wr(out, m(f'shr({a},{b})'))
        if mnem == 'INT_SRIGHT':
            return self.wr(out, m(f'sar({a},{b},{isz})'))
        if mnem in cmp_ops:
            return self.wr(out, f'(u128)({a}{cmp_ops[mnem]}{b})')
        if mnem in scmp:
            return self.wr(out, f'(u128)({sa(a, isz)}{scmp[mnem]}{sa(b, isz)})')
        if mnem == 'INT_CARRY':
            return self.wr(out, f'(u128)(mask({a}+{b},{isz})<{a})')
        if mnem == 'INT_SCARRY':
            return self.wr(out, f'scarry({a},{b},{isz})')
        if mnem == 'INT_SBORROW':
            return self.wr(out, f'sborrow({a},{b},{isz})')
        if mnem == 'INT_ZEXT':
            return self.wr(out, a)
        if mnem == 'INT_SEXT':
            return self.wr(out, m(f'(u128){sa(a, isz)}'))
        if mnem == 'INT_NEGATE':
            return self.wr(out, m(f'(~{a})'))
        if mnem == 'INT_2COMP':
            return self.wr(out, m(f'(-{a})'))
        if mnem == 'BOOL_NEGATE':
            return self.wr(out, f'(u128)!{a}')
        if mnem in ('BOOL_AND', 'BOOL_OR', 'BOOL_XOR'):
            o = {'BOOL_AND': '&', 'BOOL_OR': '|', 'BOOL_XOR': '^'}[mnem]
            return self.wr(out, f'(({a}{o}{b})&1)')
        if mnem == 'PIECE':
            return self.wr(out, m(f'(({a}<<{8 * ins[1][2]})|{b})'))
        if mnem == 'SUBPIECE':
            return self.wr(out, m(f'({a}>>{8 * ins[1][1]})'))
        if mnem == 'POPCOUNT':
            return self.wr(out, f'popc({a})')
        if mnem in fbin:
            return self.wr(out, f'd2f({fa(0)}{fbin[mnem]}{fa(1)},{osz})')
        if mnem in fcmp:
            return self.wr(out, f'(u128)({fa(0)}{fcmp[mnem]}{fa(1)})')
        if mnem == 'FLOAT_NAN':
            return self.wr(out, f'(u128)isnan({fa(0)})')
        if mnem in ('FLOAT_NEG', 'FLOAT_ABS', 'FLOAT_SQRT', 'FLOAT_CEIL', 'FLOAT_FLOOR', 'ROUND',
                    'FLOAT2FLOAT'):
            fn = {'FLOAT_NEG': '-', 'FLOAT_ABS': 'fabs', 'FLOAT_SQRT': 'sqrt', 'FLOAT_CEIL': 'ceil',
                  'FLOAT_FLOOR': 'floor', 'ROUND': 'nearbyint', 'FLOAT2FLOAT': ''}[mnem]
            return self.wr(out, f'd2f({fn}({fa(0)}),{osz})')
        if mnem == 'INT2FLOAT':
            return self.wr(out, f'd2f((double){sa(a, isz)},{osz})')
        if mnem == 'TRUNC':
            return self.wr(out, m(f'(u128)(__int128)ftrunc({fa(0)})'))
        if mnem == 'CALLOTHER':
            name = self.userops.get(ins[0][1], f'op{ins[0][1]}')
            args = ', '.join(f'f2d({self.rd(v)},{v[2]})' for v in ins[1:])
            if name == 'rdtsc':
                return self.wr(out, 'rdtsc_val()')
            if name in ('fsin', 'fcos', 'fptan', 'fpatan', 'fscale', 'fsqrt', 'f2xm1', 'fyl2x', 'frndint',
                        'log2'):
                return self.wr(out, f'd2f(x87_{name}({args}),{osz})') if out else ';'
            if name.startswith('cpuid'):
                return self.wr(out, f'cpuid_ptr()') if out else ';'
            self.unsupported[name] = self.unsupported.get(name, 0) + 1
            return f'unsupported("{name}");'
        if mnem in ('BRANCH', 'CALL'):
            return jump(ins[0])
        if mnem == 'CBRANCH':
            return f'if ({b}) {{ {jump(ins[0])} }}'
        if mnem in ('BRANCHIND', 'CALLIND', 'RETURN'):
            return f'PC=(uint32_t){a}; goto dyn;'
        self.unsupported[mnem] = self.unsupported.get(mnem, 0) + 1
        return f'unsupported("{mnem}");'


def generate(insns, userops, pe: PEFile, name: str, ident: str):
    g = Gen(userops)
    chunks = [insns[i:i + CHUNK] for i in range(0, len(insns), CHUNK)]
    out = [f'// Generated by tools/recomp/pcode2c.py from {name}. Do not commit.',
           '#include "recomp_rt.h"', '']
    for ci, chunk in enumerate(chunks):
        addrs = {a for a, _, _ in chunk}
        out.append(f'static void chunk_{ci}(void) {{')
        out.append(' goto dyn;')
        for idx, (addr, length, ops) in enumerate(chunk):
            nxt = addr + length
            rel_targets = {i + rel(v[1]) for i, (mn, _, ins) in enumerate(ops)
                           if mn in ('BRANCH', 'CBRANCH') for v in ins[:1] if v[0] == 'c'}

            def jump(v, i_ref=[0]):
                if v[0] == 'c':
                    t = i_ref[0] + rel(v[1])
                    return f'goto L_{addr:x}_{t};' if t < len(ops) else (
                        f'goto L_{nxt:x};' if nxt in addrs else f'PC=0x{nxt:x}u; return;')
                t = v[1]
                return f'goto L_{t:x};' if t in addrs else f'PC=0x{t:x}u; return;'
            out.append(f'L_{addr:x}:')
            for i, (mn, o, ins) in enumerate(ops):
                jump.__defaults__[0][0] = i
                if i in rel_targets:
                    out.append(f' L_{addr:x}_{i}:;')
                out.append(' ' + g.op(mn, o, ins, jump, None))
            if len(ops) in rel_targets:
                out.append(f' L_{addr:x}_{len(ops)}:;')
            following = chunk[idx + 1][0] if idx + 1 < len(chunk) else None
            if following != nxt:
                out.append(f' PC=0x{nxt:x}u; return;')
        out.append('dyn:')
        out.append(' switch (PC) {')
        out.extend(f'  case 0x{a:x}u: goto L_{a:x};' for a, _, _ in chunk)
        out.append('  default: recomp_miss = 1; return;')
        out.append(' }')
        out.append('}')
        out.append('')
    out.append('static const recomp_chunk chunks[] = {')
    for ci, chunk in enumerate(chunks):
        out.append(f' {{0x{chunk[0][0]:x}u, 0x{chunk[-1][0] + chunk[-1][1]:x}u, chunk_{ci}}},')
    out.append('};')
    imports = [(imp['dll'], f.get('name') or f'#{f["ordinal"]}', f['iat_va'])
               for imp in pe.imports() for f in imp['functions']]
    out.append('static const recomp_import imports[] = {')
    out.extend(f' {{"{d}", "{n}", 0x{va:x}u}},' for d, n, va in imports)
    out.append(' {0, 0, 0}')
    out.append('};')
    out.append('static const recomp_export exports[] = {')
    out.extend(f' {{"{e["name"]}", 0x{e["va"]:x}u}},' for e in pe.exports() if e.get('name'))
    out.append(' {0, 0}')
    out.append('};')
    out.append(f'const recomp_module recomp_module_{ident} = {{"{name}", 0x{pe.image_base:x}u, '
               f'0x{pe.size_of_image:x}u, 0x{pe.image_base + pe.entry_rva:x}u, chunks, {len(chunks)}, '
               f'imports, exports}};')
    return '\n'.join(out) + '\n', g.unsupported


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('pcode', type=Path)
    ap.add_argument('pe', type=Path)
    ap.add_argument('-o', '--out', type=Path, required=True)
    args = ap.parse_args()
    insns, userops, _ = parse(args.pcode)
    limits = {'r': 0x2000, 'u': 0x400000}  # must match R[] / U[] in runtime/guest.c
    for _, _, ops in insns:
        for _, o, ins in ops:
            for v in (o, *ins):
                if v and v[0] in limits and v[1] + v[2] > limits[v[0]]:
                    raise SystemExit(f'{v[0]} space offset 0x{v[1]:x} exceeds the runtime array')
    pe = PEFile(args.pe)
    ident = ''.join(c if c.isalnum() else '_' for c in args.pe.stem.lower())
    code, unsupported = generate(insns, userops, pe, args.pe.name, ident)
    args.out.write_text(code)
    print(f'{len(insns)} instructions -> {args.out}')
    if unsupported:
        print('unsupported:', unsupported)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
