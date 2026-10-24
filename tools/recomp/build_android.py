#!/usr/bin/env python3
"""Build a private ARM64 debug APK using the installed Android SDK/NDK.

No Gradle downloads, original files or generated C are bundled as APK assets.
Dependency sources and all build/signing artifacts stay in ignored directories.
"""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import struct
import sys
import zipfile

DEPENDENCIES = {
    "SDL": ("https://github.com/libsdl-org/SDL.git", "5d249570393f7a37e037abf22cd6012a4cc56a71"),
    "gl4es": ("https://github.com/ptitSeb/gl4es.git", "ec16bedd8819c475326f4f1a3063772c6d986e06"),
    "RetroTouch": ("https://github.com/Andiweli/RetroTouch.git", "cdc01db0a6d6f9acaef72d7c496f5929b1bc3b8b"),
}


def run(*args, **kwargs):
    subprocess.run([str(a) for a in args], check=True, **kwargs)


def latest(parent):
    dirs = [d for d in parent.iterdir() if d.is_dir()]
    if not dirs:
        raise SystemExit(f"No installed versions under {parent}")
    return max(dirs, key=lambda p: tuple(int(n) for n in p.name.replace("android-", "").split(".") if n.isdigit()))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sdk", type=Path, default=os.environ.get("ANDROID_SDK_ROOT", os.environ.get("ANDROID_HOME")))
    parser.add_argument("--ndk", type=Path)
    parser.add_argument("--java", type=Path, default=os.environ.get("JAVA_HOME"))
    parser.add_argument("--jobs", type=int, default=2)
    parser.add_argument("--abi", choices=("arm64-v8a", "x86_64"), default="arm64-v8a")
    parser.add_argument("--recomp-opt", choices=("0", "1"), default="1")
    parser.add_argument("--cpu-profile", action="store_true",
                        help="compile optional sampled guest CPU diagnostics")
    parser.add_argument("--gl-profile", action="store_true",
                        help="compile optional guest OpenGL call counters")
    parser.add_argument("--gl-time-profile", action="store_true",
                        help="compile opt-in CPU timing for GL4ES/GLES entry points")
    parser.add_argument("--gl-state-filter", action="store_true",
                        help="opt-in: drop provably redundant guest GL state calls before GL4ES "
                             "(enable/bind/active-texture/depth/blend/cull); default OFF")
    parser.add_argument("--gl-vk-state-capture", action="store_true",
                        help="compile opt-in GL->Vulkan typed state observer, NOT a Vulkan game backend; default OFF")
    parser.add_argument("--wsa-uncap-bench", action="store_true",
                        help="DIAGNOSTIC WSA x86_64 ONLY: bypass host 60 FPS cap; default OFF")
    parser.add_argument("--core-hot-o2", action="store_true",
                        help="ARM64 offline-profile-guided CoDSP p0/p1/p4 compilation "
                             "at strict-FP -O2; OFF by default")
    parser.add_argument("--core-hot-o2-parts", metavar="p0,p1,p4",
                        help="optional comma-separated subset of p0,p1,p4; "
                             "requires --core-hot-o2, never changes defaults")
    parser.add_argument("--cfg14-geom-region", action="store_true",
                        help="EXP: verified CoDSP 1.5 geometry block start-only native "
                             "CFG cache with original dispatcher fallback; OFF by default")
    parser.add_argument("--render-o2", action="store_true",
                        help="experiment: compile CoDSP renderer partitions p10 and p11 with -O2")
    parser.add_argument("--hot-x87-transform", action="store_true",
                        help="BLOCKED: legacy double transform fails original x87 precision")
    parser.add_argument("--fast-copy32", action="store_true",
                        help="experiment: accelerate CoDSP 1.5 32-byte copy loop; default OFF")
    parser.add_argument("--visibility-o2", action="store_true",
                        help="experiment: compile only CoDSP visibility p8 with -O2; default OFF")
    parser.add_argument("--x87-nan-bits", action="store_true",
                        help="experiment: binary80 NaN bit checks in CoDSP geometry/visibility p1/p8; default OFF")
    parser.add_argument("--x87-normal-f2d", action="store_true",
                        help="experiment: exact canonical x87 normal-to-double path in CoDSP p1/p8; default OFF")
    parser.add_argument("--x87-normal-f2d-p4", action="store_true",
                        help="ARM64-only experiment: extend exact x87 conversion to hot CoDSP p4, OFF")
    parser.add_argument("--x87-normal-f2d-p4-selective", action="store_true",
                        help="ARM64 experiment: x87 fast conversion only in four sampled p4 function bodies, OFF")
    parser.add_argument("--x87-normal-f2d-p4-profiled", action="store_true",
                        help="ARM64 experiment: only 277 x87 sites at 124 historically sampled CoDSP p4 guest PCs, OFF")
    parser.add_argument("--arm64-x87-sign-bits", action="store_true",
                        help="ARM64 opt-in: exact binary80 sign toggle at 3 verified CoDSP FCHS PCs; OFF")
    parser.add_argument("--arm64-x87-fld32-normal", action="store_true",
                        help="ARM64 opt-in: exact normal binary32->binary80 mapping at 39 CoDSP hot PCs; OFF")
    parser.add_argument("--arm64-x87-fld32-visibility", action="store_true",
                        help="ARM64 opt-in: exact normal binary32->binary80 at 10 sampled CoDSP visibility PCs; OFF")
    parser.add_argument("--x87-stack-shift-outline", action="store_true",
                        help="ARM64-only experiment: outline exact 7-step CoDSP x87 register "
                             "shifts; generated C restored in normal builds (OFF)")
    parser.add_argument("--dispatch-last-cache", action="store_true",
                        help="experiment: per-guest-run last-chunk dispatch hint; default OFF")
    parser.add_argument("--arm64-narrow-right-shift", action="store_true",
                        help="ARM64 experiment: specialize provably narrow logical right shifts; OFF")
    parser.add_argument("--arm64-narrow-sar", action="store_true",
                        help="ARM64 experiment: exact signed <=64-bit SAR; OFF by default")
    parser.add_argument("--arm64-x87-conv-fast", action="store_true",
                        help="ARM64 experiment: exact normal-value binary80<->binary64 d2f/f2d fast paths; OFF")
    parser.add_argument("--arm64-narrow-left-shift", action="store_true",
                        help="ARM64 experiment: 16 exact dynamic CoDSP p0/p8 narrow SHL sites; OFF")
    parser.add_argument("--audio-mix-span", action="store_true",
                        help="experiment: bit-identical audio mixer span loop (host thread only); OFF by default")
    parser.add_argument("--arm64-dispatch-entry-cache", action="store_true",
                        help="ARM64 experiment: cache last chunk range and callback with layout invalidation; OFF")
    parser.add_argument("--x87-fcom-fastpath", action="store_true",
                        help="experiment: fuse verified CoDSP p1/p8 x87 compare/status/pop blocks; default OFF")
    parser.add_argument("--package-only", action="store_true")
    parser.add_argument("--native-x87-region", type=Path, help="WSA experiment: verified original PE for private binary80 region")
    parser.add_argument("--wsa-cumulative", action="store_true",
                        help="WSA bundle: native x87, copy32, strict renderer/visibility O2, NaN/f2d/FCOM and dispatch cache; requires --native-x87-region PE")
    parser.add_argument("--local-guest-state", action="store_true", help="WSA experiment: link R/MEM/U/PC locally without changing generated instructions")
    parser.add_argument("--arm64-local-guest-state", action="store_true",
                        help="ARM64 experiment: local R/MEM/U/PC ELF binding, same WSA 4-symbol map; OFF by default")
    parser.add_argument("--arm64-safe-icf", action="store_true",
                        help="ARM64 experiment: safe linker folding of address-insignificant identical code; OFF")
    parser.add_argument("--arm64-bind-local", action="store_true",
                        help="ARM64 experiment: -fno-plt + -Bsymbolic-functions for libmain (no PLT for internal calls); OFF")
    parser.add_argument("--arm64-code-layout", action="store_true",
                        help="ARM64 experiment: -ffunction-sections + -mtune=cortex-a55 (MT6768 big.LITTLE), no ISA/FP change; OFF")
    parser.add_argument("--arm64-symbol-order", type=Path, metavar="FILE",
                        help="ARM64 experiment: lld --symbol-ordering-file with hot symbols first; requires --arm64-code-layout")
    parser.add_argument("--arm64-icf-metadata", action="store_true",
                        help="ARM64 ICF A/B reference: emit address-significance metadata without enabling folding; OFF")
    parser.add_argument("--wsa-release", action="store_true", help="WSA cumulative + local-state release; default native x87 on and frame limit 120")
    args = parser.parse_args()
    if args.arm64_x87_fld32_normal and args.abi != "arm64-v8a":
        parser.error("--arm64-x87-fld32-normal requires arm64-v8a")
    if args.arm64_x87_fld32_visibility and args.abi != "arm64-v8a":
        parser.error("--arm64-x87-fld32-visibility requires arm64-v8a")
    if args.arm64_x87_fld32_visibility and args.package_only:
        parser.error("--arm64-x87-fld32-visibility cannot use --package-only")
    if args.arm64_x87_fld32_visibility and (
            args.x87_stack_shift_outline or args.x87_nan_bits or
            args.x87_fcom_fastpath):
        parser.error("--arm64-x87-fld32-visibility cannot combine with x87 shift/NaN/FCOM source patches")
    if args.arm64_x87_fld32_normal and args.package_only:
        parser.error("--arm64-x87-fld32-normal cannot use --package-only")
    if args.arm64_x87_fld32_normal and args.x87_stack_shift_outline:
        parser.error("--arm64-x87-fld32-normal cannot combine with x87 stack outlining")
    if args.arm64_x87_fld32_normal and any((
            args.x87_normal_f2d_p4, args.x87_normal_f2d_p4_selective,
            args.x87_normal_f2d_p4_profiled)):
        parser.error("--arm64-x87-fld32-normal must use original CoDSP p10 layout")
    if args.arm64_x87_sign_bits and args.abi != "arm64-v8a":
        parser.error("--arm64-x87-sign-bits requires arm64-v8a")
    if args.arm64_x87_sign_bits and args.package_only:
        parser.error("--arm64-x87-sign-bits cannot use --package-only")
    if args.arm64_narrow_right_shift and args.abi != 'arm64-v8a':
        parser.error('--arm64-narrow-right-shift requires arm64-v8a')
    if args.arm64_x87_conv_fast and args.abi != 'arm64-v8a':
        parser.error('--arm64-x87-conv-fast requires arm64-v8a')
    if args.arm64_narrow_sar and args.abi != 'arm64-v8a':
        parser.error('--arm64-narrow-sar requires arm64-v8a')
    if args.arm64_narrow_left_shift and args.abi != "arm64-v8a":
        parser.error("--arm64-narrow-left-shift requires arm64-v8a")
    if args.arm64_narrow_left_shift and args.package_only:
        parser.error("--arm64-narrow-left-shift cannot use --package-only")
    if args.arm64_narrow_left_shift and any((
            args.arm64_x87_sign_bits, args.x87_nan_bits,
            args.x87_fcom_fastpath, args.x87_stack_shift_outline,
            args.arm64_x87_fld32_visibility)):
        parser.error("--arm64-narrow-left-shift cannot combine with CoDSP p0/p8 source patches")
    if args.arm64_dispatch_entry_cache and args.abi != 'arm64-v8a':
        parser.error('--arm64-dispatch-entry-cache requires arm64-v8a')
    if args.arm64_dispatch_entry_cache and args.dispatch_last_cache:
        parser.error('choose one dispatch cache: entry or last hint')
    if args.arm64_safe_icf and args.abi != 'arm64-v8a':
        parser.error('--arm64-safe-icf requires arm64-v8a')
    if args.arm64_bind_local and args.abi != 'arm64-v8a':
        parser.error('--arm64-bind-local requires arm64-v8a')
    if args.arm64_code_layout and args.abi != 'arm64-v8a':
        parser.error('--arm64-code-layout requires arm64-v8a')
    if args.arm64_symbol_order and not args.arm64_code_layout:
        parser.error('--arm64-symbol-order requires --arm64-code-layout')
    if args.arm64_symbol_order and not args.arm64_symbol_order.is_file():
        parser.error('--arm64-symbol-order file not found')
    if args.arm64_icf_metadata and args.abi != 'arm64-v8a':
        parser.error('--arm64-icf-metadata requires arm64-v8a')
    if args.wsa_release:
        if args.abi!='x86_64' or not args.native_x87_region:
            parser.error('--wsa-release requires --abi x86_64 --native-x87-region PE')
        args.wsa_cumulative=args.local_guest_state=True
    if args.local_guest_state and args.abi != 'x86_64':
        parser.error('--local-guest-state requires --abi x86_64')
    if args.arm64_local_guest_state and args.abi != "arm64-v8a":
        parser.error("--arm64-local-guest-state requires --abi arm64-v8a")
    if args.wsa_cumulative:
        if args.abi != "x86_64" or not args.native_x87_region:
            parser.error("--wsa-cumulative requires --abi x86_64 --native-x87-region PE")
        args.fast_copy32=args.visibility_o2=args.render_o2=True
        args.x87_nan_bits=args.x87_normal_f2d=args.x87_fcom_fastpath=True
        args.dispatch_last_cache=True
    if args.native_x87_region and args.abi != "x86_64":
        parser.error("--native-x87-region requires x86_64")
    if args.hot_x87_transform:
        parser.error("ORIGINAL_X87_PRECISION_UNSAFE: legacy transform loses binary80 "
                     "cancellation results; independent original-x86 outputs differ. "
                     "Do not enable until full precision/state/fault equivalence is proven.")
    if args.core_hot_o2_parts is not None:
        if not args.core_hot_o2:
            parser.error("--core-hot-o2-parts requires --core-hot-o2")
        requested = args.core_hot_o2_parts.split(",")
        allowed = ("p0", "p1", "p4")
        if (not requested or len(requested) > len(allowed)
                or any(part not in allowed for part in requested)
                or len(set(requested)) != len(requested)):
            parser.error("--core-hot-o2-parts requires distinct p0,p1,p4 "
                         "partition IDs without whitespace")
        args.core_hot_o2_parts = ",".join(
            part for part in allowed if part in requested)
    if args.core_hot_o2 and args.abi != "arm64-v8a":
        parser.error("--core-hot-o2 is ARM64-only")
    if args.cfg14_geom_region and args.abi != "arm64-v8a":
        parser.error("--cfg14-geom-region is ARM64-only")
    if args.cfg14_geom_region and args.recomp_opt != "1":
        parser.error("--cfg14-geom-region requires --recomp-opt 1")
    if args.cfg14_geom_region:
        # Phase14D original x86 fault audit: 15 of 18 sampled mid-block
        # page faults left cached R fields/PC inconsistent. Do not package
        # even an experimental APK until exception-safe deoptimization is
        # implemented and the independent original-x86 gate passes.
        parser.error("--cfg14-geom-region BLOCKED: original x86 page-fault "
                     "audit found stale architectural R/PC (15/18 faults); "
                     "requires exception-safe fallback before APK testing")
    if args.core_hot_o2 and args.recomp_opt != "1":
        parser.error("--core-hot-o2 requires --recomp-opt 1")
    if args.wsa_uncap_bench and args.abi != "x86_64":
        parser.error("--wsa-uncap-bench is for --abi x86_64 WSA only")
    if args.x87_normal_f2d_p4 and args.abi != "arm64-v8a":
        parser.error("--x87-normal-f2d-p4 is only supported for ARM64 experiments")
    if args.x87_normal_f2d_p4 and not args.x87_normal_f2d:
        parser.error("--x87-normal-f2d-p4 requires --x87-normal-f2d")
    if args.x87_normal_f2d_p4_selective and args.abi != "arm64-v8a":
        parser.error("--x87-normal-f2d-p4-selective is ARM64-only")
    if args.x87_normal_f2d_p4_selective and not args.x87_normal_f2d:
        parser.error("--x87-normal-f2d-p4-selective requires --x87-normal-f2d")
    if args.x87_normal_f2d_p4_profiled and args.abi != "arm64-v8a":
        parser.error("--x87-normal-f2d-p4-profiled is ARM64-only")
    if args.x87_normal_f2d_p4_profiled and not args.x87_normal_f2d:
        parser.error("--x87-normal-f2d-p4-profiled requires --x87-normal-f2d")
    if args.x87_stack_shift_outline and args.abi != "arm64-v8a":
        parser.error("--x87-stack-shift-outline is ARM64-only")
    if args.x87_stack_shift_outline and any((
            args.x87_normal_f2d_p4, args.x87_normal_f2d_p4_selective,
            args.x87_normal_f2d_p4_profiled)):
        parser.error("--x87-stack-shift-outline cannot combine with p4 x87 conversion "
                     "variants requiring exact generated-source hashes")
    if sum((args.x87_normal_f2d_p4, args.x87_normal_f2d_p4_selective,
            args.x87_normal_f2d_p4_profiled)) > 1:
        parser.error("p4 x87 options are mutually exclusive (not both)")
    if not args.sdk or not args.java:
        parser.error("Set ANDROID_HOME and JAVA_HOME, or pass --sdk and --java")
    root = Path(__file__).resolve().parents[2]
    sdk, java = args.sdk.resolve(), args.java.resolve()
    ndk = args.ndk.resolve() if args.ndk else latest(sdk / "ndk")
    build_tools = latest(sdk / "build-tools")
    # Target 35 explicitly: the launcher has no dependency on preview APIs.
    android_jar = sdk / "platforms/android-35/android.jar"
    if not android_jar.is_file():
        parser.error("Install the Android 35 SDK platform")
    deps, native, package = root / "build-android-deps", root / "build-android-native", root / "build-android-package"
    if args.abi != "arm64-v8a":
        native = root / ("build-android-native-" + args.abi)
        package = root / ("build-android-package-" + args.abi)
    package.mkdir(exist_ok=True)
    exe = ".exe" if os.name == "nt" else ""
    batch = ".bat" if os.name == "nt" else ""
    if not args.package_only:
        # Restore exact previous p4 patches before switching between the
        # 520-site and sampled 277-site profiles. Unknown modified game C
        # fails closed; ordinary builds of unrelated sources are untouched.
        p4_source = root / 'recomp_out/codsp_recomp_p4.c'
        patch_script = root / 'tools/recomp/patch_codsp_p4_f2d_selective.py'
        # Undo prior out-of-line x87 trial before other source-level patches:
        # their strict baseline hashes must see the original generated C.
        shift_script = root / 'tools/recomp/patch_codsp_x87_shift.py'
        pcode_path = root / 'recomp_out/codsp.pcode'
        narrow_left_script = root / 'tools/recomp/patch_codsp_narrow_left_shift.py'
        narrow_left_p0 = root / 'recomp_out/codsp_recomp_p0.c'
        narrow_left_p8 = root / 'recomp_out/codsp_recomp_p8.c'
        if args.arm64_narrow_left_shift and not (
                narrow_left_p0.is_file() and narrow_left_p8.is_file()):
            parser.error("--arm64-narrow-left-shift requires original generated CoDSP p0 and p8")
        if narrow_left_p0.is_file() and narrow_left_p8.is_file():
            # Restore first, before all other hash-pinned source patches.
            run(sys.executable, narrow_left_script, narrow_left_p0,
                narrow_left_p8, pcode_path, '--restore')
        sign_script = root / 'tools/recomp/patch_codsp_x87_sign.py'
        sign_source = root / 'recomp_out/codsp_recomp_p0.c'
        fld32_script = root / 'tools/recomp/patch_codsp_x87_fld32.py'
        fld32_source = root / 'recomp_out/codsp_recomp_p10.c'
        vis_fld32_script = root / 'tools/recomp/patch_codsp_x87_fld32_visibility.py'
        vis_fld32_source = root / 'recomp_out/codsp_recomp_p8.c'
        if args.arm64_x87_fld32_visibility and not vis_fld32_source.is_file():
            parser.error("--arm64-x87-fld32-visibility requires generated CoDSP p8")
        # pcode2c --x87-virtual-stack output is freshly generated and never
        # carries hash-pinned text patches: skip their restores, refuse applies.
        def vstack(path):
            return path.is_file() and (b'x87 virtual stack' in (data := path.read_bytes())
                                       or b'renamed x87 stack' in data)
        if (vstack(vis_fld32_source) or vstack(fld32_source) or vstack(sign_source)) and (
                args.arm64_x87_fld32_visibility or args.arm64_x87_fld32_normal or
                args.arm64_x87_sign_bits or args.arm64_narrow_left_shift or
                args.x87_stack_shift_outline):
            parser.error("x87 text patches cannot apply to --x87-virtual-stack generated C")
        if vis_fld32_source.is_file() and not vstack(vis_fld32_source):
            run(sys.executable, vis_fld32_script, vis_fld32_source,
                pcode_path, '--restore')
        if args.arm64_x87_fld32_normal and not fld32_source.is_file():
            parser.error("--arm64-x87-fld32-normal requires generated CoDSP p10")
        if fld32_source.is_file() and not vstack(fld32_source):
            # Restore before optional x87 shifts inspect generated C.
            run(sys.executable, fld32_script, fld32_source, pcode_path, '--restore')
        if args.arm64_x87_sign_bits and not sign_source.is_file():
            parser.error("--arm64-x87-sign-bits requires generated CoDSP p0")
        if sign_source.is_file():
            run(sys.executable, sign_script, sign_source, pcode_path, '--restore')
        shift_parts = [root / f'recomp_out/codsp_recomp_p{i}.c'
                       for i in range(12)]
        if args.x87_stack_shift_outline and not all(f.is_file() for f in shift_parts):
            parser.error("Require all 12 CoDSP generated C partitions")
        for part in shift_parts:
            if part.is_file():
                run(sys.executable, shift_script, part, pcode_path, '--restore')
        p4_bytes = p4_source.read_bytes() if p4_source.is_file() else b''
        if b'CODRECOMP_X87_NORMAL_F2D_P4_SELECTIVE' in p4_bytes:
            run(sys.executable, patch_script, p4_source,
                root / 'recomp_out/codsp.pcode', '--restore')
        elif b'CODRECOMP_X87_NORMAL_F2D_P4_PROFILED' in p4_bytes:
            run(sys.executable, patch_script, p4_source,
                root / 'recomp_out/codsp.pcode', '--restore', '--profiled')
        if args.x87_normal_f2d_p4_selective or args.x87_normal_f2d_p4_profiled:
            cmd = [sys.executable, patch_script, p4_source,
                   root / 'recomp_out/codsp.pcode', '--apply']
            if args.x87_normal_f2d_p4_profiled:
                cmd.append('--profiled')
            run(*cmd)
        if args.fast_copy32:
            # Recompilation output is private/ignored; fail closed if exact
            # original CoDSP 1.5 generated labels are missing.
            run(sys.executable, root / 'tools/recomp/patch_codsp_copy32.py',
                root / 'recomp_out/codsp_recomp_p1.c')
        if args.x87_nan_bits:
            run(sys.executable, root / 'tools/recomp/patch_codsp_x87_nan.py',
                root / 'recomp_out/codsp_recomp_p1.c',
                root / 'recomp_out/codsp_recomp_p8.c')
        if args.x87_fcom_fastpath:
            run(sys.executable, root / 'tools/recomp/patch_codsp_fcom.py',
                root / 'recomp_out/codsp_recomp_p1.c',
                root / 'recomp_out/codsp_recomp_p8.c')
        if args.arm64_x87_sign_bits:
            run(sys.executable, sign_script, sign_source, pcode_path, '--apply')
        if args.arm64_x87_fld32_normal:
            # Only FLD32 input conversions change; LOAD and x87 stores remain.
            run(sys.executable, fld32_script, fld32_source, pcode_path, '--apply')
        if args.arm64_x87_fld32_visibility:
            # P8 hot visibility input conversions only; rest are untouched.
            run(sys.executable, vis_fld32_script, vis_fld32_source,
                pcode_path, '--apply')
        if args.arm64_narrow_left_shift:
            # Original p0/p8 only: 16 dynamically-counted 1..8-byte SHL ops.
            run(sys.executable, narrow_left_script, narrow_left_p0,
                narrow_left_p8, pcode_path, '--apply')
        if args.x87_stack_shift_outline:
            # This is a source-level, reversible experiment. No production
            # compiler define is needed; helpers remain dead when unused.
            for part in shift_parts:
                run(sys.executable, shift_script, part, pcode_path, '--apply')
        for name, (url, revision) in DEPENDENCIES.items():
            path = deps / name
            if not path.exists():
                path.mkdir(parents=True)
                run("git", "init", path)
                run("git", "-C", path, "fetch", "--depth", "1", url, revision)
                run("git", "-C", path, "checkout", "--detach", "FETCH_HEAD")
            actual = subprocess.check_output(["git", "-C", str(path), "rev-parse", "HEAD"], text=True).strip()
            if actual != revision:
                raise SystemExit(f"{name}: expected {revision}, found {actual}; use a clean dependency directory")
        run(sys.executable, root / 'tools/recomp/patch_gl4es.py', deps / 'gl4es')
        if args.native_x87_region:
            run(sys.executable, root / 'tools/recomp/native_x87_region.py', '--pe', args.native_x87_region,
                '--out', root / 'recomp_out/codsp_native_x87_region.c')
        run("cmake", "-S", root / "android", "-B", native, "-G", "Ninja",
            f"-DCMAKE_TOOLCHAIN_FILE={(ndk / 'build/cmake/android.toolchain.cmake').as_posix()}",
            f"-DANDROID_ABI={args.abi}", "-DANDROID_PLATFORM=android-26", "-DCMAKE_BUILD_TYPE=Release",
            f"-DRECOMP_OPTIMIZATION={args.recomp_opt}",
            f"-DCODRECOMP_CPU_PROFILING={'ON' if args.cpu_profile else 'OFF'}",
            f"-DCODRECOMP_GL_PROFILING={'ON' if args.gl_profile else 'OFF'}",
            f"-DCODRECOMP_GL_TIMING={'ON' if args.gl_time_profile else 'OFF'}",
            f"-DCODRECOMP_GL_VK_STATE_CAPTURE={'ON' if args.gl_vk_state_capture else 'OFF'}",
            f"-DCODRECOMP_GL_STATE_FILTER={'ON' if args.gl_state_filter else 'OFF'}",
            f"-DCODRECOMP_WSA_UNCAP_BENCH={'ON' if args.wsa_uncap_bench else 'OFF'}",
            f"-DCODRECOMP_CORE_HOT_O2={'ON' if args.core_hot_o2 else 'OFF'}",
            f"-DCODRECOMP_CORE_HOT_O2_PARTS={args.core_hot_o2_parts or 'p0,p1,p4'}",
            f"-DCODRECOMP_CFG14_GEOM_REGION={'ON' if args.cfg14_geom_region else 'OFF'}",
            f"-DCODRECOMP_RENDER_O2={'ON' if args.render_o2 else 'OFF'}",
            f"-DCODRECOMP_HOT_X87_FASTPATH={'ON' if args.hot_x87_transform else 'OFF'}",
            f"-DCODRECOMP_NATIVE_X87_REGION={'ON' if args.native_x87_region else 'OFF'}",
            f"-DCODRECOMP_LOCAL_GUEST_STATE={'ON' if args.local_guest_state else 'OFF'}",
            f"-DCODRECOMP_ARM64_LOCAL_GUEST_STATE={'ON' if args.arm64_local_guest_state else 'OFF'}",
            f"-DCODRECOMP_WSA_RELEASE_DEFAULTS={'ON' if args.wsa_release else 'OFF'}",
            f"-DCODRECOMP_CODSP_COPY32_FASTPATH={'ON' if args.fast_copy32 else 'OFF'}",
            f"-DCODRECOMP_VISIBILITY_O2={'ON' if args.visibility_o2 else 'OFF'}",
            f"-DCODRECOMP_X87_NAN_BITS={'ON' if args.x87_nan_bits else 'OFF'}",
            f"-DCODRECOMP_X87_NORMAL_F2D={'ON' if args.x87_normal_f2d else 'OFF'}",
            f"-DCODRECOMP_X87_NORMAL_F2D_P4={'ON' if args.x87_normal_f2d_p4 else 'OFF'}",
            f"-DCODRECOMP_X87_NORMAL_F2D_P4_SELECTIVE={'ON' if args.x87_normal_f2d_p4_selective else 'OFF'}",
            f"-DCODRECOMP_X87_NORMAL_F2D_P4_PROFILED={'ON' if args.x87_normal_f2d_p4_profiled else 'OFF'}",
            f"-DCODRECOMP_DISPATCH_LAST_CACHE={'ON' if args.dispatch_last_cache else 'OFF'}",
            f"-DCODRECOMP_DISPATCH_ENTRY_CACHE={'ON' if args.arm64_dispatch_entry_cache else 'OFF'}",
            f"-DCODRECOMP_AUDIO_MIX_SPAN={'ON' if args.audio_mix_span else 'OFF'}",
            f"-DCODRECOMP_ARM64_NARROW_RIGHT_SHIFT={'ON' if args.arm64_narrow_right_shift else 'OFF'}",
             f"-DCODRECOMP_ARM64_NARROW_SAR={'ON' if args.arm64_narrow_sar else 'OFF'}",
            f"-DCODRECOMP_ARM64_BIND_LOCAL={'ON' if args.arm64_bind_local else 'OFF'}",
             f"-DCODRECOMP_ARM64_X87_CONV_FAST={'ON' if args.arm64_x87_conv_fast else 'OFF'}",
            f"-DCODRECOMP_ARM64_SAFE_ICF={'ON' if args.arm64_safe_icf else 'OFF'}",
            f"-DCODRECOMP_ARM64_CODE_LAYOUT={'ON' if args.arm64_code_layout else 'OFF'}",
            f"-DCODRECOMP_ARM64_SYMBOL_ORDER={args.arm64_symbol_order.resolve().as_posix() if args.arm64_symbol_order else ''}",
            f"-DCODRECOMP_ARM64_ICF_METADATA={'ON' if args.arm64_icf_metadata else 'OFF'}",
            f"-DCODRECOMP_X87_FCOM_FASTPATH={'ON' if args.x87_fcom_fastpath else 'OFF'}",
            f"-DSDL2_SOURCE_DIR={(deps / 'SDL').as_posix()}", f"-DGL4ES_SOURCE_DIR={(deps / 'gl4es').as_posix()}")
        run("cmake", "--build", native, "--parallel", args.jobs)
    classes, dex = package / "classes", package / "dex"
    # Remove only this builder's disposable outputs, never imported game data.
    for path in (classes, dex):
        if path.exists():
            shutil.rmtree(path)
        path.mkdir()
    sources = sorted((deps / "SDL/android-project/app/src/main/java").rglob("*.java"))
    sources += sorted((root / "android/java").rglob("*.java"))
    # The pinned AAR has no resources/dependencies; keep its binary API boundary.
    retro_jar = package / "retrotouch.jar"
    with zipfile.ZipFile(deps / "RetroTouch/source/RetroTouch-1.0.0-beta.4.aar") as aar:
        retro_jar.write_bytes(aar.read("classes.jar"))
    response = package / "javac.args"
    response.write_text("\n".join('"' + str(p).replace("\\", "/") + '"' for p in sources), encoding="utf-8")
    env = dict(os.environ, JAVA_HOME=str(java))
    env["PATH"] = str(java / "bin") + os.pathsep + env.get("PATH", "")
    run(java / f"bin/javac{exe}", "-encoding", "UTF-8", "-source", "8", "-target", "8",
        "-classpath", str(android_jar) + os.pathsep + str(retro_jar), "-d", classes, "@" + str(response), env=env)
    class_jar = package / "classes.jar"
    with zipfile.ZipFile(class_jar, "w") as jar:
        for path in classes.rglob("*.class"):
            jar.write(path, path.relative_to(classes).as_posix())
    run(build_tools / f"d8{batch}", "--min-api", "26", "--lib", android_jar, "--output", dex, class_jar, retro_jar, env=env)
    unsigned, aligned = package / "unsigned.apk", package / "aligned.apk"
    run(build_tools / f"aapt2{exe}", "link", "-I", android_jar, "--manifest", root / "android/AndroidManifest.xml", "-o", unsigned)
    with zipfile.ZipFile(unsigned, "a") as apk:
        apk.write(dex / "classes.dex", "classes.dex", compress_type=zipfile.ZIP_DEFLATED)
        apk.write(deps / "SDL/LICENSE.txt", "assets/licenses/SDL2.txt", compress_type=zipfile.ZIP_DEFLATED)
        apk.write(deps / "gl4es/LICENSE", "assets/licenses/GL4ES.txt", compress_type=zipfile.ZIP_DEFLATED)
        apk.write(deps / "RetroTouch/LICENSE", "assets/licenses/RetroTouch.txt", compress_type=zipfile.ZIP_DEFLATED)
        ndk_host = "windows-x86_64" if os.name == "nt" else ("darwin-x86_64" if os.sys.platform == "darwin" else "linux-x86_64")
        strip = ndk / f"toolchains/llvm/prebuilt/{ndk_host}/bin/llvm-strip{exe}"
        stripped = package / "native"
        stripped.mkdir(exist_ok=True)
        for name in ("SDL2", "GL", "main"):
            library = stripped / f"lib{name}.so"
            shutil.copy2(native / f"lib/lib{name}.so", library)
            run(strip, "--strip-unneeded", library)
            with library.open("rb") as stream:
                header = stream.read(64)
                machine = 183 if args.abi == "arm64-v8a" else 62
                if header[:6] != b"\x7fELF\x02\x01" or struct.unpack_from("<H", header, 18)[0] != machine:
                    raise SystemExit(f"Not a {args.abi} ELF: {library}")
                offset = struct.unpack_from("<Q", header, 32)[0]
                size, count = struct.unpack_from("<HH", header, 54)
                for i in range(count):
                    stream.seek(offset + i * size); entry = stream.read(size)
                    if struct.unpack_from("<I", entry)[0] == 1 and struct.unpack_from("<Q", entry, 48)[0] < 16384:
                        raise SystemExit(f"ELF LOAD segment lacks 16-KiB alignment: {library}")
            apk.write(library, f"lib/{args.abi}/lib{name}.so", compress_type=zipfile.ZIP_STORED)
    run(build_tools / f"zipalign{exe}", "-f", "-P", "16", "4", unsigned, aligned)
    key = root / "build-android-package/debug.keystore"
    key.parent.mkdir(exist_ok=True)
    if not key.exists():
        run(java / f"bin/keytool{exe}", "-genkeypair", "-keystore", key, "-storepass", "android",
            "-keypass", "android", "-alias", "androiddebugkey", "-keyalg", "RSA", "-keysize", "2048",
            "-validity", "10000", "-dname", "CN=Android Debug,O=CallofRecomp,C=US", env=env)
    label = "arm64" if args.abi == "arm64-v8a" else args.abi
    output = root / f"recomp_out/callofrecomp-{label}-debug.apk"
    run(build_tools / f"apksigner{batch}", "sign", "--ks", key, "--ks-pass", "pass:android",
        "--key-pass", "pass:android", "--out", output, aligned, env=env)
    run(build_tools / f"apksigner{batch}", "verify", "--verbose", output, env=env)
    run(build_tools / f"zipalign{exe}", "-c", "-P", "16", "4", output)
    print(output)


if __name__ == "__main__":
    main()
