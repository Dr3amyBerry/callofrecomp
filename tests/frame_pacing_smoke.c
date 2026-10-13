#include <stdint.h>
#include <stdio.h>
#include "frame_pacing.h"

int main(void) {
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
