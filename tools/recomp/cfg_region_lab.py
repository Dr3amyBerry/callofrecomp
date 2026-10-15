"""Phase14C offline CFG-region A/B compiler: NEVER modifies the game build.

Uses existing Ghidra original-body ownership and pcode2c.Gen lowering.
For one original x86 basic block (2+ instructions) generate two PRIVATE C
implementations: baseline (per-instruction R reads/writes), and a bounded
register-cache implementation that retains disjoint architectural varnodes
across the *whole basic block*.

All entry PCs have a separate reload label (L_pc), followed by an internal
continuation label (B_pc). Exits flush cached registers BEFORE setting guest PC.
The guest dispatcher can enter any original instruction, including an interior
one. Unknown p-code, x87, userops, indirect transfer, call or return => REFUSE.

This is an OFFLINE experimental lowering. Neither pcode2c.py nor runtime nor
Android CMake uses it. A/B correctness on simulated RAM is not real-game,
Unicorn, cross-thread, guest exception, alias or FPS equivalence.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any

from pcode2c import Gen, rel, temporary_layout
from region_cfg import recover_function_cfg, CFGError
# Entire x87 metadata+physical stack range, not just 80-byte STn slots.
# State flags/word/TOP/pending status also live at R+0x1090..0x10ac.
X87 = (0x1000, 0x1200)

# Source instruction mnemonics; x87 also requires checking R register space.
INTEGER_SAFE = frozenset({
    "COPY", "LOAD", "STORE", "INT_ADD", "INT_SUB", "INT_MULT",
    "INT_AND", "INT_OR", "INT_XOR", "INT_LEFT", "INT_RIGHT", "INT_SRIGHT",
    "INT_EQUAL", "INT_NOTEQUAL", "INT_LESS", "INT_LESSEQUAL",
    "INT_SLESS", "INT_SLESSEQUAL", "INT_CARRY", "INT_SCARRY",
    "INT_SBORROW", "INT_ZEXT", "INT_SEXT", "INT_NEGATE",
    "INT_2COMP", "BOOL_NEGATE", "BOOL_AND", "BOOL_OR", "BOOL_XOR",
    "PIECE", "SUBPIECE", "POPCOUNT", "BRANCH", "CBRANCH"
})
BRANCH_OPS = frozenset({"BRANCH","CBRANCH"})
DISALLOWED = frozenset({"CALLOTHER","CALL","CALLIND","RETURN","BRANCHIND"})


@dataclass(frozen=True)
class Region:
    function_entry: int
    start: int
    instructions: tuple
    # Reachable fallthrough within a basic block has one sequential path.
    # All other exits are emitted as real guest-PC exits, preserving state.


def select_block(insns: list, mapping: dict, entry: int, start: int,
                 *, min_instructions: int = 2) -> Region:
    cfg = recover_function_cfg(insns, mapping, entry)
    found = [block for block in cfg["basic_blocks"] if int(block["start_pc"],16)==start]
    if len(found)!=1:
        raise CFGError("requested PC is not the start of an original CFG basic block")
    pcs=tuple(int(pc,16) for pc in found[0]["pcs"])
    if len(pcs)<min_instructions:
        raise CFGError("region too short for a cross-instruction CFG experiment")
    by_pc={pc:(length,ops) for pc,length,ops in insns}
    selected=[]
    for pc in pcs:
        if pc not in by_pc:
            raise CFGError("CFG contains missing or duplicate original PC")
        size,ops=by_pc[pc]
        if not ops or temporary_layout(ops) is None:
            raise CFGError(f"missing or unproven p-code state at 0x{pc:08x}")
        if any(mn not in INTEGER_SAFE for mn,_out,_inputs in ops):
            raise CFGError(f"opaque, x87 or unsupported p-code at 0x{pc:08x}")
        for mn,out,inputs in ops:
            for v in ([out] if out else [])+list(inputs):
                if v is None: continue
                sp,off,width=v
                if width<=0 or off<0:
                    raise CFGError("invalid p-code varnode")
                if sp=="r" and (off < X87[1] and off+width>X87[0]):
                    raise CFGError("x87 architectural register disallowed")
                if sp=="r" and (off+width>0x2000):
                    raise CFGError("architectural register outside R")
                if sp=="u" and (off+width>0x400000):
                    raise CFGError("unique temporary outside U")
        # A basic block can have a terminal branch; but branching from any
        # nonfinal instruction must be a Ghidra/CFG split, not coalesced.
        if pc!=pcs[-1] and any(mn in BRANCH_OPS and args and args[0] and
                              args[0][0]=="m" for mn,_out,args in ops):
            raise CFGError("direct branch in middle of original basic block")
        if any(mn in BRANCH_OPS and args and args[0] and args[0][0]=="m" and
               not 0<=args[0][1]<=(1<<32)-1
               for mn,_out,args in ops):
            raise CFGError("branch target outside guest 32-bit PC space")
        selected.append((pc,size,ops))
    # The fallthrough of each interior instruction must be the next original
    # PC. Otherwise direct entry continuation could skip a control transfer.
    for (pc,size,_ops),following in zip(selected,selected[1:]):
        if pc+size!=following[0]:
            raise CFGError("interior CFG block contains an address gap")
    return Region(entry,start,tuple(selected))


def cache_candidates(region: Region) -> tuple:
    """Select exact nonoverlapping R varnodes used repeatedly across region.

    A 4-byte write to EAX cannot be cached alongside an 8/16-bit or AL view:
    removing any R write could break aliasing; reject overlapping candidates.
    """
    counts=Counter()
    written=set()
    all_regs=set()
    for pc,_sz,ops in region.instructions:
        for mn,out,inputs in ops:
            if out and out[0]=="r":
                all_regs.add(out)
                written.add(out)
                counts[out]+=1
            for v in inputs:
                if v and v[0]=="r":
                    all_regs.add(v)
                    counts[v]+=1
    eligible=[]
    for v,uses in counts.items():
        if uses<3 or v[2]>8:
            continue
        if any(other!=v and v[1]<other[1]+other[2]
               and other[1]<v[1]+v[2] for other in all_regs):
            continue
        # Even if this register is only read, saving read calls can help;
        # but optimizing it is never required for correctness.
        eligible.append((v,uses,v in written))
    eligible.sort(key=lambda item:(item[1],int(item[2]),-item[0][1]),reverse=True)
    return tuple(eligible)


def generate_region_c(region: Region, *, cache_count: int=0,
                      entry_policy: str="all_entries") -> tuple[str,tuple]:
    """Return generated, PRIVATE A/B C source and selected cached varnodes.

    A single exported execute_region supports an arbitrary guest start PC
    (including all interior instruction PCs). A and B have identical branch,
    memory, TEMP and guest PC handling; only register R accesses differ.
    """
    if not isinstance(cache_count,int) or not 0<=cache_count<=12:
        raise CFGError("cache_count must be in [0,12]")
    if entry_policy not in {"all_entries","start_only"}:
        raise CFGError("unsupported region entry policy")
    selected=tuple(item[0] for item in cache_candidates(region)[:cache_count])
    names={v:f"reg_{v[1]:x}_{v[2]}" for v in selected}
    written={v for v,_score,wrote in cache_candidates(region) if wrote}
    insns=region.instructions
    addrs={addr for addr,_sz,_ops in insns}
    by_addr={addr:(size,ops) for addr,size,ops in insns}
    if len(addrs)!=len(insns):
        raise CFGError("duplicate PCs in region")
    lines=[
        "/* PRIVATE DERIVED PCODE OUTPUT. DO NOT COMMIT. */",
        '#include "recomp_rt.h"',
        "#undef G",
        "#define G(a) (MEM + ((uint32_t)(a) % UINT32_C(65520)))",
        "uint8_t *MEM;",
        "uint8_t R[0x2000];",
        "uint8_t U[0x400000];",
        "uint32_t PC;",
        "int recomp_miss;",
        # noinline so static ARM64 code includes explicit A/B entry guards
        "#if defined(_WIN32)",
        "#define REGION_API __declspec(dllexport)",
        "#else",
        '#define REGION_API __attribute__((visibility("default")))',
        "#endif",
        "REGION_API uint32_t result_pc(void){return PC;}",
        "REGION_API __attribute__((noinline))",
        "void execute_region(uint8_t *regs, uint8_t *memory, uint32_t guest_pc) {",
        " MEM=memory;",
        " memcpy(R,regs,0x2000);",
        " PC=guest_pc;",
        " goto dispatch;",
    ]
    for v in selected:
        lines.append(f" u128 {names[v]};")

    def flush():
        return [f" wr(R+0x{v[1]:x},{v[2]},{names[v]});"
                for v in selected if v in written]

    def direct(target: int) -> str:
        # Within-region jumps keep the cache; outside goes to dispatcher,
        # which is allowed to enter any original guest PC later.
        if target in addrs:
            return f"goto B_{target:x};"
        return " ".join(flush()+[f"PC=0x{target:x}u; goto finished;"])

    # Separate reload point for ANY guest PC, including interior PCs. The
    # block never executes these reloads during sequential fallthrough.
    for pc,_size,_ops in insns:
        if entry_policy=="start_only" and pc!=region.start:
            continue
        lines.append(f"L_{pc:x}:")
        for v in selected:
            lines.append(f" {names[v]}=rd(R+0x{v[1]:x},{v[2]});")
        lines.append(f" goto B_{pc:x};")

    g=Gen({})
    g.reg_cache=names
    for index,(pc,size,ops) in enumerate(insns):
        lines.append(f"B_{pc:x}: {{")
        offsets=temporary_layout(ops)
        if offsets is None:
            raise CFGError("no safe per-instruction unique layout")
        g.temp_offsets=offsets
        lines.append(f" uint8_t T[{max(1,len(offsets))}];")
        rel_targets=set()
        for j,(mn,out,args) in enumerate(ops):
            if mn in BRANCH_OPS and args and args[0][0]=="c":
                target=j+rel(args[0][1])
                if target<0:
                    raise CFGError("invalid internal p-code relative branch")
                if target<=len(ops):
                    rel_targets.add(target)
                # Higher target goes to next guest PC, exactly as pcode2c.
        for op_index,(mn,out,args) in enumerate(ops):
            if op_index in rel_targets:
                lines.append(f" U_{pc:x}_{op_index}:;")
            def jump(v, i=op_index, address=pc, length=size):
                if v[0]=="c":
                    to=i+rel(v[1])
                    if 0<=to<len(ops):
                        return f"goto U_{address:x}_{to};"
                    if to<0:
                        raise CFGError("invalid p-code relative jump")
                    return direct(address+length)
                if v[0]=="m":
                    return direct(v[1])
                raise CFGError("unsupported p-code branch target")
            code=g.op(mn,out,args,jump,None)
            if "unsupported(" in code:
                raise CFGError("unsupported p-code op in region")
            lines.append(" "+code)
        if len(ops) in rel_targets:
            lines.append(f" U_{pc:x}_{len(ops)}:;")
        lines.append("}")
        following=pc+size
        lines.append(" "+direct(following))
    if g.unsupported:
        raise CFGError("unexpected unsupported generator operation")
    lines.extend([
        "dispatch:",
        " switch(PC) {",
        *[f" case 0x{pc:x}u: goto L_{pc:x};" for pc in sorted(addrs)
          if entry_policy=="all_entries" or pc==region.start],
        " default: goto finished;",
        " }",
        "finished:",
        " memcpy(regs,R,0x2000);",
        "}",
    ])
    source="\n".join(lines)+"\n"
    if "U+" in source or " U[" not in source:
        raise CFGError("unsafe unproven global temporary read/write")
    return source,selected
