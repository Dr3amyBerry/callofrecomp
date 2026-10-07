# Recompilation roadmap

## Scope

Initial milestone: boot the Call of Duty 1.5 single-player code path on Android ARM64 using original user-supplied game data externally. Multiplayer and United Offensive remain later milestones.

## Phase 0 — Immutable baseline

- Fingerprint original binaries with SHA-256.
- Record exact version and archive inventory.
- Keep original files outside Git.
- Generate machine-readable PE/PK3 reports so later findings can be reproduced.

**Status:** started.

## Phase 1 — Recover module boundaries and ABI

- Map `CoDSP.exe` engine responsibilities.
- Recover the `dllEntry` / `vmMain` ABI used by `gamex86.dll`, `cgamex86.dll` and `uix86.dll`.
- Identify syscall IDs and argument shapes from wrapper stubs.
- Build a symbol ledger with confidence levels: observed / matched / inferred.

**Status:** started. `dllEntry` is confirmed to store a callback pointer and the modules invoke it with numeric syscall IDs.

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
