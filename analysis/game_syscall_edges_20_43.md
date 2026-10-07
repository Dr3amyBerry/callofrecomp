# SP game syscall dispatcher: direct edges for IDs 20–43

## Evidence and scope

This note extends [game_syscall_findings.md](game_syscall_findings.md) without assigning unverified semantic syscall names. The input is the supplied Call of Duty **PC 1.5** single-player `CoDSP.exe`, fingerprinted in [the baseline](baselines/cod1_sp_pc_1_5.json).

The engine-side `game` module-to-engine callback starts at `0x0044A2F0`, with the `0x0044B310` jump table. `tools/syscall_handler_edges.py` parses the established jump table, disassembles each bounded handler interval using binutils `objdump`, and records **direct** `call` / `jmp` destinations.

These are **observed branch edges**, not function identities or finalized names. For many IDs, the dispatcher case forwards to a helper. Some cases use tail jumps, while others return inline or use indirect branches. The bounded handler interval ends at the next distinct syscall jump-table target (or the configurable byte limit), so a future deeper control-flow pass remains necessary.

## Decoded direct edges

| Syscall ID | dispatcher case VA | decoded edge | first direct destination |
|---:|---:|---|---:|
| 20 | `0x0044A47A` | `call` | `0x0042ABB0` |
| 21 | `0x0044A486` | `call` | `0x00425FD0` |
| 22 | `0x0044A49F` | `call` | `0x00423010` |
| 23 | `0x0044A4BA` | `call` | `0x004230E0` |
| 24 | `0x0044A4D3` | `call` | `0x00449A90` |
| 25 | `0x0044A4DF` | `call` | `0x00449AC0` |
| 26 | `0x0044A4EB` | `call` | `0x00449B10` |
| 27 | `0x0044A4FF` | `jmp` | `0x00401000` |
| 28 | `0x0044A508` | `jmp` | `0x0044A110` |
| 29 | `0x0044A511` | `call` | `0x00493F20` |
| 30 | `0x0044A526` | `jmp` | `0x0044A170` |
| 31 | `0x0044A52F` | `call` | `0x00447430` |
| 32 | `0x0044A545` | `jmp` | `0x0044A1D0` |
| 33 | `0x0044A54E` | `jmp` | `0x00408F50` |
| 34 | `0x0044A55D` | `jmp` | `0x0044A270` |
| 35 | `0x0044A566` | `call` | `0x00404910` |
| 36 | `0x0044A576` | `call` | `0x00421FE0` |
| 37 | `0x0044A58C` | `call` | `0x004220E0` |
| 38 | `0x0044A59F` | `call` | `0x00421DA0` |
| 39 | `0x0044A5B5` | `call` | `0x00422EB0` |
| 40 | `0x0044A5C4` | `call` | `0x00424310` |
| 41 | `0x0044A5E0` | `call` | `0x00420AC0` |
| 42 | `0x0044A5F7` | `call` | `0x00449990` |
| 43 | `0x0044A617` | `call` | `0x004499C0` |

**Coverage:** all 24 dispatch entries have at least one direct `call` or `jmp` in their bounded case. For each entry above, the displayed destination is its first decoded direct edge in the current baseline.

## Reproduce

```bash
python tools/syscall_handler_edges.py originals/CoDSP.exe \
  --callback-va 0x0044A2F0 \
  --start-id 20 \
  --end-id 43 \
  --json analysis/local/game_syscall_edges_20_43.json
```

This script requires a local `objdump` executable. It does not run original game code or extract proprietary assets.

## Next

1. Recover input/output register and stack argument shapes for the handlers.
2. Compare each destination's strings and surrounding control flow with the existing engine symbol map.
3. Assign semantic names only after independent checks, and update `include/codrecomp/game_sp_syscalls.h` accordingly.
4. Add optional matching against properly licensed reference code when relevant; do not import unknown-license source.
