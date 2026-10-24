"""Translation-time renaming of the x87 register stack (exact, opt-in).

Ghidra models ST0..ST7 as eight fixed 10-byte registers at 0x1100+16*k and
implements every push/pop/FXCH as COPYs that rotate all slots. Translated
literally that is ~8 ten-byte memory moves per FLD/FSTP.

Inside a straight-line run of eligible instructions this keeps a map
logical slot -> physical slot instead: slot-to-slot COPYs only update the
map, reads/writes go to the mapped physical slot, and the canonical layout
is restored (a parallel move) before every exit from the run: branches,
calls, returns, chunk exits, ineligible instructions. The values themselves
never change, so the result is bit-identical at every observable point.

Entering the middle of a run via the dispatcher or a branch must see the
canonical layout: those instructions are emitted a second time in canonical
form ("slow lane", labelled L_<addr>), chaining until the next instruction
whose fast-lane entry map is the identity.

Known limit: a host fault (guest memory access) in the middle of a run sees
renamed physical slots. Translated code already elides most per-instruction
PC stores, so fault resumption with exact x87 state was not modelled before.
"""
from __future__ import annotations

FIRST = 0x1100
STEP = 16
WIDTH = 10
SLOTS = tuple(FIRST + STEP * k for k in range(8))
LAST_END = FIRST + STEP * 8


def slot_index(v):
    """Logical slot 0..7 for an exact x87 register varnode, else None."""
    if v is None or v[0] != 'r' or v[2] != WIDTH:
        return None
    off = v[1] - FIRST
    if 0 <= off < STEP * 8 and off % STEP == 0:
        return off // STEP
    return None


def touches_stack(v):
    return v is not None and v[0] == 'r' and v[1] < LAST_END and FIRST < v[1] + v[2]


def eligible(ops, removed=frozenset(), rel_targets=frozenset()):
    """Instruction can run with a renamed stack: every stack access is an exact
    slot, no CALLOTHER/unknown op can observe R, no internal p-code labels."""
    if rel_targets:
        return False
    for i, (mn, out, ins) in enumerate(ops):
        if i in removed:
            continue
        if mn == 'CALLOTHER':
            return False
        for v in [out, *ins]:
            if touches_stack(v) and slot_index(v) is None:
                return False
    return True


def uses_stack(ops, removed=frozenset()):
    return any(touches_stack(v) for i, (_, out, ins) in enumerate(ops)
               if i not in removed for v in [out, *ins])


class VirtualStack:
    """Logical->physical slot map plus an optional binary64 value cache.

    Value cache (when `values`): a slot or 10-byte temporary written with
    d2f(E,10) keeps E in a C double instead; reads through f2d(.,10) use it.
    f2d(d2f(x,10),10) == x for every binary64 except signalling NaNs, which
    come back quiet (exhaustively checked per exponent/sign + 20M random).
    Values not produced by arithmetic are therefore read through x87_q().
    Raw (bit) reads and every exit materialize d2f(E,10) exactly as before.
    """

    def __init__(self, base='R', values=False):
        self.base = base
        self.values = values
        self.loc = list(range(8))  # logical -> physical
        self.seq = 0
        self.cache = {}   # physical -> [var, dirty, safe]
        self.tcache = {}  # temp varnode -> [var, dirty, safe]
        self.vars = []

    def identity(self):
        """Canonical layout with nothing cached: memory is the full state."""
        return self.loc == list(range(8)) and not self.cache

    def reset(self):
        self.loc = list(range(8))
        self.cache.clear()
        self.tcache.clear()

    def new_var(self):
        name = f'x87d{len(self.vars)}'
        self.vars.append(name)
        return name

    def materialize_code(self):
        """Store dirty cached values some logical slot still references.
        No state change: also used on conditional exit paths."""
        live = set(self.loc)
        return ' '.join(f'wr({self.base}+0x{SLOTS[p]:x},10,d2f({rec[0]},10));'
                        for p, rec in sorted(self.cache.items()) if rec[1] and p in live)

    def phys(self, logical):
        return SLOTS[self.loc[logical]]

    def alias(self, dst, src):
        self.loc[dst] = self.loc[src]

    def dest(self, logical):
        """Physical slot a write to `logical` may use without clobbering others.
        Any cached value of the returned slot is dropped (caller writes it)."""
        p = self.loc[logical]
        if self.loc.count(p) > 1:
            used = set(self.loc)
            p = next(q for q in range(8) if q not in used)
            self.loc[logical] = p
        self.cache.pop(p, None)
        return SLOTS[p]

    def flush_code(self):
        """C statements restoring the canonical layout (does not reset)."""
        mat = self.materialize_code()
        perm = self._permute_code()
        code = ' '.join(x for x in (mat, perm) if x)
        return '{ ' + code + ' }' if code else ''

    def _permute_code(self):
        # dest physical slot -> source (physical int, or parked scratch name).
        pending = {d: s for d, s in enumerate(self.loc) if d != s}
        if not pending:
            return ''
        b = self.base
        lines = []
        while pending:
            read = set(pending.values())
            ready = next((d for d in pending if d not in read), None)
            if ready is None:
                # Only cycles remain: park one slot, redirect its readers.
                d = next(iter(pending))
                self.seq += 1
                name = f'x87v{self.seq}'
                lines.append(f'u128 {name}=rd({b}+0x{SLOTS[d]:x},10);')
                pending = {e: (name if s == d else s) for e, s in pending.items()}
                continue
            s = pending.pop(ready)
            src = s if isinstance(s, str) else f'rd({b}+0x{SLOTS[s]:x},10)'
            lines.append(f'wr({b}+0x{SLOTS[ready]:x},10,{src});')
        return ' '.join(lines)
