#!/usr/bin/env python3
"""Phase14F source-level audit: what Android guest fault recovery actually needs.

This inspects repository source and the existing build gates, NOT Android
execution. It always reports 'not ready' unless separately certified by
actual original-x86 page-fault, native-device signal, concurrency, and end-
to-end dispatcher tests. Syntactic matches never authorize enabling CFG14.
The current Android SIGSEGV handler is intentionally absent: Java/ART owns
process-wide fault signals and Linux desktop's fallback reports and exits.

Exit code 0 = expected *blocked* safeguards are intact, not deployability.
Exit code 4 = a block safeguard is missing/modified (fail closed).
Source paths and evidence are bounded and repository-local.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[3]


def audit_runtime_sources(guest: str, cmake: str, builder: str) -> dict:
    """Static triage, never runtime safety certification."""
    signal_scope=re.search(
        r"#ifndef\s+__ANDROID__\s*"
        r"(?:(?!#endif).){0,1000}?"
        r"sigaction\s*\(\s*SIGSEGV\s*,"
        r"(?:(?!#endif).){0,400}?"
        r"sigaction\s*\(\s*SIGBUS\s*,"
        r"(?:(?!#endif).){0,200}?#endif",
        guest, re.S)
    unix_fatal=re.search(
        r"static\s+void\s+on_fault\s*\([^)]*\)\s*\{"
        r"(?:(?!\n\}).){0,550}?"
        r"_exit\s*\(\s*3\s*\)",
        guest, re.S)
    facts={
        "android_guest_fault_handler_installed_by_current_guest_init":False,
        "desktop_sigsegv_sigbus_intentionally_excluded_on_android":bool(signal_scope),
        "existing_unix_fault_handler_is_terminating":bool(unix_fatal),
        "R_is_global_not_tls":bool(re.search(r"(?m)^uint8_t\s+R\s*\[\s*0x2000\s*\]",guest)),
        "PC_is_global_not_tls":bool(re.search(r"(?m)^uint32_t\s+PC\s*;",guest)),
        "guest_mem_reservation_4GiB":bool(
            re.search(r"mmap\s*\(\s*NULL\s*,\s*1ull\s*<<\s*32",guest)),
        "guest_page_decommit_protects_none":bool(
            re.search(r"mprotect\s*\([^;]*PROT_NONE",guest)),
        "guest_data_commit_uses_mprotect":bool(
            re.search(r"mprotect\s*\([^;]*PROT_READ\s*\|\s*PROT_WRITE",guest)),
        "original_dispatcher_chunk_fallback_present":bool(
            re.search(r"dispatch_index_find\s*\(",guest) and
            re.search(r"all_chunks\s*\[\s*found\s*\]\.fn\s*\(\s*\)",guest)),
        "direct_CMake_CFG14_ON_fail_closed":bool(re.search(
            r"if\s*\(\s*CODRECOMP_CFG14_GEOM_REGION\s*\)"
            r"(?:(?!endif\(\)).){0,1500}?"
            r"message\s*\(\s*FATAL_ERROR\s*"
            r"(?:(?!endif\(\)).){0,400}?"
            r"CFG14 FAULT_STATE_UNSAFE",cmake,re.S)),
        "build_android_CFG14_ON_fail_closed":bool(
            re.search(r"if\s+args\.cfg14_geom_region\s*:\s*"
                      r"(?:(?!\n\S).){0,600}?"
                      r"parser\.error\s*\(\s*\"--cfg14-geom-region BLOCKED",builder,re.S)),
    }
    required_block_guards=(
        "desktop_sigsegv_sigbus_intentionally_excluded_on_android",
        "original_dispatcher_chunk_fallback_present",
        "direct_CMake_CFG14_ON_fail_closed",
        "build_android_CFG14_ON_fail_closed",
    )
    intact=all(facts[key] for key in required_block_guards)
    # Unknown semantics are unresolved until *runtime/device* validation,
    # even if a future source file happens to contain a sigaction call.
    blockers=[
        "Android ART/JNI signal owner: no process-wide replacement/SEH recovery verified",
        "No signal-safe guest fault snapshot + recovery trampoline attached to dispatcher",
        "R and PC are process-global; guest threads/async faults have no isolated context",
        "No atomic checked cross-page guest spans and page-permission model",
        "No full-x86 AF/DF/x87/SEH semantics at guest fault handoff",
        "No Android device tests for uncommitted, decommitted, readonly or crossing-page access",
        "No ARM64 gameplay A/B CPU-ms-per-frame measurement",
    ]
    return {
        "schema":"phase14f-android-guest-fault-recovery-readiness-source-audit-v1",
        "kind":"source-level-diagnostic_not_runtime_oracle",
        "facts":facts,
        "safety_build_gates_intact":intact,
        "ready_to_enable_CFG14_on_Android":False,
        "blocked_by":blockers,
        "required_next_actions":[
            "Keep CFG14 direct-CMake and Python-builder fatal gates intact",
            "Define original-PC checkpoint/R snapshot and guest-side fault taxonomy",
            "Implement bounded overflow/cross-page checked guest address probes and protection metadata",
            "Choose ART-compatible exception interception or explicit checked access API; never naively longjmp from arbitrary SIGSEGV",
            "Handle asynchronous/non-guest faults without swallowing ART and native signals",
            "Establish thread-local or single-thread-enforced architectural snapshot ownership",
            "Compare actual runtime resumed execution with Unicorn x86 and original translator, including committed STORE counts",
            "Require Android ARM64 APK functional regression and repeatable TECNO CPU-ms/frame A/B/A/B",
        ],
    }


def main(argv=None)->int:
    parser=argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out",type=Path,required=True,
                        help="new ignored .local/profiles/*.json diagnostic")
    args=parser.parse_args(argv)
    dest=args.out.resolve()
    root=(ROOT/".local/profiles").resolve()
    if (not dest.is_relative_to(root) or dest==root or dest.exists() or
            dest.suffix.lower()!=".json"):
        parser.error("output must be a NEW JSON inside ignored .local/profiles")
    files={
        "guest.c":ROOT/"tools/recomp/runtime/guest.c",
        "android/CMakeLists.txt":ROOT/"android/CMakeLists.txt",
        "build_android.py":ROOT/"tools/recomp/build_android.py",
    }
    sources={name:path.read_text(encoding="utf-8")
             for name,path in files.items()}
    result=audit_runtime_sources(
        sources["guest.c"],sources["android/CMakeLists.txt"],
        sources["build_android.py"])
    result["source_sha256"]={
        name:hashlib.sha256(data.encode("utf-8")).hexdigest()
        for name,data in sources.items()}
    dest.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    if not result["safety_build_gates_intact"]:
        print("PHASE14F_RUNTIME_GATES_BROKEN",dest,file=sys.stderr,flush=True)
        return 4
    print("PHASE14F_RUNTIME_GATES_INTACT_NOT_READY_FOR_ANDROID",dest,flush=True)
    return 0


if __name__=="__main__":
    raise SystemExit(main())
