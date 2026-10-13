#ifndef CODRECOMP_COMMIT_RUNS_H
#define CODRECOMP_COMMIT_RUNS_H
#include <stdint.h>

/* Return only new consecutive pages within [cursor,end). Existing pages are
 * never included, preserving their permissions and data on overlapping calls.
 * The caller records a run only after the operating-system call succeeds. */
static inline int commit_next_run(const uint8_t *pages, uint32_t *cursor,
        uint32_t end, uint32_t *first, uint32_t *count) {
    uint32_t p = *cursor;
    while (p < end && pages[p]) p++;
    if (p == end) { *cursor = p; return 0; }
    *first = p;
    while (p < end && !pages[p]) p++;
    *count = p - *first;
    *cursor = p;
    return 1;
}
#endif
