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
from flag_liveness import dead_flag_writes
from function_map import build_function_map, write_function_map

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


def temporary_layout(ops):
    """Compact byte aliases, only when each read is defined on every entry path.

    Relative p-code branches can bypass writes or loop inside an instruction.
    Unproven inputs require the module's original global unique space.
    """
    count = len(ops)
    reads, writes, successors = [], [], []
    for i, (mn, out, inputs) in enumerate(ops):
        reads.append({b for v in inputs if v and v[0] == 'u'
                      for b in range(v[1], v[1] + v[2])})
        writes.append(set(range(out[1], out[1] + out[2]))
                      if out and out[0] == 'u' else set())
        edges = [i + 1] if i + 1 < count else []
        if mn in ('BRANCH', 'CALL', 'CBRANCH'):
            target = i + rel(inputs[0][1]) if inputs[0][0] == 'c' else -1
            branch = [target] if 0 <= target < count else []
            edges = edges + branch if mn == 'CBRANCH' else branch
        elif mn in ('BRANCHIND', 'CALLIND', 'RETURN'):
            edges = []
        successors.append(edges)
    universe = set().union(*reads, *writes)
    if not universe:
        return {}
    reachable, pending = set(), [0]
    while pending:
        i = pending.pop()
        if i in reachable or i >= count:
            continue
        reachable.add(i)
        pending.extend(successors[i])
    predecessors = [[] for _ in ops]
    for i in reachable:
        for target in successors[i]:
            predecessors[target].append(i)
    defined = [set(universe) for _ in ops]
    defined[0] = set()
    changed = True
    while changed:
        changed = False
        for i in sorted(reachable):
            before = (set.intersection(*(defined[p] | writes[p] for p in predecessors[i]))
                      if i and predecessors[i] else set())
            if before != defined[i]:
                defined[i] = before
                changed = True
    if any(not reads[i] <= defined[i] for i in reachable):
        return None
    return {byte: i for i, byte in enumerate(sorted(universe))}


class Gen:
    def __init__(self, userops):
        self.userops = userops
        self.unsupported = {}
        self.temp_offsets = None

    def rd(self, v):
        sp, off, sz = v
        if sp == 'c':
            return f'(u128)0x{off & ((1 << (8 * min(sz, 8))) - 1):x}ULL'
        unique = f'T+{self.temp_offsets[off]}' if sp == 'u' and self.temp_offsets is not None else f'U+0x{off:x}'
        base = {'r': f'R+0x{off:x}', 'u': unique, 'm': f'G(0x{off:x}u)'}[sp]
        return f'rd({base},{sz})'

    def wr(self, v, expr):
        sp, off, sz = v
        unique = f'T+{self.temp_offsets[off]}' if sp == 'u' and self.temp_offsets is not None else f'U+0x{off:x}'
        base = {'r': f'R+0x{off:x}', 'u': unique, 'm': f'G(0x{off:x}u)'}[sp]
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
            if isz <= 8 and ins[1][2] <= 8:
                left = f'(int64_t){sa(a, isz)}'
                right = f'(int64_t){sa(b, ins[1][2])}'
                expr = f'(u128)({left}{o}{right})'
                # The wide reference can represent MIN/-1. Native signed
                # division cannot, even when the eventual output is narrowed.
                if isz == 8:
                    overflow = '(u128)0' if o == '%' else '((u128)1<<63)'
                    expr = f'(({left}==INT64_MIN && {right}==-1) ? {overflow} : {expr})'
                return self.wr(out, m(expr))
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
            if name in ('LOCK', 'UNLOCK'):
                return ';'  # lock-prefix markers: single guest thread, nothing to do
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


def generate(insns, userops, pe: PEFile, name: str, ident: str, parts: int = 1,
             local_temporaries: bool = True, separate_spaces: bool = True,
             eliminate_dead_flags: bool = True):
    """Return ([part sources], main source, unsupported ops)."""
    g = Gen(userops)
    # Silent per-module fallback could mix local writers with another module's
    # global readers. Refuse instead; diagnostic global storage must be selected
    # consistently for all linked modules when such dependencies exist.
    if local_temporaries:
        for addr, _, ops in insns:
            if temporary_layout(ops) is None:
                raise ValueError(f'unproven unique input at {addr:08x}; regenerate ALL linked '
                                 'modules with --global-temporaries')
    chunks = [insns[i:i + CHUNK] for i in range(0, len(insns), CHUNK)]
    header = [f'// Generated by tools/recomp/pcode2c.py from {name}. Do not commit.',
              '#include "recomp_rt.h"', '']
    bodies = [list(header) for _ in range(parts)]
    for ci, chunk in enumerate(chunks):
        dead_flags = dead_flag_writes(chunk) if eliminate_dead_flags else set()
        out = bodies[ci * parts // len(chunks)]
        start = len(out)
        unsupported_before = dict(g.unsupported)
        addrs = {a for a, _, _ in chunk}
        out.append(f'void {ident}_chunk_{ci}(void) {{')
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
            g.temp_offsets = temporary_layout(ops) if local_temporaries else None
            if g.temp_offsets is not None:
                out.append(f' {{ uint8_t T[{max(1, len(g.temp_offsets))}];')
            for i, (mn, o, ins) in enumerate(ops):
                jump.__defaults__[0][0] = i
                if i in rel_targets:
                    out.append(f' L_{addr:x}_{i}:;')
                # Keep every p-code index/label: relative branches use indices.
                out.append(' ;' if (idx, i) in dead_flags else
                           ' ' + g.op(mn, o, ins, jump, None))
            if len(ops) in rel_targets:
                out.append(f' L_{addr:x}_{len(ops)}:;')
            following = chunk[idx + 1][0] if idx + 1 < len(chunk) else None
            if following != nxt:
                out.append(f' PC=0x{nxt:x}u; return;')
            if g.temp_offsets is not None:
                out.append(' }')
        out.append('dyn:')
        out.append(' switch (PC) {')
        out.extend(f'  case 0x{a:x}u: goto L_{a:x};' for a, _, _ in chunk)
        out.append('  default: recomp_miss = 1; return;')
        out.append(' }')
        out.append('}')
        out.append('')
        if separate_spaces and g.unsupported == unsupported_before:
            # guest_init reserves RAM separately from the static register array.
            # Restrict only these two spaces, not addresses within either space.
            # Fatal diagnostics read global registers: retain their old path.
            body = [line.replace('R+', 'guest_regs+').replace('G(', 'GR(')
                    for line in out[start:]]
            body[0] = (f'static void {ident}_chunk_{ci}_spaces('
                       'uint8_t *restrict guest_regs, uint8_t *restrict guest_mem) {')
            body[1:1] = ['#define GR(a) (guest_mem + (uint32_t)(a))']
            body.append('#undef GR')
            body.append(f'void {ident}_chunk_{ci}(void) {{ '
                        f'{ident}_chunk_{ci}_spaces(R, MEM); }}')
            out[start:] = body
    out = list(header)
    out.extend(f'void {ident}_chunk_{ci}(void);' for ci in range(len(chunks)))
    out.append('static const recomp_chunk chunks[] = {')
    for ci, chunk in enumerate(chunks):
        out.append(f' {{0x{chunk[0][0]:x}u, 0x{chunk[-1][0] + chunk[-1][1]:x}u, {ident}_chunk_{ci}}},')
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
    def join(lines):
        return '\n'.join(lines) + '\n'
    return [join(b) for b in bodies], join(out), g.unsupported


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('pcode', type=Path)
    ap.add_argument('pe', type=Path)
    ap.add_argument('-o', '--out', type=Path, required=True,
                    help='main C file; with --parts N, chunk code goes to <out>_p<k>.c')
    ap.add_argument('--parts', type=int, default=1, help='split chunk code into N files for parallel builds')
    ap.add_argument('--global-temporaries', action='store_true',
                    help='diagnostic: retain global unique space consistently for all linked modules')
    ap.add_argument('--shared-spaces', action='store_true',
                    help='diagnostic: omit disjoint RAM/register alias information')
    ap.add_argument('--keep-dead-flags', action='store_true',
                    help='diagnostic: retain flag writes even when provably unobserved')
    ap.add_argument('--function-map-out', type=Path,
                    help='optional JSON: original Ghidra function entries to generated chunks; '
                         'store under ignored recomp_out/')
    args = ap.parse_args()
    if args.function_map_out:
        protected = {args.pcode.resolve(), args.pe.resolve(), args.out.resolve()}
        protected.update(args.out.with_name(f'{args.out.stem}_p{k}.c').resolve()
                         for k in range(args.parts))
        if args.function_map_out.resolve() in protected:
            ap.error('--function-map-out must not overwrite input or generated C files')
    insns, userops, funcs = parse(args.pcode)
    limits = {'r': 0x2000, 'u': 0x400000}  # must match R[] / U[] in runtime/guest.c
    for _, _, ops in insns:
        for _, o, ins in ops:
            for v in (o, *ins):
                if v and v[0] in limits and v[1] + v[2] > limits[v[0]]:
                    raise SystemExit(f'{v[0]} space offset 0x{v[1]:x} exceeds the runtime array')
    pe = PEFile(args.pe)
    ident = ''.join(c if c.isalnum() else '_' for c in args.pe.stem.lower())
    bodies, main_src, unsupported = generate(insns, userops, pe, args.pe.name, ident, args.parts,
                                             not args.global_temporaries, not args.shared_spaces,
                                             not args.keep_dead_flags)
    if args.parts == 1:
        args.out.write_text(bodies[0] + main_src.split('\n', 3)[3])  # drop the repeated header
        files = [args.out]
    else:
        files = [args.out.with_name(f'{args.out.stem}_p{k}.c') for k in range(args.parts)]
        for f, b in zip(files, bodies):
            f.write_text(b)
        args.out.write_text(main_src)
        files.append(args.out)
    if args.function_map_out:
        mapping = build_function_map([(addr, length) for addr, length, _ in insns],
                                     funcs, args.pe.name, parts=args.parts, chunk_size=CHUNK)
        write_function_map(args.function_map_out, mapping)
    print(f'{len(insns)} instructions -> ' + ' '.join(str(f) for f in files))
    if unsupported:
        print('unsupported:', unsupported)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
