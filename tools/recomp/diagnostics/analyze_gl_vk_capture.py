#!/usr/bin/env python3
"""Summarize opt-in GL->Vulkan state observations, never Vulkan gameplay FPS."""
from __future__ import annotations
import argparse, json, re
from pathlib import Path

MARKER=re.compile(
    r"gl vkstate:\s+tracked=(\d+) unsupported=(\d+) mask=0x([0-9a-f]+)"
    r" state_ready=([01]) mvproj_hash=([0-9a-f]+)"
    r" depth=([01]) blend=([01]) stencil=([01]) alpha=([01])"
    r" tex0=(\d+) tex1=(\d+) matrix_push=(\d+) matrix_pop=(\d+)"
)
FAMILY_RE=re.compile(
    r"legacy_tex=(\d+) legacy_upload=(\d+) legacy_matrix=(\d+)"
    r" legacy_vertex=(\d+) legacy_light=(\d+) legacy_buffer=(\d+)"
    r" legacy_other=(\d+)"
)
FAMILY_NAMES=("texture_state","texture_upload","matrix_transform",
              "vertex_input","lighting_fog","buffer","other")
FLAGS={0x01:"unknown_capability",0x02:"unsupported_enum",
       0x04:"matrix_error",0x08:"texture_unit_or_target",
       0x10:"untranslated_legacy_gl",0x20:"invalid_pointer"}

def analyze(source: str) -> dict:
    samples=[]
    for line in source.splitlines():
        m=MARKER.search(line)
        if not m: continue
        g=m.groups()
        family_match=FAMILY_RE.search(line)
        family={name:int(value) for name,value in zip(FAMILY_NAMES,family_match.groups())} if family_match else None
        samples.append({
            "legacy_families":family,
            "tracked":int(g[0]),"unsupported":int(g[1]),
            "mask":int(g[2],16),"subset_ready":bool(int(g[3])),
            "matrix_hash":g[4],"depth_enabled":bool(int(g[5])),
            "blend_enabled":bool(int(g[6])),"stencil_enabled":bool(int(g[7])),
            "alpha_test_enabled":bool(int(g[8])),
            "texture0":int(g[9]),"texture1":int(g[10]),
            "matrix_pushes":int(g[11]),"matrix_pops":int(g[12])
        })
    if not samples:
        raise ValueError("No GL->Vulkan capture markers. Build with --gl-vk-state-capture.")
    first,last=samples[0],samples[-1]
    for field in ("tracked","unsupported","matrix_pushes","matrix_pops"):
        for x,y in zip(samples,samples[1:]):
            if y[field]<x[field]:
                raise ValueError(f"Capture counter '{field}' decreased; mixed sessions")
    mask=0
    for sample in samples: mask|=sample["mask"]
    return {
        "kind":"GL4ES gameplay state observation, NOT Vulkan gameplay FPS",
        "samples":len(samples),
        "capture_mode":"diagnostic observer, GL4ES remains renderer",
        "subset_ready_in_any_sample":any(s["subset_ready"] for s in samples),
        "subset_ready_in_all_samples":all(s["subset_ready"] for s in samples),
        "unsupported_mask_union":f"0x{mask:x}",
        "unsupported_categories":[name for flag,name in FLAGS.items() if mask&flag],
        "legacy_family_totals_last":last["legacy_families"],
        "legacy_family_deltas":(
            {name:last["legacy_families"][name]-first["legacy_families"][name]
             for name in FAMILY_NAMES}
            if first["legacy_families"] and last["legacy_families"] else None),
        "tracked_delta_first_to_last":last["tracked"]-first["tracked"],
        "unsupported_delta_first_to_last":last["unsupported"]-first["unsupported"],
        "last":last,
        "fps_comparable":False,
        "vulkan_backend_present":False,
    }

def main() -> int:
    ap=argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--log",required=True,type=Path)
    ap.add_argument("--json-out",type=Path)
    args=ap.parse_args()
    result=analyze(args.log.read_text(encoding="utf-8",errors="replace"))
    if args.json_out:
        args.json_out.parent.mkdir(parents=True,exist_ok=True)
        args.json_out.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(result,indent=2))
    return 0
if __name__=="__main__":
    raise SystemExit(main())
