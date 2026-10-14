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



## TECNO ARM64: copy32 y visibilidad -O2 (sin nuevo aumento de FPS)

- [x] Especialización privada de la copia `0x0042B0A0`: **17.000 diferenciales completos en ARM64 y 249.371 bloques** equivalentes a la traducción p-code; A/B/A de FPS **25,45 / 25,10 / 25,30** (referencia/candidato/referencia). Sin ganancia. Flag **OFF por defecto**.
- [x] Compilar solo `codsp_recomp_p8.c` con `-O2 -ffp-contract=off`: A/B/A **25,30 / 25,50 / 25,45**. Diferencia de solo 0,05 FPS frente a la repetición; no es mejora aceptada. Flag **OFF por defecto**.
- [x] Se mantienen el avance x87 (+19,58 % frente a la versión inicial), la APK de referencia en el teléfono y la visión panorámica/HUD ya corregidos.
- [ ] Próxima intervención: optimización semánticamente equivalente *dentro* de geometría/colisiones (`0x0041B8F0`, `0x004196F0`) o visibilidad (`0x004Dxxxx`), con pruebas completas de estado + nuevo A/B/A. **60 FPS sostenidos pendientes.**

[Ver resultados detallados de ambos ensayos](ARM64_PERF_EXPERIMENTS_2026-10-14.md).

## Health bar and circular objective stars (corrected on TECNO)

- [x] Scale all Health script children (cross, backdrop, fill) together,
  without changing health values or right-edge alignment.
- [x] Distinguish cgame's 0x4a color call from the 0x4b direct objective
  draw at `0x3001cf40`; enter the original CoDSP callback, not a host thunk.
- [x] Convert pre-scaled pixel geometry back to virtual HUD units before
  applying the compass shape adjustment, then return to device pixels.
- [x] Objective gold ring measured **29×29 actual screen pixels** on
  TECNO CK6n; full 94 Python / 27 CTest regression passed.
- [ ] 60 FPS at training spawn and other untested campaign icon variants
  are still open, independently of this completed HUD fix.

## Widescreen dynamic compass pointers (corrected in training)

- [x] Isolated the original cgame dynamic friend, tank and objective marker
  callbacks rather than changing the 3D projection or other HUD elements.
- [x] Applied aspect-correct marker sizes and radial bounds so complete
  icons remain inside the circular compass without changing direction.
- [x] TECNO training screenshot plus runtime logs verified green friend
  and objective-pulse correction; 94 Python tests and 27/27 CTest passed.
- [x] Main objective-star circle visually verified in training (actual
  screenshot bbox 29×29px; cgame draw 64×38.4 → 38.4×38.4px).
- [ ] Tank and additional campaign objective icon coverage remains pending.
- [ ] Target of **60 sustained FPS at training spawn** still pending;
  current visual-fix benchmark ~25.75 FPS is not a new proven speedup.

See the HUD widescreen report for geometry and verification evidence.

## Visual aspect fix before further performance experiments (completed)

- [x] Retain real 3D widescreen camera: 1280×576 EGL aspect 2.22222 and expanded ~108.87° horizontal FOV, **not** a stretched 4:3 projection.
- [x] Correct the compass plus selected square 2D HUD icons, as confirmed on the TECNO CK6n. Original resources are unchanged; Android generates a private override from imported data before engine startup.
- [x] Guard original PK3 ZIP duplication compatibility, save/player controls and no proprietary redistributable assets; maintain synthetic Java tests and Android build.
- [ ] Separately fulfill the **60 FPS spawn target**. The widescreen HUD repair is not a performance milestone; prior +19.58% FPS remains measured and the goal is open.
- [Documentation and verification](HUD_WIDESCREEN_2026-10-14.md).

## Meta exigida: 60 FPS sostenidos donde aparece el jugador (NO alcanzada)

- [x] Mejora reproducida en TECNO CK6n, training/Equilibrado: **21,45 -> 25,65 FPS (+19,58 %)** y **44,745 -> 37,495 ms CPU/frame** mediante fast path nativo optativo de CoDSP 0x005061B0. Esta mejora sí cuenta como avance.
- [ ] Objetivo final: **60 FPS sostenidos en la zona de aparición inicial del entrenamiento**, sin sustituirla por el menú o una zona menos exigente.
- [ ] Medir al menos 60 ventanas estables seguidas, FPS bajos, CPU y temperatura; confirmar A/B/A, guardado y jugabilidad.
- [ ] Identificar en el teléfono los cuellos de botella restantes y validarlos uno a uno. El objetivo exige ~16,67 ms por frame frente a ~37,50 ms CPU/frame ahora.
- **Estado:** inacabado; la optimización experimental sigue OFF por defecto en la compilación estándar.

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
