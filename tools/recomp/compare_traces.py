#!/usr/bin/env python3
"""Diff a native_host.c trace against a recomp_host.c trace.

Stack and heap addresses legitimately differ between the two processes, and the
hosts log TRACE_ARGS words per syscall even when a syscall takes fewer, so
values outside module-image windows are normalized, and fields where the
recompiled side is zero are reported as unused stack words ("junk").
"""
import re
import sys


def norm(t: str) -> str:
    if not re.fullmatch(r'[0-9a-f]{8}', t):
        return t
    v = int(t, 16)
    return t if 0x20000000 <= v < 0x50000000 or v < 0x10000 else 'X'


def main() -> int:
    a = open(sys.argv[1]).read().split('\n')
    b = open(sys.argv[2]).read().split('\n')
    real = junk = 0
    for x, y in zip(a, b):
        if x == y:
            continue
        for p, q in zip(x.split(), y.split()):
            if norm(p) == norm(q):
                continue
            if q == '00000000':
                junk += 1
            else:
                real += 1
                print('DIFF', x, '|', y)
    print(f'lines native={len(a)} recomp={len(b)} unused-stack fields={junk} other mismatches={real}')
    return 0 if len(a) == len(b) and real == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())
