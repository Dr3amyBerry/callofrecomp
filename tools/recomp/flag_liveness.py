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


def dead_flag_writes(chunk):
    """Return {(instruction_index, op_index)} for proven dead pure flag writes.

    Direct calls are jumps, as in pcode2c; external and indirect control flow,
    user operations and unknown operations conservatively observe every flag.
    Reads of eliminated writes are intentionally retained in the analysis.
    """
    nodes = [(j, i) for j, (_, _, ops) in enumerate(chunk) for i in range(len(ops))]
    addresses = {a: j for j, (a, _, _) in enumerate(chunk)}

    def entry(address, seen=None):
        seen = set() if seen is None else seen
        if address not in addresses or address in seen:
            return None
        seen.add(address)
        j = addresses[address]
        a, size, ops = chunk[j]
        if ops:
            return (j, 0)
        if j + 1 < len(chunk) and chunk[j + 1][0] == a + size:
            return entry(a + size, seen)
        return None

    successors, reads, writes, barriers = {}, {}, {}, set()
    for node in nodes:
        j, i = node
        addr, size, ops = chunk[j]
        mn, out, inputs = ops[i]
        reads[node] = set().union(*(_bytes(v) for v in inputs)) if inputs else set()
        writes[node] = _bytes(out)
        # Physical fallthrough exists only between contiguous instructions.
        following = (j, i + 1) if i + 1 < len(ops) else (
            entry(addr + size) if j + 1 < len(chunk) and chunk[j + 1][0] == addr + size else None)
        edges = [following]
        if mn in ('BRANCH', 'CALL', 'CBRANCH'):
            target = None
            if inputs and inputs[0]:
                space, offset, _ = inputs[0]
                if space == 'c':
                    relative = offset - (1 << 64) if offset >= 1 << 63 else offset
                    t = i + relative
                    if t >= len(ops):
                        target = entry(addr + size)
                    elif t >= 0:
                        target = (j, t)
                elif space == 'm':
                    target = entry(offset)
            edges = [following, target] if mn == 'CBRANCH' else [target]
        elif mn in ('BRANCHIND', 'CALLIND', 'RETURN'):
            edges = [None]
        if mn not in KNOWN or mn == 'CALLOTHER':
            barriers.add(node)
        successors[node] = edges

    live = {node: set() for node in nodes}
    changed = True
    while changed:
        changed = False
        for node in reversed(nodes):
            after = set().union(*(FLAGS if edge is None else live[edge]
                                  for edge in successors[node]))
            before = set(FLAGS) if node in barriers else reads[node] | (after - writes[node])
            if before != live[node]:
                live[node] = before
                changed = True
    dead = set()
    for node in nodes:
        j, i = node
        mn, out, inputs = chunk[j][2][i]
        if mn not in PURE or not out or out[0] != 'r' or out[2] <= 0:
            continue
        if any(v and v[0] == 'm' for v in inputs):
            continue  # A direct memory operand can fault even if its flag dies.
        output = set(range(out[1], out[1] + out[2]))
        after = set().union(*(FLAGS if edge is None else live[edge]
                              for edge in successors[node]))
        if output <= FLAGS and not output & after:
            dead.add(node)
    return dead
