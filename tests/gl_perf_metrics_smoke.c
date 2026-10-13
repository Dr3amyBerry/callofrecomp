#include <stdint.h>
#include <stdio.h>
#include "gl_perf_metrics.h"

int main(void) {
    gl_perf_counters p = {0};
    gl_perf_record(&p, GL_PERF_DRAW_ARRAYS, 12);
    gl_perf_record(&p, GL_PERF_DRAW_ELEMENTS, 24);
    gl_perf_record(&p, GL_PERF_DRAW_RANGE, 6);
    gl_perf_record(&p, GL_PERF_BIND_TEXTURE, 0);
    gl_perf_record(&p, GL_PERF_BIND_TEXTURE, 0);
    gl_perf_record(&p, GL_PERF_TEX_IMAGE, 0);
    gl_perf_record(&p, GL_PERF_TEX_SUBIMAGE, 0);
    gl_perf_record(&p, GL_PERF_BIND_BUFFER, 0);
    gl_perf_record(&p, GL_PERF_BUFFER_DATA, 2048);
    gl_perf_record(&p, GL_PERF_BUFFER_SUBDATA, 512);
    gl_perf_record(&p, GL_PERF_LOCK_ARRAYS, 0);
    gl_perf_record(&p, GL_PERF_UNLOCK_ARRAYS, 0);
    gl_perf_record(&p, GL_PERF_ACTIVE_TEXTURE, 0);
    gl_perf_record(&p, GL_PERF_FRAME, 0);
    if (p.frames != 1 || p.draw_arrays != 1 || p.draw_elements != 1
            || p.draw_ranges != 1 || p.array_vertices != 12 || p.index_count != 30
            || p.bind_texture != 2 || p.tex_image != 1 || p.tex_subimage != 1
            || p.bind_buffer != 1 || p.bytes_buffer_data != 2048
            || p.bytes_buffer_subdata != 512 || p.lock_arrays != 1
            || p.unlock_arrays != 1 || p.active_texture != 1)
        return 1;
    gl_perf_reset(&p);
    if (p.frames || p.draw_arrays || p.bytes_buffer_data || p.index_count)
        return 2;
    puts("GL guest-call metrics passed");
    return 0;
}
