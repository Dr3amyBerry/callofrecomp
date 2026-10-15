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
    parser.add_argument("--gl-vk-state-capture", action="store_true",
                        help="compile opt-in GL->Vulkan typed state observer, NOT a Vulkan game backend; default OFF")
    parser.add_argument("--wsa-uncap-bench", action="store_true",
                        help="DIAGNOSTIC WSA x86_64 ONLY: bypass host 60 FPS cap; default OFF")
    parser.add_argument("--render-o2", action="store_true",
                        help="experiment: compile CoDSP renderer partitions p10 and p11 with -O2")
    parser.add_argument("--hot-x87-transform", action="store_true",
                        help="experiment: native CoDSP 1.5 vector transform; default OFF")
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
    parser.add_argument("--x87-stack-shift-outline", action="store_true",
                        help="ARM64-only experiment: outline exact 7-step CoDSP x87 register "
                             "shifts; generated C restored in normal builds (OFF)")
    parser.add_argument("--dispatch-last-cache", action="store_true",
                        help="experiment: per-guest-run last-chunk dispatch hint; default OFF")
    parser.add_argument("--x87-fcom-fastpath", action="store_true",
                        help="experiment: fuse verified CoDSP p1/p8 x87 compare/status/pop blocks; default OFF")
    parser.add_argument("--package-only", action="store_true")
    args = parser.parse_args()
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
        run("cmake", "-S", root / "android", "-B", native, "-G", "Ninja",
            f"-DCMAKE_TOOLCHAIN_FILE={(ndk / 'build/cmake/android.toolchain.cmake').as_posix()}",
            f"-DANDROID_ABI={args.abi}", "-DANDROID_PLATFORM=android-26", "-DCMAKE_BUILD_TYPE=Release",
            f"-DRECOMP_OPTIMIZATION={args.recomp_opt}",
            f"-DCODRECOMP_CPU_PROFILING={'ON' if args.cpu_profile else 'OFF'}",
            f"-DCODRECOMP_GL_PROFILING={'ON' if args.gl_profile else 'OFF'}",
            f"-DCODRECOMP_GL_TIMING={'ON' if args.gl_time_profile else 'OFF'}",
            f"-DCODRECOMP_GL_VK_STATE_CAPTURE={'ON' if args.gl_vk_state_capture else 'OFF'}",
            f"-DCODRECOMP_WSA_UNCAP_BENCH={'ON' if args.wsa_uncap_bench else 'OFF'}",
            f"-DCODRECOMP_RENDER_O2={'ON' if args.render_o2 else 'OFF'}",
            f"-DCODRECOMP_HOT_X87_FASTPATH={'ON' if args.hot_x87_transform else 'OFF'}",
            f"-DCODRECOMP_CODSP_COPY32_FASTPATH={'ON' if args.fast_copy32 else 'OFF'}",
            f"-DCODRECOMP_VISIBILITY_O2={'ON' if args.visibility_o2 else 'OFF'}",
            f"-DCODRECOMP_X87_NAN_BITS={'ON' if args.x87_nan_bits else 'OFF'}",
            f"-DCODRECOMP_X87_NORMAL_F2D={'ON' if args.x87_normal_f2d else 'OFF'}",
            f"-DCODRECOMP_X87_NORMAL_F2D_P4={'ON' if args.x87_normal_f2d_p4 else 'OFF'}",
            f"-DCODRECOMP_X87_NORMAL_F2D_P4_SELECTIVE={'ON' if args.x87_normal_f2d_p4_selective else 'OFF'}",
            f"-DCODRECOMP_X87_NORMAL_F2D_P4_PROFILED={'ON' if args.x87_normal_f2d_p4_profiled else 'OFF'}",
            f"-DCODRECOMP_DISPATCH_LAST_CACHE={'ON' if args.dispatch_last_cache else 'OFF'}",
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
