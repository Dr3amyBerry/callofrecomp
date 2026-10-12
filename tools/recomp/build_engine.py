#!/usr/bin/env python3
"""Build the desktop engine from private pcode2c outputs and the portable shims.

Export/generate the four modules under recomp_out first. No private generated
source or original assets are copied into the tracked tree.
"""
import argparse
import filecmp
import os
from pathlib import Path
import shutil
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cc", default=os.environ.get("CC", "clang"))
    parser.add_argument("--sdl2", type=Path, required=True, help="SDL2 development prefix (include/SDL2, lib, bin)")
    parser.add_argument("--out", type=Path, default=Path("recomp_out"))
    parser.add_argument("--reuse-objects", action="store_true", help="explicitly reuse previously compiled private generated objects")
    parser.add_argument("--input-probe", action="store_true", help="build separate integration probe: click at 45s, then hold W at 60s")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    output = args.out.resolve()
    runtime = root / "tools/recomp/runtime"
    flags = ["-O1", "-I" + str(root / "tools/recomp")]
    objects = []
    for module in ("codsp", "uix86", "cgamex86", "gamex86"):
        sources = sorted(output.glob(module + "_recomp*.c"))
        if not sources:
            parser.error(f"missing {module}_recomp*.c under {output}; generate it with pcode2c.py first")
        for source in sources:
            obj = source.with_suffix(".o")
            if not args.reuse_objects or not obj.exists():
                subprocess.run([args.cc, *flags, "-c", str(source), "-o", str(obj)], check=True)
            objects.append(str(obj))
    name = "codrecomp_input_probe" if args.input_probe else "codrecomp_engine"
    exe = output / (name + (".exe" if os.name == "nt" else ""))
    subprocess.run([args.cc, *flags, "-Wall", "-Wno-unused-function", "-DSDL_MAIN_HANDLED",
                    "-I" + str(runtime), "-I" + str(args.sdl2 / "include/SDL2"),
                    str(root / "tools/recomp/hosts" / ("engine_input_probe.c" if args.input_probe else "engine_host.c")),
                    *map(str, sorted(runtime.glob("*.c"))), *objects,
                    "-L" + str(args.sdl2 / "lib"), "-lSDL2",
                    *([] if os.name == "nt" else ["-lm"]), "-o", str(exe)], check=True)
    if os.name == "nt":
        dll, target = args.sdl2 / "bin/SDL2.dll", output / "SDL2.dll"
        if not target.exists() or not filecmp.cmp(dll, target, shallow=False):
            shutil.copy2(dll, target)
    print(exe)


if __name__ == "__main__":
    main()
