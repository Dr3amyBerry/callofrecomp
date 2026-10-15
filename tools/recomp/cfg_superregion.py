"""Phase14F conservative ORIGINAL multi-basic-block CFG superregion recovery.

This module analyzes only original Ghidra B-owned PCs and micro-pcode
successors. The resulting regions contain entire basic blocks joined by
verified forward edges, with no *guest-data* memory accesses, x87,
CALLOTHER, or CALL/RETURN. Any entry from outside the chosen region uses
the existing dispatcher, never this native candidate. All unresolved
edges and nonselected successors are explicit fallback exits.

No runtime/APK paths use this module. In particular, no FPS claim is
implied by a syntactically valid superregion or fewer CFG nodes.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from cfg_region_lab import (
    Region, INTEGER_SAFE, X87, may_fault_guest_memory,
)
from pcode2c import temporary_layout
from region_cfg import CFGError, micro_exits, recover_function_cfg


@dataclass(frozen=True)
class Superregion:
    region: Region
    block_starts: tuple[int, ...]
    internal_edges: tuple[tuple[int, int], ...]
    exits: tuple[tuple[int, int | None], ...]
    side_entry_pcs: tuple[int, ...]
    # All non-start entry PCs MUST remain dispatcher-enterable. No runtime
    # replacement or reinterpretation of the original guest chunks occurs.


def safe_instruction(pc: int, width: int, operations: list) -> bool:
    """A full original instruction with no possible guest-memory effect.

    A p-code "m" operand for COPY is a guest absolute memory reference;
    "m" on a BRANCH is a *code target*, not a data memory reference.
    Reject all opaque and unusual microbranch hazards conservatively.
    """
    if not (0 <= pc < 1 << 32 and 0 < width <= 15 and operations):
        return False
    if temporary_layout(operations) is None:
        return False
    edges, issues = micro_exits(operations, pc + width)
    if issues or not edges:
        return False
    for mnemonic, out, inputs in operations:
        if mnemonic not in INTEGER_SAFE or may_fault_guest_memory(mnemonic, out, inputs):
            return False
        if not isinstance(inputs, list):
            return False
        for operand in ([out] if out is not None else []) + inputs:
            if operand is None:
                continue
            space, offset, size = operand
            if size <= 0 or offset < 0:
                return False
            if space == "r":
                if offset + size > 0x2000 or (
                    offset < X87[1] and offset + size > X87[0]):
                    return False
            elif space == "u":
                if offset + size > 0x400000:
                    return False
            elif space == "m":
                if mnemonic not in {"BRANCH", "CBRANCH"} or offset >= 1 << 32:
                    return False
            elif space not in {"c"}:
                return False
        if mnemonic in {"BRANCH", "CBRANCH"}:
            if not inputs or inputs[0] is None or inputs[0][0] not in {"c", "m"}:
                return False
    return True


def _validated_block(block: dict, indexed: dict[int, tuple[int, list]]) -> tuple | None:
    pcs = tuple(int(item, 16) for item in block["pcs"])
    if not pcs or tuple(sorted(set(pcs))) != pcs:
        return None
    original = []
    for pc in pcs:
        if pc not in indexed:
            return None
        length, ops = indexed[pc]
        if not safe_instruction(pc, length, ops):
            return None
        original.append((pc, length, ops))
    if any(pc + length != next_pc
           for (pc, length, _), (next_pc, _, _) in zip(original, original[1:])):
        return None
    return tuple(original)


def plan_superregions(
    instructions: list, cfg: dict, *,
    minimum_blocks: int = 2, minimum_instructions: int = 6,
    maximum_blocks: int = 12, maximum_instructions: int = 48,
) -> tuple[Superregion, ...]:
    """Find forward-only, bounded, wholly eligible subgraphs of original CFG.

    A branch to a block outside the selected subset is handled by the
    existing dispatcher on that exact target PC. Exits are not fabricated.
    The function's B-interval ownership and p-code provenance must have
    been checked by recover_function_cfg; no arbitrary list of PCs accepted.

    Forward-only blocks exclude cycles and recursive native re-entry.
    A backedge from an included block to an earlier included block
    invalidates the candidate entirely, not silently taken as a loop.
    """
    if not (1 <= minimum_blocks <= maximum_blocks <= 32 and
            1 <= minimum_instructions <= maximum_instructions <= 256):
        raise CFGError("invalid superregion size bounds")
    if cfg.get("source") != "pcode_micro_cfg_plus_Ghidra_B_v2":
        raise CFGError("unverified original CFG source")
    indexed = {pc: (size, ops) for pc, size, ops in instructions}
    if len(indexed) != len(instructions):
        raise CFGError("duplicate instruction PCs")
    blocks = cfg["basic_blocks"]
    good: dict[int, tuple] = {}
    successors: dict[int, tuple[int, ...]] = {}
    for i, block in enumerate(blocks):
        data = _validated_block(block, indexed)
        if data is not None:
            good[i] = data
    for i, original in good.items():
        selected = set()
        for edge in blocks[i]["outgoing"]:
            index = edge["target_block"]
            if index is None or index not in good:
                continue
            if edge["kind"] not in {
                "fallthrough", "relative_end", "direct_jump", "conditional_taken"
            }:
                continue
            selected.add(index)
        successors[i] = tuple(sorted(
            selected, key=lambda j: good[j][0][0]))
    found = []
    entry = int(cfg["entry_va"], 16)
    known_incoming = cfg.get("known_incoming_pc", {})
    for seed in sorted(good, key=lambda j: good[j][0][0]):
        selected = set()
        queue = [seed]
        total = 0
        while queue:
            i = queue.pop(0)
            if i in selected:
                continue
            chunk = good[i]
            if len(selected) >= maximum_blocks or total + len(chunk) > maximum_instructions:
                continue
            # Expansion only to higher original PCs, making the native
            # region acyclic even if the containing function has loops.
            if i != seed and chunk[0][0] <= good[seed][0][0]:
                continue
            selected.add(i)
            total += len(chunk)
            queue.extend(j for j in successors[i]
                         if good[j][0][0] > chunk[0][0] and j not in selected)
        if len(selected) < minimum_blocks or total < minimum_instructions:
            continue
        # Crucial: the lowering checks membership by PC, so a selected
        # backedge would become a native loop even though discovery only
        # follows forward edges. Refuse candidates with such edges.
        if any(good[j][0][0] <= good[i][0][0]
               for i in selected for j in successors[i] if j in selected):
            continue
        ordered = sorted(selected, key=lambda j: good[j][0][0])
        selected_pc = {pc for i in selected for pc, _, _ops in good[i]}
        flat = tuple(op for i in ordered for op in good[i])
        if len({x[0] for x in flat}) != len(flat):
            raise CFGError("original superregion double-owns a PC")
        # Every original edge is either internal or a dispatcher fallback.
        edges = []
        exits = set()
        for i in ordered:
            source = good[i][-1][0]
            for edge in blocks[i]["outgoing"]:
                target = edge["target_pc"]
                end = int(target, 16) if target is not None else None
                if end in selected_pc:
                    edges.append((source, end))
                else:
                    exits.add((source, end))
        incoming = tuple(sorted(
            pc for pc in selected_pc
            if f"0x{pc:08x}" in known_incoming and pc != flat[0][0]
        ))
        found.append(Superregion(
            region=Region(entry, flat[0][0], flat),
            block_starts=tuple(good[i][0][0] for i in ordered),
            internal_edges=tuple(sorted(set(edges))),
            exits=tuple(sorted(exits, key=lambda t: (t[0], -1 if t[1] is None else t[1]))),
            side_entry_pcs=incoming,
        ))
    return tuple(sorted(found, key=lambda item: (
        -len(item.region.instructions), -len(item.block_starts), item.region.start,
    )))


def discover_superregions(instructions: list, mapping: dict, entry: int,
                          **limits) -> tuple[Superregion, ...]:
    """Parse CFG once per original function; never use user-provided B ranges."""
    return plan_superregions(
        instructions, recover_function_cfg(instructions, mapping, entry),
        **limits,
    )


def description(region: Superregion) -> dict[str, Any]:
    """Address-only report; no copied original game opcodes or binaries."""
    return {
        "function_entry": f"0x{region.region.function_entry:08x}",
        "entry_pc": f"0x{region.region.start:08x}",
        "basic_blocks": len(region.block_starts),
        "original_x86_instructions": len(region.region.instructions),
        "basic_block_starts": [f"0x{x:08x}" for x in region.block_starts],
        "internal_guest_edges": len(region.internal_edges),
        "external_dispatcher_exits": len(region.exits),
        "known_external_side_entries_use_original_dispatcher":
            [f"0x{x:08x}" for x in region.side_entry_pcs],
        "entry_policy": "start_only_original_dispatcher_fallback_for_all_other_pcs",
        "all_guest_data_memory_accesses_excluded": True,
        "x87_and_opaque_ops_excluded": True,
        "candidate_is_safe_to_deploy": False,
    }
