#!/usr/bin/env python3
"""Compare a Vulkan device census with the pinned Mesa Zink GL2.1 profile.

A negative result is meaningful: one required Vulkan capability is missing.
A positive result would NOT prove runtime compatibility: full Vulkan Profiles
feature/format checks and a working EGL integration would still be required.
"""
from __future__ import annotations
import argparse
import json
import re
from pathlib import Path

FEATURE=re.compile(r'^ZINK_FEATURE name=(\w+) supported=([01])$',re.MULTILINE)
EXTENSION=re.compile(
    r'^ZINK_EXTENSION name=(VK_\w+) supported=([01]) advertised=([01]) core_promoted=([01])$',
    re.MULTILINE)
GPU=re.compile(r'^ZINK_GPU index=(\d+) name=(.*?) api=(\d+\.\d+\.\d+) vendor=([^ ]+) device=([^\s]+)$',re.MULTILINE)
FULL=re.compile(r'^ZINK_SUMMARY gpu=(\d+) conservative_missing=(\d+) full_profile_checked=0$',re.MULTILINE)
REQUIRED_PROFILE="VP_ZINK_gl21_baseline"

def analyze(profile_json: dict, log: str) -> dict:
    profiles=profile_json.get("profiles",{})
    profile=profiles.get(REQUIRED_PROFILE)
    if not isinstance(profile,dict):
        raise ValueError("Mesa source does not contain the GL2.1 Zink requirements profile")
    cap=profile_json.get("capabilities",{})
    baseline=cap.get("gl21_baseline",{})
    vulkan10=cap.get("vulkan10requirements",{})
    if not baseline.get("extensions") or not baseline.get("features"):
        raise ValueError("Mesa Zink baseline is missing expected requirement groups")
    gpu=GPU.search(log)
    full=FULL.search(log)
    if not gpu or not full or gpu.group(1)!=full.group(1):
        raise ValueError("Missing or conflicting completed Zink Vulkan census")
    features={name: value=="1" for name,value in FEATURE.findall(log)}
    extensions={name: {
        "supported":support=="1",
        "advertised":advertise=="1",
        "core_promoted":promoted=="1"
    } for name,support,advertise,promoted in EXTENSION.findall(log)}
    required_core={
        **vulkan10.get("features",{}).get("VkPhysicalDeviceFeatures",{}),
        **baseline.get("features",{}).get("VkPhysicalDeviceFeatures",{})
    }
    unchecked=[name for name,value in required_core.items()
               if value is True and name not in features]
    missing_core=[name for name,value in required_core.items()
                  if value is True and name in features and not features[name]]
    required_extensions=list(baseline.get("extensions",{}))
    unchecked_ext=[e for e in required_extensions if e not in extensions]
    missing_ext=[e for e in required_extensions
                 if e in extensions and not extensions[e]["supported"]]
    if unchecked or unchecked_ext:
        raise ValueError("Incomplete census, missing checks: "+", ".join(unchecked+unchecked_ext))
    return {
        "profile":REQUIRED_PROFILE,
        "profile_api_version":profile.get("api-version"),
        "gpu":gpu.group(2),
        "vulkan_api_version":gpu.group(3),
        "missing_required_core_features":missing_core,
        "missing_required_extensions_after_core_promotion":missing_ext,
        "required_extension_count":len(required_extensions),
        "checked_core_feature_count":len(required_core),
        "checked_baseline_compatible":not (missing_core or missing_ext),
        "full_profile_checked":False,
        "complete_build_or_game_performance_test":False,
        "limitations":["Additional extended Vulkan feature structs, alternate baseline branch, formats, limits and EGL/Android integration require further testing.",
                       "No FPS or GPU timing can be inferred from device support data."]
    }

def main()->int:
    p=argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--mesa-profile",type=Path,required=True)
    p.add_argument("--probe-log",type=Path,required=True)
    p.add_argument("--json-out",type=Path)
    args=p.parse_args()
    result=analyze(json.loads(args.mesa_profile.read_text(encoding="utf-8")),
                   args.probe_log.read_text(encoding="utf-8",errors="replace"))
    if args.json_out:
        args.json_out.parent.mkdir(parents=True,exist_ok=True)
        args.json_out.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(result,indent=2))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
