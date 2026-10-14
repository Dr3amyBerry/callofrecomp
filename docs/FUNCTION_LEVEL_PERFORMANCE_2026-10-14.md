# Function-entry mapping and next performance investigations — 2026-10-14

**Repository:** Dr3amyBerry/callofrecomp, default branch `main`.
**Status:** diagnostic implementation verified on original private p-code headers;
function-level CPU attribution and any in-game FPS improvement **NOT VERIFIED**.
**Safety:** do not publish original PE/DLL/PK3 content, raw Ghidra outputs,
generated guest C, private profiling logs, APKs or JSON maps derived from them.

## 1. Why the previous optimization path stalled

The current pipeline uses Ghidra raw p-code, generates C containing guest
register/RAM operations, and compiles it for Android ARM64. The translator
used `CHUNK = 1500` instruction entries and previously parsed `F` function
entry records but discarded them in `main()`. These chunks are dispatch
ranges, **not recovered functions**. A single chunk often includes function
entries belonging to many unrelated original routines.

The 2026-10-14 WSA x86_64 comparisons in
[the rendering/translation audit](RENDER_TRANSLATION_AUDIT_2026-10-14.md)
did **not** establish a gameplay FPS benefit from targeted `-O2`, `-Oz`,
GL4ES batching or VBO modes 2/3. GL thunk draw-call CPU accounted for about
2.64 ms/frame in one diagnostic window, but excludes generated renderer
calculation and GPU work. The heavy scene on physical ARM64 remains unmeasured.
Do not retry rejected global toggles or treat WSA numbers as phone results.

## 2. External implementations and transferable ideas

| Project / concrete code | What it actually does | Possible local use / caveat |
| --- | --- | --- |
| [veritr1x/recomp-kit translator](https://github.com/veritr1x/recomp-kit/blob/main/tools/recomp/translate.py) | Translates original Windows x86 functions to generated native C, retaining original address identities | Preserve original function-entry provenance; CoD currently uses p-code and different control-flow lowering, so do **not** copy its function emitter wholesale |
| [recomp-kit runtime/profile.cpp](https://github.com/veritr1x/recomp-kit/blob/main/runtime/profile.cpp) | Samples active guest-function identities via host-maintained slots; its 1000 Hz samples include wall time/host waits | Design reference for opt-in per-function observation; first prove guest entry/return and scheduling boundaries, measure profiler overhead |
| [recomp-kit oracle.py](https://github.com/veritr1x/recomp-kit/blob/main/tools/recomp/oracle.py) and [testing](https://github.com/veritr1x/recomp-kit/blob/main/docs/testing.md) | Differential original x86 execution in Unicorn against native translated routines | Build independent register/flag/memory equivalence fixtures for selected hot leaves **before** attempting native replacements |
| [FEX redundant flag elimination](https://github.com/FEX-Emu/FEX/blob/main/FEXCore/Source/Interface/IR/Passes/RedundantFlagCalculationElimination.cpp) | IR graph analysis of flag reads/writes | Current translator already eliminates conservatively dead flag writes: study only compiler-surviving redundant work inside **measured** functions |
| [FEX x87 stack pass](https://github.com/FEX-Emu/FEX/blob/main/FEXCore/Source/Interface/IR/Passes/x87StackOptimizationPass.cpp) | Virtualizes x87 stack accesses within IR blocks | Potential later win, not a free replacement of guest 80-bit semantics; earlier float32-to-binary80 micro-optimization was rejected |
| [TeamGDB/Yakumo profile guide](https://github.com/TeamGDB/Yakumo/blob/main/docs/PROFILE_GUIDE.md) | Supports title-specific native fast paths through explicit registration | Consider reviewed native replacements **only after** isolating a small, hot, behaviorally verified original routine |
| [HybridHeaven-Recomp frametime investigation](https://github.com/ogdanimal/HybridHeaven-Recomp/blob/main/docs/frametime-investigation.md) | Found guest scheduling/event delivery, not renderer throughput, behind periodic dropped renders in an N64 port | Separate guest execution, blocking, swaps and dropped-frame logic; this does **not** establish an analogous bug in CoD |
| [WindowsRecompTool architecture](https://github.com/Zippingrocks/WindowsRecompTool/blob/main/docs/architecture.md) | Guarded x86 PE32 analysis, machine-code-to-C output, explicit guest state | Useful for verifying CFG/discovery invariants; a separate pipeline, not a drop-in backend |

All references are **research references**. Their licenses and source
provenance must be reviewed before reusing implementations. Our new tools
use original local metadata only and introduce no third-party source code.

## 3. Implemented safely in this phase

- `tools/recomp/function_map.py` reads only Ghidra `I` and `F` headers
  (without materializing operation bodies) and reproduces the generator's
  1,500-instruction chunks, partition index and exact function *entry*
  positions. The report explicitly marks unmatched entries and context.
- `tools/recomp/pcode2c.py --function-map-out <ignored JSON>` emits the same
  sidecar during an ordinary regeneration if explicitly requested.
  **Without the flag, generated C and guest runtime behavior are unchanged.**
- `tools/recomp/analyze_guest_hotspots.py` joins existing opt-in
  `cpu sample: chunk ...` records to the exact chunk address ranges.
  It aggregates sampled chunk time and shows function-entry context but
  **NEVER divides sampled time between functions**.
- Synthetic tests verify JSON stability, mapping chunk/part arithmetic,
  exact/unmatched entry handling, ambiguous/multiple function entries,
  CLI opt-in C identity and rejection of overwriting input/output files.
  Derived sidecars remain under ignored `recomp_out/`.
- Full local regression: **79 Python tests passed (4 environment-dependent skips)**; **25/25 host CTest targets passed**. This phase did not rebuild/test a phone APK because the default guest/native C code is unchanged.

### Actual private original header mapping (counts only)

| Module | I instructions | 1,500-instruction chunks | Matched F entries | Chunks with multiple F entries |
| --- | ---: | ---: | ---: | ---: |
| CoDSP.exe | 333,208 | 223 | 3,290 | 203 |
| cgamex86.dll | 81,941 | 55 | 965 | 54 |
| gamex86.dll | 144,114 | 97 | 1,432 | 95 |
| uix86.dll | 40,507 | 28 | 541 | 26 |
| **Total** | **599,770** | **403** | **6,228** | **378** |

The exact start of every one of the 6,228 exported entries coincides
with a translated instruction; this says **nothing** about full function
coverage or correct ownership of each instruction. The 378 multi-entry
chunks prove that a chunk usually cannot be named as one routine.

One prior **opt-in** WSA menu-load profile contained 22 reported
chunk records spanning 13 distinct chunk ranges. All 13 resolved to
one of these module maps. The largest cumulative sample belonged to
CoDSP chunk 207: 76,136 microseconds and 285,079 sampled invocations
reported over the logging window; that chunk contains **28 F entries**.
These are NOT per-frame totals, exhaustive CPU timings, hot function
costs, or phone ARM64 data. Profiling overhead was measured separately
in prior work.

## 4. Reproduce locally without rebuilding the game

Use the ignored/private `recomp_out/*.pcode` files generated from your
own verified 1.5 executable/DLL installation. Output files below are
private; **never commit them**:

```powershell
python tools/recomp/function_map.py recomp_out/codsp.pcode --module CoDSP.exe --parts 12 --out recomp_out/codsp_function_map.json
python tools/recomp/function_map.py recomp_out/cgamex86.pcode --module cgamex86.dll --parts 4 --out recomp_out/cgamex86_function_map.json
python tools/recomp/function_map.py recomp_out/gamex86.pcode --module gamex86.dll --parts 8 --out recomp_out/gamex86_function_map.json
python tools/recomp/function_map.py recomp_out/uix86.pcode --module uix86.dll --parts 1 --out recomp_out/uix86_function_map.json
```

Alternatively, **on a future generator run only**, add
`--function-map-out recomp_out/codsp_function_map.json` to the normal
`pcode2c.py` invocation. The integrated path uses `pcode2c.CHUNK`
and the same `--parts`, so it remains aligned with regenerated code.

Annotate an existing locally captured diagnostic log:

```powershell
python tools/recomp/analyze_guest_hotspots.py .local/profiles/menu_cpu_profile.log --map recomp_out/codsp_function_map.json --map recomp_out/cgamex86_function_map.json --map recomp_out/gamex86_function_map.json --map recomp_out/uix86_function_map.json --top 15
```

Append `--json` for machine-readable, aggregated chunk results. This does
not activate profiling, run the game or change graphics settings. If the log
doesn't contain opt-in `cpu sample: chunk` records it cannot produce hotspots.

**Critical attribution boundary:** Ghidra's `F` marker is a function
*entry*, not a contiguous source range or call stack. Original functions
can have gaps, shared tails or discontiguous bodies. A preceding `F`
entry in an adjacent chunk is **context only**, not proof of ownership.
Current `guest.c` profiler measures complete chunk function invocations.
Naming a function as the hottest from these results would be fabricated.

## 5. Evidence gates for the next engineering phases

1. **Verified (current):** deterministic private entry-to-chunk maps, sample
   join and mixed-chunk counts without recompiling or touching rendering.
2. **Pending — precise guest PC/function identity:** design an off-by-default
   method to observe original x86 function entry/return and function-level
   call counts or sample addresses, with strict correctness and overhead
   checks. Compare to native Simpleperf host PCs; do not assume each
   translated C chunk maps to one guest function.
3. **Pending — heavy-scene phone measurement:** on the real Mali-G52
   ARM64 phone reproduce the congested wire/soldier scene, capture a
   trace separating generated guest, GL4ES, GPU driver, frame pacing,
   audio and other host work. Control CPU frequency, thermal state,
   graphics profile, camera, save and run duration. WSA entrance is an
   independent control, **not** a surrogate for Android ARM64.
4. **Pending — isolated optimization:** inspect AArch64 instructions in
   the actually hot original functions; identify native integer-width,
   x87-state and redundant movement opportunities. Do not change
   memory/flag semantics, assume registers are dead, or turn on fast-math.
5. **Pending — differential validation:** introduce Unicorn/reference
   comparison for any native replacement covering registers, guest RAM,
   flags and edge cases. Demonstrate same-scene A/B and visual/gameplay
   compatibility before enabling a runtime fast path.
6. **Separate pending lifecycle issue:** repeated UI parsing follows
   `Hunk_Clear` / renderer restart. Function mapping may help identify
   parser time but does **not** justify skipping initialization or
   reusing pointers to freed memory.

**Decision rule:** a static instruction-count reduction, smaller object
file, faster synthetic benchmark or successful WSA boot must not be
called an ARM64 in-game FPS improvement without a matching device
measurement. Preserve rejected experiments in the audit to avoid
repeating unsuccessful approaches.
