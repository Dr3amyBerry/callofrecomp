# Single-player game syscall findings

This file tracks semantic recovery of the **game module → engine** syscall dispatcher in the supplied Call of Duty 1.5 single-player executable.

Dispatcher callback:

- VA: `0x0044A2F0`
- jump table: `0x0044B310`
- accepted numeric range: `0..211`

The names below are not taken blindly from multiplayer/public headers. Each mapped entry has supporting behavior in the supplied SP engine.

## Foundational syscall range

| ID | Working symbol | Evidence | SP engine behavior |
|---:|---|---|---|
| 0 | `G_PRINT` | matched | Formats argument through `"%s"` and routes it to the common print path. |
| 1 | `G_ERROR` | matched | Routes argument through the error path with the control-prefixed `"\x15%s"` format. |
| 2 | `G_ERROR_NOPREFIX` | matched | Same error path with plain `"%s"`. |
| 3 | `G_ENDGAME` | observed/matched | Calls the error/termination path with error class 5 and literal `"endgame"`. This is an SP-specific insertion relative to the known MP table. |
| 4 | `G_MILLISECONDS` | matched | Jumps to `0x00452F10`, which initializes a baseline timer once and returns the current system tick minus that baseline. |
| 5 | `G_CVAR_REGISTER` | matched | Four-argument VM-cvar registration path; initializes the VM handle/cache record. |
| 6 | `G_CVAR_UPDATE` | matched | Validates VM cvar handle and refreshes cached string/integer/float values. |
| 7 | `G_CVAR_SET` | matched | Calls the cvar-set core with name/value and forced-set flag. |
| 8 | `G_CVAR_SETVAR` | matched | Uses the VM-cvar handle to obtain the cvar name, sets the supplied value, then updates the VM-cvar cache. |
| 9 | `G_CVAR_VARIABLE_INTEGER_VALUE` | matched | Finds cvar by name and returns its integer field. |
| 10 | `G_CVAR_VARIABLE_VALUE` | matched | Finds cvar by name, reads the float field, and writes the float result through the syscall ABI output slot. |
| 11 | `G_CVAR_VARIABLE_STRING_BUFFER` | matched | Finds cvar by name and copies its string into caller buffer with explicit length handling. |
| 12 | `G_ARGC` | observed/matched | Returns the engine command-argument count global directly. |
| 13 | `G_ARGV` | matched | Copies a selected command argument into caller buffer. |
| 14 | `G_HUNK_ALLOC` | matched | Target contains the literal diagnostic `"trap_Hunk_Alloc can only be called in G_InitGame and the first few frames of G_RunFrame"`. |
| 15 | `G_HUNK_ALLOC_LOW` | matched | Target contains corresponding `trap_Hunk_AllocLow` diagnostic. |
| 16 | `G_HUNK_ALLOC_ALIGN` | matched | Target contains corresponding `trap_Hunk_AllocAlign` diagnostic. |
| 17 | `G_HUNK_ALLOC_LOW_ALIGN` | matched | Target contains corresponding `trap_Hunk_AllocLowAlign` diagnostic. |
| 18 | `G_HUNK_ALLOC_TEMP` | matched | Calls temp-hunk allocation code whose failure string is `"Hunk_AllocateTempMemory: failed on %i, needs %i"`. |
| 19 | `G_HUNK_FREE_TEMP` | matched | Calls the temp-allocation release path, including the hunk allocation sentinel validation. |

ID 20 and later are intentionally not named in this file yet. The next target performs a hunk-state reset operation, but the exact public ABI name must be verified before committing a semantic label.

## Important ABI divergence from multiplayer

A known public CoD multiplayer reconstruction has the common sequence:

```text
0 PRINT
1 ERROR
2 ERROR_NOPREFIX
3 MILLISECONDS
...
```

The supplied **single-player** engine instead has:

```text
0 PRINT
1 ERROR
2 ERROR_NOPREFIX
3 ENDGAME
4 MILLISECONDS
...
```

SP also exposes a VM-cvar set-by-handle operation before the integer/float/string query group.

That means the multiplayer enum cannot be copied into the SP port by offsetting every entry mechanically. Every range must be validated against the SP dispatcher.

## Supporting engine targets

Useful recovered targets for follow-up:

| Function | VA |
|---|---:|
| common print path used by syscall 0 | `0x0042E300` |
| common error/termination path | `0x0042E660` |
| millisecond timer | `0x00452F10` |
| VM cvar register | `0x004320A0` |
| VM cvar update | `0x004320E0` |
| cvar VM-set helper | `0x00431FC0` |
| cvar float query | `0x004321B0` |
| cvar integer query | `0x004321D0` |
| cvar string-buffer query | `0x00432210` |
| hunk alloc wrapper | `0x00449880` |
| hunk alloc-low wrapper | `0x004498B0` |
| hunk alloc-align wrapper | `0x004498E0` |
| hunk alloc-low-align wrapper | `0x00449910` |
| temp hunk allocation | `0x0042AE70` |

## Next range

The immediate continuation is to recover IDs `20+`, beginning with:

- hunk state/reset operations;
- filesystem open/read/write/close/rename;
- command dispatch;
- game-data registration;
- server/config/userinfo calls.

Names will only be committed as they receive the same evidence standard as IDs 0–19.
