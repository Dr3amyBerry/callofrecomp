# WSA frame limit implementation plan

**Goal:** reversible original/60/120/uncapped selection without changing clocks,
graphics, guest instructions or blocked CFG optimizations.

**Design:** private `files/profile/frame_limit` is read once by SDL_main.
Accepted tokens: `original`, `60`, `120`, `unlimited` (or `0`). Missing or invalid
input retains 60. Native startup supplies the same canonical value to the
guest `com_maxfps` and host pacing; a missing file preserves legacy diagnostic
build behavior. Changes require a restart. This changes pacing, not throughput.

**Execution:** inline, on main per user authorization. No new subsystem or UI.

- [x] Extend C pacing tests for 120 Hz fractional rounding, unlimited, stalls,
  overflow-sized clocks, strict config parsing and unchanged original mode.
- [x] Run failing tests; implement shared pure helpers in frame_pacing.h.
- [x] Connect native profile parsing and final guest arguments; use selected
  host rate in window.c while retaining WSA legacy diagnostic compatibility.
- [x] Build host tests and x86_64 APK; validate original then explicit 120 and
  uncapped against identical saved scene/settings. Verify save hashes.
- [x] Document actual CPU/frame and presentation separately; restore normal cap
  after diagnostic runs. No claim of physics/audio fidelity from unit
  tests alone. Continue profiling for structural optimization.

**Instrumentation:** `capture_wsa_presentation.py` samples the game's actual
SurfaceFlinger layer, deduplicates rolling buffers, detects coverage gaps and
computes individual presentation interval p95/p99. Simultaneous engine logs
retain their explicitly per-window CPU/FPS meaning. Three synthetic tests
passed after the missing-module failure; a 15 s live tool validation had no
buffer gaps. That run overlapped compilation and is not a performance baseline.

**Review:** independent review found the absent-file guest override regression;
fixed by appending com_maxfps only for an existing profile file. Re-review:
no findings. Host CTest 35/35 and native pacing executable on WSA passed.

**Completed validation:** six accepted High-quality runs (original, 120,
original, 120 retry, unlimited, explicit 60), same APK/save, no save changes,
full compositor buffer coverage. One briefing capture rejected and excluded.
No CPU efficiency gain claimed; normal cap restored and private override file
removed. Physical validation at actual >60 FPS and long-session fidelity remain
part of the broader mission, not established by this configuration block.
