# Project Progress

> Living project log for the Call of Duty 1.5 PC → Android ARM64 recompilation effort.
>
> **Rule:** this file must be updated whenever a meaningful phase starts, completes, changes direction, discovers a blocker, or requires a new external tool.

**Last updated:** 2026-10-12  
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

### Original menus and Android host checkpoint — 2026-10-12

- Current user priority is original menus and an Android build, tested through
  ADB on local WSA (`127.0.0.1:58526`, Android 13, ARM64 native-bridge support).
- Restored original cleanup callbacks `0x0047EEE0`, `0x0051A430`, `0x00532010`
  and `0x00532020`, each verified against original instructions/registration
  sites. The private export now contains 333,208 instructions. Actual desktop
  startup parses the original menus, completes common initialization and exits
  normally with `+quit` (exit 0); previously it failed during cleanup.
- Added thread-safe queued input for normalized menu touches, scancodes, buttons
  and relative look. A 400-event burst reproduced dropped releases; pumping
  now pauses before the Win32 message queue fills, preserving later events.
  All 12 CTests pass, including the new touch and overflow regressions.
- Android SDL2/GL4ES integration and all four modules now compile to a private
  ARM64 debug APK (about 51 MiB), with verified v2/v3 signature and 16-KiB
  ELF/ZIP alignment. The reproducible SDK builder also supports native x86-64 WSA.
- Real WSA launcher and SAF import succeed; SHA-256 validation accepts the owned
  baseline and rejects other binaries. Spanish localization is selected from
  imported packs. Profiles/logs use separate internal storage, preserving saves.
- ARM64 under WSA's Houdini 14 bridge completes common initialization and parses
  original menus, but a first frame/gameplay is still unverified. An isolated
  SDL inline-atomic experiment did not resolve it and was removed. An optimized
  native x86-64 comparison is being built; do not treat packaging as playability.

### PC mission checkpoint — 2026-10-12

- Current user priority: first mission playable on PC, then Android.
- Added real MP3 stream decoding through original engine filesystem callbacks,
  with owned compressed bytes, fixed decoded blocks, seek, pause and loop states.
  Decoder source is pinned CC0 minimp3; original assets remain outside Git.
  Vendored decoder files retain LF endings so recorded hashes survive Windows
  checkouts with automatic line-ending conversion.
- All 12 CTest checks pass, including synthetic MP3 streams with short reads.
- Actual `+spmap training` finishes `CL_InitCGame` and visibly shows the original
  Spanish briefing with “Haz clic para iniciar la misión”. Screenshot and run log
  are private artifacts under `recomp_out`; the process stays active beyond 45s.
- First-person scene, movement and sustained gameplay are not verified yet.
  This checkpoint does not complete the playable-mission goal.
- A queued fast-click regression reproduced lost button transitions (exit 7).
  Mouse state now follows each SDL event; the regression and all 12 CTests pass.
- Added a separate optional timed SDL integration probe. Its actual briefing
  click reached missing entry `0x004DD6E0`. Original instructions verify its
  assignment at `0x004F101A` to slot `0x011D92E4`; the entry is now included in
  the reproducible export ledger. Gameplay verification is continuing.
- The rebuilt probe passes `0x004DD6E0` and next reaches a missing GL setup
  switch branch, `0x004DBD61`. All four destinations from the original bounded
  jump table at `0x004DC180` are verified and added to the export ledger.
- An actual branch to `0x004DC14B` exposed overlapping Ghidra code units.
  Explicit code-entry export now requires an instruction starting exactly at the
  verified address and retries the independently decoded instruction span when
  necessary, then revalidates all explicit entries before writing the output.
  Original `JE` at `0x004DC13E` verifies that destination; successful export now
  contains 333,204 engine instructions. No sweeping of arbitrary bytes is enabled.
- The actual probe now enters the visible first-person training scene, with
  soldiers, terrain and HUD, and remains active after timed W down/up input.
  Original Foley speech exposed PCM WAV streams (mono, 22,050 Hz); these now use
  real SDL decoding and owned PCM. WAV stream test reproduced failure (exit 44)
  and now passes with all 12 tests. The rebuilt `pathfinder` campaign probe
  finishes `CL_InitCGame` (18.37s) but crashes at `0x0052E84C`, accessing
  `0xEF7AF00C`, before the timed click. That memory access is the next blocker;
  campaign movement and sustained gameplay remain unverified.
- The exact-entry exporter was exercised against a deliberately conflicting byte
  inside a known five-byte MOV in a read-only Ghidra session. It recovered the
  entry and exported the same 333,204 instructions without saving project changes.
- Located the campaign crash: TIB and CPUID scratch overlapped the declared 4-MiB
  stack. A large original game frame overwrote the SEH pointer. Both service pages
  now live below the stack; a regression checks disjoint ranges and fills the
  entire stack while preserving TIB/CPUID (RED exit 26, GREEN 12/12 CTest).
- The rebuilt `pathfinder` probe starts the mission, creates the original save
  and queues movement. The user confirms this is mission 1 and controls work,
  and clarifies that reload is smooth while aiming with the initial weapon
  stutters. ADS interpolation is now the active investigation.
  Closing the game also exposes missing shutdown entry `0x0047EEE0`.
- Added optional frame statistics and timed fire/reload/aim input. The first
  campaign sample rendered around 64 FPS after entry, but an existing-autosave
  operation produced the original “insufficient disk space” error despite ample
  host free space. Save finalization needs investigation before that pacing sample
  can cover the full weapon sequence.
- Located the repeated-autosave failure: MoveFileA returned failure without
  setting GetLastError, so the original CRT reported rename success and skipped
  the engine's delete-and-retry path. File moves now reject an existing target on
  every host and report Win32 errors; DeleteFileA also reports failure errors.
  Synthetic replacement regression failed with exit 9 before the fix and all
  12 CTests pass after it. The original campaign probe now replaces the existing
  autosave successfully and continues rendering. A private GL framebuffer capture
  confirms the first-person campaign scene; original assets remain ignored.
- Reproduced the isolated ADS stutter: 6 distinct aim fractions in 34 rendered
  transition frames, held between roughly 50-ms server updates. Per-call fake
  clocks made CPU calibration report 0.0625 MHz and select a no-prediction profile.
  Real mode now uses monotonic time and native x86 RDTSC; deterministic trace
  mode remains unchanged. The original engine measures 3.59 GHz, selects its
  2000-MHz profile and keeps cg_nopredict at its registered default 0. The repeat
  probe records 26 distinct fractions in 26 transition frames. Clock regression
  failed before the change (exit 17); all 12 CTests now pass. Existing profiles
  require restoring cg_nopredict 0; visual user confirmation is pending.

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

## Bounded-memory sequential VFS streaming checkpoint (2026-10-07 UTC)

- Added `Vfs::open_stream` with persistent `ReadStream` cursors for loose files, ZIP-stored members and raw-DEFLATE PK3 members. Input is refilled in fixed **32 KiB** blocks instead of allocating the complete uncompressed member.
- The existing `Vfs::read_file` API remains unchanged for compatibility. The new stream validates ZIP headers/names, bounds and CRC/declared lengths upon reaching EOF; failed integrity checks remain latched for the lifetime of the cursor.
- Updated `ReadOnlyHostAdapter` to retain one streaming cursor per opaque handle instead of an entire decompressed file. The guest VM bridge continues to stage requested bytes atomically before copying them into guest memory.
- Synthetic tests cover partial reads, EOF, empty files, loose files, CRC failures and >150 KiB DEFLATE data spanning multiple input/output refills. The optional original-PK3 test now compares streamed bytes **byte-for-byte** against the previously verified eager reader for a multiplayer menu and a Spanish localized menu. Local AddressSanitizer/UndefinedBehaviorSanitizer checks of the synthetic VFS suite passed. 
- **Limitations:** seeking is not yet implemented; ZIP CRC cannot be known until the stream is fully consumed. Loose-file opens remain vulnerable to a path-replacement race between path canonicalization and opening on filesystems modified concurrently; Android sandbox hardening is still needed. The VFS searchpath order remains provisional.
- No original binaries or archives are included in commits.

## Stream seek + host callback checkpoint (2026-10-07 UTC)

- Added `ReadStream::seek(delta, origin)` using begin/current/end origins with overflow-safe signed offset calculations and strict file bounds. Nonzero negative deltas and `INT64_MIN` are handled without signed overflow.
- For DEFLATE streams, a backward seek resets the inflater and replays through bounded 32 KiB buffers from the beginning; forward seeks discard through `read` so CRC coverage remains correct. The same bounded replay strategy validates ZIP-stored members. This is **correctness-first**, not fast random access.
- Added host-only optional `fs_seek` to `cod_host_services_t`, implemented for `ReadOnlyHostAdapter` with verified native handles. Host origin values 0/1/2 **are new adapter conventions**, not CoD syscall IDs. The 32-bit legacy bridge deliberately does not expose an unverified seek syscall.
- Synthetic tests cover backward/forward/end-relative seeks, bad ranges, large DEFLATE refills, CRC sticky errors and host EOF recovery. The VFS is still read-only; full mount precedence and locale classification are **not yet reconstructed**.
- **Next:** inspect original startup/locale searchpath node constructors; reduce remaining filesystem compatibility gaps and optimize seek when evidence permits.

## Startup indexed searchpath discovery checkpoint (2026-10-07 UTC)

- Fingerprinted the exact original `CoDSP.exe` function at `0x004250E0`. Its first call invokes helper `0x00424E10` with two zero immediate inputs. A subsequent loop invokes the same helper with selector `1` and index values `13` down to `0` (14 calls).
- Added `tools/searchpath_startup_probe.py`, synthetic unit tests and [analysis/searchpath_startup_scan.md](analysis/searchpath_startup_scan.md), preserving the uncertainty around register arguments and the meaning of package/language flags.
- This is **not the full PK3/locale search-order mapping**; node creation and classification are still under investigation, and the provisional VFS search priority is unchanged.
- **Verification:** GitHub Actions workflow `37564560085` completed successfully with all **7/7 CTest targets passing**, including the new seek fixtures and startup scan unit tests. Latest test evidence: https://github.com/Dr3amyBerry/callofrecomp/actions/runs/37564560085.
- **Open risk:** stream seeking is O(target offset) for compressed ZIP entries because it replays DEFLATE to preserve CRC; this is safe but may be costly for large map resources. No seek syscall is yet mapped into the original 32-bit VM bridge.

## Localization table and source-node identification checkpoint (2026-10-07 UTC)

- Decoded all **14** language-table entries at `CoDSP.exe` VA `0x00564B08` (English/French/German/Italian/**Spanish index 4**/British/Russian/Polish/Korean/Taiwanese/Japanese/Chinese/Thai/Leet).
- Independently established the original 20-byte searchpath-node fields: `+0` next, `+4` PK3 object pointer, `+8` directory pointer, `+0x0C` **localized flag**, `+0x10` language index. Verified through five SHA-pinned original instruction ranges and localization diagnostics.
- Matched the list-insertion model's previously unknown `class_flag` to the localized boolean without renaming/breaking the existing API. Added a focused mixed-entry regression test.
- Verified the supplied `main/` inventory includes **six localized Spanish PK3s** (`localized_spanish_pak0..5`) and **eleven plain pak* archives**. Two inspected sample PK3s have Spanish/plain menu variants, but this does not prove actual active-language selection.
- Added `tools/searchpath_localization_probe.py` to export table, prefixes, node offsets, evidence fingerprints and filename **candidates**, plus **six unit tests** (one optional real-input test). All six passed locally using the exact original executable; tests without originals skip the exact-input check.
- **Remaining unknowns:** language activation and filters, PK3 discovery order, `sp_`/`mp_`/`zz_` filename handling and directory-vs-PK3 collision behavior. The VFS mount ordering remains unchanged pending full verification.
- **No new external dependencies** for this analysis.

See [`analysis/localization_searchpath.md`](analysis/localization_searchpath.md).

## Active-language searchpath filter checkpoint (2026-10-07 UTC)

- Recovered **two distinct runtime lookup branches** that consult the verified `node+0x0C` localized flag, a global rejection check from `(*0x014DBA84)+0x20`, and the current-language index from `(*0x014BD624)+0x20` versus `node+0x10`. Both instruction windows are SHA-256 fingerprinted in the localization probe.
- Added an evidence-based `SearchpathOrder::eligible(active_language_index, reject_localized)` filter, maintaining the original insertion order and preserving the existing `class_flag` API. Added C++ tests with Spanish, English and nonlocalized nodes, plus a test for rejecting all localized nodes.
- Verified Python probe tests against the original executable and tested C++ filtering locally with strict compiler warnings. The node ordering/filter model remains **independent from the VFS** until complete startup order and global initialization semantics are known.
- **Verification:** CMake compiled successfully and GitHub Actions completed **8/8 CTest targets** on commit `b064dbd`: https://github.com/Dr3amyBerry/callofrecomp/actions/runs/37565673848. The independent Python suite also passed 6/6 locally against the supplied original executable, and the C++ filter passed a strict local `-Wall -Wextra -Werror` build.
- **Next:** identify creators and update paths for both global settings, all path-discovery/PK3-level precedence and the exact search behaviors for unmatched language resources. No Android runtime yet.

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
- [x] Recover searchpath node type/classification and the 14-language lookup table (including Spanish index 4).
- [x] Recover the observed per-node language acceptance checks in two filesystem lookup branches; independent model and tests added.
- [ ] Recover initialization/updates of language and rejection globals, the complete startup discovery sequence and only then integrate it with the VFS.
- [x] Implement bounded-memory sequential reads of loose files, ZIP-stored and raw-DEFLATE PK3 members, with end-of-stream integrity checks.
- [x] Implement bounded seek (replay-based, CRC-preserving) through VFS streams and host handles.
- [ ] Precise original error mapping; keep original mount selection unresolved.
- [ ] Reconstruct configuration and localization loading.
- [ ] Trace single-player startup from process entry to first rendered frame.

### Phase R — static recompilation of modules (hybrid plan, approved 2026-10-12)

Current direction: recompile `CoDSP.exe` and the three SP module DLLs automatically
(Ghidra p-code → C), retaining the original engine's resource parsers, renderer
and module/syscall paths. The earlier ioquake3 proposal is superseded by this
working original-engine pipeline.

- [x] Ghidra p-code exporter and `pcode2c.py` generator; zero unsupported ops across ui/cgame/game.
- [x] Recompiled `uix86.dll` matches the real DLL's 10,856-syscall init trace (DllMain + 5 vmMain calls).
- [x] Recompiled `cgamex86.dll` / `gamex86.dll` match the real DLLs up to the same harness-induced crash.
- [x] Build the generated C for Android ARM64 (NDK r30) and rerun the trace check on a real device: identical.
- [ ] Richer fake engine so game/cgame run past init; then wire real engine syscalls.
- [x] Recompile the original engine and start it through CRT/WinMain.
- [x] Replace window/context creation, GL entry-point loading and basic input with SDL2 shims.
- [x] Load the original PK3 search path and finish original renderer initialization on desktop.
- [ ] Replace the Miles audio boundary and reach the menu through the real engine.
- [ ] Exercise campaign map loading and sustained gameplay.

See [`analysis/static_recompilation_prototype.md`](analysis/static_recompilation_prototype.md).

### Desktop renderer checkpoint — 2026-10-12

- Resumed Claude's uncommitted SDL/OpenGL work and repaired its interrupted string literal.
- The pinned `CoDSP.exe` hash remains `c755c7da411c87039ade462a2299402c3c4ca5c4fc4f1ae5cea6e25b05c69f47`.
- Fixed `GetFileType`: real open files now report `FILE_TYPE_DISK`, allowing the guest CRT to read PK3s.
- Runtime reports **30,283 files in PK3 files**, executes `default.cfg` and initializes the original renderer on an AMD desktop compatibility context.
- Bounded GL extension reporting preserves supported S3TC; omitting it falsely rejected the GPU, while forwarding the unbounded driver string exposed the legacy engine's buffer limit.
- Native pointer outputs from GL are translated back to 32-bit guest pointers; external host pointers fail explicitly.
- Added a reproducible desktop builder and synthetic CTest regressions for the file/GL boundaries. Local CMake build and **10/10 CTest tests passed**.
- Current engine execution reaches `----- finished R_Init -----`, then stops at missing `mss32.dll!_AIL_set_file_callbacks@16`. **Menu, map loading, audio and Android renderer execution are not verified.**
- ADB currently lists no connected devices. Desktop work can continue; device validation requires a device when the Android host is ready.

### Audio and callback recovery checkpoint — 2026-10-12

- User clarified the immediate objective: **first mission playable on PC**, before Android gameplay validation.
- Added a portable Miles-import boundary backed by SDL audio: owned PCM buffers, WAV decoding, conversion, volume/pan/rate, looping and playback state. The audio callback never executes guest code.
- Real-engine run `recomp_out/engine_audio4.log` opens **44,100 Hz stereo float**, initializes 32 positional channels and parses every UI menu through `ui/pregame.menu`.
- Extended p-code export to discover indirect callbacks stored in initialized non-executable data. UI export now contains **40,507 instructions**; the engine contains **331,853** after explicit recovery of a verified code entry mislabeled as data.
- Missing UI callback `0x40016DB0` was verified against original instructions and recovered. The subsequent engine blocker `0x00518050` is an original `RET` stored as a callback by `0x00518073`; exported with `--code-entry 0x00518050`.
- Rebuilt and ran the engine again: it passes that recovered callback and stops at another missing entry, `0x0050B990` (`recomp_out/engine_audio5.log`). Recover remaining indirect entries before claiming menu completion.
- Confirmed `0x0050B990` is another original `RET`, installed at `0x0050B9EE`, and explicitly recovered it; export contains **331,854 instructions**. Reproducible arguments and assignment sites are recorded in [`analysis/recomp_verified_code_entries.json`](analysis/recomp_verified_code_entries.json).
- An unoptimized diagnostic build timed out after 40 seconds at `FS_Startup`; this does not verify the second callback at runtime. Restore optimized objects and rerun before advancing the checkpoint. The original menu uses `spmap training` and `spmap pathfinder` for the intended PC gameplay checks.
- UI traces still have **10,867 lines** in both runs. The generic comparator reports three differences in surplus logged argument words (IDs 51/26/8), so its strict exit status is not a clean comparison; do not report that command as passing.
- Review found and tests reproduced audio ABI/state bugs (x87 float return, 8-bit offsets, stale-buffer replay) plus invalid metadata acceptance. Fixed them before commit; **11/11 CTest tests pass** including WAV decoding and malformed metadata rejection.
- Music MP3 streams, double-buffer loading, positional attenuation/effects and full menu/map gameplay remain unfinished. Device startup is not proof of audible sound or a visible menu.
- Public source changes remain separate from ignored generated C, binaries, traces and original assets. See [`docs/AUDIO_BRIDGE.md`](docs/AUDIO_BRIDGE.md).

### Cinematic audio and first PC map attempt — 2026-10-12

- Optimized engine with both recovered RET callbacks reaches **Common Initialization Complete** (`recomp_out/engine_audio7.log`). The next missing import was `AIL_minimum_sample_buffer_size` for cinematic audio.
- Added a native x86 Miles probe using silent PCM and the supplied original DLL. Measured automatic buffer startup, one-time reservation of free slots, alternating consumption and per-buffer byte positions; no proprietary code or audio is committed.
- Implemented two owned PCM buffers, minimum buffer sizing, free/reserved/queued states, refill after underrun and EOF. Added regressions for ownership, alternation, position reset, end/EOF and invalid-buffer reservation recovery. **11/11 CTest tests pass.**
- The engine stays active through a 40-second observation after common initialization (`recomp_out/engine_buffers1.log`). This does **not** prove visible rendering, video completion or gameplay.
- Direct `+set com_introplayed 1 +spmap training` exercises a resource/UI restart and then reaches missing original code `0x0045AA90` (`recomp_out/engine_training1.log`). Its assignment at `0x0045A6ED` is confirmed by binary disassembly; explicitly exported it, bringing engine coverage to **332,034 instructions**. Optimized compilation is in progress; map completion remains unverified.
- Optimized rerun passes that entry and now stops at **guest heap exhausted (4096 bytes)** (`recomp_out/engine_training2.log`). The runtime has a 256 MiB bump arena, no-op HeapFree/VirtualFree, and VirtualAlloc shares that arena. Correct allocation/release semantics are the next concrete task; no playable-map claim is made.
- The first campaign route remains the original `spmap pathfinder`; training is the preliminary map-loading check. MP3 streaming, spatial audio and sustained input/rendering validation remain required.

### Memory lifecycle checkpoint — 2026-10-12

- Reproduced the old no-op HeapFree behavior with a synthetic thunk test (exit 2 before the fix).
- Replaced monotonic-only heap allocation with tracked live blocks and coalescing free spans, including HeapFree, HeapSize and failure-preserving HeapReAlloc.
- Separated VirtualAlloc reservations from the 256 MiB CRT heap. Added page commit/decommit, exact-base release and region reuse; reservation metadata remains host-owned.
- Review exposed an inclusive-end lookup bug between adjacent reservations; regression failed at exit 17, then passed after excluding the end address. **12/12 CTest tests pass**, including heap reuse/coalescing, reserve/commit lifecycle and overflow checks.
- Original `+set com_introplayed 1 +spmap training` now passes heap exhaustion and stops at **RaiseException(c000008f)**, called by the original CRT at return address `0x00524BE3` (`recomp_out/engine_training4.log`). Next: investigate guest floating-point state and the CRT exception path. Do not suppress the exception without evidence.
- Scope and remaining memory limitations are recorded in [`docs/RECOMP_MEMORY.md`](docs/RECOMP_MEMORY.md). Playable training/campaign, visible rendering, MP3 and sustained input remain unverified.

### x87 startup checkpoint — 2026-10-12

- Located the original CRT exception call at `0x00524BDD` (return `0x00524BE3`). Its control-word updates depend on the initial x87 exception masks.
- Verified Ghidra x86 `ia.sinc`: FPUControlWord/StatusWord/TagWord are at register offsets `0x10A0/0x10A2/0x10A4`; FINIT defines control `0x037F`, status zero and tag `0xFFFF`. Runtime previously left all three zero.
- A regression reproduced the invalid initial state (exit 25). Initialized these registers before engine entry; **12/12 CTest tests pass**.
- The original training run now passes the CRT exception, starts **Server: training**, restarts resources/UI and reaches missing **gamex86.dll callback `0x20035480`** (`recomp_out/engine_training5.log`). Verified original instructions at that address; expanding game-module callback coverage next. This is server initialization, not verified map completion or gameplay.

### Original training resource loading checkpoint — 2026-10-12

- Expanded game-module data-held callback coverage: **188 candidates disassembled**, **144,114 instructions**, zero unsupported p-code operations. Explicit callback `0x20035480` is referenced by original data slot `0x200A4DE8`; hash and reproduction arguments are in [`analysis/recomp_verified_game_entries.json`](analysis/recomp_verified_game_entries.json).
- Expanded client-module coverage before its deeper map path: **154 candidates disassembled**, **81,941 instructions**, zero unsupported operations. Both regenerated private modules compile with Clang `-O1` and link with the actual engine.
- Original `spmap training` now runs past the game callback and loads **surfaces, cull groups, visibility, models/entities and lights**, merges lightmaps and initializes the effects system (`recomp_out/engine_training6.log`). This is materially deeper than boot/UI parsing.
- The next concrete blocker is **mss32.dll!AIL_open_stream**, called from original sound playback at return address `0x00442D9F`. Implement original filesystem-callback access and compressed audio streaming next; no dummy success or audio suppression.
- Local repository checks remain **12/12 CTest passing**; CI for memory and x87 commits succeeded. Rendered map, movement/input, sustained gameplay and the campaign `pathfinder` map remain unverified. The first mission goal is still active.

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
- available on the local Windows workstation (2026-10-11): Ghidra 12.1.4 headless (`tools/ghidra_decompile.sh`), JDK 21, Android SDK + `adb`
- Android NDK r30 installed (2026-10-12); an arm64-v8a device is reachable over adb
- not currently available: radare2/rizin, GNU binutils on Windows (tools fall back to `llvm-objdump`)

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
| Ghidra headless | scalable decompilation, p-code, xrefs, function recovery | **installed**; full SP decompilation is exported to ignored `decomp/` |
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
