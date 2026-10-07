# Public reference sources and verification policy

Public source/reconstruction projects are allowed to accelerate analysis, but they are **references, not authority for the supplied single-player 1.5 binaries**.

## Sources currently useful

### OpenCoD1

Repository:
`https://github.com/opencod1/opencod1`

OpenCoD1 is a public reverse-engineering/reconstruction effort focused largely on Call of Duty 1.x multiplayer. It contains recovered engine/module interfaces, subsystem reconstructions, function-address notes, and CoD-specific ABI information. At the time of this review the repository metadata exposes no declared license and no root `LICENSE`, `LICENSE.md`, or `COPYING` file was found, so this project must **not copy or vendor OpenCoD1 source code**. It is used only as a research/indexing reference whose claims are independently checked against the supplied binaries.

High-value reference areas:

- `src/game_mp/g_public.h`
- `src/cgame_mp/cg_public.h`
- `src/ui_mp/ui_public.h`
- `src/game_mp/g_syscalls_mp.c`
- `src/client_mp/cl_cgame_mp.c`
- `src/server_mp/sv_game_mp.c`
- `src/universal/cvar.c`
- `src/universal/com_memory.c`
- renderer and qcommon reconstruction files

This is especially useful because several CoD-specific interfaces differ materially from stock Quake III / RTCW.

### id Software Return to Castle Wolfenstein SP source

Repository:
`https://github.com/id-Software/RTCW-SP`

RTCW SP is useful as an id Tech 3-family structural ancestor for VM boundaries, UI/game/cgame organization, renderer concepts, filesystem design, command/cvar systems, and platform abstraction.

It is **not** assumed to have identical Call of Duty command numbers, structures, or behavior.

## Verification rule

A public-reference symbol may enter our symbol ledger as **matched** only when the supplied CoD 1.5 SP binary provides independent supporting evidence, for example:

- identical command number plus compatible argument shape;
- distinctive string references;
- matching constants;
- matching control flow;
- matching engine call sites;
- matching data offsets/layout;
- behavior of the engine-side dispatcher;
- behavior of the DLL wrapper/dispatch target.

If only the external reference suggests a name, it remains **inferred** or is left unnamed.

## Why this rule is necessary

The supplied SP binary has already demonstrated real ABI differences:

- SP UI command ordering is not a verbatim RTCW UI table.
- SP UI ordering also differs from the reconstructed CoD multiplayer UI table.
- The SP game syscall dispatcher contains additional slots before the common cvar/hunk sequence.
- The SP game, cgame and UI vmMain ranges differ from the multiplayer reconstruction.

Therefore the executable/module pair being ported remains the source of truth.

## Practical workflow

```text
supplied SP binary
       │
       ├── recover numeric ABI / addresses / behavior
       │
public references
       │
       └── propose likely semantic correspondence
                    │
                    ↓
          independent comparison
                    │
            ┌───────┴────────┐
            │                │
          matched         inferred
            │                │
       symbol ledger     keep researching
```

This policy is intended to gain the speed advantage of existing public research without contaminating the project with false assumptions.
