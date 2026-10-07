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
- [x] Recovered direct argument-slot references and return shapes for SP game syscall IDs 20–43 against the original `CoDSP.exe`.
- [x] Added `tools/syscall_signature_probe.py` with deterministic JSON export and conservative confidence terminology.
- [x] Verified the result categories for all 24 cases: **12 forced-zero EAX**, **6 tail-jumps**, and **6 EAX-not-cleared**.
- [x] Added five synthetic unit tests covering argument indexing, explicit zero returns, tail returns, untouched EAX and out-of-range instruction windows.
- [x] Added seven independently matched non-contiguous SP syscall names (21–23, 36–37, 40–41) to `include/codrecomp/game_sp_syscalls.h`.
- [x] Added numeric ABI assertions to the C host smoke test and verified GitHub CI success for the test/header changes.
- [x] Documented signatures, addresses, evidence and unverified cases in `analysis/sp_game_syscall_signatures_20_43.md`.
- [x] Identified all seven canonical game-module syscall wrappers (21/22/23/36/37/40/41) at their exact 1.5 SP virtual addresses.
- [x] Independently confirmed the DLL callback pointer slot at `0x200A4834` and reconstructed ordered wrapper argument origins.
- [x] Provenanced ID 40's *fourth* callback argument to a preserved `EAX` value and its first to the caller's stack word; avoided a three-argument ABI mistake.
- [x] Added `tools/module_wrapper_probe.py` with optional SHA-256 guard, bounded scanning, deterministic JSON output and fail-closed parsing.
- [x] Added wrapper-provenance regression tests (four synthetic + one optional exact-original DLL check).
- [x] Added portable native-pointer-width filesystem/command service contract `include/codrecomp/host_services.h` (interface only; runtime bridge not yet implemented).
- [x] Added `tests/host_services_smoke.c` and registered it in CTest/CMake to verify calling through the new host boundary without pointer truncation.
- [x] GitHub Actions succeeded for wrapper tests and host-services compilation/CTest registration.
- [x] Documented source addresses and exact argument order in `analysis/module_syscall_wrapper_provenance.md`.
- [x] Extended the one-command verified baseline analyzer with the optional `--with-wrapper-provenance` flag; the existing default pipeline remains unchanged.
- [x] Updated the README to document provenance recovery and pointer-width-safe host service contracts.
- [x] Implemented a **working read-only C++17 VFS** for loose files and ZIP32/PK3 members with zlib.
- [x] Added central-directory indexing, stored/DEFLATE extraction, CRC-32 and file-size validation.
- [x] Added traversal/absolute path/symlink escape checks, 64 MiB per-file read caps, and ZIP32-only fail-closed behavior.
- [x] Added `tests/vfs_smoke.cpp` with generated stored/deflated PK3 fixtures, invalid CRC/ZIP, mount order and traversal checks.
- [x] Verified original `main/pakb.pk3` can be mounted and its two known binary/menu members read and CRC-validated (24 indexed files).
- [x] Verified original Spanish localization PK3 `localized_spanish_pak4.pk3` mounts and both menu files can be read and CRC-validated (2 indexed files).
- [x] Integrated `codrecomp_vfs` with zlib and CTest in CMake; corrected a compilation error found by CI and confirmed a subsequent GitHub Actions run succeeded.
- [x] Fixed CI paths so changes under `src/**` trigger source compilation/testing.
- [x] Independently mapped the four numeric `FS_FOpenFile` branches in original `CoDSP.exe`, leaving their semantic mode names unverified.
- [x] Documented this phase in `analysis/filesystem_vfs_phase.md`.
- [x] Implemented native read-only `ReadOnlyHostAdapter`: connects VFS to `cod_host_services_t` callbacks (`fs_open`/`fs_read`/`fs_close`).
- [x] Added opaque host handles, independent read cursors, partial read/EOF handling, error checks and mutex-protected handle state.
- [x] Exposed a caller-provided accepted read mode; **did not** guess or hardcode the original game's numeric mode semantics.
- [x] Kept write/rename/list/console host callbacks disabled until their semantics are verified.
- [x] Added `tests/host_adapter_smoke.cpp` and CTest target; local test and GitHub CI completed successfully.
- [x] Updated `analysis/filesystem_vfs_phase.md` with the host interface versus original VM ABI distinction.
- [x] Verified original FS open modes against the exact CoD 1.5 SP binary: `0=rb/read`, `1=wb/write`, `2=ab/append`, `3=ab/append with post-write sync flag`.
- [x] Located the original filesystem searchpath head at `0x013F9E3C`, its linked-list traversal from the read helper, and a conditional insertion routine; full package/localization priority remains **unresolved**.
- [x] Added `analysis/fs_modes_and_searchpath_evidence.md` with original VAs and reproducible disassembly commands.
- [x] Implemented `GuestMemory` as bounded explicit 32-bit address regions with mapping permissions, NUL-bounded string reads, overflow checks and little-endian u32 access.
- [x] Added `LegacyFsReadBridge` for observed SP syscall IDs `21` (mode 0 open), `22` (read) and `37` (close). The bridge never casts a guest address to a native pointer.
- [x] Added guest-memory, handle, bounds, error, EOF and forbidden-write regression tests in `tests/guest_vm_bridge_smoke.cpp`, integrated into CMake/CTest.
- [x] Confirmed **6/6 CTest targets passed** in GitHub Actions for commit `8a1f743`, including the new VM bridge. No original game binary was bundled.
- [x] Documented contract, confidence limits and test instructions in `docs/LEGACY_FS_BRIDGE.md`.

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
- **Next task (superseded by the signature pass below):** signature/return categories and selected evidence-backed semantic names are now recovered. Full callee argument/ownership tracing remains open.

## Signature-analysis checkpoint (2026-10-07)

**Inputs verified:** the pinned original `CoDSP.exe` SHA-256 matches `analysis/baselines/cod1_sp_pc_1_5.json`. All 24 dispatcher cases (20–43) were parsed from binary disassembly, and their direct `[EBP + offset]` references were decoded to argument indices.

- EBP points to the syscall word array; slot `[EBP+0]` is the syscall ID, not a user argument.
- 12 handlers force EAX=0; 6 delegate via a tail jump; 6 do not reset EAX. These are **low-level shapes**, not finalized C types or behavior claims.
- Matched working names: `G_FS_FOPEN_FILE` (21), `G_FS_READ` (22), `G_FS_WRITE` (23), `G_FS_RENAME` (36), `G_FS_FCLOSE_FILE` (37), `G_FS_GETFILELIST` (40), `G_SEND_CONSOLE_COMMAND` (41).
- ID 20 and the other unnamed IDs remain intentionally **unknown**; an adjacent `Hunk_Clear` diagnostic is **not enough** to name ID 20 because it belongs to a different entry address.
- Five new synthetic tests passed locally. The corresponding tool and enum/smoke-test CI runs have completed successfully on GitHub.
- No new external tool is needed yet. A full decompiler (e.g. Ghidra) will be requested only when materially necessary to recover unverified callee semantics/ownership.
- **Next autonomous work:** trace the module-side syscall wrappers for the seven matched IDs, strengthen argument/return signatures, and implement portable filesystem/Cbuf interface contracts without relying on C casts from 64-bit pointers to 32-bit legacy VM words.

Reference: [`analysis/sp_game_syscall_signatures_20_43.md`](analysis/sp_game_syscall_signatures_20_43.md).

## Module-wrapper and native host-interface checkpoint (2026-10-07)

**Verified original DLL:** `gamex86.dll` SHA-256 `27930aa3f663d0af39a90e6956c980be1e599e0f0c98191a9fb7eaba61481577`; `dllEntry` stores callback at `0x200A4834`.

Canonical native wrappers recovered directly from the original DLL:

| ID | Wrapper VA | Data words supplied to engine callback |
|---:|---:|---|
| 21 | `0x20042840` | `EDX, ECX, EAX` |
| 22 | `0x20042850` | `EDX, ECX, EAX` |
| 23 | `0x20042860` | `EDX, ECX, EAX` |
| 36 | `0x20042940` | `ECX, EAX` |
| 37 | `0x20042950` | `EAX` |
| 40 | `0x20042980` | `stack_arg_0, EDX, ECX, EAX` |
| 41 | `0x200429A0` | `ECX, EAX` |

The word order is **observed**, but does **not** establish each wrapper's higher-level C calling convention. This is a bounded and deliberately conservative analysis. Code that accesses unmodeled instructions fails rather than inventing sources.

**Validation:** an implementation prototype ran the five wrapper-provenance checks against the original local binary (passed); the same narrow logic and synthetic fixtures were committed. GitHub Actions successfully ran the new tests and the new host-services CMake target. The host interface is currently a compiled/tested **contract**, not a working filesystem implementation or native Android binary.

**No active external blockers.** The existing GitHub Actions CI also passed the opt-in baseline analyzer change. Remaining work: trace caller/callee parameter types, filesystem modes, directory policy and handles, then implement a safe 32-bit VM-to-native host bridge with runtime validation. Do not confuse the new native host-service prototypes with original x86 exports.

See [`analysis/module_syscall_wrapper_provenance.md`](analysis/module_syscall_wrapper_provenance.md).

## Read-only VFS/PK3 checkpoint (2026-10-07)

- A C++17/zlib VFS now compiles and **reads real game data**, not just PK3 metadata.
- The independently supplied `main/pakb.pk3` indexed 24 unique non-directory files; `ui_mp/createserver.menu` (27,514 bytes) and `ui_mp_x86.dll` (274,432 bytes) were decompressed with matching CRC-32.
- The original Spanish localization archive `localized_spanish_pak4.pk3` indexed 2 non-directory entries; `ui_mp/spanish/createserver.menu` (15,193 bytes) and `ui_mp/spanish/joinserver.menu` (35,057 bytes) passed the same read/CRC checks.
- Synthetic tests cover stored + deflated entries, empty files, case-insensitive PK3 lookup, path traversal, invalid archives, invalid CRC, symlink escape and explicit mount priority.
- The original engine's `FS_FOpenFile` routine at `0x00425FD0` dispatches numeric modes **0–3**, but these modes do not yet have independently proven semantics or names. The VFS does **not** implement original filesystem modes.
- The provisional precedence used here is **most recently mounted source wins**; original COD1 priority, paths and localization behavior remain to be mapped.
- Source and tests are committed only to `main`; original EXE/DLL/PK3 assets remain external. GitHub CI passed after correcting a C++ compilation mistake. The failed intermediate runs are historical and not counted as successful tests.
- **Scope remains M1 + early M2:** there is no engine/VM adapter, savegame write support, streaming/seek, Android NDK executable, menu or playable campaign yet.
- **Next autonomous task:** trace original PK3 precedence and file-open mode behavior, then implement a validated read-only VM/host bridge and streaming handle operations.

See [`analysis/filesystem_vfs_phase.md`](analysis/filesystem_vfs_phase.md).

## Host service adapter checkpoint (2026-10-07)

- The independently tested native VFS is now wired to a separate, functioning read-only host callback layer with opaque handles.
- `ReadOnlyHostAdapter` loads VFS contents on open (bounded to 64 MiB), tracks cursor and allows partial reads and EOF, and frees the associated buffer when closed.
- Thread safety is limited to adapter-owned handle/cursor state. The VFS mount list must not be modified concurrently.
- This is **not** a reconstruction of the original game module's callback ABI or an ARM64 build: there is no conversion of untrusted legacy 32-bit pointers into host pointers, and original file-open modes remain unverified.
- Test coverage now includes synthetic ZIP fixtures and host callback semantics; local checks against two original PK3 archives were also successful.
- The updated CMake job passed on GitHub Actions: `https://github.com/Dr3amyBerry/callofrecomp/actions/runs/37559079417`.
- **Next task:** verify original file mode semantics and package precedence, then implement a validated VM→host bridge; follow with streaming seek and writable save/config support only once their behaviors are understood.
- **Active blockers:** none for continued static analysis and native host scaffolding. Android NDK and real-device validation will be needed later.

## Verified file modes and read-only guest VM bridge checkpoint (2026-10-07 UTC)

- The original `CoDSP.exe` dispatches `FS_FOpenFile` mode **0** to an `rb` path, **1** to `wb`, and **2/3** to `ab`; mode 3 additionally sets a flag tested by the write/flush path. See [mode evidence](analysis/fs_modes_and_searchpath_evidence.md).
- The **linked-list searchpath implementation** is observed (head `0x013F9E3C`; read helper `0x004226A0`; conditional insertion `0x004248B0`), but exact PK3 priority is still not reconstructed. Do not silently switch the current provisional last-mounted-wins VFS rule.
- `GuestMemory` maps host-provided bytes into explicit bounded guest 32-bit VA ranges, checks write permissions, rejects overlaps/overflow and provides NUL-terminated strings and little-endian word access. Host pointers are never truncated.
- `LegacyFsReadBridge` now calls the native host service table only for **21 FS_FOPEN_FILE (read mode 0)**, **22 FS_READ** and **37 FS_FCLOSE_FILE**; all write/rename/list/console syscalls remain unsupported. Open handles are tracked, stale/invalid handles rejected, and incomplete reads never partially copy into guest RAM.
- Synthetic regression tests validate the bridge without original proprietary EXE/DLL/PK3 files. GitHub CI compiled the C++ library and ran **6/6 CTest targets successfully**: `https://github.com/Dr3amyBerry/callofrecomp/actions/runs/37560393331`.
- This is a **portable host-side ABI harness**, not native execution of CoD game/cgame/ui modules. No Android build, renderer or playable menu is yet present.
- **Next autonomous phase:** complete original mount order and file-read error/handle semantics; add safe streaming/seek and a writable sandbox separately, then integrate the bridge into a reconstructed module host.
- **External blockers:** none for immediate static/host work; Android NDK and a runnable emulator/device will eventually be needed for ARM64 validation.

## Searchpath insertion checkpoint (2026-10-07 UTC)

- Confirmed the byte fingerprint of the **55-byte** searchpath insertion function at `CoDSP.exe` VA `0x004248B0`; its SHA-256 is `51a41202f498c49d4e8c7d001c8ac647d531882c324f220c57fc7bb6ebe07683`. Verification is tied to the original known-good executable hash.
- Modeled its conditional linked-list behavior in portable C++: zero-class nodes prepend; nonzero-class nodes insert after the head and its consecutive zero-class successors. The model includes unusual nonzero-only ordering that simple priority sorting would get wrong.
- Added `tools/searchpath_order_probe.py` and portable C++ regression fixtures; no proprietary executable bytes are committed.
- The `+0x0C` flag semantics and **full engine startup/mount precedence are still unconfirmed**. The model deliberately stays separate from the working VFS until discovery calls and class assignments are traced.
- No additional user action is required. Next: trace node construction and connect the recovered behavior to actual PK3/locale discovery; continue streaming I/O development.

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
- [x] Recover direct argument-slot references and EAX-return shapes for syscall handlers 20–43.
- [x] Identify seven evidence-backed filesystem/console SP syscall names in the 20–43 range.
- [ ] Recover full argument semantics, indirect inputs, ownership and side effects for remaining unknown IDs in 20–43.
- [x] Recover observed module-wrapper argument word order for the seven matched IDs (21–23, 36, 37, 40, 41).
- [ ] Trace every caller of these wrappers to determine higher-level register/stack calling conventions and actual input types.
- [ ] Independently recover filesystem modes, pointer ownership, path normalization and output-buffer semantics before adopting final C prototypes.
- [ ] Harden the binary parsers' bounds checks against malformed PE files and add failure-mode tests.

### Phase B — reconstruct interfaces

- [x] Define the first portable C declarations for the observed 32-bit VM word/call representation.
- [x] Codify the verified SP game syscall prefix 0–19 without naming unverified IDs.
- [ ] Expand portable ABI declarations as additional syscall/export ranges are verified.
- [x] Define the first portable host-side filesystem/console command function-pointer contract (interface only, without guessed legacy ABI).
- [x] Implement validated 32-bit guest address resolution and a **read-only** VM→native host filesystem bridge for IDs 21/22/37.
- [ ] Verify `FS_GETFILELIST` list-buffer encoding and directory precedence against the original engine.
- [ ] Recover native caller-level data types and filesystem error semantics before implementing platform I/O.
- [x] Connect the functioning VFS to **native host** open/read/close callbacks, preserving host-width pointers.
- [x] Validate legacy x86 pointer/handle translation for **read-only** game FS syscalls 21/22/37 with synthetic host/file inputs.
- [ ] Extend beyond the read-only subset (seek, list, mode 1–3 writable save/config sandbox) only after verifying original behavior.
- [ ] Integrate this bridge with reconstructed game-module/engine dispatch logic; original x86 code is **not** executed by the bridge.
- [ ] Reconstruct the minimum filesystem/cvar/command/memory interfaces needed for module startup.
- [ ] Build a host-side test harness that can call reconstructed module interfaces without launching the full game.

### Phase C — data and boot path

- [ ] Deep-inventory required PK3 contents.
- [ ] Identify formats required before the first menu/map boot.
- [x] Build and test an independent, read-only PK3/loose-file loader; **does not yet reproduce original mount priority**.
- [x] Model the original engine's **one verified searchpath insertion routine** and fingerprint the exact original code region.
- [ ] Reconstruct PK3 search/load precedence (node creation, classification, language selection and all insertion paths) before integrating this isolated model into VFS.
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
