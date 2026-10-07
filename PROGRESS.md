# Project Progress

> Living project log for the Call of Duty 1.5 PC → Android ARM64 recompilation effort.
>
> **Rule:** this file must be updated whenever a meaningful phase starts, completes, changes direction, discovers a blocker, or requires a new external tool.

**Last updated:** 2026-10-07  
**Primary branch:** `main`  
**Primary target:** Call of Duty 1.5 single-player  
**Long-term target:** native Android ARM64 execution without x86 emulation

---

## 1. Operating objective

The objective is to complete as much of the reverse-engineering and native recompilation work as possible autonomously, with the least possible user intervention.

Default operating model:

1. Inspect the original game files from the connected Google Drive.
2. Build reproducible static-analysis tooling in this repository.
3. Record evidence and uncertainty instead of guessing.
4. Reconstruct interfaces and behavior in clean C/C++.
5. Build a portable platform-neutral core.
6. Add the Android ARM64 host/platform layer.
7. Validate against the original PC behavior.
8. Ask the user for help only when a required capability is genuinely outside the available tools or permissions.

I should not stop merely because a task is large. Work should be split into phases and committed incrementally to `main`.

---

## 2. Current status

### Completed foundation

- [x] Connected to and inspected the supplied Call of Duty Deluxe installation in Google Drive.
- [x] Confirmed the base game reports Call of Duty **1.5** on PC.
- [x] Isolated the initial single-player binaries:
  - `CoDSP.exe`
  - `gamex86.dll`
  - `cgamex86.dll`
  - `uix86.dll`
- [x] Confirmed all initial target binaries are PE32 / x86.
- [x] Fingerprinted the initial binaries with SHA-256.
- [x] Inventoried the base `main/` PK3 set at Drive metadata level.
- [x] Established the repository policy that original proprietary game assets remain outside Git.
- [x] Added a dependency-free PE32 analysis tool.
- [x] Added a non-extracting PK3 inventory tool.
- [x] Added a first module-ABI probe.
- [x] Confirmed all three single-player modules export `dllEntry` and `vmMain`.
- [x] Recovered the module-global syscall callback slots installed by `dllEntry`.
- [x] Recovered indexed `vmMain` dispatch tables.
- [x] Began recovering numeric module → engine syscall IDs.
- [x] Located the native module loader / VM creation path in `CoDSP.exe`.
- [x] Located the engine `VM_Call` wrapper and all three VM-handle globals.
- [x] Located the game/cgame/ui module→engine syscall callbacks.
- [x] Recovered all three engine-side syscall jump tables and their numeric ranges.
- [x] Added an engine VM probe that emits reproducible JSON for both directions of the ABI.
- [x] Extended the PE inspector to record import IAT addresses.
- [x] Confirmed the dynamic OpenGL/WGL loader path: `LoadLibraryA("opengl32.dll")` + `GetProcAddress` and renderer function-pointer population.
- [x] Corrected and completed the current SP UI export map: IDs 0–8 and 10–13 are matched; ID 9 remains deliberately unnamed.
- [x] Mapped the evidence-backed SP game syscall prefix 0–19, including SP-only `G_ENDGAME` and `G_CVAR_SETVAR` insertions.
- [x] Added a verified build profile containing hashes and recovered VM addresses for this exact CoD 1.5 SP baseline.
- [x] Added a one-command baseline analyzer that verifies the binary hashes before generating PE/module/engine VM reports.
- [x] Added a portable 32-bit legacy VM word ABI header and the first reconstructed SP game syscall enum.
- [x] Added CMake host-build scaffolding and a first ABI smoke test.
- [x] Added CI that compiles/smoke-tests analysis tools and builds/runs the host ABI test.
- [x] Documented the external-reference verification/licensing policy; public reconstruction code without a declared license is not copied into this repository.
- [x] Established an evidence ledger using `observed`, `matched`, and `inferred` confidence levels.
- [x] Audited the current `main` tree before editing; preserved the newer engine/renderer/reference findings and existing build files.
- [x] Rechecked SHA-256 fingerprints for all four private single-player binaries; they match the pinned baseline.
- [x] Reproduced module `vmMain` limits and callback-slot RVAs using the original binaries.
- [x] Verified existing CI runs pass before expanding tools.
- [x] Added six offline Python regression tests covering synthetic PE structure, malformed input, ASCII extraction, dispatch limits, immediate syscall sites, and an optional exact-binary check.
- [x] Registered those Python regressions with CTest; existing GitHub Actions executes them without requiring a workflow rewrite.
- [x] Added an evidence-only engine syscall-handler edge inventory tool using bounded `objdump` disassembly.
- [x] Recorded the first direct branch targets for all 24 SP game syscall handler entries 20–43 in `analysis/game_syscall_edges_20_43.md`.
- [x] Added a decoded-branch regression test for the new edge tool.

### Confirmed module ABI data

| Module | `vmMain` commands | callback-slot RVA | jump-table RVA |
|---|---:|---:|---:|
| `gamex86.dll` | 25 (`0..24`) | `0x000A4834` | `0x0001CF4C` |
| `cgamex86.dll` | 26 (`0..25`) | `0x000657E8` | `0x00018F3C` |
| `uix86.dll` | 14 (`0..13`) | `0x00034030` | `0x00007A50` |

### Confirmed engine VM boundary

| Module | engine VM-handle slot | module→engine callback | syscall range |
|---|---:|---:|---:|
| `game` | `0x013F9DB8` | `0x0044A2F0` | `0..211` |
| `cgame` | `0x014BD620` | `0x00401A50` | `0..252` |
| `ui` | `0x014BD648` | `0x00410B00` | `0..84` |

Observed engine VM functions:

- native VM loader / creation path: `0x0044F0E0`
- VM call wrapper: `0x0044F270`

### First module syscall recovery pass

| Module | indirect callback calls | distinct immediate IDs recovered | unresolved sites |
|---|---:|---:|---:|
| `gamex86.dll` | 1,187 | 161 | 214 |
| `cgamex86.dll` | 1,144 | 240 | 179 |
| `uix86.dll` | 377 | 74 | 63 |

These IDs are numeric evidence only. Semantic names are not assigned until supported by additional evidence.

### First engine→module command recovery pass

| Module | classified `VM_Call` sites | distinct immediate command IDs |
|---|---:|---:|
| `game` | 43 | 19 |
| `cgame` | 33 | 23 |
| `ui` | 37 | 13 |

The narrow scanner intentionally leaves non-immediate/register-driven cases unresolved rather than guessing.

### UI export commands matched so far

The supplied SP UI binary now has evidence-backed working names for IDs 0–8 and 10–13:

`UI_GETAPIVERSION`, `UI_INIT`, `UI_SHUTDOWN`, `UI_KEY_EVENT`, `UI_MOUSE_EVENT`, `UI_REFRESH`, `UI_IS_FULLSCREEN`, `UI_SET_ACTIVE_MENU`, `UI_GET_ACTIVE_MENU`, `UI_CONSOLE_COMMAND`, `UI_DRAW_CONNECT_SCREEN`, `UI_LOAD_SCRIPT_MENU`, and `UI_GET_FONT_INFO`.

ID 9 is an observed zero-argument menu-state boolean query but remains intentionally unnamed instead of inheriting an incorrect RTCW/MP label.

### SP game syscall semantic recovery

The game-module dispatcher range is `0..211`. IDs `0..19` now have independently verified working semantics:

`G_PRINT`, `G_ERROR`, `G_ERROR_NOPREFIX`, `G_ENDGAME`, `G_MILLISECONDS`, the VM-cvar register/update/set/setvar/query group, `G_ARGC`, `G_ARGV`, and the first hunk allocation/temp-allocation group.

The SP table is not a drop-in copy of the known multiplayer enum: `G_ENDGAME` is inserted at ID 3 and a VM-cvar set-by-handle operation is also present.

---

## Verification checkpoint (2026-10-07)

- Inspected the repository `main` tree and current commit before changes. Existing analysis and source were not overwritten.
- Recomputed SHA-256 hashes of the four exact private PC 1.5 SP binaries and independently confirmed the stored fingerprints.
- Re-ran the PE32 metadata collector and initial VM ABI probe against all four originals; observed the original module-command and immediate-call counts.
- Ran the new synthetic/optional-real binary tests locally before publishing; **6 passed** with `CODRECOMP_ORIGINALS` set. Without original files, **5 passed + 1 expected skip**.
- GitHub CI for the Python/CTest regression integration and subsequent edge-tool update completed successfully. This verifies repository checks, not Android playability.
- A change to `.github/workflows/tools-ci.yml` was not accepted by the integration; the necessary test registration was instead made through the existing `CMakeLists.txt`/CTest path. No workflow override was needed.
- The edge analysis is evidence-only: entries 20–43 have decoded direct branch destinations, **not** fully identified syscall semantics.
- **Next task:** map input/output ABI signatures and evidence-backed semantic labels for these new dispatch entries; continue tracking unknowns rather than guessing.

## 3. Current work queue

### Phase A — strengthen the static-analysis pipeline

- [ ] Recover every `vmMain` target and produce deterministic function maps.
- [ ] Recover syscall wrappers with argument-count / argument-shape evidence.
- [x] Add first direct-call recovery around the engine `VM_Call` boundary.
- [ ] Expand direct/indirect call-target recovery beyond the current narrow patterns.
- [x] Add first reproducible absolute string-reference scanner.
- [ ] Extend string/xref recovery with instruction-aware decoding and broader reference forms.
- [ ] Add broader cross-reference output suitable for machine processing.
- [x] Produce reproducible JSON reports for the PE, module ABI, and engine VM boundary.
- [x] Map engine code responsible for loading the game/cgame/ui modules.
- [x] Confirm the dynamic OpenGL loader path rather than only inferring it from strings.
- [ ] Inventory the renderer GL/WGL function-pointer table and classify Android replacement requirements.
- [ ] Recover engine-side semantic names for remaining syscall IDs with independent evidence.
- [x] Map SP game syscall IDs 0–19.
- [x] Extract first bounded direct `call` / `jmp` edges for SP game syscalls 20–43 (addresses only; semantic names remain unverified).
- [ ] Recover argument shapes, side effects, and independently supported names for syscall handlers 20–43.
- [ ] Harden the binary parsers' bounds checks against malformed PE files and add failure-mode tests.

### Phase B — reconstruct interfaces

- [x] Define the first portable C declarations for the observed 32-bit VM word/call representation.
- [x] Codify the verified SP game syscall prefix 0–19 without naming unverified IDs.
- [ ] Expand portable ABI declarations as additional syscall/export ranges are verified.
- [ ] Reconstruct the minimum filesystem/cvar/command/memory interfaces needed for module startup.
- [ ] Build a host-side test harness that can call reconstructed module interfaces without launching the full game.

### Phase C — data and boot path

- [ ] Deep-inventory required PK3 contents.
- [ ] Identify formats required before the first menu/map boot.
- [ ] Reconstruct PK3 search/load precedence.
- [ ] Reconstruct configuration and localization loading.
- [ ] Trace single-player startup from process entry to first rendered frame.

### Phase D — native implementation

- [x] Start portable C/C++ host scaffolding with CMake and an ABI interface target.
- [x] Add the first deterministic host ABI smoke test.
- [ ] Add regression tests for recovered parsers, dispatch tables, and reconstructed subsystem behavior.
- [ ] Replace Win32 filesystem/time/thread/input dependencies with portable interfaces.
- [ ] Replace Miles/Windows-specific audio integration with a portable backend.
- [ ] Adapt rendering to an Android-supported graphics path.

### Phase E — Android ARM64

- [ ] Add Android NDK/CMake target.
- [ ] Build ARM64 native library/executable.
- [ ] Add Android asset/filesystem bridge for user-owned original game files.
- [ ] Add touch and controller input layer.
- [ ] Reach menu.
- [ ] Load first single-player map.
- [ ] Validate gameplay and save/load behavior.

---

## 4. What I can do directly

The following work is currently within my reach and should be performed without asking the user to do it manually:

- Read and list the connected Google Drive installation.
- Download individual original binaries or archives from Drive when needed for analysis.
- Read and write the private GitHub repository.
- Commit directly to `main`.
- Create and maintain analysis tools, source code, tests, build files, and documentation.
- Parse PE32 binaries and PK3/ZIP structures.
- Compute hashes and reproducible metadata.
- Use local Python for binary-analysis automation.
- Use local `objdump` and `llvm-objdump`.
- Compile/test portable C and C++ locally with Clang.
- Use CMake and Ninja for host-side builds.
- Perform static string/import/export/xref/function-pattern analysis.
- Build custom disassembly/analysis utilities when practical.
- Compare behavior against public reference implementations where legally and technically appropriate.
- Design the portable architecture and Android boundary.
- Keep the progress log, symbol ledger, findings, and roadmap synchronized with actual work.
- Make safe incremental commits without requesting approval for every commit.

---

## 5. Capabilities not currently available in the working environment

These are tool/environment limitations, not reasons to abandon the project.

### Not currently installed

At the time of this update the working environment has:

- available: Python, GNU `objdump`, `llvm-objdump`, Clang/Clang++, CMake, Ninja
- not currently available: Ghidra headless tools, radare2/rizin, Android SDK, Android NDK, `adb`

When one of the missing tools becomes the most efficient or necessary path, I should record the exact requirement here and ask the user to provide/enable it rather than making the user perform the analysis manually.

### Outside direct reach

I cannot directly:

- operate the user's physical Android phone unless a device/emulator interface is made available;
- click through software running only on the user's local Windows desktop;
- inspect a local-only file that has not been uploaded/shared through an accessible source;
- use a proprietary decompiler/debugger that is not installed or connected;
- obtain unpublished proprietary Call of Duty source code;
- guarantee that decompiler output is identical to the original source code;
- perform real-device performance/input/audio validation without an accessible Android runtime/device;
- sign or publish a final application with user-owned store/signing credentials unless those capabilities are explicitly provided;
- continue executing work in the background after the current tool execution ends.

These limitations should be handled by building automated artifacts/scripts so that any unavoidable user action is minimal and narrowly specified.

---

## 6. User assistance policy

The project should require the least possible help from the user.

### Do not ask the user for

- manual binary inspection that I can automate;
- copying function addresses by hand;
- manually listing Drive files I can access;
- creating repository files or commits I can create myself;
- running ordinary static-analysis commands merely to paste their output back;
- repeatedly approving safe incremental work on `main`.

### Ask the user only when necessary for

- granting access to a file, repository, device, or service I cannot access;
- providing/installing a missing specialist tool that materially blocks the next phase;
- attaching an Android device/emulator/runtime for validation;
- supplying signing/store credentials for release work;
- making a product/legal decision that should not be chosen silently;
- authorizing an irreversible or externally consequential action.

Whenever user help is required, the request must state:

1. **exactly what is missing**;
2. **why it is needed now**;
3. **the minimum action the user must take**;
4. **what work will resume immediately afterward**.

---

## 7. Tool requests / blockers

### Active blockers

None for the current static-analysis phase.

The available Python + PE tooling + objdump/LLVM tooling is enough to continue recovering the ABI, call graph, strings, loaders, and binary structure.

### Expected future tool needs

These are anticipated, not yet active blockers:

| Tool/capability | Why it may be needed | When to request it |
|---|---|---|
| Ghidra headless | scalable decompilation, p-code, xrefs, function recovery | when custom/static tooling stops being efficient for large-scale function reconstruction |
| Android NDK | native ARM64 compilation | when the reconstructed portable core reaches Android build stage |
| Android SDK + adb or accessible emulator/device | install/run/log/debug | when first Android binary is ready |
| Optional debugger/emulator | runtime behavioral validation of original x86 code | only if static evidence is insufficient for a specific behavior |

Do not request these merely because they could be useful. Request them only when they become the next concrete dependency.

---

## 8. Quality rules

- Never commit original proprietary game binaries/assets.
- Never present inferred semantics as recovered facts.
- Every recovered interface should be reproducible from scripts where practical.
- Prefer small focused commits with a clear technical purpose.
- Keep working on `main` unless the user explicitly requests another branch.
- Avoid dead code and one-off throwaway patches.
- New tooling should have a deterministic CLI and machine-readable output when useful.
- The Android port should ultimately use user-owned original assets externally rather than bundling proprietary game data.
- Correctness comes before optimization.
- A subsystem is not considered reconstructed merely because it compiles; behavior must be validated.

---

## 9. Definition of major milestones

### M1 — Static architecture mapped

**Status: in progress.**

Complete when the executable/module boundaries, startup path, `vmMain` commands, syscall interfaces, major engine subsystems, and necessary asset formats have usable evidence-backed maps.

The native VM boundary is now mapped, the Win32 OpenGL dynamic-loader seam is confirmed, the SP UI export table is mostly named, the SP game syscall prefix 0–19 is mapped, and portable host scaffolding has started. Remaining M1 work is dominated by the rest of the syscall/export semantics, startup/subsystem maps, renderer dispatch classification, and required data formats.

### M2 — Portable host harness

Complete when reconstructed interfaces can initialize and execute meaningful module behavior in a host-side C/C++ test program without the original Windows executable.

### M3 — Native desktop proof

Complete when enough reconstructed engine behavior runs natively from our own build to exercise startup/data/module paths using externally supplied original assets.

### M4 — Android first boot

Complete when an ARM64 Android build initializes, reads original PK3 data, opens graphics/audio/input subsystems, and reaches visible game UI.

### M5 — Playable single player

Complete when the Android build can enter a campaign map and sustain core gameplay without x86 emulation.

### M6 — Compatibility/polish

Save/load correctness, controls, audio, rendering fixes, device compatibility, performance, and packaging are addressed after the playable milestone.

---

## 10. Progress-log maintenance rule

Every substantive commit should cause this file to be reviewed.

Update at least one of:

- completed work;
- current work queue;
- confirmed findings;
- blockers/tool requirements;
- milestone status;
- scope changes.

The log should reflect what actually exists in the repository, not what is merely planned.
