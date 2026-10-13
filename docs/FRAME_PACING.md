# Desktop and Android frame pacing

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

Frame timing output is opt-in through `CODRECOMP_FRAME_STATS`. On Android,
create `frame_stats` in the writable profile directory to enable it; remove
that file to disable it on the next launch. Reported times cover the runtime
swap cadence rather than hardware scan-out timestamps.
