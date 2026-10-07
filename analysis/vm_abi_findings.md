# vmMain / dllEntry ABI probe

The first dedicated ABI probe now recovers two structures directly from the three single-player modules:

1. the callback storage used by `dllEntry`, and
2. the indexed jump table used by `vmMain`.

It also scans calls through the stored callback and records immediate syscall IDs when the command is directly visible as a `push imm` immediately before the indirect call. That syscall-ID recovery is intentionally heuristic; unresolved sites remain unresolved rather than being guessed.

## Recovered module dispatch tables

| Module | Callback slot RVA | `vmMain` jump-table RVA | vmMain command range | Entries |
|---|---:|---:|---:|---:|
| `gamex86.dll` | `0x000A4834` | `0x0001CF4C` | `0..24` | 25 |
| `cgamex86.dll` | `0x000657E8` | `0x00018F3C` | `0..25` | 26 |
| `uix86.dll` | `0x00034030` | `0x00007A50` | `0..13` | 14 |

These counts come from the actual `cmp eax, maxCommand` guard immediately before each indexed jump.

## Engine-syscall call sites

| Module | Indirect calls through callback | Distinct immediate IDs recovered | Immediate ID span | Unresolved call sites |
|---|---:|---:|---:|---:|
| `gamex86.dll` | 1,187 | 161 | `0..161` | 214 |
| `cgamex86.dll` | 1,144 | 240 | `0..252` | 179 |
| `uix86.dll` | 377 | 74 | `0..84` | 63 |

Important: the syscall column is **not yet a semantic enum**. It only proves numeric IDs observed at direct-immediate call sites. The next phase is to group wrappers by ID, recover argument shapes, and attach semantic names only when supported by independent evidence.

## First architectural consequence

The three modules all use the same broad shape:

```text
engine
  └─ passes syscall callback -> dllEntry(callback)
                              └─ stores callback in module global

engine -> vmMain(command, ...)
          └─ indexed dispatch table -> module operation

module wrapper -> callback(syscallId, ...)
```

That gives the recompilation project a concrete interface boundary to reconstruct before touching the renderer or Android platform layer.
