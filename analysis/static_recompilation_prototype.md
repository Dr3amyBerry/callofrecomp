# Static recompilation prototype (Ghidra p-code → C)

**Date:** 2026-10-12  
**Status:** feasibility proven for the three SP modules on a PC host.

## Question

Can the original x86 module DLLs (`uix86.dll`, `cgamex86.dll`, `gamex86.dll`)
be turned automatically into portable C that behaves like the original, as the
module half of the hybrid plan (recompiled modules + ioquake3-derived engine)?

## Pipeline

1. `tools/ghidra/ExportPcode.java` dumps Ghidra's raw p-code for every
   instruction (Ghidra already models x86 flags, x87 and SSE semantics).
2. `tools/recomp/pcode2c.py` emits one labelled C block per guest instruction.
   Control flow is a whole-program state machine: in-chunk direct branches are
   `goto`s, everything else (indirect jumps, `CALL`/`RETURN`, cross-chunk)
   sets `PC` and returns to the dispatcher. The guest stack lives in guest
   memory, so `CALL`/`RETURN` need no native recursion.
3. `tools/recomp/recomp_host.c` reserves a 4 GiB guest space on a 64-bit
   host, maps the **original DLL file's sections at runtime** (no game bytes are
   embedded in generated code), gives the guest a minimal TIB (`fs:[0]`),
   implements the ~45 KERNEL32 calls the static MSVC CRT needs, runs the
   recompiled `DllMain`, then `dllEntry` and `vmMain`.
4. `tools/recomp/native_host.c` (i686) loads the **real DLL** with
   `LoadLibrary` and replays the same `vmMain` sequence; both hosts log every
   engine syscall through `trace.h`.
5. `tools/recomp/compare_traces.py` diffs the traces.

Run end to end: `GHIDRA_HOME=... tools/recomp/run_module.sh <originals> uix86`.
Generated C, p-code and traces go to ignored `recomp_out/`.

## Results (CoD 1.5 SP, pinned SHA-256 baseline)

| Module | Instructions | Unsupported ops | Trace lines (native / recomp) | Outcome |
|---|---:|---:|---:|---|
| `uix86.dll` | 38,246 | 0 | 10,867 / 10,867 | identical through `DllMain` + `vmMain` 0, 1 (init), 5, 6, 2 |
| `cgamex86.dll` | 79,742 | 0 | 218 / 218 | identical, both stop at the same null dereference |
| `gamex86.dll` | 135,888 | 0 | 5 / 5 | identical, both stop at the same null dereference |

`uix86` initialisation performs 10,856 engine syscalls (cvar registration such
as `ui_menuFiles "ui/menus.txt"`, shader/menu loading). All IDs, strings,
image pointers and small-integer arguments match. The only differing fields are
words logged past a syscall's real arguments (e.g. syscall 8 takes one
argument, the name), i.e. leftover stack contents.

`cgame`/`game` stop early because the harness feeds zero arguments and every
syscall returns 0; the **original DLL crashes at the same place**, so this is
harness depth, not a recompilation error. The crash PC differs by a few bytes
because the recompiled `PC` is only updated at block dispatch.

Timing for the full UI init: 0.16 s recompiled (`-O1`, unoptimised design)
versus 0.06 s native.

## Android ARM64 (real device)

The same generated C, built with NDK r30 (`aarch64-linux-android30-clang`)
against the portable runtime (`mmap`-reserved guest space, POSIX fault
handler), was run on an arm64-v8a device via `adb`. Its trace for `uix86.dll`
equals the native Windows x86 trace (10,867 lines, only unused-stack fields
differ) and the full init takes 0.10 s on the device.

## Known limitations

- x87 80-bit values are carried as `double`; 10-byte memory loads/stores
  (`fld tword`) are not yet handled specially.
- `PC` is block-granular; precise faulting addresses need per-instruction PC.
- KERNEL32 shims are Latin-1 only and deterministic (`rdtsc`, tick counts).
- No x86 exceptions/SEH unwinding at runtime.
- Deeper validation needs a richer fake engine (meaningful syscall return
  values) so `game`/`cgame` paths beyond init are exercised.

## Conclusion

Automatic static recompilation of the SP modules is viable: zero unsupported
p-code operations across ~254k instructions and an identical syscall trace for
the full UI initialisation. The generated C is portable (no x86 assumptions in
the runtime besides little-endian), so the same output should build for
Android ARM64; that build is the next proof point, together with an
engine-side syscall implementation.
