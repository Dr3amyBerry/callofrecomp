"""Phase14B conservative byte-granular register boundary contracts.

Read-only static analysis; NOT an optimizer. Values in the x86 R register
array are tracked by byte, including partial GPR views, EFLAGS and x87 slots.
P-code paths within a single x86 instruction form a control-flow graph.
Opaque guest-memory effects and nonlocal transfers block promotion.

A region may be entered at ANY instruction PC by the existing dispatcher.
Therefore these summaries are diagnostic upper bounds, not permission to
cache a register or remove a write.
"""
from __future__ import annotations

from collections import Counter, deque
from typing import NamedTuple

from region_cfg import signed_relative, extract_function, recover_function_cfg, CFGError

REGISTER_BYTES=0x2000
ALL_REGISTER_BYTES=(1<<(REGISTER_BYTES))-1
FLAGS=tuple((off,off+1) for off in (0x200,0x202,0x206,0x207,0x20b))
X87=(0x1100,0x1180)

OPAQUE=set(("CALLOTHER","LOAD","STORE","CALL","CALLIND","BRANCHIND","RETURN"))
TERMINAL=set(("BRANCH","CALL","BRANCHIND","CALLIND","RETURN"))
CONTROL=set(("BRANCH","CALL","CBRANCH","BRANCHIND","CALLIND","RETURN"))
SUPPORTED=set("""COPY LOAD STORE INT_ADD INT_SUB INT_MULT INT_AND INT_OR INT_XOR
INT_LEFT INT_RIGHT INT_SRIGHT INT_EQUAL INT_NOTEQUAL INT_LESS INT_LESSEQUAL
INT_SLESS INT_SLESSEQUAL INT_CARRY INT_SCARRY INT_SBORROW INT_ZEXT INT_SEXT
INT_NEGATE INT_2COMP BOOL_NEGATE BOOL_AND BOOL_OR BOOL_XOR PIECE SUBPIECE
POPCOUNT FLOAT_ADD FLOAT_SUB FLOAT_MULT FLOAT_DIV FLOAT_EQUAL FLOAT_NOTEQUAL
FLOAT_LESS FLOAT_LESSEQUAL FLOAT_NAN FLOAT_NEG FLOAT_ABS FLOAT_SQRT
FLOAT_CEIL FLOAT_FLOOR ROUND FLOAT2FLOAT INT2FLOAT TRUNC INT_DIV INT_REM
INT_SDIV INT_SREM CALLOTHER BRANCH CALL CBRANCH BRANCHIND CALLIND RETURN""".split())


class InstructionState(NamedTuple):
    read_before_write: int
    may_read: int
    may_write: int
    must_write: int
    hazards: tuple[str,...]


def mask(varnode) -> int:
    if not varnode or varnode[0]!="r":
        return 0
    _space,off,length=varnode
    if not isinstance(off,int) or not isinstance(length,int) or off<0 or length<=0 or off+length>REGISTER_BYTES:
        raise CFGError("register read/write outside original R[0x2000]")
    return ((1<<length)-1)<<off


def mask_ranges(bits: int) -> list[list[int]]:
    """Represent exact byte sets as [start,end_exclusive] (not guest data)."""
    if not isinstance(bits,int) or bits<0 or bits & ~ALL_REGISTER_BYTES:
        raise CFGError("invalid register-byte mask")
    result=[]
    pos=0
    while bits:
        # Remove long leading zero gaps in O(1) via trailing-bit detection.
        first=(bits & -bits).bit_length()-1
        pos+=first
        bits >>= first
        # Simpler contiguous-bit count using complement's first set bit.
        inv=(~bits)&ALL_REGISTER_BYTES
        length=((inv&-inv).bit_length()-1) if inv else REGISTER_BYTES-pos
        result.append([pos,pos+length])
        bits >>= length
        pos+=length
    return result


def _successors(ops: list, i: int) -> tuple[int,...]:
    mn,_out,inputs=ops[i]
    if mn in ("BRANCHIND","CALLIND","RETURN"):
        return ()
    if mn in ("BRANCH","CALL","CBRANCH"):
        fall=(i+1,) if mn=="CBRANCH" else ()
        if not inputs or not inputs[0]:
            return fall
        dest=inputs[0]
        if dest[0]=="c":
            index=i+signed_relative(dest[1])
            if index<0:
                return fall
            if index>=len(ops):
                return tuple(sorted(set(fall+(len(ops),))))
            return tuple(sorted(set(fall+(index,))))
        # Direct guest-PC jump is an exit from this instruction.
        return fall
    return (i+1,)


def analyze_instruction(ops: list) -> InstructionState:
    """Path-sensitive MUST-write and MAY-read-before-write at an x86 PC.

    Dataflow merge is INTERSECTION of definitely-written bytes. A conditional
    p-code branch can skip a write; then a later read must be live-in.
    """
    if not ops:
        return InstructionState(ALL_REGISTER_BYTES,ALL_REGISTER_BYTES,0,0,
                                ("missing_pcode",))
    incoming={0:0}
    queue=deque([0])
    may_read=may_write=read_before_write=0
    hazards=set()
    reached=set()
    # Monotone fixedpoint: incoming register masks only shrink on joins.
    while queue:
        i=queue.popleft()
        defined=incoming[i]
        if i==len(ops):
            continue
        if not 0<=i<len(ops):
            hazards.add("invalid_micro_target")
            continue
        reached.add(i)
        mn,out,args=ops[i]
        if mn not in SUPPORTED:
            hazards.add("unknown_pcode_operation")
        if mn in OPAQUE:
            hazards.add("opaque_"+mn.lower())
        if mn in ("BRANCH","CBRANCH","CALL") and args and args[0] and args[0][0]=="c":
            if i+signed_relative(args[0][1])<0:
                hazards.add("invalid_micro_target")
        reads=0
        for arg in args:
            reads|=mask(arg)
        writes=mask(out)
        may_read|=reads
        may_write|=writes
        read_before_write|=reads&~defined
        successors=_successors(ops,i)
        after=defined|writes
        for dest in successors:
            if dest==len(ops):
                continue
            if dest not in incoming:
                incoming[dest]=after
                queue.append(dest)
            else:
                merged=incoming[dest]&after
                if merged!=incoming[dest]:
                    incoming[dest]=merged
                    queue.append(dest)
    # Recorded interim exits could have been reached before a looping
    # predecessor removed a definite write. Re-evaluate ALL exits at final
    # fixedpoint rather than trusting stale snapshots.
    masks=[]
    for i in reached:
        nexts=_successors(ops,i)
        if not nexts or len(ops) in nexts:
            masks.append(incoming[i]|mask(ops[i][1]))
    must_write=0
    if masks:
        must_write=masks[0]
        for bits in masks[1:]:
            must_write&=bits
    if "unknown_pcode_operation" in hazards or "invalid_micro_target" in hazards:
        read_before_write|=ALL_REGISTER_BYTES
        must_write=0
    if any(e=="opaque_callother" for e in hazards):
        read_before_write|=ALL_REGISTER_BYTES
        must_write=0
    # Guest call exposes every architectural register to callee at its exit.
    if any(x in hazards for x in ("opaque_call","opaque_callind","opaque_return","opaque_branchind")):
        # Assumed external reader observes all guest registers unless
        # prior writes definitively replaced their incoming bytes.
        read_before_write |= ALL_REGISTER_BYTES & ~must_write
    if any(mn in ("BRANCH","CALL","CBRANCH") and args and args[0] and args[0][0]=="c"
           and i+signed_relative(args[0][1])<=i
           for i,(mn,_out,args) in enumerate(ops)):
        hazards.add("possible_micro_cycle")
    return InstructionState(read_before_write&ALL_REGISTER_BYTES,may_read,
                            may_write,must_write,tuple(sorted(hazards)))


def _program_blocks(instructions: list, mapping: dict, entry: int):
    body,_,_=extract_function(instructions,mapping,entry)
    cfg=recover_function_cfg(instructions,mapping,entry)
    by_pc={pc:ops for pc,_width,ops in body}
    reports=[]
    for b in cfg["basic_blocks"]:
        pcs=[int(a,16) for a in b["pcs"]]
        must=may=uses=reads=0
        hazards=Counter()
        for pc in pcs:
            ins=analyze_instruction(by_pc[pc])
            uses |= ins.read_before_write & ~must
            reads|=ins.may_read
            may|=ins.may_write
            must|=ins.must_write
            hazards.update(ins.hazards)
        # Any block can be entered at its first PC, but the dispatcher also
        # allows entry at internal instruction PCs.
        reports.append({
            "start_pc":b["start_pc"],"instruction_count":len(pcs),
            "read_before_write_mask":uses,"may_read_mask":reads,
            "may_write_mask":may,"must_write_mask":must,
            "hazards":dict(sorted(hazards.items())),
            "successor_blocks":tuple(sorted(set(e["target_block"] for e in b["outgoing"]
                                                    if e["target_block"] is not None))),
            "has_external_exit":any(e["target_block"] is None for e in b["outgoing"]),
        })
    return cfg,reports


def region_contract(instructions: list, mapping: dict, entry: int) -> dict:
    """Read-only function boundary and block liveness, conservative at exits."""
    cfg,blocks=_program_blocks(instructions,mapping,entry)
    n=len(blocks)
    live_in=[0]*n
    live_out=[0]*n
    # Every external exit must preserve FULL guest R to the dispatcher.
    # No outgoing read is assumed absent: external R state is observable.
    for iteration in range(1,n*REGISTER_BYTES+2):
        changed=False
        for i in range(n-1,-1,-1):
            b=blocks[i]
            out=ALL_REGISTER_BYTES if b["has_external_exit"] else 0
            for succ in b["successor_blocks"]:
                out|=live_in[succ]
            uses=b["read_before_write_mask"]
            ins=uses|(out&~b["must_write_mask"])
            if out!=live_out[i] or ins!=live_in[i]:
                live_out[i],live_in[i]=out,ins
                changed=True
        if not changed:
            break
    else:
        raise CFGError("register liveness failed to converge")
    covered_may_read=0
    covered_may_write=0
    hazards=Counter()
    block_summaries=[]
    for i,b in enumerate(blocks):
        covered_may_read|=b["may_read_mask"]
        covered_may_write|=b["may_write_mask"]
        hazards.update(b["hazards"])
        block_summaries.append({
            "start_pc":b["start_pc"],"instruction_count":b["instruction_count"],
            "reads_before_def_bytes":mask_ranges(b["read_before_write_mask"]),
            "must_write_bytes":mask_ranges(b["must_write_mask"]),
            "may_write_bytes":mask_ranges(b["may_write_mask"]),
            "live_in_bytes":mask_ranges(live_in[i]),
            "live_out_bytes":mask_ranges(live_out[i]),
            "needs_full_R_flush_on_external_exit":b["has_external_exit"],
            "hazards":b["hazards"],
        })
    x87_mask=((1<<(X87[1]-X87[0]))-1)<<X87[0]
    flags_mask=sum(((1<<(hi-lo))-1)<<lo for lo,hi in FLAGS)
    return {
        "entry_va":cfg["entry_va"],"block_count":cfg["block_count"],
        "instruction_count":cfg["instruction_count"],
        "bytes_of_R":REGISTER_BYTES,
        "may_read_arch_bytes":covered_may_read.bit_count(),
        "may_write_arch_bytes":covered_may_write.bit_count(),
        "x87_register_bytes_read":(covered_may_read&x87_mask).bit_count(),
        "x87_register_bytes_written":(covered_may_write&x87_mask).bit_count(),
        "eflags_bytes_read":(covered_may_read&flags_mask).bit_count(),
        "eflags_bytes_written":(covered_may_write&flags_mask).bit_count(),
        "hazards":dict(sorted(hazards.items())),
        "external_cfg_exits":len(cfg["outgoing_external_edges"])+len(cfg["dynamic_exit_edges"]),
        "entry_policy":"ANY valid original x86 instruction PC may enter via dispatcher",
        "proof_limit":"Conservative per-byte MUST and MAY across original p-code; no x86 independent state oracle for full body",
        "promote_registers_in_production":False,
        "blocks":block_summaries,
    }
