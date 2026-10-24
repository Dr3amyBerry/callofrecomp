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
import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pe_inspect import PEFile  # noqa: E402
from flag_liveness import dead_flag_writes, dead_flag_writes_module
from temp_liveness import dead_unique_writes
from register_liveness import dead_arch_register_writes
from x87_stack_fusion import plan_x87_shift
from x87_virtual_stack import (VirtualStack, eligible as x87_eligible,
                               slot_index as x87_slot, uses_stack as x87_uses)
from function_map import build_function_map, write_function_map, scan_pcode_provenance

CHUNK = 1500

# Two disjoint original-body intervals within CoDSP p0. The adjacent p1
# hot body has private x87/FCOM patches, so it is intentionally excluded.
HOT_CODSP_DEAD_REGISTER_RANGES = (
    (0x004196F0, 0x00419779),
    (0x00419780, 0x00419ED6),
)
HOT_CODSP_PCODE_SHA256 = (
    '36f9093b386e03b4bcdc489cff2a708f7c0b8012e9a0fa78a7001bd3f125da1e'
)


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


# Only this profiled CoDSP 1.5 geometry body is eligible.
# Other modules, instructions, control-flow and overlapping register views
# retain the original store/load sequence exactly.
HOT_CODSP_REGISTER_CACHE_RANGES = (
    # This body is in original CoDSP p0, which has no unrelated private
    # source-level hot patches. Do not rewrite p1's FCOM/NaN experiments.
    (0x004196F0, 0x00419ED6),
)
# Only instructions whose side effects are completely modelled by Gen.op.
# Unknown CALLOTHER/unsupported operations can inspect R or abort.
CACHE_SAFE_OPS = frozenset({
    'COPY', 'LOAD', 'STORE',
    'INT_ADD', 'INT_SUB', 'INT_MULT', 'INT_AND', 'INT_OR', 'INT_XOR',
    'INT_LEFT',
    'INT_RIGHT', 'INT_SRIGHT', 'INT_EQUAL', 'INT_NOTEQUAL',
    'INT_LESS', 'INT_LESSEQUAL', 'INT_SLESS', 'INT_SLESSEQUAL',
    'INT_CARRY', 'INT_SCARRY', 'INT_SBORROW', 'INT_ZEXT',
    'INT_SEXT', 'INT_NEGATE', 'INT_2COMP', 'BOOL_NEGATE',
    'BOOL_AND', 'BOOL_OR', 'BOOL_XOR', 'PIECE', 'SUBPIECE',
    'POPCOUNT', 'FLOAT_ADD', 'FLOAT_SUB', 'FLOAT_MULT',
    'FLOAT_DIV', 'FLOAT_EQUAL', 'FLOAT_NOTEQUAL', 'FLOAT_LESS',
    'FLOAT_LESSEQUAL', 'FLOAT_NAN', 'FLOAT_NEG', 'FLOAT_ABS',
    'FLOAT_SQRT', 'FLOAT_CEIL', 'FLOAT_FLOOR', 'ROUND',
    'FLOAT2FLOAT', 'INT2FLOAT', 'TRUNC'
})


def instruction_register_cache(ops, removed=frozenset()):
    """Select whole, disjoint register varnodes in one linear p-code instruction.

    Avoid all internal control flow and CALLOTHER (may observe the live R
    array). Overlapping architectural views are never cached. The cache is
    flushed at *each instruction boundary*, including chunk exit/fallthrough.
    Return: selected varnodes -> (needs_input_load, needs_final_store).
    """
    if not ops or any(mn not in CACHE_SAFE_OPS
                      for mn, _, _ in ops):
        return {}
    used = {}
    for i, (_, out, inputs) in enumerate(ops):
        if i in removed:
            continue
        # Inputs are consumed before the corresponding p-code output.
        for v in inputs:
            if v is not None and v[0] == 'r':
                rec = used.setdefault(v, [0, False, False])
                rec[0] += 1
                if not rec[2]:
                    rec[1] = True
        if out is not None and out[0] == 'r':
            rec = used.setdefault(out, [0, False, False])
            rec[0] += 1
            rec[2] = True
    chosen = {}
    for reg, (occurrences, needs_load, wrote) in used.items():
        if not (1 <= reg[2] <= 16 and occurrences >= 2):
            continue
        if any(reg != other and
               reg[1] < other[1] + other[2] and
               other[1] < reg[1] + reg[2] for other in used):
            continue
        chosen[reg] = (needs_load, wrote)
    return chosen


class Gen:
    def __init__(self, userops):
        self.userops = userops
        self.unsupported = {}
        self.temp_offsets = None
        self.reg_cache = {}
        self.x87 = None  # VirtualStack while emitting a renamed-stack instruction

    def rd(self, v):
        if v[0] == 'r' and v in self.reg_cache:
            return self.reg_cache[v]
        if self.x87 is not None and (k := x87_slot(v)) is not None:
            return f'rd(R+0x{self.x87.phys(k):x},10)'
        sp, off, sz = v
        if sp == 'c':
            return f'(u128)0x{off & ((1 << (8 * min(sz, 8))) - 1):x}ULL'
        unique = f'T+{self.temp_offsets[off]}' if sp == 'u' and self.temp_offsets is not None else f'U+0x{off:x}'
        base = {'r': f'R+0x{off:x}', 'u': unique, 'm': f'G(0x{off:x}u)'}[sp]
        return f'rd({base},{sz})'

    def wr(self, v, expr):
        if v[0] == 'r' and v in self.reg_cache:
            return f'{self.reg_cache[v]}=mask({expr},{v[2]});'
        if self.x87 is not None and (k := x87_slot(v)) is not None:
            return f'wr(R+0x{self.x87.dest(k):x},10,{expr});'
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
            if self.x87 is not None and x87_slot(out) is not None and x87_slot(ins[0]) is not None:
                self.x87.alias(x87_slot(out), x87_slot(ins[0]))
                return ';'
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


EXIT_OPS = frozenset({'BRANCH', 'CALL', 'BRANCHIND', 'CALLIND', 'RETURN'})


def emit_virtual_stack_chunk(g, chunk, addrs, out, dead_flags, dead_registers,
                             dead_temps, local_temporaries):
    """Emit one chunk with the x87 stack renamed inside straight-line runs.

    Fast lane: instructions in order, eligible ones with a VirtualStack map.
    An instruction whose fast-lane entry map is not the identity gets no
    L_<addr> label there; its canonical copy (slow lane, after the fast lane)
    carries the label for dispatcher/branch entries and chains forward.
    """
    vs = VirtualStack()
    slow = []

    def emit(idx, fast, lane):
        addr, length, ops = chunk[idx]
        nxt = addr + length
        rel_targets = {i + rel(v[1]) for i, (mn, _, ins) in enumerate(ops)
                       if mn in ('BRANCH', 'CBRANCH') for v in ins[:1] if v[0] == 'c'}
        removed = {i for i in range(len(ops))
                   if (idx, i) in dead_flags or (idx, i) in dead_registers
                   or (idx, i) in dead_temps}
        g.temp_offsets = temporary_layout(ops) if local_temporaries else None
        g.x87 = vs if fast else None
        cur = [0]

        def flush():
            return (vs.flush_code() + ' ') if fast else ''

        def jump(v):
            if v[0] == 'c':
                t = cur[0] + rel(v[1])
                if t < len(ops):
                    return f'goto L_{addr:x}{lane}_{t};'
                return flush() + (f'goto L_{nxt:x};' if nxt in addrs else f'PC=0x{nxt:x}u; return;')
            t = v[1]
            return flush() + (f'goto L_{t:x};' if t in addrs else f'PC=0x{t:x}u; return;')
        lines = []
        if g.temp_offsets is not None:
            lines.append(f' {{ uint8_t T[{max(1, len(g.temp_offsets))}];')
        for i, (mn, o, ins) in enumerate(ops):
            cur[0] = i
            if i in rel_targets:
                lines.append(f' L_{addr:x}{lane}_{i}:;')
            if i in removed:
                lines.append(' ;')
                continue
            prefix = flush() if mn in ('BRANCHIND', 'CALLIND', 'RETURN') else ''
            lines.append(' ' + prefix + g.op(mn, o, ins, jump, None))
            if fast and mn in EXIT_OPS:
                vs.reset()  # following code is reachable only through labels
        if len(ops) in rel_targets:
            lines.append(f' L_{addr:x}{lane}_{len(ops)}:;')
        following = chunk[idx + 1][0] if idx + 1 < len(chunk) else None
        if following != nxt:
            lines.append(' ' + flush() + f'PC=0x{nxt:x}u; return;')
            if fast:
                vs.reset()
        elif not fast and lane:
            lines.append(f' goto L_{nxt:x};')
        if g.temp_offsets is not None:
            lines.append(' }')
        g.x87 = None
        return lines

    for idx, (addr, _, ops) in enumerate(chunk):
        rel_targets = {i + rel(v[1]) for i, (mn, _, ins) in enumerate(ops)
                       if mn in ('BRANCH', 'CBRANCH') for v in ins[:1] if v[0] == 'c'}
        removed = {i for i in range(len(ops))
                   if (idx, i) in dead_flags or (idx, i) in dead_registers
                   or (idx, i) in dead_temps}
        ok = x87_eligible(ops, removed, rel_targets)
        if not ok and not vs.identity():
            out.append(' ' + vs.flush_code())
            vs.reset()
        if vs.identity():
            out.append(f'L_{addr:x}:')
        else:
            slow.append(idx)
            out.append(f'/* L_{addr:x}: renamed x87 stack, canonical entry below */')
        out.extend(emit(idx, ok and (x87_uses(ops, removed) or not vs.identity()), ''))
    if slow:
        out.append('/* x87 virtual stack: canonical slow lane */')
    for idx in slow:
        out.append(f'L_{chunk[idx][0]:x}:')
        out.extend(emit(idx, False, '_s'))


def generate(insns, userops, pe: PEFile, name: str, ident: str, parts: int = 1,
             local_temporaries: bool = True, separate_spaces: bool = True,
             eliminate_dead_flags: bool = True, eliminate_dead_temporaries: bool = False,
             dead_temp_parts: frozenset[int] | None = None,
             cache_hot_registers: bool = False,
             prune_hot_register_writes: bool = False,
             x87_stack_shift_outline: bool = False,
             module_flag_liveness: bool = False,
             x87_virtual_stack: bool = False):
    """Return ([part sources], main source, unsupported ops)."""
    if x87_virtual_stack and (cache_hot_registers or x87_stack_shift_outline):
        raise ValueError('--x87-virtual-stack excludes register cache and shift outlining')
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
    module_dead = (dead_flag_writes_module(chunks)
                   if module_flag_liveness and eliminate_dead_flags else None)
    for ci, chunk in enumerate(chunks):
        dead_flags = (module_dead[ci] if module_dead is not None else
                      dead_flag_writes(chunk) if eliminate_dead_flags else set())
        dead_registers = (dead_arch_register_writes(
            chunk, removed_flags=dead_flags,
            eligible_ranges=HOT_CODSP_DEAD_REGISTER_RANGES)
            if prune_hot_register_writes and separate_spaces and ident == 'codsp'
            and any(any(lo <= addr < hi for lo, hi in HOT_CODSP_DEAD_REGISTER_RANGES)
                    for addr, _, _ in chunk) else set())
        output_part = ci * parts // len(chunks)
        dead_temps = set()
        if eliminate_dead_temporaries and local_temporaries and (
                dead_temp_parts is None or output_part in dead_temp_parts):
            dead_flags_by_instruction = {}
            for j, k in dead_flags:
                dead_flags_by_instruction.setdefault(j, set()).add(k)
            for j, (_, _, ops) in enumerate(chunk):
                if temporary_layout(ops) is not None:
                    for k in dead_unique_writes(
                            ops, removed_flags=dead_flags_by_instruction.get(j, ())):
                        dead_temps.add((j, k))
        out = bodies[ci * parts // len(chunks)]
        start = len(out)
        unsupported_before = dict(g.unsupported)
        addrs = {a for a, _, _ in chunk}
        out.append(f'void {ident}_chunk_{ci}(void) {{')
        out.append(' goto dyn;')
        if x87_virtual_stack:
            emit_virtual_stack_chunk(g, chunk, addrs, out, dead_flags, dead_registers,
                                     dead_temps, local_temporaries)
        for idx, (addr, length, ops) in enumerate(chunk if not x87_virtual_stack else ()):
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
            removed = {i for i in range(len(ops))
                       if (idx, i) in dead_flags or (idx, i) in dead_registers
                       or (idx, i) in dead_temps}
            cache = instruction_register_cache(ops, removed) if (
                cache_hot_registers and separate_spaces and ident == 'codsp'
                and any(lo <= addr <= hi for lo, hi in HOT_CODSP_REGISTER_CACHE_RANGES)
            ) else {}
            g.reg_cache = {reg: f'regcache_{reg[1]:x}_{reg[2]}' for reg in cache}
            shifts = (plan_x87_shift(ops, removed=removed, branch_targets=rel_targets)
                      if x87_stack_shift_outline and separate_spaces and
                      ident == 'codsp' and not cache and
                      not prune_hot_register_writes else {})
            scoped = g.temp_offsets is not None or bool(cache)
            if cache:
                out.append(' {')
                if g.temp_offsets is not None:
                    out.append(f' uint8_t T[{max(1, len(g.temp_offsets))}];')
            elif g.temp_offsets is not None:
                # Preserve byte-for-byte output for unaffected instructions.
                out.append(f' {{ uint8_t T[{max(1, len(g.temp_offsets))}];')
            for reg, (load, _) in cache.items():
                name = g.reg_cache[reg]
                initializer = f'=rd(R+0x{reg[1]:x},{reg[2]})' if load else ''
                out.append(f' u128 {name}{initializer};')
            for i, (mn, o, ins) in enumerate(ops):
                jump.__defaults__[0][0] = i
                if i in rel_targets:
                    out.append(f' L_{addr:x}_{i}:;')
                # Keep every p-code index/label: relative branches use indices.
                if i in removed:
                    out.append(' ;')
                elif i in shifts:
                    direction = shifts[i]
                    out.append((' codsp_x87_shift_' + direction +
                                '(R); /* CODSP_X87_SHIFT_OUTLINED */')
                               if direction else ' ;')
                else:
                    out.append(' ' + g.op(mn, o, ins, jump, None))
            for reg, (_, wrote) in cache.items():
                if wrote:
                    out.append(f' wr(R+0x{reg[1]:x},{reg[2]},{g.reg_cache[reg]});')
            g.reg_cache = {}
            if len(ops) in rel_targets:
                out.append(f' L_{addr:x}_{len(ops)}:;')
            following = chunk[idx + 1][0] if idx + 1 < len(chunk) else None
            if following != nxt:
                out.append(f' PC=0x{nxt:x}u; return;')
            if scoped:
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
                    .replace('codsp_x87_shift_push(R)', 'codsp_x87_shift_push(guest_regs)')
                    .replace('codsp_x87_shift_pop(R)', 'codsp_x87_shift_pop(guest_regs)')
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
    ap.add_argument('--prune-dead-temporaries', action='store_true',
                    help='EXPERIMENT: eliminate proven-dead integer unique calculations, OFF by default')
    ap.add_argument('--dead-temp-parts', type=str,
                    help='optional comma-separated output part numbers to constrain DCE, e.g. 1,8')
    ap.add_argument('--cache-hot-registers', action='store_true',
                    help='EXPERIMENT: cache nonoverlapping architectural registers inside '
                         'straight-line CoDSP geometry instructions only, OFF by default')
    ap.add_argument('--prune-hot-register-writes', action='store_true',
                    help='EXPERIMENT: omit provably dead architectural register writes '
                         'in the audited CoDSP p0 geometry body, OFF by default')
    ap.add_argument('--module-flag-liveness', action='store_true',
                    help='EXPERIMENT: flag DCE across chunk boundaries (static direct '
                         'edges within the module, natively hooked PCs stay live), OFF by default')
    ap.add_argument('--x87-stack-shift-outline', action='store_true',
                    help='EXPERIMENT: outline seven identical x87 register moves in verified '
                         'CoDSP 1.5 p-code; OFF by default')
    ap.add_argument('--x87-virtual-stack', action='store_true',
                    help='EXPERIMENT: rename the x87 register stack at translation time inside '
                         'straight-line runs (exact; canonical layout at every exit); OFF')
    ap.add_argument('--function-map-out', type=Path,
                    help='optional JSON: original Ghidra function entries to generated chunks; '
                         'store under ignored recomp_out/')
    args = ap.parse_args()
    dead_temp_parts = None
    if args.dead_temp_parts:
        if not args.prune_dead_temporaries:
            ap.error('--dead-temp-parts requires --prune-dead-temporaries')
        try:
            chosen = [int(x) for x in args.dead_temp_parts.split(',')]
        except ValueError:
            ap.error('--dead-temp-parts must be comma-separated integers')
        if not chosen or any(x < 0 or x >= args.parts for x in chosen):
            ap.error('--dead-temp-parts contains an invalid output part')
        dead_temp_parts = frozenset(chosen)
    if args.function_map_out:
        protected = {args.pcode.resolve(), args.pe.resolve(), args.out.resolve()}
        protected.update(args.out.with_name(f'{args.out.stem}_p{k}.c').resolve()
                         for k in range(args.parts))
        if args.function_map_out.resolve() in protected:
            ap.error('--function-map-out must not overwrite input or generated C files')
    if args.x87_stack_shift_outline and (
            args.cache_hot_registers or args.prune_hot_register_writes or
            args.shared_spaces):
        ap.error('--x87-stack-shift-outline cannot combine with register caching, '
                 'register-write pruning or shared spaces')
    if args.cache_hot_registers or args.prune_hot_register_writes or args.x87_stack_shift_outline:
        # Neither pass is safe to generalize to unknown game executables.
        # In particular, the full-register DCE needs disjoint R and guest RAM.
        if (args.pe.name.casefold() != 'codsp.exe' or
                hashlib.sha256(args.pcode.read_bytes()).hexdigest() != HOT_CODSP_PCODE_SHA256):
            ap.error('experimental register optimizations require verified '
                     'CoDSP.exe 1.5 p-code')
    if args.prune_hot_register_writes and (args.shared_spaces or args.global_temporaries):
        ap.error('--prune-hot-register-writes requires the disjoint register/RAM '
                 'and local temporary layout')
    if args.x87_virtual_stack and (args.cache_hot_registers or args.x87_stack_shift_outline):
        ap.error('--x87-virtual-stack excludes --cache-hot-registers and --x87-stack-shift-outline')
    if args.module_flag_liveness and args.keep_dead_flags:
        ap.error('--module-flag-liveness conflicts with --keep-dead-flags')
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
                                             not args.keep_dead_flags, args.prune_dead_temporaries,
                                             dead_temp_parts, args.cache_hot_registers,
                                             args.prune_hot_register_writes,
                                             args.x87_stack_shift_outline,
                                             args.module_flag_liveness,
                                             args.x87_virtual_stack)
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
        _, _, bodies = scan_pcode_provenance(args.pcode)
        mapping = build_function_map([(addr, length) for addr, length, _ in insns],
                                     funcs, args.pe.name, parts=args.parts, chunk_size=CHUNK,
                                     function_bodies=bodies)
        write_function_map(args.function_map_out, mapping)
    print(f'{len(insns)} instructions -> ' + ' '.join(str(f) for f in files))
    if unsupported:
        print('unsupported:', unsupported)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
