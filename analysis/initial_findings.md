# Initial static-analysis findings

## Installation identity

The supplied installation identifies itself as:

```text
ExtVersion=1.5
IntVersion=5.3
Platform=PC
Product=Call of Duty
```

The installation also contains United Offensive, but the current recompilation target is the base single-player game first.

## Binary fingerprints

| Binary | Size | SHA-256 | Image base | Entry RVA |
|---|---:|---|---:|---:|
| `CoDSP.exe` | 1,716,224 | `c755c7da411c87039ade462a2299402c3c4ca5c4fc4f1ae5cea6e25b05c69f47` | `0x00400000` | `0x0011DD4C` |
| `gamex86.dll` | 737,280 | `27930aa3f663d0af39a90e6956c980be1e599e0f0c98191a9fb7eaba61481577` | `0x20000000` | `0x00075E1B` |
| `cgamex86.dll` | 462,848 | `6e51c61f3780654cbaecdef149810ccf3ab665aaeafa5ae75a13f714abc0f29b` | `0x30000000` | `0x0003EBCB` |
| `uix86.dll` | 253,952 | `dd0738043c287a923357afe53bf2084fda8dd121ece20fcd57828bf5d8c68a4e` | `0x40000000` | `0x00019904` |

All four are PE32 i386 binaries.

## Engine imports observed in `CoDSP.exe`

Static PE imports currently include:

- `WINMM.dll`
- `mss32.dll` (Miles Sound System)
- `DDRAW.dll`
- `KERNEL32.dll`
- `USER32.dll`
- `GDI32.dll`
- `ADVAPI32.dll`
- `SHELL32.dll`

The executable contains extensive OpenGL initialization and extension strings, while `opengl32` is not present in the static import table. This strongly suggests the OpenGL library/procedures are resolved dynamically; the exact loader call chain still needs to be mapped before it is treated as confirmed architecture.

## Module ABI: first confirmed behavior

`gamex86.dll`, `cgamex86.dll`, and `uix86.dll` each export exactly two named functions:

- `dllEntry`
- `vmMain`

Static disassembly at each `dllEntry` export shows the same important pattern: the function receives a callback/function pointer and stores it in module-global state. Nearby wrappers call that stored pointer with a small integer command ID followed by arguments. This is the first confirmed engine-to-module syscall boundary.

Observed export addresses:

| Module | `dllEntry` RVA | `vmMain` RVA |
|---|---:|---:|
| `gamex86.dll` | `0x00042730` | `0x0001CD70` |
| `cgamex86.dll` | `0x00022540` | `0x00018CD0` |
| `uix86.dll` | `0x00017E80` | `0x000079A0` |

`vmMain` in all three modules dispatches on a numeric command. The next analysis task is to recover those command tables and map each target to a semantic operation with explicit confidence levels.

## Why this boundary matters for Android

The module ABI gives us a practical seam for the port. Instead of trying to translate the entire Windows executable in one pass, we can recover and validate the game/cgame/ui command interfaces first, then recreate the engine-facing host side in portable code. That reduces the amount of Win32 behavior that must survive into the ARM64 implementation.

## Next concrete work

1. Recover `vmMain` jump-table entries for the three modules.
2. Enumerate syscall wrapper IDs reached through the pointer installed by `dllEntry`.
3. Build a symbol ledger that records address, module, evidence and confidence.
4. Add deterministic disassembly/decompiler export tooling.
5. Inventory PK3 contents and group formats needed for the first boot path.
