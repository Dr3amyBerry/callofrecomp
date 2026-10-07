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
| `gamex86.dll` | `0x00042730` | `dllEntry` | observed | Exported name; stores incoming callback pointer. |
| `gamex86.dll` | `0x0001CD70` | `vmMain` | observed | Exported name; numeric command dispatcher. |
| `cgamex86.dll` | `0x00022540` | `dllEntry` | observed | Exported name; stores incoming callback pointer. |
| `cgamex86.dll` | `0x00018CD0` | `vmMain` | observed | Exported name; numeric command dispatcher. |
| `uix86.dll` | `0x00017E80` | `dllEntry` | observed | Exported name; stores incoming callback pointer. |
| `uix86.dll` | `0x000079A0` | `vmMain` | observed | Exported name; numeric command dispatcher. |
