# Recompilation roadmap

## Scope

Initial milestone: boot the Call of Duty 1.5 single-player code path on Android ARM64 using original user-supplied game data externally. Multiplayer and United Offensive remain later milestones.

## Current status snapshot (2026-10-14)

- Exact 1.5 original PE32/DLL fingerprints, SP ABI probes and the portable host: implemented and exercised in local tests.
- Native ARM64 and WSA x86_64 debug APKs: compiled and signed; WSA menus, training and saves have functional smoke coverage. Full campaign on a real phone remains unverified.
- Recompiled graphics path: GL4ES/GLES2; original-menu parse repeats after `Hunk_Clear`. Never label it duplicate per-frame rendering or skip lifecycle work without memory analysis.
- **New diagnostics:** [function-entry/chunk correlation](FUNCTION_LEVEL_PERFORMANCE_2026-10-14.md) is verified with private original p-code (6,228 mapped entry points). Native per-function CPU attribution and crowded ARM64 scene measurements remain pending.
- `-O2`, `-Oz`, GL4ES batching and VBO mode 2/3 experiments were neutral/negative in controlled WSA tests; do not enable indiscriminately.
- **TECNO ARM64:** an opt-in native x87 transform at original CoDSP.exe `0x005061B0` improved one saved training view from 21.45 to **25.65 median FPS** (A/B/A, +19.58%). Default Android build **OFF**; see [measured phone report](TECNO_CK6N_ARM64_PERF_2026-10-14.md).



## Phase 0 — Immutable baseline

- Fingerprint original binaries with SHA-256.
- Record exact version and archive inventory.
- Keep original files outside Git.
- Generate machine-readable PE/PK3 reports so later findings can be reproduced.

**Status:** completed for the verified exact CoD 1.5 SP binary baseline.

## Phase 1 — Recover module boundaries and ABI

- Map `CoDSP.exe` engine responsibilities.
- Recover the `dllEntry` / `vmMain` ABI used by `gamex86.dll`, `cgamex86.dll` and `uix86.dll`.
- Identify syscall IDs and argument shapes from wrapper stubs.
- Build a symbol ledger with confidence levels: observed / matched / inferred.

**Status:** core SP ABI mapping verified; detailed names/semantics of some syscall IDs remain unresolved. `dllEntry` stores the engine callback and modules call it by numeric syscall ID.

## Phase 2 — Static analysis pipeline

- Add deterministic function discovery and call-target extraction.
- Integrate a headless decompiler workflow for functions selected by address.
- Export function metadata to JSON instead of relying on a GUI project file.
- Add cross-reference and string-reference reports.
- Add optional matching against public id Tech 3 reference code where behavior is genuinely homologous; never assume identity from naming alone.

## Phase 3 — Reconstructed platform-neutral core

- Recreate engine/module interfaces in clean C/C++.
- Preserve gameplay/data formats while replacing Win32-specific platform code.
- Create regression harnesses for parsers, command dispatch, math and serialization.

## Phase 4 — Android host layer

- Android NDK / ARM64 build.
- Filesystem bridge for externally supplied game assets.
- Renderer adaptation from desktop OpenGL behavior to a supported Android path.
- Audio backend replacement for Miles/Win32-specific calls.
- Input abstraction for touch, controller and keyboard/mouse where available.

## Phase 5 — First boot milestone

Definition of done:

1. Native ARM64 executable/library starts on Android.
2. Filesystem initializes and reads original PK3 data.
3. Renderer opens a frame and reaches the game UI.
4. Single-player module initializes through the reconstructed ABI.
5. A map can be entered without x86 emulation.

## Phase 6 — Correctness and optimization

- Compare deterministic behavior against the PC baseline.
- Fix endian/alignment/pointer-width assumptions.
- Optimize renderer/resource loading only after correctness.
- Add device-specific input/UI polish.

## Phase 7 — Function-level performance proof and measured optimization (active)

- [x] Restore Ghidra original function-entry metadata to an optional, ignored mapping sidecar without changing default compiled behavior.
- [x] Associate existing guest CPU chunk samples with the exact private maps, without fabricating per-function CPU percentages.
- [x] Archive references, rejected experiments, repeatable commands and correctness restrictions in [the 2026-10-14 research](FUNCTION_LEVEL_PERFORMANCE_2026-10-14.md).
- [x] Export noncontiguous original Ghidra B body ranges from the saved project into ignored v2 provenance maps; real modules yielded 519,757 uniquely assigned x86 instructions and 80,013 unassigned.
- [x] Add native ARM64 ELF-PC → inline stack → generated C line → x86 instruction → Ghidra body resolution, verified with the unstripped real shared library and artificial ELF-address fixtures.
- [x] Capturadas muestras reales con Simpleperf en el TECNO ARM64 en la entrada de training; correlación estadística a funciones mediante DWARF y Ghidra (ver [auditoría TECNO](TECNO_CK6N_ARM64_PERF_2026-10-14.md)). No equivale a tiempo exclusivo por función.
- [ ] If source-line sampling is insufficient, capture guest function entry/return activity behind opt-in instrumentation and measure overhead before enabling any native fast path.
- [ ] Capture **native physical ARM64** CPU/GPU traces from the crowded training scene with controlled camera/save/thermal variables.
- [x] Identificada función x86 caliente original CoDSP.exe 0x005061B0 (656 muestras en un perfil físico) y descartados -O2, -Oz y reducción global de detalle como solución.
- [x] Implementar y medir **optativamente** la ruta matemática 0x005061B0: 75.000 diferenciales bit a bit frente al p-code, A/B/A físico +19,58 % FPS en una vista concreta, 26/26 CTest. Mantener OFF por defecto.
- [ ] Antes de habilitar por defecto, completar oráculo de ejecución **x86 original** independiente (la evidencia actual compara contra p-code), excepciones/precisión FPU, jugabilidad y calidad visual en otras misiones/escena concurrida y más dispositivos.

**Non-goals until evidence exists:** wholesale renderer replacement, disabling menu reloads after `Hunk_Clear`, changing original game logic or promising a universal FPS gain.
