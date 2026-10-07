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

See [`analysis/initial_findings.md`](analysis/initial_findings.md) for the first binary-level findings and [`docs/ROADMAP.md`](docs/ROADMAP.md) for the implementation plan.

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

### PK3 inventory

Reads PK3/ZIP metadata without extracting the archive:

```bash
python tools/pk3_inventory.py originals/main/pak0.pk3 --json analysis/local/pak0.json
```

## Development rule

Analysis output must be reproducible. Do not rename guessed functions as facts: recovered names must record whether they are **observed**, **matched**, or **inferred**. This matters because the final native port will be built from reconstructed behavior rather than copied proprietary source.
