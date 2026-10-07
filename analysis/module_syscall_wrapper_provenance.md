# SP game syscall wrapper provenance (IDs 21, 22, 23, 36, 37, 40, 41)

## Input and evidence

This analysis uses the exact supplied Call of Duty **PC 1.5 single-player** `gamex86.dll` (SHA-256 `27930aa3f663d0af39a90e6956c980be1e599e0f0c98191a9fb7eaba61481577`).

- Image base: `0x20000000`.
- `dllEntry`: `0x20042730`.
- Engine callback pointer is stored in the module global at `0x200A4834`.
- The game module has a compact cluster of native syscall wrappers just after `dllEntry`.
- `tools/module_wrapper_probe.py` finds their immediate syscall IDs, decodes their instructions using `objdump`, and symbolically tracks a deliberately limited selection of `push` and `mov` operations. Unsupported instruction forms fail closed.

## Recovered callback arguments

Each line gives **the order of words presented to the engine callback AFTER the syscall ID**, not the order in which a C caller supplies parameters.

| ID | Working syscall name | Canonical wrapper VA | Callback argument origins |
|---:|---|---:|---|
| 21 | `G_FS_FOPEN_FILE` | `0x20042840` | `EDX, ECX, EAX` |
| 22 | `G_FS_READ` | `0x20042850` | `EDX, ECX, EAX` |
| 23 | `G_FS_WRITE` | `0x20042860` | `EDX, ECX, EAX` |
| 36 | `G_FS_RENAME` | `0x20042940` | `ECX, EAX` |
| 37 | `G_FS_FCLOSE_FILE` | `0x20042950` | `EAX` |
| 40 | `G_FS_GETFILELIST` | `0x20042980` | `stack_arg_0, EDX, ECX, EAX` |
| 41 | `G_SEND_CONSOLE_COMMAND` | `0x200429A0` | `ECX, EAX` |

Example: the native wrapper for ID 21 executes `push eax; push ecx; push edx; push 0x15; call [0x200A4834]`. Because x86 push order reverses the arguments at the callback, its data words are `EDX, ECX, EAX`.

**ID 40 matters especially:** `push eax; mov eax, [esp+0x8]; push ecx; push edx; push eax; push 0x28` preserves the initial EAX as the *fourth* data word, and loads its *first* data word from the caller's first stack argument. Treating the wrapper as a simple three-register call would silently lose a parameter. The engine case for ID 40 independently references four syscall argument words and forwards them to the list-files helper.

## Limits of confidence

The mapping above is **observed wrapper data flow**, **not** a recovered higher-level C calling convention. The actual meaning and ownership of pointer-shaped values still require caller and callee analysis. Other callsites may invoke the callback directly. The binary's mode and error conventions are not yet fully known.

A new portable header, `include/codrecomp/host_services.h`, defines native-pointer-width host service contracts for future reconstructed filesystem and console-command implementations. These are **new porting interfaces**, not claimed recovered original prototypes. Any eventual adapter from 32-bit legacy VM words must validate/resolve pointers and handles rather than truncating Android ARM64 pointers.

## Reproduction

Use an original DLL in the ignored `originals/` folder:

```bash
python tools/module_wrapper_probe.py originals/gamex86.dll \
  --ids 21,22,23,36,37,40,41 \
  --require-sha256 27930aa3f663d0af39a90e6956c980be1e599e0f0c98191a9fb7eaba61481577 \
  --json analysis/local/sp_game_wrappers_21_41.json
```

The tool does not modify or upload the DLL. Synthetic regression tests are in `tests/test_module_wrapper_probe.py`; an additional exact-binary test runs only when `CODRECOMP_ORIGINALS` is set.

## Follow-up

1. Trace callers and callees to determine actual pointer, handle and mode semantics.
2. Recover filesystem search precedence, safe path handling and file-list encoding.
3. Implement and validate a 64-bit-safe VM-to-host adapter.
4. Expand wrapper analysis to other IDs without assigning unknown C names prematurely.
