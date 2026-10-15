#!/usr/bin/env python3
"""Classify already-symbolized inlined CPU samples from an archived profile.

A leaf-inline-frame class is NOT an exclusive time attribution: profiler samples
are weighted observations, inline stacks overlap, and frame order depends on DWARF.
This file never reads game data, accesses ADB or changes production builds.
"""
from collections import Counter
from itertools import combinations

CLASSES=("memcpy","rd","wr","f2d","d2f")

def summarize(rows):
    total=0
    leaf=Counter()
    inclusive=Counter()
    overlap=Counter()
    leaf_pc={k:Counter() for k in (*CLASSES,"other")}
    for row in rows:
        hits=row["samples"]
        pc=row["guest_pc"]
        frames=row["frames"]
        if type(hits) is not int or hits<=0 or type(pc) is not int or pc<0:
            raise ValueError("Expected positive integer samples and guest PC")
        if not isinstance(frames,(tuple,list)) or any(not isinstance(f,str) for f in frames):
            raise ValueError("Expected DWARF inline-function names in leaf-first order")
        total+=hits
        matched=set(frames)&set(CLASSES)
        for name in matched:
            inclusive[name]+=hits
        for left,right in combinations(sorted(matched),2):
            overlap[f"{left}+{right}"]+=hits
        first=next((f for f in frames if f in CLASSES),"other")
        leaf[first]+=hits
        leaf_pc[first][pc]+=hits
    if sum(leaf.values())!=total:
        raise AssertionError("Leaf classes must partition resolved samples")
    if any(inclusive[k]>total for k in CLASSES):
        raise AssertionError("Inclusive count exceeds resolved sample count")
    return {
        "resolved_samples":total,
        "inclusive_inline_samples":{k:inclusive[k] for k in CLASSES},
        "innermost_named_inline_frame_samples":{k:leaf[k] for k in (*CLASSES,"other")},
        "pairwise_overlaps":dict(sorted(overlap.items())),
        "top_guest_pc_by_innermost_frame":{
            k:[[hex(pc),n] for pc,n in leaf_pc[k].most_common(8)]
            for k in CLASSES if leaf_pc[k]
        },
        "method_limitations":"DWARF inlining + CPU samples, not exclusive function time, call rates or FPS",
    }
