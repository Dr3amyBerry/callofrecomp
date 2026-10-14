# Renderer and x86-to-ARM64 translation audit — 2026-10-14

## Scope and safeguards

CallofRecomp statically recompiles Call of Duty 1.5 x86 PEs through Ghidra
p-code -> generated portable C -> native Android AArch64. Its original
desktop OpenGL rendering calls go through generated GL bridge thunks ->
GL4ES fixed-function/shader emulation -> OpenGL ES 2.0 -> mobile GPU.

All the A/B experiments below use **WSA x86_64**, with the same saved,
initial stationary Camp Toccoa training view and the **Balanced** visual
profile. Each result is the median of 60 approximately one-second engine
`frame stats` windows. These are not percentiles of individual frames,
not a full-game benchmark, and **not native Mali-G52 measurements**.
Each option was enabled in an isolated APK; game files and saves were
never added to Git. Experimental options were reverted after testing.

## Controlled comparisons

| Experimental change | Normal median FPS | Experiment median FPS | Normal engine CPU ms | Experiment engine CPU ms | Decision |
| --- | ---: | ---: | ---: | ---: | --- |
| CoDSP p10/p11 `-O2` instead of `-O1` | 54.50 | 54.25 | 17.75 | 17.79 | No established benefit; already OFF by default |
| GL4ES `LIBGL_BATCH=1` (0–100 vertices) | 54.50 | **51.75** | 17.75 | **19.13** | Worse; do not enable |
| CoDSP p10/p11 `-Oz` instead of `-O1` | 54.50 | **49.95** | 17.75 | **19.87** | Worse in WSA; experimental flag reverted |
| GL4ES `LIBGL_USEVBO=3` | 54.50 | 51.55 | 17.855 | 19.35 | Worse; keep default mode 1 |
| GL4ES `LIBGL_USEVBO=2` | 54.50 | 49.25 | 17.855 | 20.29 | Worse; keep default mode 1 |

The normal CPU value differs slightly for the older VBO study, which used
a separate reference capture. Do not compare numerical results between
the two reference captures as if all settings were identical.

The `-Oz` candidate does reduce generated **ARM64 static machine code**:
`codsp_recomp_p10.c.o` text sections: 1,999,712 B under `-O1` vs
654,000 B under `-Oz` (**-67.3%**); `p11`: 855,176 vs 575,236 B
(**-32.7%**). ARM64 compilation succeeds, but we have **no ARM64 runtime
A/B**: the WSA regression must not be extrapolated to Mali CPUs. Smaller
code alone does not establish improved instruction-cache behavior.

## What the renderer timing actually measured

In a WSA diagnostic run, selected guest GL calls into GL4ES/GLES took
approximately **2.64 ms CPU per frame for drawing** in one 272-frame
window; GL state, attribute-pointer setup, texture binding and locks
were individually below about 0.11 ms/frame. Total engine-thread CPU
in that scene was roughly 18 ms/frame. These inclusive call timings
**exclude** the upstream recompiled renderer's calculations and **exclude
GPU execution**. They cannot identify the remaining engine-thread time
as entirely graphics work. A previous Mali-G52 phone log in a different,
heavier stretch reported about 94.55 ms engine-thread CPU and 10.2 FPS,
but it is not controlled against this WSA stationary view.

## Translation audit (Ghidra p-code -> C -> AArch64)

- In the generated CoDSP p10 translation unit, `llvm-objdump` counted
  approximately **499,928 AArch64 machine instructions** in the entire
  object. This is static object-wide code, not per frame.
- Chunk 186 (`0x00505485..0x005069dd`) has 8,605 exported p-code
  operations. A private **conservative candidate** analysis marked 1,813
  operations as potentially removable (including dead flag computations
  and temporary calculations). This does **not** establish that they
  survive Clang's optimization or consume runtime CPU. No DCE pass was
  committed because proof of preservation across aliases/control flow is
  incomplete.
- Two sampled phone-hot chunks (186 and 187) contain multiple distinct
  original x86 functions. Chunks are sized by a generated 1,500-instruction
  boundary, **not function boundaries**; attributing all chunk CPU to
  `RB_StageIteratorGenericARB` would be incorrect.
- More than 16,000 float32->x87 binary80 conversion operations appear in
  static CoDSP p-code. A specialized float32->80-bit value converter passed
  deterministic reference tests but failed to improve the synthetic CPU
  microbenchmark and generated more AArch64 assembly overall. **Rejected**:
  no production change, no loss of x87 value semantics.
- The pinned GL4ES revision `ec16bedd8819c475326f4f1a3063772c6d986e06`
  was confirmed to equal upstream `master` on 2026-10-14 (commit from
  2026-10-04). There is no newer upstream release commit to adopt here.

## Why Vulkan is not the first change

The current game needs legacy desktop fixed-function OpenGL. GL4ES
translates that API to GLES2; simply replacing GLES with Vulkan would
not bypass the guest CPU work or GL4ES state/array conversion.
ANGLE implements a GLES frontend and may use a Vulkan backend: placing
it *under GL4ES* adds an additional compatibility layer unless its use
and correctness are proved by profiling.

Mesa Zink provides desktop OpenGL over Vulkan, which could replace some
layers, but its actual OpenGL feature profile depends on Vulkan driver
features/extensions. Integrating Mesa/Zink as an Android app dependency,
validating old fixed-function behavior, shader semantics, and device
compatibility is a substantial port—not an immediate FPS switch.

## Highest-value next measurements and implementation work

1. **On the actual ARM64 Mali device, reproduce the heavy training
   position** (the scene reporting 9–15 FPS, not the static entrance).
   Record CPU samples with Android NDK **Simpleperf** and per-frame
   graphics/GPU timelines with **Android GPU Inspector** (including
   Mali system trace support where available). Capture thermal,
   frequency and exact scene settings to avoid comparing unlike runs.
2. Split collected CPU samples into **generated CoDSP code**, GL4ES,
   GLES driver, game logic, audio, and other host functions. Resolve hot
   addresses within chunk 186, 187, 19 rather than labeling an entire
   chunk as the renderer. The linked unstripped `libmain.so` provides
   useful symbol/line information locally. Check whether system-level
   GPU counter samples indicate real shading/bandwidth saturation.
3. Only then optimize the proved hotspot: either a specific generated
   x86 p-code operation (with cross-architecture equivalence tests), a
   GL4ES vertex conversion/copy path (with pixel correctness tests), or
   excess original renderer state changes. Compare repeatable A/B
   scenes under the same device and power conditions.
4. The experimental `-Oz` ARM64 size result can be revisited **only if**
   native Simpleperf identifies instruction-fetch/cache pressure. No
   blanket `-Oz`, `-O2`, Vulkan, VBO2/3, batching or `fast-math`
   switches are justified by the current performance evidence.

## New function-level provenance research

The generator's Ghidra `F` function-entry markers are now preserved in
optional, private function maps. A real four-module mapping found 378 of
403 chunks containing multiple function entries. Therefore earlier hotspot
attribution to chunk 186/187 or another range must not be presented as
single-function cost. See [function-level performance research](FUNCTION_LEVEL_PERFORMANCE_2026-10-14.md) for exact reproducible mapping,
safe sample correlation and reference recompilers.

## Function-body and inlined native source attribution — follow-up

A saved Ghidra project was used to export inclusive, noncontiguous function
body ranges for all four original modules. 519,757 / 599,770 translated
x86 instruction addresses map uniquely to a static Ghidra body. An
**offline** ARM64 native ELF-PC resolver now follows Clang's *inlined*
generated-C callsite rather than misattributing helpers from
`recomp_rt.h` and NDK headers. The real unstripped shared library
proved address-to-line resolution, and artificial PC fixtures verified
the end-to-end mapping, NOT actual performance or frames per second.
See [body mapping and native sample procedure](FUNCTION_LEVEL_PERFORMANCE_2026-10-14.md).

## Technical references

- GL4ES environment and batching/VBO modes:
  https://github.com/ptitSeb/gl4es/blob/master/USAGE.md
- GL4ES pinned source:
  https://github.com/ptitSeb/gl4es/commit/ec16bedd8819c475326f4f1a3063772c6d986e06
- Clang optimization level semantics:
  https://clang.llvm.org/docs/CommandGuide/clang.html
- Mesa Zink Vulkan requirements:
  https://docs.mesa3d.org/drivers/zink.html
- ANGLE GLES translation backends:
  https://github.com/google/angle
- Official Simpleperf CPU profiling:
  https://developer.android.com/ndk/guides/simpleperf
- Android GPU Inspector:
  https://developer.android.com/agi

All raw game binaries, p-code dumps, APKs and private logs remain ignored
locally. Only reproducible observations and public documentation are
recorded here.
