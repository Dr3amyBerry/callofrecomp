# Desktop and Android frame pacing

## Reversible runtime selection

Android reads the private profile file `files/profile/frame_limit` once at
startup. Accepted contents are `original`, `60`, `120`, and `unlimited` (or
`0`), with optional surrounding ASCII whitespace. Missing, invalid, oversized
or embedded-NUL input selects the original 60-FPS behavior. No settings or
game assets are rewritten by reading this file. Restart to apply changes.

The native launcher supplies the same selected value to guest `com_maxfps`
and host pacing, overriding the Java launcher's legacy 60. The clocks used
by simulation, audio and input are unchanged. This does not prove all original
engine physics remain independent of frame rate; gameplay validation is still
required before recommending higher limits.

Example for the explicitly identified WSA (verify its serial before use):

```sh
adb -s 127.0.0.1:58526 shell "run-as org.callofrecomp sh -c 'echo 120 > files/profile/frame_limit'"
```

Write `60` or `original`, or remove only `files/profile/frame_limit`, to
restore normal pacing. Write `unlimited` to request no software cap. This
does not disable driver/compositor synchronization, produce more unique
frames than the display can present, or speed up CPU work. On an old
`--wsa-uncap-bench` diagnostic build, a missing file preserves its legacy
uncapped host behavior; an explicit `original`/`60` overrides that build default.

Positive driver VSync on a display at or below the selected limit replaces
the software wait. Higher/unknown/adaptive refresh retains the host limit;
unlimited never adds a host wait. Fractional periods round upward and each
deadline starts at the previous actual swap, without catch-up debt.

The implementation is being tested for the WSA 120-FPS mission; no FPS gain
or complete gameplay fidelity is certified by the configuration tests alone.

## Original default behavior

Real-time rendering requests swap interval zero and applies a monotonic host
cap before presenting each frame. The target period is rounded up to clock
ticks, so an integer-millisecond clock does not turn 60 FPS into 62.5 FPS.
A slow frame starts a new interval; the cap does not accumulate catch-up debt.
This limits rendering throughput; it does not guarantee that a device can
render every frame in 16.67 ms or that an unsynchronized swap cannot tear.

Some drivers retain VSync despite the request. The runtime checks the effective
swap interval and the window's current display refresh rate. When the interval
is positive and refresh is known to be at most 60 Hz, VSync alone limits
presentation and the additional host wait is skipped. For example, a 30 Hz
display remains at most 30 FPS. This avoids accidentally halving a 60 Hz
VSync display by waiting twice.

Unknown refresh rates, refresh above 60 Hz, and adaptive swap interval `-1`
retain the strict host cap. A warning identifies that combination because
remaining driver synchronization may lower FPS. Display mode information is
checked again during swaps while synchronization remains enabled.

### WSA-only uncapped diagnostic

The ordinary engine intentionally limits itself to **60 FPS**, even on WSA's **75-Hz** virtual display. To measure WSA gameplay headroom without the host cap, build an isolated APK using `python tools/recomp/build_android.py --abi x86_64 --wsa-uncap-bench`. The flag is **OFF by default**, rejected for ARM64, and does not switch OpenGL/GL4ES to Vulkan; driver VSync can still limit presentation. On WSA the controlled A2/B/A3 measurement was **55.05 → 57.20 → 55.30 FPS** with no CPU/frame reduction, so removing this cap alone cannot deliver 120 FPS. Restore the reference APK after the experiment. [Staged WSA benchmark](WSA_VULKAN_STAGED_BENCHMARK_2026-10-14.md).

Frame timing output is opt-in through `CODRECOMP_FRAME_STATS`. On Android,
create `frame_stats` in the writable profile directory to enable it; remove
that file to disable it on the next launch. Reported times cover the runtime
swap cadence rather than hardware scan-out timestamps.
