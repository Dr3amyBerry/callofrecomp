# Symbol ledger

Function names and semantics must carry an evidence level.

| Level | Meaning |
|---|---|
| **observed** | Directly established from PE metadata, exports, strings, constants, or unambiguous machine-code behavior. |
| **matched** | Behavior/signature has been matched against a public reference implementation with enough independent evidence to make the correspondence credible. |
| **inferred** | Working hypothesis used to guide analysis; it must not silently become a recovered fact. |

Initial entries:

| Module | RVA | Name | Evidence | Notes |
|---|---:|---|---|---|
| `CoDSP.exe` | `0x0004F0E0` | native VM loader / create path | observed | Uses `%sx86.dll`; resolves `dllEntry` and `vmMain`; calls `dllEntry` with the engine syscall callback. |
| `CoDSP.exe` | `0x0004F270` | VM call wrapper | observed | Forwards export command + argument slots to loaded VM function pointer at VM-object offset `0x48`. |
| `CoDSP.exe` | `0x0004A2F0` | game syscall callback | observed | Indexed dispatcher for module→engine syscall IDs `0..211`. |
| `CoDSP.exe` | `0x00001A50` | cgame syscall callback | observed | Indexed dispatcher for module→engine syscall IDs `0..252`. |
| `CoDSP.exe` | `0x00010B00` | ui syscall callback | observed | Indexed dispatcher for module→engine syscall IDs `0..84`. |
| `gamex86.dll` | `0x00042730` | `dllEntry` | observed | Exported name; stores incoming callback pointer. |
| `gamex86.dll` | `0x0001CD70` | `vmMain` | observed | Exported name; numeric command dispatcher. |
| `cgamex86.dll` | `0x00022540` | `dllEntry` | observed | Exported name; stores incoming callback pointer. |
| `cgamex86.dll` | `0x00018CD0` | `vmMain` | observed | Exported name; numeric command dispatcher. |
| `uix86.dll` | `0x00017E80` | `dllEntry` | observed | Exported name; stores incoming callback pointer. |
| `uix86.dll` | `0x000079A0` | `vmMain` | observed | Exported name; numeric command dispatcher. |

## UI export command ledger

These names are **matched**, not original symbols recovered from the proprietary binary.

| ID | Working symbol | Evidence | Notes |
|---:|---|---|---|
| 0 | `UI_GETAPIVERSION` | matched | CoD UI returns 6; engine validates command 0 against 6. |
| 1 | `UI_INIT` | matched | Called immediately after version validation. |
| 2 | `UI_SHUTDOWN` | matched | Called during teardown before VM unload. |
| 3 | `UI_KEY_EVENT` | matched | Two-argument dispatch signature and inherited ordering. |
| 4 | `UI_MOUSE_EVENT` | matched | Two-argument dispatch signature and inherited ordering. |
| 5 | `UI_REFRESH` | matched | One-argument dispatch; called from refresh paths. |
| 6 | `UI_IS_FULLSCREEN` | matched | No-argument result-returning dispatch. |
| 7 | `UI_SET_ACTIVE_MENU` | matched | One-argument command used by menu transitions. |
| 8 | `UI_GET_ACTIVE_MENU` | matched | Returns stored active-menu state. |
| 9 | `UI_CONSOLE_COMMAND` | matched | Engine invokes it from console-command fallback and checks result. |
| 10 | `UI_DRAW_CONNECT_SCREEN` | matched | One-argument command called from screen/connect drawing. |

IDs 11–13 remain intentionally unnamed.
