# callofrecomp

Clean-room static analysis and native recompilation research for the **PC release of Call of Duty 1.5** with an eventual **Android ARM64** target.

## Repository policy

The repository intentionally does **not** contain original Call of Duty executables, DLLs, PK3 archives, audio, textures, maps, videos, or other copyrighted game assets. Original files are treated as external inputs and are only used to produce reproducible metadata and compatibility findings.

Recommended local layout:

```text
originals/
├── CoDSP.exe
├── CoDMP.exe
├── gamex86.dll
├── cgamex86.dll
├── uix86.dll
└── main/
    └── *.pk3
```

`originals/` is ignored by Git.

## Current target

The first target is single-player Call of Duty 1.5. Multiplayer and United Offensive are deliberately out of scope until the base single-player path is understood and bootable.

Verified baseline from the supplied installation:

- `version.inf`: `ExtVersion=1.5`, `Platform=PC`, `Product=Call of Duty`.
- `CoDSP.exe`: PE32 / x86 executable.
- `gamex86.dll`, `cgamex86.dll`, `uix86.dll`: PE32 / x86 modules exporting `dllEntry` and `vmMain`.
- The engine contains OpenGL initialization/extension strings and loads several Windows-specific system/audio APIs.
- The native VM loader, VM call wrapper, and all three module-to-engine syscall dispatchers have now been located and mapped.

See [`PROGRESS.md`](PROGRESS.md) for the living project status, autonomy rules, blockers, and tool requirements.

Technical references: [`analysis/initial_findings.md`](analysis/initial_findings.md), [`analysis/vm_abi_findings.md`](analysis/vm_abi_findings.md), [`analysis/engine_vm_findings.md`](analysis/engine_vm_findings.md), [`analysis/game_syscall_findings.md`](analysis/game_syscall_findings.md), [`analysis/opengl_loader_findings.md`](analysis/opengl_loader_findings.md), and [`docs/ROADMAP.md`](docs/ROADMAP.md).

## Reproduce the verified baseline

For the exact supplied CoD 1.5 SP binaries, the preferred analysis entry point is now:

```bash
python tools/analyze_baseline.py --originals originals
```

The command first verifies all four SHA-256 fingerprints against `analysis/baselines/cod1_sp_pc_1_5.json`. It refuses to continue on a mismatched binary, then regenerates the PE, module-ABI, and engine-VM JSON reports under `analysis/local/`.

A small portable host scaffold is also available:

```bash
cmake -S . -B build
cmake --build build
ctest --test-dir build --output-on-failure
```

The current C layer contains only evidence-backed VM word/ABI definitions and the verified SP game syscall prefix; unverified syscall names are intentionally absent.

## Tools

### PE inspector

Dependency-free PE32 parser used to fingerprint the original binaries and recover sections, imports, exports, entry points and hashes.

```bash
python tools/pe_inspect.py \
  originals/CoDSP.exe \
  originals/gamex86.dll \
  originals/cgamex86.dll \
  originals/uix86.dll \
  --json analysis/local/pe_report.json
```

### Module ABI probe

Recovers the observed `dllEntry` callback slot, `vmMain` indexed dispatch table, and direct-immediate syscall IDs from the native single-player modules.

```bash
python tools/vm_abi_probe.py \
  originals/gamex86.dll \
  originals/cgamex86.dll \
  originals/uix86.dll \
  --json analysis/local/vm_abi.json
```

The syscall-ID pass is deliberately conservative: call sites that cannot be resolved with the supported patterns remain unresolved instead of being guessed.

### Engine VM probe

Maps both directions of the VM boundary inside `CoDSP.exe`: engine→module `VM_Call` command sites and module→engine syscall callback jump tables.

For the verified 1.5 baseline:

```bash
python tools/engine_vm_probe.py originals/CoDSP.exe \
  --vm-call-va 0x44f270 \
  --handle game=0x13f9db8 \
  --handle cgame=0x14bd620 \
  --handle ui=0x14bd648 \
  --callback game=0x44a2f0 \
  --callback cgame=0x401a50 \
  --callback ui=0x410b00 \
  --json analysis/local/engine_vm.json
```

### Engine syscall-handler edge inventory

Disassembles bounded jump-table handler cases using `objdump`, recording direct
`call` and `jmp` destinations as address evidence. This does **not** infer syscall names.

```bash
python tools/syscall_handler_edges.py originals/CoDSP.exe \
  --callback-va 0x0044A2F0 \
  --start-id 20 \
  --end-id 43 \
  --json analysis/local/game_syscall_edges_20_43.json
```

See [`analysis/game_syscall_edges_20_43.md`](analysis/game_syscall_edges_20_43.md).

### SP syscall ABI signature probe

For the verified 1.5 single-player baseline, this reads the numbered engine
dispatcher handlers and records **direct argument-slot references** and
**conservative EAX return shapes**, without guessing types or hidden arguments.

```bash
python tools/syscall_signature_probe.py originals/CoDSP.exe \
  --callback-va 0x0044A2F0 \
  --start-id 20 --end-id 43 \
  --json analysis/local/game_sp_abi_20_43.json
```

This phase documents seven independently matched syscall IDs while retaining
unknown identifiers for the others. See
[`analysis/sp_game_syscall_signatures_20_43.md`](analysis/sp_game_syscall_signatures_20_43.md).

### Recovered game module wrappers

For the exact supplied SP game DLL, this tool recovers the canonical wrapper
addresses and the **order of data words** passed from module registers/stack
through its engine syscall callback. It does *not* claim the higher-level C
calling convention is known.

```bash
python tools/module_wrapper_probe.py originals/gamex86.dll \
  --ids 21,22,23,36,37,40,41 \
  --require-sha256 27930aa3f663d0af39a90e6956c980be1e599e0f0c98191a9fb7eaba61481577 \
  --json analysis/local/game_wrapper_provenance.json
```

Alternatively, after verifying all four original binaries, generate that report
alongside the other baseline JSON files in one step:

```bash
python tools/analyze_baseline.py --originals originals --with-wrapper-provenance
```

The optional wrapper pass uses GNU `objdump`. Without the option,
`analyze_baseline.py` keeps its previous tool dependencies and output behavior.

For the seven analyzed syscalls, the callback receives 1–4 data words. ID 40
is especially important: its four origins are **caller stack word 0, EDX, ECX,
EAX**, not just the three registers. See
[`analysis/module_syscall_wrapper_provenance.md`](analysis/module_syscall_wrapper_provenance.md).

### Portable native host services

The new [`include/codrecomp/host_services.h`](include/codrecomp/host_services.h)
defines pointer-width-safe filesystem/console services for a future reconstructed
engine. It is a new host **contract, not yet a runtime implementation** or
a claim that native CoD 1.5 callers use the same C prototypes.

`tests/host_services_smoke.c` covers the interface and native pointer handling
through CTest on the existing CI workflow.

### Static-analysis regression tests

```bash
python -m unittest discover -s tests -p 'test_*.py' -v

# Optional: also validate the exact private PC 1.5 binaries locally
CODRECOMP_ORIGINALS=originals python -m unittest discover -s tests -p 'test_*.py' -v
```

The tests use synthetic PE fixtures in CI; proprietary game files are never
required or committed. The Python tests are also registered with CTest.

### PK3 inventory

Reads PK3/ZIP metadata without extracting the archive:

```bash
python tools/pk3_inventory.py originals/main/pak0.pk3 --json analysis/local/pak0.json
```

## Read-only virtual filesystem and PK3 support

The C++17 library `codrecomp_vfs` mounts loose-file directories and ZIP32/PK3
archives **without extracting proprietary game assets to disk**. It supports
ZIP stored/DEFLATE members (zlib), CRC-32 and size verification, case-insensitive
PK3 keys, bounded read sizes and unsafe-path rejection.

```bash
cmake -S . -B build -DCMAKE_BUILD_TYPE=Debug
cmake --build build --parallel
ctest --test-dir build --output-on-failure
```

The `codrecomp_vfs_smoke` test generates synthetic PK3 archives and needs no
original data. To additionally test with user-owned game archives:

```bash
./build/codrecomp_vfs_smoke /path/to/originals/main/pakb.pk3
./build/codrecomp_vfs_smoke /path/to/originals/main/localized_spanish_pak4.pk3
```

Both archives were mounted and their known sample members read successfully,
including CRC validation, using the original files supplied through Drive.

The C++ `ReadOnlyHostAdapter` exposes native host-width callbacks for
`fs_open`, `fs_read` and `fs_close`. The new
[`GuestMemory`](include/codrecomp/guest_memory.hpp) +
[`LegacyFsReadBridge`](include/codrecomp/legacy_fs_read_bridge.hpp) then
bridges **only three verified SP game syscall IDs** (21 open, 22 read,
37 close) using validated guest 32-bit addresses, permissions and handles.
It accepts original read mode **0**; write/append modes **1–3** are blocked.

The original `CoDSP.exe` has now been independently matched against
file-mode strings: `0=rb`, `1=wb`, `2=ab`, `3=ab` with an extra post-write
sync flag. Details: [FS mode and searchpath evidence](analysis/fs_modes_and_searchpath_evidence.md).

The bridge is exercised in the host-only `guest_vm_bridge_smoke` CTest.
All six current CTest targets passed in GitHub Actions. This is **not**
an x86 emulator or a playable Android port: reconstructed game-module
code is not yet connected, streaming/seek and writable saves are missing,
and the original engine's linked-list PK3 search ordering is only partly
understood. Our VFS's last-mounted-wins lookup is provisional.

See the [VM filesystem bridge contract](docs/LEGACY_FS_BRIDGE.md) and
[technical VFS analysis](analysis/filesystem_vfs_phase.md) for evidence,
limits and next steps.

### Observed searchpath insertion order (partial)

The portable `codrecomp_searchpath_order` library independently models one
verified searchpath insertion function from the original executable. It is
fingerprinted by `tools/searchpath_order_probe.py` and covered by CTest.
This **does not yet define full PK3 loading precedence**, so it is not wired
into the VFS until all node constructors and classification rules are mapped.
See [searchpath insertion evidence](analysis/searchpath_insertion.md).

### Sequential PK3 streaming

`Vfs::open_stream` reads loose files and PK3 ZIP store/DEFLATE members
through bounded 32 KiB refills rather than buffering entire resources.
`ReadOnlyHostAdapter` now holds these stream cursors for native opaque
handles. ZIP CRC/declared sizes are verified when the cursor reaches EOF;
a corrupted stream becomes permanently failed. `ReadStream::seek` now
supports begin/current/end offsets with bounded rewind/replay; it preserves
ZIP CRC integrity, but compressed-file backward seeks are O(file offset).
`ReadOnlyHostAdapter` exposes an optional **host-only** `fs_seek` callback;
no unverified original game syscall ID has been assigned.

Synthetic CTest coverage includes large incompressible ZIP data, partial
reads, invalid CRC and EOF; the implementation was also locally validated
against user-owned original PK3 archives. The guest bridge still validates
32-bit guest memory and copies from a staging buffer, and game asset data
remains outside Git.

### Startup searchpath discovery (partial)

`tools/searchpath_startup_probe.py` fingerprints an original CoD 1.5 SP
function which first calls an engine helper with zero-valued selectors and
then scans indices **13 down to 0** with another selector. This does not
establish complete PK3 mount priority or locale overlay behavior.
See [the startup scan evidence](analysis/searchpath_startup_scan.md).

## Development rule

Analysis output must be reproducible. Do not rename guessed functions as facts: recovered names must record whether they are **observed**, **matched**, or **inferred**. This matters because the final native port will be built from reconstructed behavior rather than copied proprietary source.
