"""Proven-dead local unique temporaries in p-code instruction CFGs.

Only independent, nonfaulting INTEGER p-code calculations are eligible.
The caller must have proven every unique byte read is defined locally by
pcode2c.temporary_layout; global unique storage cannot be optimized here.

A removed architectural flag write may orphan the intermediate operands
used to calculate it. This pass propagates liveness through every internal
conditional/relative branch and eliminates those orphaned operands too.
The output is a set of original p-code indices; labels never move.
"""

from __future__ import annotations

from flag_liveness import KNOWN, PURE


def _bytes(varnode):
    if varnode is None or varnode[0] != "u":
        return set()
    return set(range(varnode[1], varnode[1] + varnode[2]))


def _successors(ops, idx):
    """Intra-instruction successors; None means local-temp lifetime ends."""
    mnemonic, _, inputs = ops[idx]
    following = idx + 1 if idx + 1 < len(ops) else None
    if mnemonic in ("BRANCHIND", "CALLIND", "RETURN"):
        return (None,)
    if mnemonic in ("BRANCH", "CALL", "CBRANCH"):
        target = None
        if inputs and inputs[0] and inputs[0][0] == "c":
            off = inputs[0][1]
            signed = off - (1 << 64) if off >= (1 << 63) else off
            candidate = idx + signed
            if 0 <= candidate < len(ops):
                target = candidate
        return (following, target) if mnemonic == "CBRANCH" else (target,)
    return (following,)


def dead_unique_writes(ops, *, removed_flags=()):
    """Return dead pure writes into *local* 'u' storage, to omit entirely.

    Caller MUST prove instruction-local unique storage is safe. Flags
    removed by the existing cross-instruction proof are treated as no-ops;
    their unique inputs are not live. Unknown p-code/userops conservatively
    observe all unique bytes. Potentially faulting operations are retained.
    """
    if not ops:
        return set()
    n = len(ops)
    prior_dead = frozenset(removed_flags)
    if any(not (0 <= i < n) for i in prior_dead):
        raise ValueError("invalid pre-eliminated p-code index")
    universe = set()
    for _, out, inputs in ops:
        universe.update(_bytes(out))
        for inp in inputs:
            universe.update(_bytes(inp))
    if not universe:
        return set()

    edges = [_successors(ops, i) for i in range(n)]
    writes = [_bytes(op[1]) for op in ops]
    reads = [set().union(*(_bytes(v) for v in op[2])) if op[2] else set()
             for op in ops]
    # We don't remove operations that can fault, have effects, or are not
    # fully implemented. Unknown operations may access guest unique storage.
    barriers = {i for i, (mn, _, _) in enumerate(ops)
                if mn not in KNOWN or mn == 'CALLOTHER'}
    safe = {i for i, (mn, out, inputs) in enumerate(ops)
            if mn in PURE and out is not None and out[0] == "u"
            and out[2] > 0 and all(v is None or v[0] != "m" for v in inputs)}

    discarded = set(prior_dead)
    removed = set()
    while True:
        live = [set() for _ in ops]
        # Termination is monotonic over a finite set of unique bytes.
        while True:
            changed = False
            for i in range(n - 1, -1, -1):
                if i in discarded:
                    before = set().union(*(live[x] for x in edges[i] if x is not None))
                else:
                    after = set().union(*(live[x] for x in edges[i] if x is not None))
                    before = reads[i] | (after - writes[i])
                    if i in barriers:
                        before |= universe
                if before != live[i]:
                    live[i] = before
                    changed = True
            if not changed:
                break

        newly_dead = set()
        for i in safe - discarded:
            after = set().union(*(live[x] for x in edges[i] if x is not None))
            if not (writes[i] & after):
                newly_dead.add(i)
        if not newly_dead:
            return removed
        discarded.update(newly_dead)
        removed.update(newly_dead)
