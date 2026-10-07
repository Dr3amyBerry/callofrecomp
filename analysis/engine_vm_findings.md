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

The SP UI export table was rechecked directly against `uix86.dll` after a Call of Duty-specific public reconstruction became available. This corrected an earlier RTCW-only assumption for IDs 9 and 10.

References used only as comparison sources:

- RTCW SP UI ABI:
  `https://github.com/id-Software/RTCW-SP/blob/70951bc71b730efe6bcb07db7ae76ef0c4ae7c14/src/ui/ui_public.h`
- OpenCoD1 multiplayer reconstruction:
  `https://github.com/opencod1/opencod1/blob/718e994af62ca2cbc79d911bab73c445637b94e7/src/ui_mp/ui_public.h`

The supplied SP binary provides the deciding evidence:

| ID | Working symbol | Evidence |
|---:|---|---|
| 0 | `UI_GETAPIVERSION` | **matched** — module returns constant `6`; engine validates command 0 against 6. |
| 1 | `UI_INIT` | **matched** — engine invokes command 1 immediately after API validation. |
| 2 | `UI_SHUTDOWN` | **matched** — engine invokes command 2 during UI teardown before unloading the VM; the SP module implementation is effectively empty. |
| 3 | `UI_KEY_EVENT` | **matched** — dispatch target consumes two arguments and matches the inherited input slot. |
| 4 | `UI_MOUSE_EVENT` | **matched** — dispatch target consumes two arguments and matches the inherited input slot. |
| 5 | `UI_REFRESH` | **matched** — one-argument dispatch and engine refresh call sites. |
| 6 | `UI_IS_FULLSCREEN` | **matched** — zero-argument boolean query over active menu state. |
| 7 | `UI_SET_ACTIVE_MENU` | **matched** — one-argument command heavily used by engine menu transitions. |
| 8 | `UI_GET_ACTIVE_MENU` | **matched** — returns the stored active-menu value. |
| 9 | unknown SP UI boolean query | **observed** — zero-argument boolean query over menu state; the engine tests the result in an input/menu path. It is deliberately not named yet. |
| 10 | `UI_CONSOLE_COMMAND` | **matched** — engine passes its realtime value; the target obtains command arguments and recognizes UI console commands including `ui_test`, `ui_report`, `ui_load`, and `ui_cache`. |
| 11 | `UI_DRAW_CONNECT_SCREEN` | **matched** — the target finds the menu named `Connect` and routes it through the menu drawing path. |
| 12 | `UI_LOAD_SCRIPT_MENU` | **matched** — two-argument target references `ui/scriptmenus/`, `.menu`, `loadmenu`, and `cl_language`; an engine call supplies image-track value 5. |
| 13 | `UI_GET_FONT_INFO` | **matched** — target converts the second integer argument by multiplying it by `0.01f` before calling the font-selection routine, matching the CoD UI ABI's percentage-scale convention. |

This SP table is therefore **not** a verbatim RTCW table and is also shorter/differently ordered than the known CoD multiplayer UI table. The project must continue treating each executable/module pair as authoritative.

## Immediate next analysis

1. Recover command-call sites missed by the current direct-pattern scanner.
2. Attach argument-shape metadata to every engine→module command.
3. Group engine-side syscall targets by shared implementation and argument shape.
4. Start assigning syscall names only where strings, engine call targets, or a public reference provide independent support.
5. Use the now-confirmed VM loader to trace the single-player startup sequence in order.
