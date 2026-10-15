#include <stdint.h>
#include <stdio.h>
#include "frame_pacing.h"

int main(void) {
    if (frame_limit_parse("120\n", 4) != 120
            || frame_limit_parse("original", 8) != 60
            || frame_limit_parse("60", 2) != 60
            || frame_limit_parse("unlimited\r\n", 11) != 0
            || frame_limit_parse("0", 1) != 0
            || frame_limit_parse(" 120 \n", 6) != 120) return 10;
    const char *invalid[] = {"", "-1", "121", "120x", "120\n0", "nan", "999999999999999999999"};
    for (unsigned i = 0; i < sizeof invalid / sizeof *invalid; ++i)
        if (frame_limit_parse(invalid[i], strlen(invalid[i])) != 60) return 11;
    if (frame_limit_parse("120\0junk", 8) != 60
            || frame_limit_parse(NULL, 0) != 60) return 12;
    if (frame_delay_ticks_limit(100, 108, 1000, 120) != 1
            || frame_delay_ticks_limit(100, 109, 1000, 120) != 0
            || frame_delay_ticks_limit(100, 101, 1000, 0) != 0
            || frame_delay_ticks_limit(100, 300, 1000, 120) != 0
            || frame_delay_ticks_limit(0, 100, 1000, 120) != 0
            || frame_delay_ticks_limit(100, 50, 1000, 120) != 0
            || frame_delay_ticks_limit(100, 101, 0, 120) != 0) return 13;
    if (frame_delay_ticks_limit(1, 1, UINT64_MAX, 120)
            != UINT64_MAX / 120 + 1) return 14;
    if (!frame_vsync_caps_limit(1, 75, 120)
            || frame_vsync_caps_limit(1, 75, 60)
            || frame_vsync_caps_limit(1, 75, 0)
            || frame_vsync_caps_limit(-1, 60, 120)) return 15;
    uint64_t t = 1000000000;
    for (int i = 0; i < 1000; ++i) {
        uint64_t now = t + (i % 9 == 0 ? 20000000 : 2000000);
        uint64_t next = now + frame_delay_ticks_limit(t, now, 1000000000, 120);
        if (next - t < 8333334) return 16;
        t = next;
    }
    // A driver retaining VSync must not get a second wait on <=60 Hz displays.
    const int intervals[] = {0, 1, -1};
    const int refreshes[] = {60, 30, 120, 0};
    const int expected[3][4] = {{0, 0, 0, 0}, {1, 1, 0, 0}, {0, 0, 0, 0}};
    for (unsigned i = 0; i < 3; i++)
        for (unsigned j = 0; j < 4; j++)
            if (frame_vsync_caps_60(intervals[i], refreshes[j]) != expected[i][j]) return 7;
    if (!frame_vsync_caps_60(2, 60) || frame_vsync_caps_60(1, -1)) return 8;
    // 1000 ticks cannot represent a 60 Hz period: 16 would mean 62.5 FPS.
    if (frame_delay_ticks(100, 116, 1000) != 1) return 1;
    if (frame_delay_ticks(100, 117, 1000) != 0) return 2;
    // A stalled frame must not create catch-up bursts or delay a full period.
    if (frame_delay_ticks(100, 300, 1000) != 0) return 3;
    if (frame_delay_ticks(300, 301, 1000) != 16) return 4;
    if (frame_delay_ticks(0, 100, 1000) != 0
            || frame_delay_ticks(100, 50, 1000) != 0
            || frame_delay_ticks(100, 101, 0) != 0) return 5;
    uint64_t previous = 1000000000, frequency = 1000000000;
    for (int i = 0; i < 600; i++) {
        uint64_t rendered = previous + (i % 7 == 0 ? 50000000 : 3000000);
        uint64_t presented = rendered + frame_delay_ticks(previous, rendered, frequency);
        if (presented - previous < 16666667) return 6;
        previous = presented;
    }
    puts("60 FPS fractional clock, stall and reset pacing passed");
    return 0;
}
