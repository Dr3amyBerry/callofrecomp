#!/usr/bin/env python3
"""AArch64 (Unicorn) differential + dynamic-instruction cost of the opt-in
CODRECOMP_ARM64_X87_CONV_FAST d2f(double,10)/f2d(binary80,10) fast paths.

Compiles tests/x87_conv_fast_unit.c twice for aarch64 (reference vs flag),
emulates both on identical inputs, requires bit-identical results and reports
dynamic instruction counts per input class. Instruction counts are NOT cycles
or FPS. No game data, no device, no binary80 arithmetic (conversions only).
"""
from __future__ import annotations
import argparse
from hashlib import sha256
import json
from pathlib import Path
import random
import struct
import subprocess

ROOT = Path(__file__).resolve().parents[3]
CODE, RET, DATA, STACK = 0x100000, 0x10fff0, 0x200000, 0x300000


def d2f_class(b: int) -> str:
    e = (b >> 52) & 0x7ff
    f = b & 0xfffffffffffff
    if e == 0x7ff:
        return "inf_nan"
    if e == 0:
        return "zero_subnormal"
    return "normal"


def f2d_class(sig: int, se: int) -> str:
    e = se & 0x7fff
    if e == 0 and sig == 0:
        return "zero"
    if 15361 <= e <= 16406 and (sig & 0x80000000000007ff) == 0x8000000000000000:
        return "canonical_normal"
    if 15361 <= e <= 16406 and sig >> 63:
        return "normal_needs_rounding"
    return "other"


def verify(llvm: Path, out: Path, cases: int = 4000) -> dict:
    if not __debug__:
        raise RuntimeError("Do not run with python -O")
    if not out.resolve().is_relative_to((ROOT / ".local/profiles/runs").resolve()):
        raise ValueError("Use a private run directory under .local/profiles/runs")
    out.mkdir(parents=True, exist_ok=False)

    def tool(n):
        p = llvm / (n + ".exe")
        return str(p if p.is_file() else llvm / n)

    def run(a):
        p = subprocess.run(a, capture_output=True, text=True, timeout=200)
        if p.returncode:
            raise RuntimeError(f"{a[0]} failed: {p.stderr[-1500:]}")
        return p.stdout

    unit = ROOT / "tests/x87_conv_fast_unit.c"
    base = [tool("clang"), "--target=aarch64-linux-android26", "-O2", "-fno-pic",
            "-fno-pie", "-ffunction-sections", "-I" + str(ROOT / "tools/recomp"), "-c"]
    run(base + ["-DCONV_PREFIX=ref", str(unit), "-o", str(out / "ref.o")])
    run(base + ["-DCONV_PREFIX=fast", "-DCODRECOMP_ARM64_X87_CONV_FAST", str(unit), "-o", str(out / "fast.o")])
    elf = out / "conv.elf"
    run([tool("clang"), "--target=aarch64-linux-android26", "-nostdlib", "-Wl,-Ttext=0x100000",
         "-Wl,-e,ref_f2d10", "-Wl,--build-id=none", str(out / "ref.o"), str(out / "fast.o"), "-o", str(elf)])
    (out / "disassembly.txt").write_text(run([tool("llvm-objdump"), "-d", str(elf)]), encoding="utf8")
    run([tool("llvm-objcopy"), "-O", "binary", "--only-section=.text", str(elf), str(out / "text.bin")])
    symbols = {}
    for line in run([tool("llvm-nm"), "-S", "--defined-only", str(elf)]).splitlines():
        f = line.split()
        if len(f) == 4 and f[3] in ("ref_f2d10", "fast_f2d10", "ref_d2f10", "fast_d2f10"):
            symbols[f[3]] = {"address": int(f[0], 16), "size": int(f[1], 16)}
    if len(symbols) != 4:
        raise RuntimeError("Missing conversion symbols")
    from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM, UC_HOOK_CODE
    from unicorn.arm64_const import (UC_ARM64_REG_X0, UC_ARM64_REG_X1, UC_ARM64_REG_X2,
                                     UC_ARM64_REG_LR, UC_ARM64_REG_SP, UC_ARM64_REG_FPCR,
                                     UC_ARM64_REG_FPSR, UC_ARM64_REG_PC)
    uc = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
    uc.mem_map(CODE, 0x10000)
    uc.mem_map(DATA, 0x10000)
    uc.mem_map(STACK, 0x10000)
    uc.mem_write(CODE, (out / "text.bin").read_bytes())
    cnt = [0]
    uc.hook_add(UC_HOOK_CODE, lambda *_: cnt.__setitem__(0, cnt[0] + 1))

    def call(sym, x0, x1=0, x2=0):
        uc.mem_write(DATA, b"\xa5" * 64)
        uc.reg_write(UC_ARM64_REG_X0, x0)
        uc.reg_write(UC_ARM64_REG_X1, x1)
        uc.reg_write(UC_ARM64_REG_X2, x2)
        uc.reg_write(UC_ARM64_REG_LR, RET)
        uc.reg_write(UC_ARM64_REG_SP, STACK + 0xfff0)
        uc.reg_write(UC_ARM64_REG_FPCR, 0x400000)
        uc.reg_write(UC_ARM64_REG_FPSR, 0)
        cnt[0] = 0
        uc.emu_start(symbols[sym]["address"], RET, count=2000)
        assert uc.reg_read(UC_ARM64_REG_PC) == RET
        assert uc.reg_read(UC_ARM64_REG_SP) == STACK + 0xfff0
        return (uc.reg_read(UC_ARM64_REG_X0), bytes(uc.mem_read(DATA, 64)),
                uc.reg_read(UC_ARM64_REG_FPSR), cnt[0])

    rng = random.Random(0x87c0)
    d2f_in = [0, 1 << 63, 0x7ff0000000000000, 0xfff0000000000000, 0x7ff8000000000001,
              0x7ff0000000000001, 0xfff7ffffffffffff, 0x000fffffffffffff, 0x8000000000000001,
              0x0010000000000000, 0x7fefffffffffffff, 0x3ff0000000000000, 0xbff0000000000000]
    d2f_in += [rng.getrandbits(64) for _ in range(cases)]
    d2f_in += [(rng.getrandbits(1) << 63) | (rng.randrange(1, 0x7ff) << 52) | rng.getrandbits(52)
               for _ in range(cases)]
    f2d_in = [(0, 0), (0x8000000000000000, 0), (0x8000000000000000, 0x3fff), (0x8000000000000000, 0xbfff),
              (0x8000000000000000, 0x7fff), (0xc000000000000000, 0x7fff), (0xffffffffffffffff, 0x7fff),
              (0x8000000000000001, 0x3fff), (0x80000000000007ff, 0x3fff), (0x8000000000000400, 0x3fff),
              (0x8000000000000c00, 0x3fff), (0x7fffffffffffffff, 0x3fff), (0x8000000000000000, 0x3c00),
              (0x8000000000000000, 0x3c01), (0x8000000000000000, 0x43fe), (0x8000000000000000, 0x43ff),
              (0x8000000000000000, 0x43fd)]
    f2d_in += [(0, 0), (0, 0x8000)] * 16
    f2d_in += [(rng.getrandbits(64), rng.getrandbits(16)) for _ in range(cases)]
    f2d_in += [(0x8000000000000000 | (rng.getrandbits(52) << 11), (rng.getrandbits(1) << 15) | rng.randrange(15361, 16407))
               for _ in range(cases)]

    stats: dict = {}

    def add(kind, cls, which, n):
        s = stats.setdefault(kind, {}).setdefault(cls, {"cases": 0, "ref": 0, "fast": 0})
        s[which] += n
    for b in d2f_in:
        a = call("ref_d2f10", b, DATA, DATA + 8)
        c = call("fast_d2f10", b, DATA, DATA + 8)
        assert a[:3] == c[:3], f"d2f10 mismatch {b:016x}"
        cls = d2f_class(b)
        stats.setdefault("d2f10", {}).setdefault(cls, {"cases": 0, "ref": 0, "fast": 0})["cases"] += 1
        add("d2f10", cls, "ref", a[3]); add("d2f10", cls, "fast", c[3])
    for sig, se in f2d_in:
        a = call("ref_f2d10", sig, se)
        c = call("fast_f2d10", sig, se)
        assert a[:3] == c[:3], f"f2d10 mismatch {se:04x}/{sig:016x}"
        cls = f2d_class(sig, se)
        stats.setdefault("f2d10", {}).setdefault(cls, {"cases": 0, "ref": 0, "fast": 0})["cases"] += 1
        add("f2d10", cls, "ref", a[3]); add("f2d10", cls, "fast", c[3])
    for kind in stats:
        for cls, s in stats[kind].items():
            s["ref_avg"] = round(s["ref"] / s["cases"], 3)
            s["fast_avg"] = round(s["fast"] / s["cases"], 3)
            s["saved_avg"] = round(s["ref_avg"] - s["fast_avg"], 3)
    result = {"status": "pass", "elf_sha256": sha256(elf.read_bytes()).hexdigest(),
              "d2f10_cases": len(d2f_in), "f2d10_cases": len(f2d_in), "symbols": symbols,
              "dynamic_instructions": stats,
              "limits": "Isolated conversion functions (call+ret wrapper included) on synthetic "
                        "inputs; instruction counts only, not cycles, FPS, x87 SW/CW/TOP or tag model."}
    (out / "result.json").write_text(json.dumps(result, indent=2), encoding="utf8")
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--llvm-bin", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--cases", type=int, default=4000)
    a = ap.parse_args()
    print(json.dumps(verify(a.llvm_bin, a.out, a.cases), indent=2))


if __name__ == "__main__":
    main()
