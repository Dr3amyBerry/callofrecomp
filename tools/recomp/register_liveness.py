"""Conservative full-register liveness for generated x86 p-code chunks.

Eliminate only nonfaulting architectural register writes whose every byte is
provably overwritten along all paths before any read or dispatcher exit.
All register bytes are observable at exits, indirect branches, and unknown
operations. Guest memory and PC side effects remain unchanged.
"""
from __future__ import annotations

from collections import deque

from flag_liveness import KNOWN, PURE, FLAGS


def _bytes(v):
    if not v or v[0] != "r" or v[2] <= 0:
        return 0
    return ((1 << v[2]) - 1) << v[1]


def dead_arch_register_writes(chunk, *, removed_flags=(), eligible_ranges=()):
    """Return (instruction_index, operation_index) pairs of provably dead R writes.

    All R bytes are observable at every exit. CALLOTHER and unknown operations
    are full-register barriers. Only PURE p-code operations without RAM
    operands are eligible; eligible_ranges lists closed-open guest PC windows.
    Other instructions participate in the proof but are not transformed.
    """
    if not chunk or not eligible_ranges:
        return set()
    addresses = {addr: j for j, (addr, _, _) in enumerate(chunk)}
    nodes = [(j, i) for j, (_, _, ops) in enumerate(chunk) for i in range(len(ops))]
    if not nodes:
        return set()
    flagged = frozenset(removed_flags)
    if not flagged <= set(nodes):
        raise ValueError("invalid removed flag position")

    def entry(address):
        seen = set()
        while address in addresses and address not in seen:
            seen.add(address)
            j = addresses[address]
            if chunk[j][2]:
                return (j, 0)
            nxt = chunk[j][0] + chunk[j][1]
            if j + 1 < len(chunk) and chunk[j + 1][0] == nxt:
                address = nxt
            else:
                return None
        return None

    # Byte bitsets can span all of R, but the universe includes only outputs
    # eligible for removal within the targeted hot function.
    universe = 0
    flag_bytes = sum(1 << k for k in FLAGS)
    for j, (addr, _, ops) in enumerate(chunk):
        if not any(lo <= addr < hi for lo, hi in eligible_ranges):
            continue
        for i, (mn, out, ins) in enumerate(ops):
            if (j, i) in flagged:
                continue
            if (mn in PURE and out and out[0] == "r" and
                    not any(v and v[0] == "m" for v in ins)):
                written = _bytes(out)
                if written and not written & flag_bytes:
                    universe |= written
    if not universe:
        return set()

    successors = {}
    predecessors = {node: [] for node in nodes}
    reads, writes = {}, {}
    candidates = set()
    barriers = set()
    for node in nodes:
        j, i = node
        addr, length, ops = chunk[j]
        mn, out, ins = ops[i]
        if node in flagged:
            rd = wr = 0
        else:
            rd = 0
            for v in ins:
                rd |= _bytes(v) & universe
            wr = _bytes(out) & universe
        reads[node], writes[node] = rd, wr
        following = (j, i + 1) if i + 1 < len(ops) else (
            entry(addr + length) if j + 1 < len(chunk) and
            chunk[j + 1][0] == addr + length else None)
        targets = [following]
        if mn in ("BRANCH", "CALL", "CBRANCH"):
            target = None
            if ins and ins[0]:
                space, off, _ = ins[0]
                if space == "c":
                    relative = off - (1 << 64) if off >= 1 << 63 else off
                    k = i + relative
                    if 0 <= k < len(ops):
                        target = (j, k)
                    elif k >= len(ops):
                        target = entry(addr + length)
                elif space == "m":
                    target = entry(off)
            targets = [following, target] if mn == "CBRANCH" else [target]
        elif mn in ("BRANCHIND", "CALLIND", "RETURN"):
            targets = [None]
        successors[node] = tuple(targets)
        if mn not in KNOWN or mn == "CALLOTHER":
            barriers.add(node)
        if (node not in flagged and mn in PURE and out and out[0] == "r"
                and _bytes(out) and _bytes(out) & universe == _bytes(out)
                and not any(v and v[0] == "m" for v in ins)
                and any(lo <= addr < hi for lo, hi in eligible_ranges)):
            candidates.add(node)
    for node, targets in successors.items():
        for target in targets:
            if target is not None:
                predecessors[target].append(node)

    live = {node: 0 for node in nodes}
    pending = deque(nodes)
    queued = set(nodes)
    while pending:
        node = pending.popleft()
        queued.discard(node)
        after = 0
        for target in successors[node]:
            after |= universe if target is None else live[target]
        before = (after if node in flagged else
                  ((after & ~writes[node]) | reads[node]))
        if node in barriers:
            before |= universe
        if before != live[node]:
            live[node] = before
            for parent in predecessors[node]:
                if parent not in queued:
                    pending.append(parent)
                    queued.add(parent)
    dead = set()
    for node in candidates:
        after = 0
        for target in successors[node]:
            after |= universe if target is None else live[target]
        if not (writes[node] & after):
            dead.add(node)
    return dead
