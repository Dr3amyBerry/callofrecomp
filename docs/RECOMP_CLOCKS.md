# Recompiled engine clocks

`shim_realtime = 1` is used by the desktop engine. GetTickCount and timeGetTime
use a monotonic millisecond clock; QueryPerformanceCounter uses the same clock
in nanoseconds, with QueryPerformanceFrequency returning 1,000,000,000. Windows
uses its native performance counter and POSIX hosts use CLOCK_MONOTONIC.
Guest RDTSC reads the native TSC on x86 hosts. Other architectures use the
nanosecond counter as a virtual 1-GHz TSC; this is not a host CPU speed report.

The original engine calibrates CPU speed using RDTSC, the performance counter
and Sleep. Previously all counters advanced by fixed amounts per call even in
real mode. It measured approximately 0.0625 MHz and selected the lowest original
configure.csv profile, which disables prediction with `cg_nopredict 1`.

This explains the observed ADS transition: rendering continued near 100 FPS,
but the aim fraction changed only with roughly 50-ms server updates. A private
campaign trace recorded 6 distinct fractions in 34 transition frames. With real
clocks the local x86 host measured 3.59 GHz, selected the original 2000-MHz
configuration and enabled prediction. The same probe recorded 26 distinct aim
fractions in 26 transition frames, with no repeated neighboring fractions.
Logs and traces derived from original game execution stay under ignored
`recomp_out`; no original resources or generated module code are committed.

Existing profiles retain their saved settings. For a profile created before
this fix, pass `+set cg_nopredict 0` once when launching the engine to restore
the original registered default. This also allows the original engine to save
the corrected value through its normal configuration path. Android performance
and automatic configuration still require device validation.

`shim_realtime = 0` retains the deterministic increments used by trace tests:
GetTickCount advances 16 ms, QueryPerformanceCounter 16,000 ticks at 1 MHz, and
RDTSC 1,000 ticks per call. The synthetic file/runtime test checks elapsed-time
advancement across Sleep in real mode and deterministic counter increments
after switching back.

The Win32 performance-counter contract is documented by
[Microsoft](https://learn.microsoft.com/en-us/windows/win32/api/profileapi/nf-profileapi-queryperformancecounter).
