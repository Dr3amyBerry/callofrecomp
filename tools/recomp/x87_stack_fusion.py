"""Exact basic-block fusion for the repeated x87 ten-byte stack shifts.

Only groups of *seven* consecutive p-code COPY operations, matching the
audited 16-byte-stride/10-byte-value architectural slots, are eligible.
The transformation preserves every p-code index and rejects branches into
the interior. Caller is responsible for original-binary identity gating.
"""
from __future__ import annotations

FIRST=0x1100
STEP=16
WIDTH=10
PUSH=tuple((FIRST+STEP*(i+1),FIRST+STEP*i) for i in range(6,-1,-1))
POP=tuple((FIRST+STEP*i,FIRST+STEP*(i+1)) for i in range(7))
PATTERNS={"push":PUSH,"pop":POP}

def plan_x87_shift(ops, *, removed=(), branch_targets=()):
    """Return op index -> 'push'/'pop' or None (consumed-op placeholder).

    These are ordered byte-wise COPY operations. Every source/destination
    slot has 10 observable bytes and an untouched 6-byte gap. This is NOT
    a generalized 16-byte register memmove.
    """
    removed=frozenset(removed)
    targets=frozenset(branch_targets)
    if any(not isinstance(i,int) or not 0<=i<len(ops) for i in removed):
        raise ValueError("invalid removed p-code operation")
    if any(not isinstance(i,int) or not 0<=i<=len(ops) for i in targets):
        raise ValueError("invalid local p-code branch target")
    mapping={}
    i=0
    while i<=len(ops)-7:
        if any(j in removed or j in mapping for j in range(i,i+7)) or any(
            j in targets for j in range(i+1,i+7)
        ):
            i+=1
            continue
        sequence=[]
        for mn,out,inputs in ops[i:i+7]:
            if (mn!="COPY" or not out or out[0]!="r" or out[2]!=WIDTH
                    or len(inputs)!=1 or not inputs[0] or inputs[0][0]!="r"
                    or inputs[0][2]!=WIDTH):
                break
            sequence.append((out[1],inputs[0][1]))
        if len(sequence)==7:
            direction=next((name for name,pattern in PATTERNS.items()
                            if tuple(sequence)==pattern),None)
            if direction:
                mapping[i]=direction
                mapping.update((j,None) for j in range(i+1,i+7))
                i+=7
                continue
        i+=1
    return mapping
