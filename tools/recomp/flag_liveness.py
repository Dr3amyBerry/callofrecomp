"""Conservative byte-level flag liveness for a complete generated chunk.

Results identify statements to replace with semicolons, never delete indices.
Every dispatcher exit observes all flags. No inputs or instruction data mutate.
"""

FLAGS = frozenset((0x200, 0x202, 0x206, 0x207, 0x20b))
PURE = frozenset('''COPY INT_ADD INT_SUB INT_MULT INT_AND INT_OR INT_XOR
INT_LEFT INT_RIGHT INT_SRIGHT INT_EQUAL INT_NOTEQUAL INT_LESS INT_LESSEQUAL
INT_SLESS INT_SLESSEQUAL INT_CARRY INT_SCARRY INT_SBORROW INT_ZEXT INT_SEXT
INT_NEGATE INT_2COMP BOOL_NEGATE BOOL_AND BOOL_OR BOOL_XOR PIECE SUBPIECE
POPCOUNT'''.split())
KNOWN = PURE | frozenset('''LOAD STORE INT_DIV INT_REM INT_SDIV INT_SREM
FLOAT_ADD FLOAT_SUB FLOAT_MULT FLOAT_DIV FLOAT_EQUAL FLOAT_NOTEQUAL FLOAT_LESS
FLOAT_LESSEQUAL FLOAT_NAN FLOAT_NEG FLOAT_ABS FLOAT_SQRT FLOAT_CEIL FLOAT_FLOOR
ROUND FLOAT2FLOAT INT2FLOAT TRUNC BRANCH CALL CBRANCH BRANCHIND CALLIND RETURN
CALLOTHER'''.split())


def _bytes(v):
    return set(range(v[1], v[1] + v[2])) & FLAGS if v and v[0] == 'r' else set()


def _solve(chunk, external_live=None, collect_external=None):
    """Backward byte-liveness over one chunk.

    Returns (nodes, live, after_of, entry). Successor edges are ('n', node)
    inside the chunk, ('x', address) for a statically known instruction start
    in another chunk (only when external_live is given), or None for an exit
    that observes every flag. external_live(address) gives the flag bytes live
    on entry to such an address (default: all flags, the classic behaviour).
    """
    nodes = [(j, i) for j, (_, _, ops) in enumerate(chunk) for i in range(len(ops))]
    addresses = {a: j for j, (a, _, _) in enumerate(chunk)}
    modular = external_live is not None

    def entry(address, seen=None):
        seen = set() if seen is None else seen
        if address in seen:
            return None
        if address not in addresses:
            return ('x', address) if modular else None
        seen.add(address)
        j = addresses[address]
        a, size, ops = chunk[j]
        if ops:
            return ('n', (j, 0))
        if j + 1 < len(chunk) and chunk[j + 1][0] == a + size:
            return entry(a + size, seen)
        # Empty-op instruction at the chunk end: generated code sets PC and returns.
        return ('x', a + size) if modular and j + 1 == len(chunk) else None

    def physical_next(j, addr, size):
        if j + 1 < len(chunk) and chunk[j + 1][0] == addr + size:
            return entry(addr + size)
        # Chunk-final instruction: generated code does PC=addr+size; return.
        if j + 1 == len(chunk) and modular:
            return ('x', addr + size)
        return None

    successors, reads, writes, barriers = {}, {}, {}, set()
    for node in nodes:
        j, i = node
        addr, size, ops = chunk[j]
        mn, out, inputs = ops[i]
        reads[node] = set().union(*(_bytes(v) for v in inputs)) if inputs else set()
        writes[node] = _bytes(out)
        # Physical fallthrough exists only between contiguous instructions.
        following = ('n', (j, i + 1)) if i + 1 < len(ops) else physical_next(j, addr, size)
        edges = [following]
        if mn in ('BRANCH', 'CALL', 'CBRANCH'):
            target = None
            if inputs and inputs[0]:
                space, offset, _ = inputs[0]
                if space == 'c':
                    relative = offset - (1 << 64) if offset >= 1 << 63 else offset
                    t = i + relative
                    if t >= len(ops):
                        target = physical_next(j, addr, size)
                    elif t >= 0:
                        target = ('n', (j, t))
                elif space == 'm':
                    target = entry(offset)
            edges = [following, target] if mn == 'CBRANCH' else [target]
        elif mn in ('BRANCHIND', 'CALLIND', 'RETURN'):
            edges = [None]
        if mn not in KNOWN or mn == 'CALLOTHER':
            barriers.add(node)
        successors[node] = edges

    live = {node: set() for node in nodes}

    def after_of(node):
        result = set()
        for edge in successors[node]:
            if edge is None:
                result |= FLAGS
            elif edge[0] == 'n':
                result |= live[edge[1]]
            else:
                if collect_external is not None:
                    collect_external.add(edge[1])
                result |= external_live(edge[1])
        return result

    changed = True
    while changed:
        changed = False
        for node in reversed(nodes):
            before = (set(FLAGS) if node in barriers else
                      reads[node] | (after_of(node) - writes[node]))
            if before != live[node]:
                live[node] = before
                changed = True
    return nodes, live, after_of, entry


def _dead_from(chunk, nodes, after_of):
    dead = set()
    for node in nodes:
        j, i = node
        mn, out, inputs = chunk[j][2][i]
        if mn not in PURE or not out or out[0] != 'r' or out[2] <= 0:
            continue
        if any(v and v[0] == 'm' for v in inputs):
            continue  # A direct memory operand can fault even if its flag dies.
        output = set(range(out[1], out[1] + out[2]))
        if output <= FLAGS and not output & after_of(node):
            dead.add(node)
    return dead


def dead_flag_writes(chunk):
    """Return {(instruction_index, op_index)} for proven dead pure flag writes.

    Direct calls are jumps, as in pcode2c; external and indirect control flow,
    user operations and unknown operations conservatively observe every flag.
    Reads of eliminated writes are intentionally retained in the analysis.
    """
    nodes, _, after_of, _ = _solve(chunk)
    return _dead_from(chunk, nodes, after_of)


# Guest PCs at which guest_run() (tools/recomp/runtime/guest.c) may divert to
# native code before dispatching a chunk. Native regions read/write R, so a
# flag value arriving there is treated as observed (tests keep this in sync).
OPAQUE_ENTRY_PCS = frozenset((0x0041c017, 0x005061b0, 0x30012260, 0x30012200))


def dead_flag_writes_module(chunks, opaque_pcs=OPAQUE_ENTRY_PCS):
    """Whole-module flag DCE: returns [set_of_dead_nodes] aligned with chunks.

    A chunk exit (branch, call or physical fallthrough) to a statically known
    instruction start in another chunk of the SAME module observes only the
    flag bytes live on entry there, computed as a least fixpoint over all
    chunks. Indirect transfers, returns, unknown addresses, user ops and
    opaque (natively hooked) entry PCs still observe every flag. Dispatcher
    entries happen only at instruction starts, so no other observer exists.
    """
    owner = {a for chunk in chunks for a, _, _ in chunk}
    entry_live = {}            # address -> frozenset of flag bytes live on entry
    consumers = {}             # address -> chunk indexes depending on it
    solved = [None] * len(chunks)

    def resolve(address):
        if address in opaque_pcs or address not in owner:
            return FLAGS
        return entry_live.get(address, frozenset())

    def run(ci):
        used = set()
        res = _solve(chunks[ci], external_live=resolve, collect_external=used)
        solved[ci] = res
        for address in used:
            consumers.setdefault(address, set()).add(ci)
        _, live, _, entry = res
        changed = []
        for a, _, _ in chunks[ci]:
            target = entry(a)
            if target is None:
                value = frozenset(FLAGS)
            elif target[0] == 'n':
                value = frozenset(live[target[1]])
            else:
                consumers.setdefault(target[1], set()).add(ci)
                value = frozenset(resolve(target[1]))
            if entry_live.get(a) != value:
                entry_live[a] = value
                changed.append(a)
        return changed

    pending = list(range(len(chunks)))
    queued = set(pending)
    while pending:
        ci = pending.pop(0)
        queued.discard(ci)
        for address in run(ci):
            for consumer in consumers.get(address, ()):
                if consumer not in queued:
                    pending.append(consumer)
                    queued.add(consumer)
    return [_dead_from(chunk, solved[ci][0], solved[ci][2])
            for ci, chunk in enumerate(chunks)]
