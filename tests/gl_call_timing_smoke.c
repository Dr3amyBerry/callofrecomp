#include <stdint.h>
#include <stdio.h>
#include "gl_call_timing.h"

int main(void) {
    gl_time_counters c = {0};
    c.frames = 60;
    gl_time_record(&c, GL_TIME_DRAW, 120000);
    gl_time_record(&c, GL_TIME_DRAW, 90000);
    gl_time_record(&c, GL_TIME_TEXTURE_BIND, 24000);
    gl_time_record(&c, GL_TIME_ARRAY_LOCK, 5000);
    gl_time_record(&c, GL_TIME_ARRAY_POINTER, 6000);
    gl_time_record(&c, GL_TIME_RENDER_STATE, 7000);
    gl_time_record(&c, GL_TIME_TEXTURE_UPLOAD, 8000);
    gl_time_record(&c, GL_TIME_BUFFER, 9000);
    gl_time_record(&c, (gl_time_kind)123, 20000); // malformed category ignored
    if (c.frames != 60 || c.events[GL_TIME_DRAW].count != 2 ||
        c.events[GL_TIME_DRAW].cpu_ns != 210000 ||
        c.events[GL_TIME_TEXTURE_BIND].count != 1 ||
        c.events[GL_TIME_TEXTURE_BIND].cpu_ns != 24000 ||
        c.events[GL_TIME_ARRAY_LOCK].cpu_ns != 5000 ||
        c.events[GL_TIME_ARRAY_POINTER].cpu_ns != 6000 ||
        c.events[GL_TIME_RENDER_STATE].cpu_ns != 7000 ||
        c.events[GL_TIME_TEXTURE_UPLOAD].cpu_ns != 8000 ||
        c.events[GL_TIME_BUFFER].cpu_ns != 9000) return 1;
    gl_time_reset(&c);
    if (c.frames || c.events[GL_TIME_DRAW].cpu_ns || c.events[GL_TIME_DRAW].count) return 2;
    puts("Guest GL bridge timing aggregation passed");
    return 0;
}
