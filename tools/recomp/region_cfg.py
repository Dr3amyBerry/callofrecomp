"""Conservative, read-only CFG recovery for native regions of x86 p-code.

No generated C is changed here. A Ghidra B range is a claimed static owner,
NOT proof that only the function entry can reach a given instruction.
A p-code instruction is itself a micro-CFG: conditional branches can occur
before the final p-code operation, and local 'c' branches use OP INDICES.
Unknown outgoing edges and dispatcher entry PCs remain explicitly visible.
"""
from __future__ import annotations

from bisect import bisect_left
from collections import Counter, defaultdict, deque
from dataclasses import dataclass
from typing import Any


class CFGError(ValueError):
    """Input provenance, ambiguous ownership or malformed CFG."""


@dataclass(frozen=True, order=True)
class Exit:
    kind: str
    target: int | None = None


TRANSFER_DIRECT = {"BRANCH", "CALL", "CBRANCH"}
TRANSFER_DYNAMIC = {"RETURN", "BRANCHIND", "CALLIND"}
HARD_BARRIERS = {"CALLOTHER"}
FLAG_BYTE_OFFSETS = frozenset((0x200, 0x202, 0x206, 0x207, 0x20b))


def signed_relative(value: int) -> int:
    if not 0 <= value < (1 << 64):
        raise CFGError("invalid 64-bit p-code relative branch")
    return value - (1 << 64) if value >= (1 << 63) else value


def micro_exits(ops: list, next_pc: int) -> tuple[tuple[Exit, ...], tuple[str, ...]]:
    """Return all reachable exits from p-code micro-op 0.

    This is a MAY-successor graph, not an execution trace: either side of
    CBRANCH is possible. CALL transfers immediately to its callee. No implicit
    CALL fallthrough is invented; higher layers label may-return separately.
    """
    if not ops:
        return ((Exit("unknown_missing_pcode"),), ("missing_pcode",))
    work = [0]
    visited = set()
    ends: set[Exit] = set()
    issues: set[str] = set()
    while work:
        i = work.pop()
        if i == len(ops):
            ends.add(Exit("fallthrough", next_pc))
            continue
        if not 0 <= i < len(ops):
            issues.add("invalid_micro_target")
            ends.add(Exit("unknown_invalid_micro_target"))
            continue
        if i in visited:
            continue
        visited.add(i)
        mnemonic, _out, operands = ops[i]
        if mnemonic in TRANSFER_DYNAMIC:
            ends.add(Exit("dynamic_" + mnemonic.lower()))
            continue
        if mnemonic not in TRANSFER_DIRECT:
            if mnemonic == "CALLOTHER":
                issues.add("callother_side_effect_barrier")
            work.append(i + 1)
            continue
        if mnemonic == "CBRANCH":
            work.append(i + 1)
        if not operands or operands[0] is None:
            issues.add("missing_branch_operand")
            ends.add(Exit("unknown_branch_operand"))
            continue
        space, off, _width = operands[0]
        if space == "c":
            # Ghidra relative p-code branches use indices WITHIN THIS x86 insn.
            try:
                dest = i + signed_relative(off)
            except CFGError:
                dest = -1
            if 0 <= dest < len(ops):
                if dest <= i:
                    issues.add("micro_cycle_possible")
                work.append(dest)
            elif dest >= len(ops):
                # Match pcode2c.generate(): target beyond final op is next PC.
                ends.add(Exit("relative_end", next_pc))
            else:
                issues.add("invalid_micro_target")
                ends.add(Exit("unknown_invalid_micro_target"))
        elif space == "m" and 0 <= off < (1 << 32):
            ends.add(Exit({
                "BRANCH": "direct_jump",
                "CBRANCH": "conditional_taken",
                "CALL": "direct_call",
            }[mnemonic], off))
        else:
            issues.add("unresolved_direct_target")
            ends.add(Exit("unknown_direct_target"))
    if not ends:
        issues.add("no_micro_exit")
    return tuple(sorted(ends)), tuple(sorted(issues))


def _ranges_from_map(mapping: dict, entry: int) -> list[tuple[int, int]]:
    if mapping.get("schema_version") != 2:
        raise CFGError("Ghidra v2 B body intervals required; F markers are insufficient")
    declared = {
        int(rec["entry_va"], 16): rec for rec in mapping.get("functions", [])
    }
    if entry not in declared or not declared[entry]["entry_in_translation"]:
        raise CFGError(f"entry 0x{entry:08x} is not a verified F marker")
    ranges = sorted((int(x["start_va"], 16), int(x["end_va_inclusive"], 16))
                    for x in mapping["ghidra_body_ranges"]
                    if int(x["entry_va"], 16) == entry)
    if not ranges:
        raise CFGError(f"no Ghidra B ranges for 0x{entry:08x}")
    if entry not in range(ranges[0][0], ranges[0][1] + 1) and not any(
            low <= entry <= high for low, high in ranges):
        raise CFGError("function entry absent from its claimed B body")
    if any(low > high or (i and low <= ranges[i-1][1])
           for i, (low, high) in enumerate(ranges)):
        raise CFGError("overlapping or malformed B intervals")
    return ranges


def extract_function(instructions: list, mapping: dict, entry: int) -> tuple[list, list, list]:
    """Verify body membership; returns selected instructions, ranges, hazards.

    Do not silently assign overlapping Ghidra bodies to one function. Detect
    intervals that partially cover an instruction or whose map count is stale.
    """
    ranges = _ranges_from_map(mapping, entry)
    addresses = [a for a, _, _ in instructions]
    if addresses != sorted(set(addresses)):
        raise CFGError("p-code instruction addresses must be unique, sorted")
    selected = []
    for low, high in ranges:
        pos = bisect_left(addresses, low)
        while pos < len(instructions) and instructions[pos][0] <= high:
            ins = instructions[pos]
            if ins[0] + ins[1] - 1 > high:
                raise CFGError("p-code instruction straddles Ghidra B body boundary")
            selected.append(ins)
            pos += 1
    if not selected or selected[0][0] > entry or entry not in {
            addr for addr, _, _ in selected}:
        raise CFGError("original entry absent from parsed function body")
    # Selected B ranges can intersect other function bodies; fail closed.
    overlap_events = []
    for record in mapping.get("ghidra_body_ranges", []):
        low, high = int(record["start_va"], 16), int(record["end_va_inclusive"], 16)
        owner = int(record["entry_va"], 16)
        if any(low <= b and high >= a for a, b in ranges):
            overlap_events += [(low, owner, 1), (high + 1, owner, -1)]
    overlap_events.sort()
    active: Counter[int] = Counter()
    cursor = 0
    for a, length, _ops in selected:
        while cursor < len(overlap_events) and overlap_events[cursor][0] <= a:
            _, owner, delta = overlap_events[cursor]
            active[owner] += delta
            if active[owner] == 0:
                del active[owner]
            cursor += 1
        owners = [owner for owner, count in active.items() if count > 0]
        if owners != [entry]:
            raise CFGError(f"ambiguous/missing B ownership for PC 0x{a:08x}")
        if cursor < len(overlap_events) and overlap_events[cursor][0] < a + length:
            raise CFGError("instruction changes ownership mid-byte")
    expected = next(int(record["body_uniquely_owned_instruction_count"])
                    for record in mapping["functions"]
                    if int(record["entry_va"], 16) == entry)
    if len(selected) != expected:
        raise CFGError(f"stale Ghidra map: expected {expected} instructions, got {len(selected)}")
    return selected, ranges, []


def _effects(ops: list) -> dict[str, Any]:
    arch_read, arch_write = set(), set()
    touched_x87 = False
    memory_reads = memory_writes = callothers = 0
    for mnemonic, output, inputs in ops:
        memory_reads += mnemonic == "LOAD"
        memory_writes += mnemonic == "STORE"
        callothers += mnemonic == "CALLOTHER"
        for field, value in ((False, output), *((True, x) for x in inputs)):
            if value is None:
                continue
            space, offset, size = value
            if space == "r":
                if offset < 0 or size <= 0:
                    raise CFGError("invalid architecture varnode")
                bytes_ = set(range(offset, offset + size))
                if field:
                    arch_read.update(bytes_)
                else:
                    arch_write.update(bytes_)
                if bytes_ & set(range(0x1100, 0x1180)):
                    touched_x87 = True
    return {
        "architecture_read_bytes": len(arch_read),
        "architecture_write_bytes": len(arch_write),
        "eflags_read": bool(arch_read & FLAG_BYTE_OFFSETS),
        "eflags_write": bool(arch_write & FLAG_BYTE_OFFSETS),
        "x87_registers_touched": touched_x87,
        "guest_load_ops": memory_reads,
        "guest_store_ops": memory_writes,
        "callother_ops": callothers,
    }


def external_direct_entries(instructions: list, inside: set[int]) -> dict[int, list[dict]]:
    """Direct incoming jumps/calls from all OTHER original instructions.

    Computed jumps are fundamentally unknown and are intentionally NOT
    represented as known incoming edges.
    """
    incoming: dict[int, list[dict]] = defaultdict(list)
    for pc, _length, ops in instructions:
        if pc in inside:
            continue
        for mnemonic, _out, operands in ops:
            if mnemonic not in TRANSFER_DIRECT or not operands or operands[0] is None:
                continue
            target = operands[0]
            if target[0] == "m" and target[1] in inside:
                incoming[target[1]].append({"source_pc": f"0x{pc:08x}",
                                            "kind": mnemonic.lower()})
    return dict(incoming)


def recover_function_cfg(instructions: list, mapping: dict, entry: int) -> dict:
    """Recover original-function basic blocks, hazards and side-entry proof.

    Output is private-address-only JSON; it contains no proprietary p-code
    statements, bytes, decoded instructions or assets.
    """
    body, ranges, _ = extract_function(instructions, mapping, entry)
    nodes = {pc: (width, ops) for pc, width, ops in body}
    inside = set(nodes)
    successors: dict[int, tuple[Exit, ...]] = {}
    all_issues: dict[int, tuple[str, ...]] = {}
    for pc, (size, ops) in nodes.items():
        exits, issues = micro_exits(ops, pc + size)
        successors[pc] = exits
        all_issues[pc] = issues

    incoming = external_direct_entries(instructions, inside)
    # Not all dynamic incoming edges can be recovered, and the native
    # dispatcher accepts any instruction PC; never claim single-entry safety.
    addresses = [pc for pc, _, _ in instructions]
    for pc in inside:
        ix = bisect_left(addresses, pc)
        if ix > 0:
            pred = instructions[ix-1]
            if pred[0] not in inside and pred[0] + pred[1] == pc:
                pred_exits, _ = micro_exits(pred[2], pc)
                if any(x.kind in {"fallthrough", "relative_end"} and x.target == pc
                       for x in pred_exits):
                    incoming.setdefault(pc, []).append({
                        "source_pc": f"0x{pred[0]:08x}", "kind": "fallthrough"
                    })
    predecessors: dict[int, set[int]] = defaultdict(set)
    internal: dict[int, tuple[Exit, ...]] = {}
    externals: list[dict] = []
    dynamic: list[dict] = []
    unsupported_targets = []
    for pc, exits in successors.items():
        accepted = []
        for edge in exits:
            if edge.target in inside:
                accepted.append(edge)
                predecessors[edge.target].add(pc)
            elif edge.target is not None:
                externals.append({"source_pc": f"0x{pc:08x}",
                                  "target_pc": f"0x{edge.target:08x}",
                                  "kind": edge.kind})
                if any(low <= edge.target <= high for low, high in ranges):
                    unsupported_targets.append({"source_pc": f"0x{pc:08x}",
                                                "target_pc": f"0x{edge.target:08x}"})
            else:
                dynamic.append({"source_pc": f"0x{pc:08x}", "kind": edge.kind})
        internal[pc] = tuple(accepted)
    # Build leaders at branch targets, alternative entries, gaps, joins and
    # distinct fallthrough continuations. A CALL's return continuation is
    # handled by the interpreter/dispatcher, not an immediate CFG successor.
    leaders = {entry, *incoming}
    for pc, (size, _ops) in nodes.items():
        outgoing = internal[pc]
        if len(outgoing) != 1 or outgoing[0].kind not in {"fallthrough", "relative_end"}:
            leaders.update(x.target for x in outgoing if x.target is not None)
            if pc + size in inside:
                leaders.add(pc + size)
        for edge in outgoing:
            if edge.kind not in {"fallthrough", "relative_end"}:
                leaders.add(edge.target)
    for pc in inside:
        if len(predecessors[pc]) != 1:
            leaders.add(pc)
    covered: set[int] = set()
    blocks = []
    for pc in sorted(inside):
        if pc in covered:
            continue
        cur = pc
        pcs = []
        while cur not in covered:
            pcs.append(cur)
            covered.add(cur)
            size, _ops = nodes[cur]
            edges = internal[cur]
            if len(edges) != 1 or edges[0].kind not in {"fallthrough", "relative_end"}:
                break
            nxt = edges[0].target
            if (nxt not in inside or nxt in covered or nxt in leaders or
                    nxt != cur + size or predecessors[nxt] != {cur}):
                break
            cur = nxt
        blocks.append({"start_pc": f"0x{pc:08x}",
                       "end_pc_exclusive": f"0x{pcs[-1] + nodes[pcs[-1]][0]:08x}",
                       "instruction_count": len(pcs), "pcs": pcs})
    if covered != inside:
        raise CFGError("basic block construction lost instructions")
    pc_to_block = {}
    for idx, block in enumerate(blocks):
        for pc in block["pcs"]:
            if pc in pc_to_block:
                raise CFGError("two blocks claim same instruction PC")
            pc_to_block[pc] = idx
    for block in blocks:
        last = block["pcs"][-1]
        block["outgoing"] = [{
            "kind": edge.kind,
            "target_block": pc_to_block.get(edge.target),
            "target_pc": f"0x{edge.target:08x}" if edge.target is not None else None,
        } for edge in successors[last]]
        block["pcs"] = [f"0x{pc:08x}" for pc in block["pcs"]]
    reachable = set()
    pending = [entry]
    while pending:
        pc = pending.pop()
        if pc in reachable:
            continue
        reachable.add(pc)
        pending.extend(edge.target for edge in internal[pc] if edge.target not in reachable)
    # CALL may return via the dispatcher: model a conservative reachable
    # superset separately from actual immediate p-code successor edges.
    with_returns = set()
    pending = [entry]
    while pending:
        pc = pending.pop()
        if pc in with_returns:
            continue
        with_returns.add(pc)
        pending.extend(edge.target for edge in internal[pc] if edge.target not in with_returns)
        if any(edge.kind in {"direct_call", "dynamic_callind"} for edge in successors[pc]):
            nxt = pc + nodes[pc][0]
            if nxt in inside:
                pending.append(nxt)
    effects = Counter()
    eflags_reads = eflags_writes = x87_touches = 0
    for _pc, _size, ops in body:
        e = _effects(ops)
        for k in ("architecture_read_bytes", "architecture_write_bytes",
                  "guest_load_ops", "guest_store_ops", "callother_ops"):
            effects[k] += e[k]
        eflags_reads += e["eflags_read"]
        eflags_writes += e["eflags_write"]
        x87_touches += e["x87_registers_touched"]
    hazards = Counter(x for problems in all_issues.values() for x in problems)
    hazards["unresolved_dynamic_exits"] = len(dynamic)
    hazards["invalid_static_targets_inside_body"] = len(unsupported_targets)
    hazards["known_external_direct_entries"] = sum(len(v) for v in incoming.values())
    return {
        "entry_va": f"0x{entry:08x}",
        "source": "pcode_micro_cfg_plus_Ghidra_B_v2",
        "confidence": "structural_diagnostic_only",
        "body_ranges_inclusive": [[f"0x{a:08x}", f"0x{b:08x}"] for a, b in ranges],
        "instruction_count": len(body),
        "block_count": len(blocks),
        "direct_reachable_instructions": len(reachable),
        "may_return_reachable_instructions": len(with_returns),
        "unknown_entry_policy": ("Every instruction PC remains dispatcher-enterable; "
                                 "indirect callers cannot be enumerated statically."),
        "known_incoming_pc": {
            f"0x{pc:08x}": items for pc, items in sorted(incoming.items())
        },
        "outgoing_external_edges": externals,
        "dynamic_exit_edges": dynamic,
        "invalid_targets_inside_body": unsupported_targets,
        "hazards": dict(sorted(hazards.items())),
        "effects_sum_per_instruction": dict(sorted(effects.items())),
        "instructions_touching_eflags": {"reads": eflags_reads, "writes": eflags_writes},
        "instructions_touching_x87": x87_touches,
        "basic_blocks": blocks,
        "eligible_for_automatic_native_replacement": False,
        "replacement_blockers": [
            "no independent x86 full-body oracle",
            "dispatcher can enter any guest instruction PC",
            "indirect exits/return edges are not completely enumerable",
            "architectural state and aliasing not yet proven for region boundaries",
        ],
    }
