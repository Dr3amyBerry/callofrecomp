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

Technical references: [`analysis/initial_findings.md`](analysis/initial_findings.md), [`analysis/vm_abi_findings.md`](analysis/vm_abi_findings.md), [`analysis/engine_vm_findings.md`](analysis/engine_vm_findings.md), and [`docs/ROADMAP.md`](docs/ROADMAP.md).

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

### PK3 inventory

Reads PK3/ZIP metadata without extracting the archive:

```bash
python tools/pk3_inventory.py originals/main/pak0.pk3 --json analysis/local/pak0.json
```

## Development rule

Analysis output must be reproducible. Do not rename guessed functions as facts: recovered names must record whether they are **observed**, **matched**, or **inferred**. This matters because the final native port will be built from reconstructed behavior rather than copied proprietary source.
