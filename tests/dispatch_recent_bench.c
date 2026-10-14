/* Manual, deterministic host CPU microbenchmark for recent-chunk lookup.
   This tests index lookup only, NOT gameplay FPS or Android CPU frequency.
   No proprietary module layout, native profile, or game data is embedded.
   Usage: cmake --build build --target codrecomp_dispatch_recent_bench
          build/codrecomp_dispatch_recent_bench
*/
#include "recomp_rt.h"
#include "dispatch_index.h"
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>

enum { CHUNKS = 403, TRACE_SIZE = 1 << 15, CALLS = 8000000 };
static dispatch_index idx;
static recomp_chunk chunks[CHUNKS];
static uint32_t trace[TRACE_SIZE];
static uint32_t seed = 0x27e3437fu;
static volatile uint64_t sink;

static uint32_t rng(void) {
    seed = seed * UINT32_C(1664525) + UINT32_C(1013904223);
    return seed;
}
static void make_layout(void) {
    uint32_t pc = 0x401000u;
    for (int i = 0; i < CHUNKS; i++) {
        uint32_t len = 0x1200u + (uint32_t)(i % 13) * 47u;
        chunks[i] = (recomp_chunk){pc, pc + len, 0};
        pc += len + ((i % 19) == 0 ? 7u : 0u);
    }
    dispatch_index_build(&idx, chunks, CHUNKS);
}
static void make_trace(int which) {
    seed = 0x27e3437fu;
    for (int i = 0; i < TRACE_SIZE; i++) {
        unsigned chunk;
        if (which == 0) chunk = 201;
        else if (which == 1) chunk = (unsigned)((i / 8) % 16 + 190);
        else if (which == 2) chunk = (unsigned)(i & 1 ? 201 : 202);
        else chunk = rng() % CHUNKS;
        uint32_t len = chunks[chunk].end - chunks[chunk].start;
        trace[i] = chunks[chunk].start + (rng() % len);
    }
}
typedef struct { double ns; uint64_t sum; } result;
static result bench(int cached) {
    dispatch_recent recent = { .generation = 0, .last_chunk = -1 };
    uint64_t sum = 0;
    clock_t start = clock();
    for (uint32_t i = 0; i < CALLS; i++) {
        uint32_t pc = trace[i & (TRACE_SIZE - 1)];
        int got = cached
            ? dispatch_index_find_recent(&idx, chunks, CHUNKS, pc, &recent)
            : dispatch_index_find(&idx, chunks, CHUNKS, pc);
        sum += (uint64_t)(got + 1);
    }
    clock_t end = clock();
    sink = sum;
    if (start == (clock_t)-1 || end == (clock_t)-1 || end <= start) {
        fprintf(stderr, "CPU clock unavailable\n");
        exit(3);
    }
    return (result){
        (double)(end - start) * 1e9 /
            ((double)CLOCKS_PER_SEC * (double)CALLS), sum
    };
}
int main(void) {
    make_layout();
    const char *names[] = {"same_chunk", "burst_8", "alternate_2", "random_403"};
    for (int mode = 0; mode < 4; mode++) {
        make_trace(mode);
        /* Alternating order avoids consistently favoring either candidate
           with the first warm or the last warmed CPU cache. */
        result a0 = bench(0), b0 = bench(1), b1 = bench(1), a1 = bench(0);
        if (a0.sum != b0.sum || a0.sum != a1.sum || a0.sum != b1.sum) {
            fprintf(stderr, "Lookup mismatch in benchmark %s\n", names[mode]);
            return 2;
        }
        printf("%s: baseline_ns=%.2f recent_ns=%.2f ratio=%.3f "
               "(two-run means; smaller is better)\n", names[mode],
               (a0.ns + a1.ns)/2, (b0.ns + b1.ns)/2,
               (b0.ns + b1.ns)/(a0.ns + a1.ns));
    }
    return 0;
}
