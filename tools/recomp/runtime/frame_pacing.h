#ifndef CODRECOMP_FRAME_PACING_H
#define CODRECOMP_FRAME_PACING_H
#include <stdint.h>
#include <stddef.h>
#include <string.h>

/* Bounded ASCII tokens only. Invalid/partial/embedded-NUL input fails closed. */
static inline int frame_limit_parse(const char *text, size_t length) {
    if (!text || length > 31) return 60;
    while (length && (*text == ' ' || *text == '\t' || *text == '\r' || *text == '\n')) {
        ++text; --length;
    }
    while (length && (text[length - 1] == ' ' || text[length - 1] == '\t'
            || text[length - 1] == '\r' || text[length - 1] == '\n')) --length;
    if (length == 3 && !memcmp(text, "120", 3)) return 120;
    if ((length == 1 && text[0] == '0')
            || (length == 9 && !memcmp(text, "unlimited", 9))) return 0;
    return 60;
}

static inline int frame_vsync_caps_limit(int interval, int refresh_hz, int limit) {
    return limit > 0 && interval > 0 && refresh_hz > 0 && refresh_hz <= limit;
}

static inline uint64_t frame_delay_ticks_limit(uint64_t previous, uint64_t now,
        uint64_t frequency, unsigned limit) {
    if (!previous || now < previous || !frequency || !limit) return 0;
    uint64_t period = frequency / limit + (frequency % limit != 0);
    uint64_t elapsed = now - previous;
    return elapsed < period ? period - elapsed : 0;
}

/* Only a positive, non-adaptive interval and a known <=60 Hz display can
 * replace the host cap. Unknown/high refresh and adaptive VSync need the cap. */
static inline int frame_vsync_caps_60(int interval, int refresh_hz) {
    return frame_vsync_caps_limit(interval, refresh_hz, 60);
}

/* Round up: integer clocks must never turn the cap into 62.5 FPS.
 * Base each interval on the actual previous frame, without catch-up debt. */
static inline uint64_t frame_delay_ticks(uint64_t previous, uint64_t now,
        uint64_t frequency) {
    return frame_delay_ticks_limit(previous, now, frequency, 60);
}
#endif
