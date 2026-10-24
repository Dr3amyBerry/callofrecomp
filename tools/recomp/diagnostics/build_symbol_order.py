#!/usr/bin/env python3
"""Build an lld symbol-ordering file from simpleperf symbol sample counts.

Input: text lines "<samples-or-percent> <symbol>" (e.g. simpleperf report
--sort symbol) or "<symbol>" alone (already ranked). Output: one symbol per
line, hottest first, deduplicated. Pure text transform; no ELF/saves read.
"""
import argparse, re
from pathlib import Path

def build_order(lines, limit=0, min_share=0.0):
    rows = []
    for i, line in enumerate(lines):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        m = re.match(r'^([0-9.]+)%?\s+(\S+)$', line)
        weight, sym = (float(m.group(1)), m.group(2)) if m else (-i, line.split()[-1])
        rows.append((weight, i, sym))
    rows.sort(key=lambda r: (-r[0], r[1]))
    total = sum(r[0] for r in rows if r[0] > 0) or 1.0
    out, seen = [], set()
    for w, _, sym in rows:
        if sym in seen or (w > 0 and w / total < min_share):
            continue
        seen.add(sym)
        out.append(sym)
        if limit and len(out) >= limit:
            break
    return out

def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument('--input', required=True, type=Path)
    p.add_argument('--out', required=True, type=Path)
    p.add_argument('--limit', type=int, default=0)
    p.add_argument('--min-share', type=float, default=0.0)
    a = p.parse_args()
    order = build_order(a.input.read_text(encoding='utf-8').splitlines(), a.limit, a.min_share)
    a.out.write_text('\n'.join(order) + '\n', encoding='utf-8')
    print(f'{len(order)} symbols -> {a.out}')

if __name__ == '__main__':
    main()
