// Guest OpenGL bridge timing categories (CPU on the calling thread, not GPU time).
#pragma once
#include <stdint.h>
#include <string.h>

typedef enum gl_time_kind {
    GL_TIME_DRAW,
    GL_TIME_TEXTURE_BIND,
    GL_TIME_TEXTURE_UPLOAD,
    GL_TIME_ARRAY_POINTER,
    GL_TIME_ARRAY_LOCK,
    GL_TIME_RENDER_STATE,
    GL_TIME_BUFFER,
    GL_TIME_CATEGORY_COUNT
} gl_time_kind;

typedef struct gl_time_stat {
    uint64_t count;
    uint64_t cpu_ns;
} gl_time_stat;

typedef struct gl_time_counters {
    uint64_t frames;
    gl_time_stat events[GL_TIME_CATEGORY_COUNT];
} gl_time_counters;

static inline void gl_time_reset(gl_time_counters *stats) {
    memset(stats, 0, sizeof(*stats));
}

static inline void gl_time_record(gl_time_counters *stats, gl_time_kind category, uint64_t elapsed_ns) {
    if ((unsigned)category >= GL_TIME_CATEGORY_COUNT) return;
    stats->events[category].count++;
    stats->events[category].cpu_ns += elapsed_ns;
}
