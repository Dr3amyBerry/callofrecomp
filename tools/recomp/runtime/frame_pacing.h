#ifndef CODRECOMP_FRAME_PACING_H
#define CODRECOMP_FRAME_PACING_H
#include <stdint.h>

/* Only a positive, non-adaptive interval and a known <=60 Hz display can
 * replace the host cap. Unknown/high refresh and adaptive VSync need the cap. */
static inline int frame_vsync_caps_60(int interval, int refresh_hz) {
    return interval > 0 && refresh_hz > 0 && refresh_hz <= 60;
}

/* Round up: integer clocks must never turn the cap into 62.5 FPS.
 * Base each interval on the actual previous frame, without catch-up debt. */
static inline uint64_t frame_delay_ticks(uint64_t previous, uint64_t now,
        uint64_t frequency) {
    if (!previous || now < previous || !frequency) return 0;
    uint64_t period = frequency / 60 + (frequency % 60 != 0);
    uint64_t elapsed = now - previous;
    return elapsed < period ? period - elapsed : 0;
}
#endif
