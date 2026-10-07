# SP game syscalls 20–43: conservative ABI shape recovery

## Method and evidence

This record applies **only** to the SHA-256-pinned Call of Duty 1.5 **single-player** `CoDSP.exe`, not to United Offensive or multiplayer. The engine callback at `0x0044A2F0` dispatches by numeric syscall ID through a jump table starting at `0x0044B310`.

Verified callback prologue:

```asm
0x0044A2F2 mov ebp, [esp+0x0c]   ; points to syscall word array
0x0044A2F6 mov eax, [ebp]        ; syscall command ID
```

Thus `[ebp+4]` is input slot 0, `[ebp+8]` is input slot 1, and so on. Our `tools/syscall_signature_probe.py` uses binutils `objdump` to decode **bounded** jump-table handlers, records direct `[ebp+offset]` references and classifies observed return shape. This is **not** a full C function prototype or a complete dataflow proof: indirect argument reads, register-passed values, side effects, and downstream callee behavior can require further tracing.

Return category legend:

- **forces EAX=0:** handler explicitly writes zero to EAX after its final call and before its `ret`.
- **EAX not cleared:** handler returns without such an explicit zero overwrite. The precise result type/value is not yet proven by this category alone.
- **tail jump:** handler transfers control directly via `jmp` after unwinding its own registers; the delegated callee decides the return value.

## Observed case signatures

| ID | handler VA | directly referenced argument slots | return shape | independently matched working name | first call / branch VA |
|---:|---:|---|---|---|---|
| 20 | `0x0044A47A` | - | forces EAX=0 | — | `0x0042ABB0` |
| 21 | `0x0044A486` | 0,1,2 | EAX not cleared | `G_FS_FOPEN_FILE` | `0x00425FD0` |
| 22 | `0x0044A49F` | 0,1,2 | forces EAX=0 | `G_FS_READ` | `0x00423010` |
| 23 | `0x0044A4BA` | 0,1,2 | EAX not cleared | `G_FS_WRITE` | `0x004230E0` |
| 24 | `0x0044A4D3` | - | forces EAX=0 | — | `0x00449A90` |
| 25 | `0x0044A4DF` | - | forces EAX=0 | — | `0x00449AC0` |
| 26 | `0x0044A4EB` | 0,1 | EAX not cleared | — | `0x00449B10` |
| 27 | `0x0044A4FF` | - | tail jump | — | `0x00401000` |
| 28 | `0x0044A508` | - | tail jump | — | `0x0044A110` |
| 29 | `0x0044A511` | 0,1 | EAX not cleared | — | `0x00493F20` |
| 30 | `0x0044A526` | - | tail jump | — | `0x0044A170` |
| 31 | `0x0044A52F` | 0,1 | forces EAX=0 | — | `0x00447430` |
| 32 | `0x0044A545` | - | tail jump | — | `0x0044A1D0` |
| 33 | `0x0044A54E` | 0,1 | tail jump | — | `0x00408F50` |
| 34 | `0x0044A55D` | - | tail jump | — | `0x0044A270` |
| 35 | `0x0044A566` | 0,1 | EAX not cleared | — | `0x00404910` |
| 36 | `0x0044A576` | 0,1 | forces EAX=0 | `G_FS_RENAME` | `0x00421FE0` |
| 37 | `0x0044A58C` | 0 | forces EAX=0 | `G_FS_FCLOSE_FILE` | `0x004220E0` |
| 38 | `0x0044A59F` | 0,1 | forces EAX=0 | — | `0x00421DA0` |
| 39 | `0x0044A5B5` | 0 | forces EAX=0 | — | `0x00422EB0` |
| 40 | `0x0044A5C4` | 0,1,2,3 | EAX not cleared | `G_FS_GETFILELIST` | `0x00424310` |
| 41 | `0x0044A5E0` | 0,1 | forces EAX=0 | `G_SEND_CONSOLE_COMMAND` | `0x00420AC0` |
| 42 | `0x0044A5F7` | 0,1,2,3,4 | forces EAX=0 | — | `0x00449990` |
| 43 | `0x0044A617` | 0,1 | forces EAX=0 | — | `0x004499C0` |

**Summary:** 24 IDs analyzed; 12 force EAX=0, 6 tail-jump, 6 do not clear EAX. A dash for direct slots means **no direct reads seen in that dispatch stub**, not a proven zero-argument signature. The highest directly seen slot is 4 (ID 42), corresponding to five visible argument words.

## Named entries with independent binary evidence

- **21 `G_FS_FOPEN_FILE`** → Mode validation and literal `FSH_FOpenFile: bad mode`.
- **22 `G_FS_READ`** → Literal `FS_Read: -1 bytes read`; handler resets EAX.
- **23 `G_FS_WRITE`** → Literal `FS_Write: 0 bytes written`; EAX not overwritten.
- **36 `G_FS_RENAME`** → Literal `FS_Rename: %s --> %s`.
- **37 `G_FS_FCLOSE_FILE`** → Handle-indexed file cleanup and close operations.
- **40 `G_FS_GETFILELIST`** → Directory name/extension filtering and counted buffer copy; `$modlist`.
- **41 `G_SEND_CONSOLE_COMMAND`** → Switch on exec_when; literal `Cbuf_ExecuteText: bad exec_when`.

The names above are **working ABI labels** tied to verified CoD 1.5 SP dispatch IDs, not recovered original linker symbols. They are encoded without filling unverified gaps in `include/codrecomp/game_sp_syscalls.h`.

## Representative prototype hypotheses

The following are useful **hypotheses for future portable adapter design**; they are *not* authoritative types until the module wrappers, engine callees and pointer ownership are traced end-to-end.

- **21:** `(const char* path, fileHandle_t* out_handle, fsMode_t mode) -> integer`. The helper checks opening mode, populates handle state, and the dispatcher preserves EAX.
- **22:** `(void* buffer, integer length, fileHandle_t handle) -> void-like`. Three slots are forwarded, with EAX explicitly zeroed by the dispatcher.
- **23:** `(const void* buffer, integer length, fileHandle_t handle) -> integer-like`. The helper is a write path, and the dispatcher retains EAX.
- **36:** `(const char* old_path, const char* new_path) -> void-like`. The helper emits the `FS_Rename` diagnostic.
- **37:** `(fileHandle_t handle) -> void-like`. The helper closes and clears file-handle-associated state.
- **40:** `(const char* path, const char* extension, char* output, integer output_bytes) -> integer-like`. The helper copies a counted string list into a size-bounded output buffer.
- **41:** `(integer exec_when, const char* text) -> void-like`. The helper switches on `exec_when` and reports invalid selector values.

**Important:** `void-like` here means the dispatcher returns the integer word 0; whether the original higher-level trap API declares `void` requires further module-wrapper evidence. `integer-like` does not guarantee that the result is a byte count or error code.

## Other structural findings not yet semantically named

- **20/24–26:** memory state, marks, or data copying, with different return shapes; avoid automatically naming ID 20 `Hunk_Clear`. That diagnostic is located at the nearby **0x0042ABF0** function, whereas ID 20 actually calls **0x0042ABB0**.
- **27:** returns a formatted PC build timestamp/string through `0x00401000`.
- **28/30/32–34:** memory and save/restore buffer forwarding, including explicit game-message overflow diagnostics.
- **38/39:** disk/journal/save-path operations. A `save` string alone does not prove a specific filesystem function.
- **42/43:** shared state/buffer management, with arguments copied into global state.

## Reproducibility

```bash
python tools/syscall_signature_probe.py originals/CoDSP.exe \
  --callback-va 0x0044A2F0 \
  --start-id 20 --end-id 43 \
  --json analysis/local/game_sp_abi_20_43.json

python -m unittest discover -s tests -p "test_*.py" -v
```

To preserve copyright separation, raw proprietary executable contents and extracted source are not committed to the repository. The tool emits **metadata only**.

## Next investigation

1. Recover full arguments/side effects in callees, especially 24–35 and 38–39.
2. Map the module-side syscall wrapper signatures for the seven named entries.
3. Add a portable filesystem adapter contract with 64-bit-safe host pointers while retaining the on-wire legacy 32-bit ABI.
4. Add deterministic tests for handler bounds/ambiguity, including jump-table alias cases.
