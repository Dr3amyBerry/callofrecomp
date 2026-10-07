# Engine VM boundary findings

This document records the first end-to-end map of the native module boundary inside the supplied `CoDSP.exe` 1.5 baseline.

Evidence level in this file is **observed** unless a section explicitly says otherwise.

## Core engine VM functions

| Item | VA | RVA | Notes |
|---|---:|---:|---|
| VM loader / native module creation | `0x0044F0E0` | `0x0004F0E0` | Builds/loads `%sx86.dll`, resolves `dllEntry` and `vmMain`, and invokes `dllEntry` with the engine syscall callback. |
| VM call wrapper | `0x0044F270` | `0x0004F270` | Calls the loaded module's function pointer at VM-object offset `0x48`, forwarding command + argument slots. |

The loader is anchored by the observed strings `%sx86.dll`, `dllEntry`, and `vmMain` in the engine binary.

## Registered native modules

| Module | engine VM-handle slot | module→engine callback | creation site |
|---|---:|---:|---:|
| `game` | `0x013F9DB8` | `0x0044A2F0` | `0x0044B7F0` region |
| `cgame` | `0x014BD620` | `0x00401A50` | `0x004046D8` region |
| `ui` | `0x014BD648` | `0x00410B00` | `0x004114D0` region |

The module name strings are supplied to the same VM creation path, and each returned VM object is stored in the corresponding global slot.

## Engine → module command calls

A first direct-call scan of `VM_Call` recovered the following immediate command coverage.

| Module | classified VM_Call sites | distinct immediate command IDs recovered | IDs currently observed |
|---|---:|---:|---|
| `game` | 43 | 19 | `0,1,2,5,8,10,11,13,14,15,16,17,18,19,20,21,22,23,24` |
| `cgame` | 33 | 23 | `1,2,3,5,6,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25` |
| `ui` | 37 | 13 | `0,1,2,3,4,5,6,7,8,9,10,12,13` |

Not seeing an ID in this table does **not** prove that the engine never invokes it. Some call sites keep the VM handle or command in a register or flow through patterns not yet covered by the narrow scanner.

## Module → engine syscall dispatchers

The callbacks passed through each module's `dllEntry` are themselves indexed command dispatchers.

| Module | callback VA | max syscall ID | table entries | unique targets | jump-table VA |
|---|---:|---:|---:|---:|---:|
| `game` | `0x0044A2F0` | 211 | 212 | 174 | `0x0044B310` |
| `cgame` | `0x00401A50` | 252 | 253 | 244 | `0x00403E10` |
| `ui` | `0x00410B00` | 84 | 85 | 85 | `0x004112A8` |

This closes the loop around the ABI:

```text
CoDSP.exe
   │
   ├── VM_Create(name, syscallCallback)
   │       │
   │       └── native module dllEntry(syscallCallback)
   │
   ├── VM_Call(vm, exportCommand, ...)
   │       │
   │       └── module vmMain(exportCommand, ...)
   │
   └── syscallCallback([syscallId, ...])
           │
           └── indexed engine-side syscall dispatcher
```

## UI export alignment

The first UI export IDs have a strong structural match to the public Return to Castle Wolfenstein SP UI ABI, which is an id Tech 3-family reference and is used here only as a comparison source.

Reference:
`https://github.com/id-Software/RTCW-SP/blob/70951bc71b730efe6bcb07db7ae76ef0c4ae7c14/src/ui/ui_public.h`

The supplied CoD UI module and engine provide independent evidence for the following mapping:

| ID | Working symbol | Evidence |
|---:|---|---|
| 0 | `UI_GETAPIVERSION` | **matched** — module returns constant `6`; engine calls command 0 and checks result against 6. |
| 1 | `UI_INIT` | **matched** — engine invokes command 1 immediately after API validation; signature/control flow aligns with reference ordering. |
| 2 | `UI_SHUTDOWN` | **matched** — engine invokes command 2 during UI teardown before unloading the VM. |
| 3 | `UI_KEY_EVENT` | **matched** — module dispatch target consumes two arguments; ordering aligns with the inherited UI ABI. |
| 4 | `UI_MOUSE_EVENT` | **matched** — module dispatch target consumes two arguments; ordering aligns with the inherited UI ABI. |
| 5 | `UI_REFRESH` | **matched** — module dispatch target consumes one argument and engine calls it from UI refresh paths. |
| 6 | `UI_IS_FULLSCREEN` | **matched** — zero-argument dispatch path returns a value. |
| 7 | `UI_SET_ACTIVE_MENU` | **matched** — one-argument command heavily used by engine menu transitions. |
| 8 | `UI_GET_ACTIVE_MENU` | **matched** — zero-argument path returns a stored UI state value. |
| 9 | `UI_CONSOLE_COMMAND` | **matched** — engine calls command 9 from console-command fallback handling and tests the return value. |
| 10 | `UI_DRAW_CONNECT_SCREEN` | **matched** — engine passes one overlay/state argument from screen drawing paths. |

The alignment is intentionally stopped at ID 10. CoD 1.5 has additional UI exports and its ID 11 behavior does not simply mirror the RTCW SP `UI_HASUNIQUECDKEY` implementation, so IDs 11–13 remain unlabelled until independently recovered.

## Immediate next analysis

1. Recover command-call sites missed by the current direct-pattern scanner.
2. Attach argument-shape metadata to every engine→module command.
3. Group engine-side syscall targets by shared implementation and argument shape.
4. Start assigning syscall names only where strings, engine call targets, or a public reference provide independent support.
5. Use the now-confirmed VM loader to trace the single-player startup sequence in order.
