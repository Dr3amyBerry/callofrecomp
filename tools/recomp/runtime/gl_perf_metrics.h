// Opt-in accounting of guest OpenGL calls; not GLES draw submissions or GPU time.
#pragma once
#include <stdint.h>
#include <string.h>

typedef enum gl_perf_event {
    GL_PERF_DRAW_ARRAYS, GL_PERF_DRAW_ELEMENTS, GL_PERF_DRAW_RANGE,
    GL_PERF_BIND_TEXTURE, GL_PERF_TEX_IMAGE, GL_PERF_TEX_SUBIMAGE,
    GL_PERF_BIND_BUFFER, GL_PERF_BUFFER_DATA, GL_PERF_BUFFER_SUBDATA,
    GL_PERF_LOCK_ARRAYS, GL_PERF_UNLOCK_ARRAYS, GL_PERF_ACTIVE_TEXTURE,
    GL_PERF_FRAME
} gl_perf_event;

typedef struct gl_perf_counters {
    uint64_t frames, draw_arrays, draw_elements, draw_ranges;
    uint64_t array_vertices, index_count;
    uint64_t bind_texture, tex_image, tex_subimage;
    uint64_t bind_buffer, bytes_buffer_data, bytes_buffer_subdata;
    uint64_t lock_arrays, unlock_arrays, active_texture;
} gl_perf_counters;

static inline void gl_perf_reset(gl_perf_counters *s) { memset(s, 0, sizeof *s); }

// "amount" is a count of vertices/indices or payload bytes, never a duration.
static inline void gl_perf_record(gl_perf_counters *s, gl_perf_event event, uint64_t amount) {
    switch (event) {
    case GL_PERF_DRAW_ARRAYS: s->draw_arrays++; s->array_vertices += amount; break;
    case GL_PERF_DRAW_ELEMENTS: s->draw_elements++; s->index_count += amount; break;
    case GL_PERF_DRAW_RANGE: s->draw_ranges++; s->index_count += amount; break;
    case GL_PERF_BIND_TEXTURE: s->bind_texture++; break;
    case GL_PERF_TEX_IMAGE: s->tex_image++; break;
    case GL_PERF_TEX_SUBIMAGE: s->tex_subimage++; break;
    case GL_PERF_BIND_BUFFER: s->bind_buffer++; break;
    case GL_PERF_BUFFER_DATA: s->bytes_buffer_data += amount; break;
    case GL_PERF_BUFFER_SUBDATA: s->bytes_buffer_subdata += amount; break;
    case GL_PERF_LOCK_ARRAYS: s->lock_arrays++; break;
    case GL_PERF_UNLOCK_ARRAYS: s->unlock_arrays++; break;
    case GL_PERF_ACTIVE_TEXTURE: s->active_texture++; break;
    case GL_PERF_FRAME: s->frames++; break;
    }
}
